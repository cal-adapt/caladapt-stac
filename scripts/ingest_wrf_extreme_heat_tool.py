"""ingest_wrf_extreme_heat_tool.py

Ingest WRF extreme heat tool county-aggregated Zarr data into pgSTAC.

Bias-corrected WRF dynamically downscaled extreme heat projections for
California at global warming levels (0.8°C–3.0°C), supporting the Cal-Adapt
Extreme Heat Tool. County-aggregated exceedance counts for three heat metrics
across 5 WRF-downscaled CMIP6 models.

S3 path structure:
    wrf/extreme-heat-tool/county/{scenario}/gwl/{metric}/d03/

Usage:
    uv run python -m scripts.ingest_wrf_extreme_heat_tool

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

import pystac

from scripts.constants import (
    API_ENDPOINT,
    BUCKET_CADCAT,
    CA_BBOX,
    CALADAPT_DATA_LICENSE,
    ICON_BASE_URL,
    PGDSN,
    WRF_EXTREME_HEAT_TOOL_PREFIX,
    WRF_VARIABLE_LABELS,
)
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

COUNTY_PREFIX = WRF_EXTREME_HEAT_TOOL_PREFIX + "county/"

EXPERIMENT_DATE_RANGES = {
    "ssp370": (
        datetime(2015, 1, 1, tzinfo=timezone.utc),
        datetime(2100, 12, 31, tzinfo=timezone.utc),
    ),
}


def parse_county_store(store_prefix):
    """
    Parse a county zarr store S3 prefix into components.

    Parameters
    ----------
    store_prefix : str
        S3 prefix, e.g. wrf/extreme-heat-tool/county/ssp370/gwl/t2max_ge100F/d03/

    Returns
    -------
    dict
        Parsed components: scenario, metric, grid_label, path.
    """
    # county/{scenario}/gwl/{metric}/{grid_label}/
    inner = store_prefix.removeprefix(COUNTY_PREFIX)
    scenario, _gwl, metric, grid_label, *_ = inner.split("/")
    return {
        "scenario": scenario,
        "metric": metric,
        "grid_label": grid_label,
        "path": f"s3://{BUCKET_CADCAT}/{store_prefix}",
    }


def build_wrf_extreme_heat_tool_collection():
    """
    Build a pystac Collection for WRF extreme heat tool county-aggregated Zarr data.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="wrf-extreme-heat-tool-county",
        title="Cal Adapt extreme heat metrics tool (county Zarr)",
        keywords=[
            "climate model",
            "cloud-optimized",
            "California",
            "geospatial",
            "CMIP6",
            "dynamical",
            "extreme heat",
            "global warming levels",
            "counties",
        ],
        extra_fields={"caladapt:spatial_type": "county"},
        description=(
            "County-aggregated WRF extreme heat projections for California at global warming levels (0.8°C–3.0°C), "
            "supporting the Cal-Adapt Extreme Heat Tool."
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
            href=f"{ICON_BASE_URL}wrf_extreme_heat_ridgeplot.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="WRF extreme heat tool preview",
        ),
    )
    collection.add_link(
        pystac.Link(
            rel="related",
            target=f"{API_ENDPOINT}/collections/wrf-extreme-heat-tool-county-csv",
            media_type="application/json",
            title="WRF extreme heat tool county CSV",
        )
    )

    print("  Listing county zarr stores...")
    for store_prefix in list_zarr_stores(COUNTY_PREFIX, BUCKET_CADCAT, depth=4):
        parsed = parse_county_store(store_prefix)
        scenario = parsed["scenario"]
        metric = parsed["metric"]
        grid_label = parsed["grid_label"]

        start_dt, end_dt = EXPERIMENT_DATE_RANGES[scenario]
        item_id = f"wrf-extreme-heat-tool-county-{scenario}-gwl-{metric}-{grid_label}"

        props = {
            "cmip6:activity_id": "WRF",
            "cmip6:institution_id": "CAE",
            "cmip6:experiment_id": scenario,
            "cmip6:table_id": "gwl",
            "cmip6:grid_label": grid_label,
            "variable_id": metric,
            "variable_label": WRF_VARIABLE_LABELS.get(metric, metric),
            "caladapt:spatial_type": "county",
            "bias_adjusted": True,
            "start_datetime": start_dt.isoformat(),
            "end_datetime": end_dt.isoformat(),
        }
        item = pystac.Item(
            id=item_id,
            geometry=bbox_to_geometry(CA_BBOX),
            bbox=CA_BBOX,
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
    print("  Building WRF extreme heat tool county collection...")
    collection = build_wrf_extreme_heat_tool_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
