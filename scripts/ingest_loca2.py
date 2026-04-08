"""ingest_loca2_gridded.py

Ingest LOCA2 gridded zarr data into pgSTAC by building pystac items
from S3 keys and loading them directly into pgSTAC.

Workflow:
1. List S3 keys under the LOCA2 gridded prefix
2. Parse store prefixes to extract metadata
3. Build one pystac Item per zarr store (one per variable)
4. Load directly into pgSTAC

Each item represents one variable for a given model, scenario, ensemble
member, temporal frequency, and spatial grid.

S3 path structure:
    loca2/ucsd/{source_id}/{experiment_id}/{member_id}/{table_id}/{variable_id}/{grid_label}/

Usage:
    uv run python -m scripts.ingest_loca2_gridded

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

import pystac

from scripts.constants import (
    BUCKET_CADCAT,
    CALADAPT_DATA_LICENSE,
    LOCA2_GRIDDED_BBOX,
    LOCA2_GRIDDED_PREFIX,
    PGDSN,
)
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

# Date ranges by experiment_id
EXPERIMENT_DATE_RANGES = {
    "historical": (
        datetime(1950, 1, 1, tzinfo=timezone.utc),
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


def parse_loca2_gridded_store(store_prefix):
    """
    Parse a LOCA2 gridded zarr store S3 prefix into components.

    Parameters
    ----------
    store_prefix : str
        S3 prefix for a zarr store,
        e.g. loca2/ucsd/access-cm2/historical/r1i1p1f1/day/tasmax/d03/

    Returns
    -------
    dict
        Parsed components: source_id, experiment_id, member_id, table_id,
        variable_id, grid_label, path.
    """
    # loca2/ucsd/{source_id}/{experiment_id}/{member_id}/{table_id}/{variable_id}/{grid_label}/
    inner = store_prefix.removeprefix(LOCA2_GRIDDED_PREFIX)
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


def build_loca2_gridded_collection():
    """
    Build a pystac Collection for LOCA2 gridded zarr data.

    Builds one item per zarr store (one per variable) with variable_id
    as a queryable property.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="loca2-gridded",
        title="LOCA2 (zarr)",
        description="Hybrid-statistically downscaled climate projections for California produced by UCSD using the Localized Constructed Analogs version 2 (LOCA2) method.",
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Cal-Adapt",
                roles=[
                    pystac.ProviderRole.HOST,
                    pystac.ProviderRole.PROCESSOR,
                ],
                url="https://cal-adapt.org/",
            ),
            pystac.Provider(
                name="UCSD",
                roles=[pystac.ProviderRole.PRODUCER],
                url="https://loca.ucsd.edu/",
            ),
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[LOCA2_GRIDDED_BBOX]),
            temporal=pystac.TemporalExtent(
                intervals=[
                    [
                        datetime(1950, 1, 1, tzinfo=timezone.utc),
                        datetime(2100, 12, 31, tzinfo=timezone.utc),
                    ]
                ]
            ),
        ),
    )

    # depth=6: source_id/experiment_id/member_id/table_id/variable_id/grid_label
    print("  Listing zarr stores...")
    for i, store_prefix in enumerate(
        list_zarr_stores(LOCA2_GRIDDED_PREFIX, BUCKET_CADCAT, depth=6)
    ):
        if i % 50 == 0 and i > 0:
            print(f"  {i} stores found...")
        parsed = parse_loca2_gridded_store(store_prefix)

        source_id = parsed["source_id"]
        experiment_id = parsed["experiment_id"]
        member_id = parsed["member_id"]
        table_id = parsed["table_id"]
        variable_id = parsed["variable_id"]
        grid_label = parsed["grid_label"]

        item_id = f"loca2-gridded-{source_id}-{experiment_id}-{member_id}-{table_id}-{variable_id}-{grid_label}"

        start_dt, end_dt = EXPERIMENT_DATE_RANGES.get(
            experiment_id,
            (
                datetime(1950, 1, 1, tzinfo=timezone.utc),
                datetime(2100, 12, 31, tzinfo=timezone.utc),
            ),
        )

        props = {
            "cmip6:source_id": source_id,
            "cmip6:experiment_id": experiment_id,
            "cmip6:member_id": member_id,
            "cmip6:table_id": table_id,
            "variable_id": variable_id,
            "grid_label": grid_label,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
        }
        item = pystac.Item(
            id=item_id,
            geometry=bbox_to_geometry(LOCA2_GRIDDED_BBOX),
            bbox=LOCA2_GRIDDED_BBOX,
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
    print("  Building LOCA2 gridded collection...")
    collection = build_loca2_gridded_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
