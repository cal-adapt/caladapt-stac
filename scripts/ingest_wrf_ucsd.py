"""ingest_wrf_ucsd.py

Ingest UCSD WRF dynamically downscaled zarr data into pgSTAC.

Workflow:
1. List S3 keys under the WRF UCSD prefix
2. Parse store prefixes to extract metadata
3. Build one pystac Item per zarr store (one per variable)
4. Load directly into pgSTAC

Each item represents one variable for a given model, scenario, ensemble
member, temporal frequency, and spatial grid.

S3 path structure:
    wrf/ucsd/{source_id}/{experiment_id}/{member_id}/{table_id}/{variable_id}/{grid_label}/

Usage:
    uv run python -m scripts.ingest_wrf_ucsd

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
    WRF_BBOX,
    WRF_UCSD_PREFIX,
)
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

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


def parse_wrf_ucsd_store(store_prefix):
    """
    Parse a WRF UCSD zarr store S3 prefix into components.

    Parameters
    ----------
    store_prefix : str
        S3 prefix for a zarr store,
        e.g. wrf/ucsd/cesm2/historical/r11i1p1f1/day/prec/d03/

    Returns
    -------
    dict
        Parsed components: source_id, experiment_id, member_id, table_id,
        variable_id, grid_label, path.
    """
    # wrf/ucsd/{source_id}/{experiment_id}/{member_id}/{table_id}/{variable_id}/{grid_label}/
    inner = store_prefix.removeprefix(WRF_UCSD_PREFIX)
    source_id, experiment_id, member_id, table_id, variable_id, grid_label, *_ = (
        inner.split("/")
    )
    return {
        "source_id": source_id,
        "experiment_id": experiment_id,
        "member_id": member_id,
        "table_id": table_id,
        "variable_id": variable_id,
        "grid_label": grid_label,
        "path": f"s3://{BUCKET_CADCAT}/{store_prefix}",
    }


def build_wrf_ucsd_collection():
    """
    Build a pystac Collection for UCSD WRF dynamically downscaled zarr data.

    Builds one item per zarr store (one per variable) with variable_id
    as a queryable property.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="wrf-ucsd",
        title="WRF UCSD (zarr)",
        description="Dynamically downscaled climate projections for California produced by UCSD using the Weather Research & Forecasting Model (WRF)",
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Cal-Adapt",
                roles=[pystac.ProviderRole.HOST, pystac.ProviderRole.PROCESSOR],
                url="https://cal-adapt.org/",
            ),
            pystac.Provider(
                name="UCSD",
                roles=[pystac.ProviderRole.PRODUCER],
                url="https://scripps.ucsd.edu/",
            ),
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[WRF_BBOX]),
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

    # depth=6: source_id/experiment_id/member_id/table_id/variable_id/grid_label
    print("  Listing zarr stores...")
    for i, store_prefix in enumerate(
        list_zarr_stores(WRF_UCSD_PREFIX, BUCKET_CADCAT, depth=6)
    ):
        if i % 50 == 0 and i > 0:
            print(f"  {i} stores found...")
        parsed = parse_wrf_ucsd_store(store_prefix)

        source_id = parsed["source_id"]
        experiment_id = parsed["experiment_id"]
        member_id = parsed["member_id"]
        table_id = parsed["table_id"]
        variable_id = parsed["variable_id"]
        grid_label = parsed["grid_label"]

        item_id = f"wrf-ucsd-{source_id}-{experiment_id}-{member_id}-{table_id}-{variable_id}-{grid_label}"

        start_dt, end_dt = EXPERIMENT_DATE_RANGES.get(
            experiment_id,
            (
                datetime(1980, 1, 1, tzinfo=timezone.utc),
                datetime(2100, 12, 31, tzinfo=timezone.utc),
            ),
        )

        props = {
            "source_id": source_id,
            "experiment_id": experiment_id,
            "member_id": member_id,
            "table_id": table_id,
            "variable_id": variable_id,
            "grid_label": grid_label,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
        }
        item = pystac.Item(
            id=item_id,
            geometry=bbox_to_geometry(WRF_BBOX),
            bbox=WRF_BBOX,
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
    print("  Building WRF UCSD collection...")
    collection = build_wrf_ucsd_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
