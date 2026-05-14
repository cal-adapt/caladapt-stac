"""ingest_wrf_climate_metrics_map.py

Ingest WRF climate metrics map data into pgSTAC.

Ensemble statistics for gridded WRF-downscaled climate extremes data (heat,
precipitation, fire weather) at global warming levels, supporting the Cal-Adapt
Climate Metrics Map tool. Statistics computed across 4 CMIP6 models
(cesm2, cnrm-esm2-1, ec-earth3-veg, fgoals-g3).

S3 path structure:
    wrf/climate-metrics-map/{statistic}/{scenario}/gwl/{metric}/d03/

Usage:
    uv run python -m scripts.ingest_wrf_climate_metrics_map

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
    WRF_CLIMATE_METRICS_MAP_PREFIX,
    WRF_UCLA_GRID_BBOXES,
    WRF_VARIABLE_LABELS,
)
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

EXPERIMENT_DATE_RANGES = {
    "ssp370": (
        datetime(2015, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 12, 31, tzinfo=timezone.utc),
    ),
}


def parse_climate_metrics_store(store_prefix):
    """
    Parse a climate-metrics-map zarr store S3 prefix into components.

    Parameters
    ----------
    store_prefix : str
        S3 prefix, e.g. wrf/climate-metrics-map/mm4mean/ssp370/gwl/TX99p/d03/

    Returns
    -------
    dict
        Parsed components: statistic, scenario, metric, grid_label, path.
    """
    # {statistic}/{scenario}/gwl/{metric}/{grid_label}/
    inner = store_prefix.removeprefix(WRF_CLIMATE_METRICS_MAP_PREFIX)
    statistic, scenario, _gwl, metric, grid_label, *_ = inner.split("/")
    return {
        "statistic": statistic,
        "scenario": scenario,
        "metric": metric,
        "grid_label": grid_label,
        "path": f"s3://{BUCKET_CADCAT}/{store_prefix}",
    }


def build_wrf_climate_metrics_map_collection():
    """
    Build a pystac Collection for WRF climate metrics map data.

    Returns
    -------
    pystac.Collection
    """
    bbox = WRF_UCLA_GRID_BBOXES["d03"]

    collection = pystac.Collection(
        id="wrf-climate-metrics-map",
        title="Cal Adapt climate metrics map data",
        keywords=[
            "climate model",
            "cloud-optimized",
            "California",
            "geospatial",
            "CMIP6",
            "dynamical",
            "extreme heat",
            "precipitation",
            "fire weather",
            "global warming levels",
        ],
        extra_fields={"caladapt:spatial_type": "grid"},
        description=(
            "Ensemble statistics for gridded WRF-downscaled climate extremes (heat, precipitation, fire weather) "
            "at global warming levels for California, supporting the Cal-Adapt Climate Metrics Map tool."
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
                        datetime(2015, 1, 1, tzinfo=timezone.utc),
                        datetime(2100, 12, 31, tzinfo=timezone.utc),
                    ]
                ]
            ),
        ),
    )

    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}climate_metrics_map.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="WRF climate metrics map preview",
        ),
    )

    print("  Listing zarr stores...")
    for store_prefix in list_zarr_stores(
        WRF_CLIMATE_METRICS_MAP_PREFIX, BUCKET_CADCAT, depth=5
    ):
        parsed = parse_climate_metrics_store(store_prefix)
        statistic = parsed["statistic"]
        scenario = parsed["scenario"]
        metric = parsed["metric"]
        grid_label = parsed["grid_label"]

        start_dt, end_dt = EXPERIMENT_DATE_RANGES[scenario]
        item_id = f"wrf-climate-metrics-map-{statistic}-{scenario}-gwl-{metric}-{grid_label}"

        props = {
            "cmip6:activity_id": "WRF",
            "cmip6:institution_id": "CAE",
            "cmip6:experiment_id": scenario,
            "cmip6:table_id": "gwl",
            "cmip6:grid_label": grid_label,
            "statistic": statistic,
            "variable_id": metric,
            "variable_label": WRF_VARIABLE_LABELS.get(metric, metric),
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

    return collection


def main():
    print("  Building WRF climate metrics map collection...")
    collection = build_wrf_climate_metrics_map_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
