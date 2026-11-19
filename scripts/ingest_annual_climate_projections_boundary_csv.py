"""ingest_annual_climate_projections_boundary_csv.py

Ingest the Annual Climate Projections tool's boundary CSVs into pgSTAC as three
collections:

    acp-wrf-boundary-csv    WRF, one item per variable x boundary (ssp370 only)
    acp-loca2-boundary-csv  LOCA2-Hybrid, one item per variable x SSP x boundary
    acp-era5-boundary-csv   WRF-downscaled ERA5 (observed), one item per variable x boundary

Each projection CSV holds one region's annual values: year, mean, min, max,
then one column per simulation. Each ERA5 CSV holds year, value.

S3 path structure (under DATA_SUBDIR while the data is a prototype):
    wrf/annual-climate-projections/per_boundary/{variable}/{boundary}/ssp370/csv/
        Files within: {Region}_{variable}_ssp370.csv
    loca2/annual-climate-projections/per_boundary/{variable}/{boundary}/{ssp}/csv/
        Files within: {Region}_{variable}_{ssp}.csv
    wrf/annual-climate-projections/era5_per_boundary/{variable}/{boundary}/csv/
        Files within: {Region}_{variable}_era5.csv

Each item has one `data` asset pointing to the S3 prefix directory.

Usage:
    uv run python -m scripts.ingest_annual_climate_projections_boundary_csv --dry-run
    uv run python -m scripts.ingest_annual_climate_projections_boundary_csv

Requires (without --dry-run):
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

import argparse
from datetime import datetime, timezone

import boto3
import pystac
from botocore import UNSIGNED
from botocore.config import Config

from scripts.constants import (
    BUCKET_CADCAT,
    CA_BBOX,
    CALADAPT_DATA_LICENSE,
    COLLECTION_KEYWORDS,
    LOCA2_ANNUAL_CLIMATE_PROJECTIONS_PREFIX,
    PGDSN,
    WRF_ANNUAL_CLIMATE_PROJECTIONS_PREFIX,
)
from scripts.utils import bbox_to_geometry, load_direct

# Prototype data lives in tmp/. Set to "" once the final outputs are on S3,
# then delete and re-ingest the collections (asset hrefs change).
DATA_SUBDIR = "tmp/"

# Only boundaries with data on S3. Add the other boundaries (and the new state
# mask) as the pipeline produces them; census tracts and IOU/POUs will need the
# weighted_median/ subdirectory like the HDD/CDD script.
BOUNDARY_LABELS = {
    "ca_counties": "California counties",
}

WRF_VARIABLES = ["t2", "t2max", "t2min", "dew_point", "prec"]
LOCA2_VARIABLES = ["tasmax", "tasmin", "pr"]
WRF_SCENARIO = "ssp370"
LOCA2_SCENARIOS = ["ssp245", "ssp370", "ssp585"]

WRF_DATE_RANGE = (
    datetime(1981, 1, 1, tzinfo=timezone.utc),
    datetime(2099, 12, 31, tzinfo=timezone.utc),
)
LOCA2_DATE_RANGE = (
    datetime(1950, 1, 1, tzinfo=timezone.utc),
    datetime(2099, 12, 31, tzinfo=timezone.utc),
)
ERA5_DATE_RANGE = (
    datetime(1981, 1, 1, tzinfo=timezone.utc),
    datetime(2019, 12, 31, tzinfo=timezone.utc),
)

CALADAPT_PROVIDER = pystac.Provider(
    name="Cal-Adapt",
    roles=[pystac.ProviderRole.HOST, pystac.ProviderRole.PROCESSOR],
    url="https://cal-adapt.org/",
)
UCLA_PROVIDER = pystac.Provider(
    name="UCLA",
    roles=[pystac.ProviderRole.PRODUCER],
    url="https://www.energy.ca.gov/sites/default/files/2024-06/02_DynamicalDownscaling_DataJustificationMemo_Rahimi_Adopted_v2May2024_ada.pdf",
)
UCSD_PROVIDER = pystac.Provider(
    name="UCSD",
    roles=[pystac.ProviderRole.PRODUCER],
    url="https://loca.ucsd.edu/",
)


def new_collection(collection_id, title, description, source, producer, date_range):
    """Collection shell shared by all three collections."""
    return pystac.Collection(
        id=collection_id,
        title=title,
        description=description,
        keywords=COLLECTION_KEYWORDS[collection_id],
        extra_fields={
            "caladapt:spatial_type": "spatial-aggregate",
            "caladapt:source": source,
            "caladapt:boundary_labels": BOUNDARY_LABELS,
        },
        license=CALADAPT_DATA_LICENSE,
        providers=[CALADAPT_PROVIDER, producer],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[CA_BBOX]),
            temporal=pystac.TemporalExtent(intervals=[list(date_range)]),
        ),
    )


def add_item(collection, item_id, path, date_range, properties, asset_title):
    """Add one item whose `data` asset points at an S3 prefix of CSVs."""
    start_dt, end_dt = date_range
    item = pystac.Item(
        id=item_id,
        geometry=bbox_to_geometry(CA_BBOX),
        bbox=CA_BBOX,
        datetime=None,
        properties={
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
            "caladapt:spatial_type": "spatial-aggregate",
            **properties,
        },
    )
    item.add_asset(
        "data",
        pystac.Asset(
            href=f"s3://{BUCKET_CADCAT}/{path}",
            media_type="text/csv",
            title=asset_title,
            roles=["data"],
        ),
    )
    collection.add_item(item)


def build_wrf_collection():
    collection_id = "acp-wrf-boundary-csv"
    collection = new_collection(
        collection_id,
        title="Annual climate projections by region (WRF)",
        description=(
            "Annual temperature and total precipitation for California regions from "
            "bias-adjusted CMIP6 models dynamically downscaled with WRF, historical "
            "through ssp370 (1981-2099). Each CSV holds one region's annual mean, min "
            "and max across models, plus one column per model."
        ),
        source="wrf",
        producer=UCLA_PROVIDER,
        date_range=WRF_DATE_RANGE,
    )
    prefix = WRF_ANNUAL_CLIMATE_PROJECTIONS_PREFIX + DATA_SUBDIR
    for variable in WRF_VARIABLES:
        for boundary, label in BOUNDARY_LABELS.items():
            add_item(
                collection,
                item_id=f"{collection_id}-{variable}-{boundary}",
                path=f"{prefix}per_boundary/{variable}/{boundary}/{WRF_SCENARIO}/csv/",
                date_range=WRF_DATE_RANGE,
                properties={
                    "cmip6:activity_id": "WRF",
                    "cmip6:institution_id": "UCLA",
                    "cmip6:experiment_id": WRF_SCENARIO,
                    "variable_id": variable,
                    "boundary": boundary,
                    "bias_adjusted": True,
                },
                asset_title=f"{label} — annual {variable}, {WRF_SCENARIO}",
            )
    return collection


def build_loca2_collection():
    collection_id = "acp-loca2-boundary-csv"
    collection = new_collection(
        collection_id,
        title="Annual climate projections by region (LOCA2)",
        description=(
            "Annual temperature and total precipitation for California regions from "
            "CMIP6 models statistically downscaled with LOCA2-Hybrid, historical "
            "through ssp245, ssp370 and ssp585 (1950-2099). Each CSV holds one "
            "region's annual mean, min and max across all runs, plus one column per run."
        ),
        source="loca2",
        producer=UCSD_PROVIDER,
        date_range=LOCA2_DATE_RANGE,
    )
    prefix = LOCA2_ANNUAL_CLIMATE_PROJECTIONS_PREFIX + DATA_SUBDIR
    for variable in LOCA2_VARIABLES:
        for scenario in LOCA2_SCENARIOS:
            for boundary, label in BOUNDARY_LABELS.items():
                add_item(
                    collection,
                    item_id=f"{collection_id}-{variable}-{scenario}-{boundary}",
                    path=f"{prefix}per_boundary/{variable}/{boundary}/{scenario}/csv/",
                    date_range=LOCA2_DATE_RANGE,
                    properties={
                        "cmip6:activity_id": "LOCA2",
                        "cmip6:institution_id": "UCSD",
                        "cmip6:experiment_id": scenario,
                        "variable_id": variable,
                        "boundary": boundary,
                    },
                    asset_title=f"{label} — annual {variable}, {scenario}",
                )
    return collection


def build_era5_collection():
    collection_id = "acp-era5-boundary-csv"
    collection = new_collection(
        collection_id,
        title="Annual observed climate by region (ERA5)",
        description=(
            "Annual temperature and total precipitation for California regions from "
            "the ERA5 reanalysis dynamically downscaled with WRF (1981-2019). Each CSV "
            "holds one region's annual values."
        ),
        source="wrf",
        producer=UCLA_PROVIDER,
        date_range=ERA5_DATE_RANGE,
    )
    prefix = WRF_ANNUAL_CLIMATE_PROJECTIONS_PREFIX + DATA_SUBDIR
    for variable in WRF_VARIABLES:
        for boundary, label in BOUNDARY_LABELS.items():
            add_item(
                collection,
                item_id=f"{collection_id}-{variable}-{boundary}",
                path=f"{prefix}era5_per_boundary/{variable}/{boundary}/csv/",
                date_range=ERA5_DATE_RANGE,
                properties={
                    "cmip6:activity_id": "WRF",
                    "cmip6:institution_id": "UCLA",
                    "cmip6:source_id": "ERA5",
                    "cmip6:experiment_id": "reanalysis",
                    "variable_id": variable,
                    "boundary": boundary,
                },
                asset_title=f"{label} — annual {variable}, ERA5",
            )
    return collection


def build_collections():
    return [build_wrf_collection(), build_loca2_collection(), build_era5_collection()]


def report(collections):
    """Print each item's ID, data href and CSV count (anonymous S3 listing)."""
    s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))
    for collection in collections:
        items = list(collection.get_items())
        print(f"\n{collection.id}: {len(items)} items")
        for item in items:
            href = item.assets["data"].href
            prefix = href.removeprefix(f"s3://{BUCKET_CADCAT}/")
            response = s3.list_objects_v2(Bucket=BUCKET_CADCAT, Prefix=prefix)
            n_csv = sum(o["Key"].endswith(".csv") for o in response.get("Contents", []))
            flag = "" if n_csv else "  <-- no CSVs"
            print(f"  {item.id}  {n_csv} CSV  {href}{flag}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[1])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Build the collections and report items without loading into pgSTAC.",
    )
    args = parser.parse_args()

    print("  Building Annual Climate Projections boundary CSV collections...")
    collections = build_collections()
    report(collections)
    if args.dry_run:
        print("\n  Dry run: nothing loaded.")
        return
    for collection in collections:
        print(f"\n  Loading {collection.id} into pgSTAC...")
        load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
