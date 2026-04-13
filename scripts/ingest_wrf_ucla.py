"""ingest_wrf_ucla.py

Ingest UCLA WRF dynamically downscaled zarr data into pgSTAC.

Workflow:
1. List S3 keys under the WRF UCLA prefix
2. Parse store prefixes to extract metadata
3. Build one pystac Item per zarr store (one per variable)
4. Load directly into pgSTAC

Each item represents one variable for a given model, scenario,
temporal frequency, and spatial grid.

S3 path structure:
    wrf/ucla/{source_id}/{experiment_id}/{table_id}/{variable_id}/{grid_label}/

Usage:
    uv run python -m scripts.ingest_wrf_ucla

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

import pystac

from scripts.constants import (
    BUCKET_CADCAT,
    CALADAPT_DATA_LICENSE,
    PGDSN,
    WRF_UCLA_GRID_BBOXES,
    WRF_UCLA_PREFIX,
)
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

# UCLA source_ids (as they appear in S3 paths) without a-priori bias adjustment
UCLA_NON_BA_SOURCE_IDS = {"fgoals-g3", "cnrm-esm2-1", "cesm2", "ensmean"}

EXPERIMENT_DATE_RANGES = {
    "historical": (
        datetime(1980, 1, 1, tzinfo=timezone.utc),
        datetime(2014, 12, 31, tzinfo=timezone.utc),
    ),
    "ssp245": (
        datetime(2015, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 12, 31, tzinfo=timezone.utc),
    ),
    "ssp370": (
        datetime(2015, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 12, 31, tzinfo=timezone.utc),
    ),
    "ssp585": (
        datetime(2015, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 12, 31, tzinfo=timezone.utc),
    ),
}


def parse_wrf_ucla_store(store_prefix):
    """
    Parse a WRF UCLA zarr store S3 prefix into components.

    Parameters
    ----------
    store_prefix : str
        S3 prefix for a zarr store,
        e.g. wrf/ucla/cesm2/historical/1hr/lwdnb/d03/

    Returns
    -------
    dict
        Parsed components: source_id, experiment_id, table_id,
        variable_id, grid_label, path.
    """
    # wrf/ucla/{source_id}/{experiment_id}/{table_id}/{variable_id}/{grid_label}/
    inner = store_prefix.removeprefix(WRF_UCLA_PREFIX)
    source_id, experiment_id, table_id, variable_id, grid_label, *_ = inner.split("/")
    return {
        "source_id": source_id,
        "experiment_id": experiment_id,
        "table_id": table_id,
        "variable_id": variable_id,
        "grid_label": grid_label,
        "path": f"s3://{BUCKET_CADCAT}/{store_prefix}",
    }


def build_wrf_ucla_collection():
    """
    Build a pystac Collection for UCLA WRF dynamically downscaled zarr data.

    Builds one item per zarr store (one per variable) with variable_id
    as a queryable property.

    Returns
    -------
    pystac.Collection
    """
    THUMBNAIL_URL = "https://raw.githubusercontent.com/cal-adapt/caladapt-stac/main/data/icons/wrf_icon.gif"

    collection = pystac.Collection(
        id="wrf-ucla",
        title="WRF",
        extra_fields={"caladapt:spatial_type": "grid"},
        description="Dynamically downscaled climate projections for California using the Weather Research & Forecasting Model (WRF).",
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
            spatial=pystac.SpatialExtent(bboxes=list(WRF_UCLA_GRID_BBOXES.values())),
            temporal=pystac.TemporalExtent(
                intervals=[
                    [
                        datetime(1980, 1, 1, tzinfo=timezone.utc),
                        datetime(2100, 12, 31, tzinfo=timezone.utc),
                    ]
                ]
            ),
        ),
    )

    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=THUMBNAIL_URL,
            media_type="image/gif",
            roles=["thumbnail"],
            title="WRF t2 animated preview",
        ),
    )

    # depth=5: source_id/experiment_id/table_id/variable_id/grid_label
    print("  Listing zarr stores...")
    for i, store_prefix in enumerate(
        list_zarr_stores(WRF_UCLA_PREFIX, BUCKET_CADCAT, depth=5)
    ):
        if i % 50 == 0 and i > 0:
            print(f"  {i} stores found...")
        parsed = parse_wrf_ucla_store(store_prefix)

        source_id = parsed["source_id"]
        experiment_id = parsed["experiment_id"]
        table_id = parsed["table_id"]
        variable_id = parsed["variable_id"]
        grid_label = parsed["grid_label"]

        item_id = f"wrf-ucla-{source_id}-{experiment_id}-{table_id}-{variable_id}-{grid_label}"

        start_dt, end_dt = EXPERIMENT_DATE_RANGES.get(
            experiment_id,
            (
                datetime(1980, 1, 1, tzinfo=timezone.utc),
                datetime(2100, 12, 31, tzinfo=timezone.utc),
            ),
        )

        bbox = WRF_UCLA_GRID_BBOXES.get(grid_label, WRF_UCLA_GRID_BBOXES["d02"])
        props = {
            "activity_id": "WRF",
            "institution_id": "UCLA",
            "source_id": source_id,
            "experiment_id": experiment_id,
            "table_id": table_id,
            "variable_id": variable_id,
            "grid_label": grid_label,
            "bias_adjusted": source_id not in UCLA_NON_BA_SOURCE_IDS,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
        }
        item = pystac.Item(
            id=item_id,
            geometry=bbox_to_geometry(bbox),
            bbox=bbox,
            datetime=None,
            properties=props,
        )
        item.add_asset(
            "data",
            pystac.Asset(href=parsed["path"], media_type="application/vnd+zarr"),
        )
        collection.add_item(item)

    return collection


def main():
    print("  Building WRF UCLA collection...")
    collection = build_wrf_ucla_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
