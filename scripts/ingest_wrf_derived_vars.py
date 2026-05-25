"""ingest_wrf_derived_vars.py

Ingest WRF derived variable data into pgSTAC.

Hourly derived climate variables (FFWI, relative humidity, wind speed) for
California, produced by the Cal-Adapt team from WRF-downscaled CMIP6 outputs
at 3 km resolution.

S3 path structure:
    wrf/derived-vars/{model}/{scenario}/1hr/{variable}/d03/

Usage:
    uv run python -m scripts.ingest_wrf_derived_vars

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
    WRF_DERIVED_VARS_PREFIX,
    WRF_UCLA_GRID_BBOXES,
    WRF_VARIABLE_LABELS,
)
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

EXPERIMENT_DATE_RANGES = {
    "historical": (
        datetime(1980, 9, 1, tzinfo=timezone.utc),
        datetime(2014, 12, 31, tzinfo=timezone.utc),
    ),
    "ssp370": (
        datetime(2014, 9, 1, tzinfo=timezone.utc),
        datetime(2100, 12, 31, tzinfo=timezone.utc),
    ),
}


def parse_derived_vars_store(store_prefix):
    """
    Parse a derived-vars zarr store S3 prefix into components.

    Parameters
    ----------
    store_prefix : str
        S3 prefix, e.g. wrf/derived-vars/ec-earth3/ssp370/1hr/ffwi/d03/

    Returns
    -------
    dict
        Parsed components: model, scenario, table_id, variable_id, grid_label, path.
    """
    # {model}/{scenario}/{table_id}/{variable_id}/{grid_label}/
    inner = store_prefix.removeprefix(WRF_DERIVED_VARS_PREFIX)
    model, scenario, table_id, variable_id, grid_label, *_ = inner.split("/")
    return {
        "model": model,
        "scenario": scenario,
        "table_id": table_id,
        "variable_id": variable_id,
        "grid_label": grid_label,
        "path": f"s3://{BUCKET_CADCAT}/{store_prefix}",
    }


def build_wrf_derived_vars_collection():
    """
    Build a pystac Collection for WRF derived variable data.

    Returns
    -------
    pystac.Collection
    """
    bbox = WRF_UCLA_GRID_BBOXES["d03"]

    collection = pystac.Collection(
        id="wrf-derived-vars",
        title="WRF derived climate variables",
        keywords=[
            "climate model",
            "cloud-optimized",
            "California",
            "geospatial",
            "CMIP6",
            "dynamical",
            "fire weather",
            "wind",        ],
        extra_fields={"caladapt:spatial_type": "grid"},
        description=(
            "Hourly derived climate variables (FFWI, relative humidity, wind speed) for California, "
            "produced from WRF-downscaled CMIP6 outputs at 3 km resolution."
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
            spatial=pystac.SpatialExtent(bboxes=[bbox]),
            temporal=pystac.TemporalExtent(
                intervals=[
                    [
                        datetime(1980, 9, 1, tzinfo=timezone.utc),
                        datetime(2100, 12, 31, tzinfo=timezone.utc),
                    ]
                ]
            ),
        ),
    )

    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}wrf_cae_ffwi_d03_2030.gif",
            media_type="image/gif",
            roles=["thumbnail"],
            title="WRF derived variables preview",
        ),
    )

    print("  Listing zarr stores...")
    seen_variables: set[str] = set()
    for store_prefix in list_zarr_stores(WRF_DERIVED_VARS_PREFIX, BUCKET_CADCAT, depth=5):
        parsed = parse_derived_vars_store(store_prefix)
        model = parsed["model"]
        scenario = parsed["scenario"]
        variable_id = parsed["variable_id"]
        grid_label = parsed["grid_label"]

        seen_variables.add(variable_id)
        start_dt, end_dt = EXPERIMENT_DATE_RANGES[scenario]
        item_id = f"wrf-derived-vars-{model}-{scenario}-1hr-{variable_id}-{grid_label}"

        props = {
            "cmip6:activity_id": "WRF",
            "cmip6:institution_id": "CAE",
            "cmip6:source_id": model,
            "cmip6:experiment_id": scenario,
            "cmip6:table_id": "1hr",
            "cmip6:grid_label": grid_label,
            "variable_id": variable_id,
            "caladapt:spatial_type": "grid",
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

    collection.extra_fields["caladapt:variable_labels"] = {
        var: WRF_VARIABLE_LABELS.get(var, var) for var in seen_variables
    }
    return collection


def main():
    print("  Building WRF derived vars collection...")
    collection = build_wrf_derived_vars_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
