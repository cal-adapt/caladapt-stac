"""ingest_wrf_cae.py

Ingest Cal-Adapt Analytics Engine (CAE) WRF zarr data into pgSTAC.

CAE data are derived from WRF UCLA dynamically downscaled projections.

Workflow:
1. List S3 keys under the WRF CAE prefix
2. Parse store prefixes to extract metadata
3. Build one pystac Item per zarr store (one per variable)
4. Load directly into pgSTAC

S3 path structure:
    wrf/cae/{source_id}/{experiment_id}/{table_id}/{variable_id}/{grid_label}/

Usage:
    uv run python -m scripts.ingest_wrf_cae

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

import pystac

from scripts.constants import (
    BUCKET_CADCAT,
    CALADAPT_DATA_LICENSE,
    ICON_BASE_URL,
    PGDSN,
    WRF_CAE_PREFIX,
    WRF_UCLA_GRID_BBOXES,
    WRF_VARIABLE_LABELS,
)
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

EXPERIMENT_DATE_RANGES = {
    "historical": (
        datetime(1980, 1, 1, tzinfo=timezone.utc),
        datetime(2014, 12, 31, tzinfo=timezone.utc),
    ),
    "ssp370": (
        datetime(2015, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 12, 31, tzinfo=timezone.utc),
    ),
}


def parse_wrf_cae_store(store_prefix):
    """
    Parse a WRF CAE zarr store S3 prefix into components.

    Parameters
    ----------
    store_prefix : str
        S3 prefix for a zarr store,
        e.g. wrf/cae/ec-earth3/historical/1hr/ffwi/d03/

    Returns
    -------
    dict
        Parsed components: source_id, experiment_id, table_id,
        variable_id, grid_label, path.
    """
    # wrf/cae/{source_id}/{experiment_id}/{table_id}/{variable_id}/{grid_label}/
    inner = store_prefix.removeprefix(WRF_CAE_PREFIX)
    source_id, experiment_id, table_id, variable_id, grid_label, *_ = inner.split("/")
    return {
        "source_id": source_id,
        "experiment_id": experiment_id,
        "table_id": table_id,
        "variable_id": variable_id,
        "grid_label": grid_label,
        "path": f"s3://{BUCKET_CADCAT}/{store_prefix}",
    }


def build_wrf_cae_collection():
    """
    Build a pystac Collection for CAE WRF zarr data.

    Returns
    -------
    pystac.Collection
    """
    THUMBNAIL_URL = f"{ICON_BASE_URL}wrf_cae_ffwi_d03_2030.gif"

    collection = pystac.Collection(
        id="wrf-cae",
        title="WRF-derived climate metrics",
        keywords=["climate model", "cloud optimized"],
        extra_fields={"caladapt:spatial_type": "grid"},
        description=(
            "Extreme heat, precipitation, and fire weather metrics derived from "
            "bias-adjusted WRF dynamically downscaled projections, aggregated across "
            "global warming levels (0.8°C–3.0°C) for California."
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
            title="WRF animated preview",
        ),
    )

    # depth=5: source_id/experiment_id/table_id/variable_id/grid_label
    print("  Listing zarr stores...")
    for i, store_prefix in enumerate(
        list_zarr_stores(WRF_CAE_PREFIX, BUCKET_CADCAT, depth=5)
    ):
        if i % 50 == 0 and i > 0:
            print(f"  {i} stores found...")
        parsed = parse_wrf_cae_store(store_prefix)

        source_id = parsed["source_id"]
        experiment_id = parsed["experiment_id"]
        table_id = parsed["table_id"]
        variable_id = parsed["variable_id"]
        grid_label = parsed["grid_label"]

        item_id = (
            f"wrf-cae-{source_id}-{experiment_id}-{table_id}-{variable_id}-{grid_label}"
        )

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
            "institution_id": "CAE",
            "cmip6:source_id": source_id,
            "cmip6:experiment_id": experiment_id,
            "cmip6:table_id": table_id,
            "variable_id": variable_id,
            "variable_label": WRF_VARIABLE_LABELS.get(variable_id, variable_id),
            "grid_label": grid_label,
            "bias_adjusted": True,  # all CAE models are bias-adjusted (ensmean/mm4* are derived from BA models)
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
    print("  Building WRF CAE collection...")
    collection = build_wrf_cae_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
