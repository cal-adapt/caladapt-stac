"""ingest_wrf_extreme_heat_season_boundary_csv.py

Ingest WRF extreme heat season tool multi-model boundary CSV data into pgSTAC.

Multi-model mean CSVs (across 4 WRF models) of day-of-year threshold
exceedance frequency at each global warming level, organized by boundary ×
threshold. For each calendar day, frequency_percent is the share of years in
the 30-year GWL window whose daily maximum temperature (t2max) exceeded the
threshold. Days run 1-365 on a no-leap calendar (February 29 removed). This
is not a heat-wave event metric: consecutive days are not considered. Covers
4 of the 6 California boundary types produced by the pipeline: counties,
watersheds, forecast zones, and electric balancing areas.

Census tracts and IOU/POUs are excluded to match the HDD/CDD and heat-wave
tools' launch scope (see ingest_wrf_hdd_cdd_tool_boundary_csv.py).

S3 path structure:
    wrf/extreme-heat-season/multimodel_per_boundary/{boundary}/gwl/csv/{thresh}/
    Files within: {Region_Name}_{thresh}.csv (1,825 rows: 5 GWLs × 365 days)

One STAC item per (boundary × threshold) combination.
Each item has one asset pointing to the S3 prefix directory.

Usage:
    uv run python -m scripts.ingest_wrf_extreme_heat_season_boundary_csv

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
    WRF_EXTREME_HEAT_SEASON_PREFIX,
)
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

MULTIMODEL_CSV_PREFIX = WRF_EXTREME_HEAT_SEASON_PREFIX + "multimodel_per_boundary/"

# Launch scope: 4 of the 6 boundary types the pipeline produces, matching the
# HDD/CDD tool. Census tracts and IOU/POUs are intentionally excluded (see
# module docstring), so this is a deliberate allowlist rather than something
# to discover from S3.
BOUNDARY_LABELS = {
    "ca_counties": "California counties",
    "ca_watersheds": "California watersheds (HUC8)",
    "forecast_zones": "California forecast zones",
    "electric_balancing_areas": "California electric balancing areas",
}
VALID_BOUNDARIES = list(BOUNDARY_LABELS)

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
        wrf/extreme-heat-season/multimodel_per_boundary/ca_counties/gwl/csv/t2max_ge90F/

    Returns
    -------
    dict or None
        Parsed components, or None if prefix does not match expected structure.
    """
    inner = prefix.removeprefix(MULTIMODEL_CSV_PREFIX).rstrip("/")
    parts = inner.split("/")
    # expected: [boundary, gwl, csv, thresh]
    if len(parts) != 4 or parts[1:3] != ["gwl", "csv"]:
        return None
    boundary, _, _, thresh = parts
    return {
        "boundary": boundary,
        "thresh": thresh,
        "path": f"s3://{BUCKET_CADCAT}/{prefix}",
    }


def build_collection():
    """
    Build a pystac Collection for WRF extreme heat season multi-model boundary CSVs.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="ehs-metrics-mm-boundary-csv",
        title="Cal-Adapt extreme heat season tool (boundary CSV)",
        keywords=[
            "climate model",
            "California",
            "extreme heat",
            "extreme heat season",
            "seasonality",
            "global warming levels",
            "CSV",
        ],
        description=(
            "Multi-model mean CSVs of WRF day-of-year threshold exceedance frequency for "
            "California at global warming levels (0.8°C–3.0°C), aggregated by boundary "
            "region, for each threshold. Covers 4 boundary types: counties, watersheds, "
            "forecast zones, and electric balancing areas. Each CSV contains one value "
            "per warming level and day of year for one region."
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
    # TODO: swap in a dedicated extreme heat season thumbnail once one exists.
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}wrf_extreme_heat_ridgeplot.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="WRF extreme heat season tool preview",
        ),
    )

    print("  Discovering boundary CSV prefixes from S3...")
    geometry = bbox_to_geometry(CA_BBOX)
    start_dt, end_dt = EXPERIMENT_DATE_RANGE
    items_built = 0

    prefixes = (
        prefix
        for boundary in VALID_BOUNDARIES
        # depth=1: thresh
        for prefix in list_zarr_stores(
            f"{MULTIMODEL_CSV_PREFIX}{boundary}/gwl/csv/", BUCKET_CADCAT, depth=1
        )
    )
    for prefix in prefixes:
        parsed = parse_csv_prefix(prefix)
        if parsed is None:
            continue

        boundary = parsed["boundary"]
        thresh = parsed["thresh"]
        boundary_label = BOUNDARY_LABELS[boundary]
        item_id = f"ehs-metrics-mm-boundary-csv-{boundary}-{thresh}"

        item = pystac.Item(
            id=item_id,
            geometry=geometry,
            bbox=CA_BBOX,
            datetime=None,
            properties={
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
                "cmip6:activity_id": "WRF",
                "cmip6:institution_id": "UCLA",
                "cmip6:experiment_id": "ssp370",
                "variable_id": "frequency_percent",
                "threshold_name": thresh,
                "boundary": boundary,
                "boundary_label": boundary_label,
                "caladapt:spatial_type": "boundary",
                "bias_adjusted": True,
            },
        )
        item.add_asset(
            "data",
            pystac.Asset(
                href=parsed["path"],
                media_type="text/csv",
                title=f"{boundary_label} — extreme heat season | {thresh}",
                roles=["data"],
            ),
        )
        collection.add_item(item)
        items_built += 1

    collection.extra_fields["caladapt:boundary_labels"] = BOUNDARY_LABELS

    print(f"  Built {items_built} items.")
    return collection


def main():
    print("  Building WRF extreme heat season tool boundary CSV collection...")
    collection = build_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
