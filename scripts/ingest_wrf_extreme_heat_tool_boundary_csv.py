"""ingest_wrf_extreme_heat_tool_boundary_csv.py

Ingest WRF extreme heat tool multi-model boundary CSV data into pgSTAC.

Multi-model ensemble summary CSVs (median/p10/p90 across 4 WRF models) at each
global warming level, organized by metric × boundary × threshold. Covers 6
California boundary types: counties, watersheds, census tracts, IOU/POUs,
forecast zones, and electric balancing areas.

S3 path structure:
    wrf/extreme-heat-tool/multimodel_per_boundary/{metric}/{boundary}/ssp370/csv/{thresh}/
    Files within: {Region_Name}_{thresh}.csv

One STAC item per (metric × boundary × threshold) combination.
Each item has one asset pointing to the S3 prefix directory.

Items in `DATA_RANGE_BOUNDARIES` also carry `data_min`/`data_max` properties:
the min/max across every region's multimodel_median/p10/p90 values at every
global warming level (the frontend uses these to size its chart's y-axis).
Other boundaries (e.g. ca_census_tracts, at 2,338 regions/threshold) are
excluded -- not yet user-selectable in the frontend, and too high a file
count to fetch reliably.


Usage:
    uv run python -m scripts.ingest_wrf_extreme_heat_tool_boundary_csv

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import pandas as pd
import pystac

from scripts.constants import (
    BUCKET_CADCAT,
    CA_BBOX,
    CALADAPT_DATA_LICENSE,
    ICON_BASE_URL,
    PGDSN,
    WRF_EXTREME_HEAT_TOOL_PREFIX,
    WRF_VARIABLE_LABELS,
)
from scripts.utils import bbox_to_geometry, list_keys, list_zarr_stores, load_direct

MULTIMODEL_CSV_PREFIX = WRF_EXTREME_HEAT_TOOL_PREFIX + "multimodel_per_boundary/"

BOUNDARY_LABELS = {
    "ca_counties": "California counties",
    "ca_watersheds": "California watersheds (HUC8)",
    "ca_census_tracts": "California census tracts",
    "ious_pous": "California IOUs and POUs",
    "forecast_zones": "California forecast zones",
    "electric_balancing_areas": "California electric balancing areas",
}

EXPERIMENT_DATE_RANGE = (
    datetime(2015, 1, 1, tzinfo=timezone.utc),
    datetime(2100, 12, 31, tzinfo=timezone.utc),
)

# Columns whose combined min/max define each item's data_min/data_max: the
# plotted median plus the p10/p90 uncertainty bounds, so a downstream axis
# never clips a future uncertainty band even though only the median is
# plotted today.
VALUE_COLUMNS = ["multimodel_median", "multimodel_p10", "multimodel_p90"]

# Boundary types to compute data_min/data_max for -- the ones the frontend
# currently exposes as spatial-aggregation options (SPATIAL_AGGREGATIONS in
# the website's options.ts). Excludes ca_census_tracts (2,338 regions per
# threshold) and ious_pous, which aren't user-selectable yet and are too
# high a file count to fetch reliably at this concurrency.
DATA_RANGE_BOUNDARIES = frozenset(
    {
        "ca_counties",
        "ca_watersheds",
        "forecast_zones",
        "electric_balancing_areas",
    }
)

# Each in-scope item's prefix can hold up to ~140 small (~450 B) region CSVs,
# so fetching them is network-latency bound rather than CPU bound.
CSV_FETCH_WORKERS = 8

# Retries for a single CSV fetch before giving up on it. A file that still
# fails after retries raises rather than being skipped -- silently dropping a
# region would understate the computed data_min/data_max without anyone
# noticing.
CSV_FETCH_RETRIES = 3
CSV_FETCH_RETRY_DELAY_SECONDS = 1


def parse_csv_prefix(prefix):
    """
    Parse a multimodel boundary CSV S3 prefix into components.

    Parameters
    ----------
    prefix : str
        S3 prefix, e.g.
        wrf/extreme-heat-tool/multimodel_per_boundary/eh_days/ca_counties/ssp370/t2max_ge95F/

    Returns
    -------
    dict or None
        Parsed components, or None if prefix does not match expected structure.
    """
    inner = prefix.removeprefix(MULTIMODEL_CSV_PREFIX).rstrip("/")
    parts = inner.split("/")
    # expected: [metric, boundary, ssp370, thresh]
    if len(parts) != 4 or parts[2] != "ssp370":
        return None
    metric, boundary, scenario, thresh = parts
    return {
        "metric": metric,
        "boundary": boundary,
        "scenario": scenario,
        "thresh": thresh,
        "path": f"s3://{BUCKET_CADCAT}/{prefix}",
    }


def fetch_csv_with_retries(url):
    """
    Fetch and parse one CSV, retrying transient failures (e.g. connection
    resets) up to `CSV_FETCH_RETRIES` times.

    Raises if every attempt fails. Callers must not silently drop a region --
    doing so would understate the item's computed data_min/data_max without
    anyone noticing.

    Parameters
    ----------
    url : str

    Returns
    -------
    pd.DataFrame
    """
    last_exc = None
    for attempt in range(1, CSV_FETCH_RETRIES + 1):
        try:
            return pd.read_csv(url)
        except Exception as exc:
            last_exc = exc
            if attempt < CSV_FETCH_RETRIES:
                print(f"    Retry {attempt}/{CSV_FETCH_RETRIES - 1} for {url}: {exc}")
                time.sleep(CSV_FETCH_RETRY_DELAY_SECONDS)
    raise RuntimeError(
        f"Failed to fetch {url} after {CSV_FETCH_RETRIES} attempts"
    ) from last_exc


def load_region_dataframes(prefix):
    """
    Read every region CSV under an item's S3 prefix into a DataFrame.

    Fetches concurrently since each file is tiny and latency-bound. Raises if
    any file still fails after retries, so the ingest run fails loudly rather
    than silently understating data_min/data_max for the item.

    Parameters
    ----------
    prefix : str
        S3 prefix for one (metric x boundary x threshold) item, e.g.
        wrf/extreme-heat-tool/multimodel_per_boundary/eh_days/ca_counties/ssp370/t2max_ge95F/

    Returns
    -------
    list[pd.DataFrame]
    """
    keys = [
        key for key, _size in list_keys(prefix, BUCKET_CADCAT) if key.endswith(".csv")
    ]

    def _read(key):
        url = f"https://{BUCKET_CADCAT}.s3.amazonaws.com/{key}"
        return fetch_csv_with_retries(url)

    with ThreadPoolExecutor(max_workers=CSV_FETCH_WORKERS) as pool:
        return list(pool.map(_read, keys))


def compute_data_range(dfs):
    """
    Compute the (min, max) across `VALUE_COLUMNS` in a list of region
    DataFrames -- the full data-driven range for one (metric x boundary x
    threshold) item, across every region and global warming level.

    Parameters
    ----------
    dfs : list[pd.DataFrame]

    Returns
    -------
    tuple[float, float] or tuple[None, None]
        (min, max), or (None, None) when there is no finite data to derive a
        range from.
    """
    columns = [df[col] for df in dfs for col in VALUE_COLUMNS if col in df.columns]
    if not columns:
        return None, None
    values = pd.concat(columns, ignore_index=True)
    values = values[values.notna()]
    if values.empty:
        return None, None
    return float(values.min()), float(values.max())


def build_collection():
    """
    Build a pystac Collection for WRF extreme heat tool multi-model boundary CSVs.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="eh-metrics-mm-boundary-csv",
        title="Cal Adapt extreme heat tool (boundary CSV)",
        keywords=[
            "climate model",
            "California",
            "CMIP6",
            "dynamical",
            "extreme heat",
            "global warming levels",
            "boundaries",
            "CSV",
        ],
        description=(
            "Multi-model ensemble summary CSVs of WRF extreme heat projections for California "
            "at global warming levels (0.8°C–3.0°C), aggregated by boundary region. "
            "Covers 6 boundary types: counties, watersheds, census tracts, IOU/POUs, "
            "forecast zones, and electric balancing areas. Each CSV contains multi-model "
            "median/p10/p90 exceedance counts across all warming levels for one region."
        ),
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Cal-Adapt",
                roles=[pystac.ProviderRole.HOST, pystac.ProviderRole.PROCESSOR],
                url="https://cal-adapt.org/",
            ),
            pystac.Provider(
                name="UCLA",
                roles=[pystac.ProviderRole.PRODUCER],
                url="https://www.energy.ca.gov/sites/default/files/2024-06/02_DynamicalDownscaling_DataJustificationMemo_Rahimi_Adopted_v2May2024_ada.pdf",
            ),
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[CA_BBOX]),
            temporal=pystac.TemporalExtent(
                intervals=[[EXPERIMENT_DATE_RANGE[0], EXPERIMENT_DATE_RANGE[1]]]
            ),
        ),
    )
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}wrf_extreme_heat_ridgeplot.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="WRF extreme heat tool preview",
        ),
    )

    print("  Discovering boundary CSV prefixes from S3...")
    seen_metrics: set[str] = set()
    items_built = 0

    # depth=4: metric / boundary / ssp370 / thresh
    for prefix in list_zarr_stores(MULTIMODEL_CSV_PREFIX, BUCKET_CADCAT, depth=4):
        parsed = parse_csv_prefix(prefix)
        if parsed is None:
            continue

        metric = parsed["metric"]
        boundary = parsed["boundary"]
        scenario = parsed["scenario"]
        thresh = parsed["thresh"]
        seen_metrics.add(metric)

        start_dt, end_dt = EXPERIMENT_DATE_RANGE
        item_id = f"eh-metrics-mm-boundary-csv-{metric}-{boundary}-{thresh}"

        properties = {
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "cmip6:activity_id": "WRF",
            "cmip6:institution_id": "CAE",
            "cmip6:experiment_id": scenario,
            "variable_id": metric,
            "threshold_name": thresh,
            "boundary": boundary,
            "boundary_label": BOUNDARY_LABELS.get(boundary, boundary),
            "caladapt:spatial_type": "boundary",
            "bias_adjusted": True,
        }
        if boundary in DATA_RANGE_BOUNDARIES:
            print(f"    Computing data range for {item_id}...")
            # Data-driven min/max for this (metric x boundary x threshold)
            # combination: across every region's median and p10/p90 values
            # at every global warming level.
            properties["data_min"], properties["data_max"] = compute_data_range(
                load_region_dataframes(prefix)
            )

        item = pystac.Item(
            id=item_id,
            geometry=bbox_to_geometry(CA_BBOX),
            bbox=CA_BBOX,
            datetime=None,
            properties=properties,
        )
        item.add_asset(
            "data",
            pystac.Asset(
                href=parsed["path"],
                media_type="text/csv",
                title=f"{BOUNDARY_LABELS.get(boundary, boundary)} — {metric} | {thresh}",
                roles=["data"],
            ),
        )
        collection.add_item(item)
        items_built += 1

    collection.extra_fields["caladapt:variable_labels"] = {
        var: WRF_VARIABLE_LABELS.get(var, var) for var in seen_metrics
    }
    collection.extra_fields["caladapt:boundary_labels"] = BOUNDARY_LABELS

    print(f"  Built {items_built} items.")
    return collection


def main():
    print("  Building WRF extreme heat tool boundary CSV collection...")
    collection = build_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
