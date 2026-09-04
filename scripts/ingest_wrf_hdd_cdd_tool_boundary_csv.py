"""ingest_wrf_hdd_cdd_tool_boundary_csv.py

Ingest WRF HDD/CDD tool multi-model boundary timeseries CSV data into pgSTAC.

Multi-model ensemble annual HDD65/CDD65 timeseries CSVs (mean/min/max across
4 WRF models, historical + ssp370, 1981-2099) organized by boundary. Covers 4
of the 6 California boundary types produced by the pipeline: counties,
watersheds, forecast zones, and electric balancing areas.

Census tracts and IOU/POUs are excluded at this launch scope -- the IOU/POU
boundary raster mask only assigns 42 of 52 utility geometries (see
HDD/CDD MVP Requirements doc, "Outstanding Questions"), the same known issue
that scopes the extreme heat tool's boundary options.

NOTE: the source data currently has a known bug -- see cal-adapt-data-gen PR
"fix: multimodel mean/min/max only reflected one model (hdd_cdd, extreme_heat)".
The `hdd_mean`/`hdd_min`/`hdd_max`/`cdd_mean`/`cdd_min`/`cdd_max` columns do
not yet reflect a true multi-model aggregate. Ingesting anyway so STAC/frontend
work can proceed in parallel; the underlying CSVs will be regenerated in place
(same S3 paths) once the pipeline fix is rerun, with no changes needed here.

S3 path structure:
    wrf/hdd-cdd-tool/multimodel_per_boundary/{boundary}/ssp370/timeseries/csv/
    Files within: {Region_Name}.csv

One STAC item per boundary type. Each item has one asset pointing to the S3
prefix directory.

Usage:
    uv run python -m scripts.ingest_wrf_hdd_cdd_tool_boundary_csv

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
)
from scripts.utils import bbox_to_geometry, load_direct

MULTIMODEL_CSV_PREFIX = "wrf/hdd-cdd-tool/multimodel_per_boundary/"

SCENARIO = "ssp370"
THRESHOLD_NAME = "65F"

VALID_BOUNDARIES = [
    "ca_counties",
    "ca_watersheds",
    "forecast_zones",
    "electric_balancing_areas",
]

BOUNDARY_LABELS = {
    "ca_counties": "California counties",
    "ca_watersheds": "California watersheds (HUC8)",
    "forecast_zones": "California forecast zones",
    "electric_balancing_areas": "California electric balancing areas",
}

# Historical (1981) through the end of the ssp370 projection (2099), matching
# the continuous per-region timeseries CSVs.
TIMESERIES_DATE_RANGE = (
    datetime(1981, 1, 1, tzinfo=timezone.utc),
    datetime(2099, 12, 31, tzinfo=timezone.utc),
)


def build_collection():
    """
    Build a pystac Collection for WRF HDD/CDD tool multi-model boundary timeseries CSVs.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="hdd-cdd-metrics-mm-boundary-csv",
        title="Cal Adapt HDD/CDD tool (boundary CSV)",
        keywords=[
            "climate model",
            "California",
            "CMIP6",
            "dynamical",
            "heating degree days",
            "cooling degree days",
            "HDD",
            "CDD",
            "boundaries",
            "CSV",
        ],
        description=(
            "Multi-model ensemble annual HDD65/CDD65 timeseries CSVs of WRF projections "
            "for California, aggregated by boundary region. Covers 4 boundary types: "
            "counties, watersheds, forecast zones, and electric balancing areas. Each CSV "
            "contains multi-model mean/min/max annual HDD and CDD (65 degF threshold) for "
            "one region, spanning the historical period through the ssp370 projection "
            "(1981-2099)."
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
                intervals=[[TIMESERIES_DATE_RANGE[0], TIMESERIES_DATE_RANGE[1]]]
            ),
        ),
    )
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}wrf_hdd_cdd_timeseries.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="WRF HDD/CDD tool preview",
        ),
    )

    items_built = 0
    for boundary in VALID_BOUNDARIES:
        path = f"{MULTIMODEL_CSV_PREFIX}{boundary}/{SCENARIO}/timeseries/csv/"
        start_dt, end_dt = TIMESERIES_DATE_RANGE
        item_id = f"hdd-cdd-metrics-mm-boundary-csv-{boundary}"

        item = pystac.Item(
            id=item_id,
            geometry=bbox_to_geometry(CA_BBOX),
            bbox=CA_BBOX,
            datetime=None,
            properties={
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
                "cmip6:activity_id": "WRF",
                "cmip6:institution_id": "UCLA",
                "cmip6:experiment_id": SCENARIO,
                "threshold_name": THRESHOLD_NAME,
                "boundary": boundary,
                "boundary_label": BOUNDARY_LABELS.get(boundary, boundary),
                "caladapt:spatial_type": "boundary",
                "bias_adjusted": True,
            },
        )
        item.add_asset(
            "data",
            pystac.Asset(
                href=f"s3://{BUCKET_CADCAT}/{path}",
                media_type="text/csv",
                title=f"{BOUNDARY_LABELS.get(boundary, boundary)} — annual HDD65/CDD65 timeseries",
                roles=["data"],
            ),
        )
        collection.add_item(item)
        items_built += 1

    collection.extra_fields["caladapt:boundary_labels"] = BOUNDARY_LABELS
    print(f"  Built {items_built} items.")
    return collection


def main():
    print("  Building WRF HDD/CDD tool boundary CSV collection...")
    collection = build_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
