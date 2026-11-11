"""ingest_wrf_extreme_heat_tool_boundary_csv.py

Ingest WRF extreme heat tool multi-model boundary CSV data into pgSTAC.

Multi-model ensemble summary CSVs (median/p10/p90 across 4 WRF models) at each
global warming level, organized by metric × boundary × threshold. Covers 6
California boundary types: counties, watersheds, census tracts, IOU/POUs,
forecast zones, and electric balancing areas.

S3 path structure:
    wrf/extreme-heat-tool/multimodel_per_boundary/{metric}/{boundary}/ssp370/{thresh}/
    Files within: {Region_Name}_{thresh}.csv

    Census tracts use the weighted median outputs, one level deeper:
    wrf/extreme-heat-tool/multimodel_per_boundary/{metric}/ca_census_tracts/weighted_median/ssp370/{thresh}/
    Files within: {GEOID}.csv

One STAC item per (metric × boundary × threshold) combination.
Each item has one asset pointing to the S3 prefix directory.

Usage:
    uv run python -m scripts.ingest_wrf_extreme_heat_tool_boundary_csv

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
    WRF_EXTREME_HEAT_TOOL_PREFIX,
    WRF_VARIABLE_LABELS,
    COLLECTION_KEYWORDS,
)
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

MULTIMODEL_CSV_PREFIX = WRF_EXTREME_HEAT_TOOL_PREFIX + "multimodel_per_boundary/"

METRICS = ["eh_days", "warm_nights"]
SCENARIO = "ssp370"

# All 6 boundary types the pipeline produces. This is a deliberate allowlist
# rather than something to discover from S3, so older outputs left on S3
# (e.g. the unweighted census tract folder) are never picked up.
BOUNDARY_LABELS = {
    "ca_counties": "California counties",
    "ca_watersheds": "California watersheds (HUC8)",
    "ca_census_tracts": "California census tracts",
    "ious_pous": "California IOUs and POUs",
    "forecast_zones": "California forecast zones",
    "electric_balancing_areas": "California electric balancing areas",
}
VALID_BOUNDARIES = list(BOUNDARY_LABELS)

# Census tract outputs sit under an extra aggregation directory. Only the
# weighted median is ingested; the weighted mean is not used.
BOUNDARY_SUBDIRS = {
    "ca_census_tracts": "weighted_median/",
}

EXPERIMENT_DATE_RANGE = (
    datetime(2015, 1, 1, tzinfo=timezone.utc),
    datetime(2100, 12, 31, tzinfo=timezone.utc),
)


def build_collection():
    """
    Build a pystac Collection for WRF extreme heat tool multi-model boundary CSVs.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="eh-metrics-mm-boundary-csv",
        title="Extreme heat days and warm nights by region",
        keywords=COLLECTION_KEYWORDS["eh-metrics-mm-boundary-csv"],
        extra_fields={
            "caladapt:spatial_type": "spatial-aggregate",
            "caladapt:source": "wrf",
            "caladapt:boundary_labels": BOUNDARY_LABELS,
        },
        description=(
            "Multi-model ensemble summary CSVs of WRF projections of extreme heat days "
            "and warm nights for California at global warming levels (0.8°C–3.0°C), "
            "aggregated by boundary region. Each CSV contains multi-model "
            "median/p10/p90 exceedance counts across all warming levels for one region."
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
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}wrf_extreme_heat_days_warm_nights.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="WRF extreme heat tool preview",
        ),
    )

    print("  Discovering threshold CSV prefixes from S3...")
    geometry = bbox_to_geometry(CA_BBOX)
    start_dt, end_dt = EXPERIMENT_DATE_RANGE
    items_built = 0

    for metric in METRICS:
        for boundary in VALID_BOUNDARIES:
            subdir = BOUNDARY_SUBDIRS.get(boundary, "")
            boundary_prefix = (
                f"{MULTIMODEL_CSV_PREFIX}{metric}/{boundary}/{subdir}{SCENARIO}/"
            )
            # depth=1: thresh
            for prefix in list_zarr_stores(boundary_prefix, BUCKET_CADCAT, depth=1):
                thresh = prefix.rstrip("/").rsplit("/", 1)[-1]
                item_id = f"eh-metrics-mm-boundary-csv-{metric}-{boundary}-{thresh}"

                item = pystac.Item(
                    id=item_id,
                    geometry=geometry,
                    bbox=CA_BBOX,
                    datetime=None,
                    properties={
                        "start_datetime": start_dt.isoformat(),
                        "end_datetime": end_dt.isoformat(),
                        "cmip6:activity_id": "WRF",
                        "cmip6:institution_id": "CAE",
                        "cmip6:experiment_id": SCENARIO,
                        "variable_id": metric,
                        "threshold_name": thresh,
                        "boundary": boundary,
                        "caladapt:spatial_type": "spatial-aggregate",
                        "bias_adjusted": True,
                    },
                )
                item.add_asset(
                    "data",
                    pystac.Asset(
                        href=f"s3://{BUCKET_CADCAT}/{prefix}",
                        media_type="text/csv",
                        title=f"{BOUNDARY_LABELS[boundary]} — {metric} | {thresh}",
                        roles=["data"],
                    ),
                )
                collection.add_item(item)
                items_built += 1

    collection.extra_fields["caladapt:variable_labels"] = {
        var: WRF_VARIABLE_LABELS.get(var, var) for var in METRICS
    }

    print(f"  Built {items_built} items.")
    return collection


def main():
    print("  Building WRF extreme heat tool boundary CSV collection...")
    collection = build_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
