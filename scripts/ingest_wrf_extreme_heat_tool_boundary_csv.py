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

Usage:
    uv run python -m scripts.ingest_wrf_extreme_heat_tool_boundary_csv

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

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
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

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

        item = pystac.Item(
            id=item_id,
            geometry=bbox_to_geometry(CA_BBOX),
            bbox=CA_BBOX,
            datetime=None,
            properties={
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
            },
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
