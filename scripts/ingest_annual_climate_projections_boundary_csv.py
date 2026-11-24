"""ingest_annual_climate_projections_boundary_csv.py

Ingest the Annual Climate Projections tool's boundary CSVs into pgSTAC as one
collection, `acp-boundary-csv`, holding three kinds of items:

    WRF projections     one item per variable x boundary (ssp370 only)
    LOCA2 projections   one item per variable x SSP x boundary (LOCA2-Hybrid)
    ERA5 observed       one item per variable x boundary (WRF-downscaled ERA5)

`cmip6:activity_id` + `cmip6:experiment_id` + `variable_id` + `boundary`
identify exactly one item. ERA5 items use activity WRF and experiment
`reanalysis`, matching the Cal-Adapt data catalog.

Each projection CSV holds one region's annual values: year, ensemble_mean,
ensemble_min, ensemble_max, then one column per simulation. Each ERA5 CSV
holds year, value.

S3 path structure:
    wrf/annual-climate-projections/per_boundary/{variable}/{boundary}/ssp370/csv/
        Files within: {Region}_{variable}_ssp370.csv
    loca2/annual-climate-projections/per_boundary/{variable}/{boundary}/{ssp}/csv/
        Files within: {Region}_{variable}_{ssp}.csv
    wrf/annual-climate-projections/era5_per_boundary/{variable}/{boundary}/csv/
        Files within: {Region}_{variable}_era5.csv

Each item has one `data` asset pointing to the S3 prefix directory.

Usage:
    uv run python -m scripts.ingest_annual_climate_projections_boundary_csv

Requires:
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

import pystac

from scripts.constants import (
    BOUNDARY_LABELS,
    BUCKET_CADCAT,
    CA_BBOX,
    CALADAPT_DATA_LICENSE,
    COLLECTION_KEYWORDS,
    LOCA2_ANNUAL_CLIMATE_PROJECTIONS_PREFIX,
    PGDSN,
    WRF_ANNUAL_CLIMATE_PROJECTIONS_PREFIX,
)
from scripts.utils import bbox_to_geometry, load_direct

COLLECTION_ID = "acp-boundary-csv"

# Boundaries with data on S3. The pipeline doesn't produce census tracts or
# IOU/POUs; if it does later, check whether they land under a weighted_median/
# subdirectory and add a BOUNDARY_SUBDIRS lookup like the HDD/CDD script.
VALID_BOUNDARIES = [
    "ca_counties",
    "ca_watersheds",
    "forecast_zones",
    "electric_balancing_areas",
    "state",
]

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


def build_collection():
    """
    Build a pystac Collection for the Annual Climate Projections boundary CSVs.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id=COLLECTION_ID,
        title="Annual climate projections by region",
        keywords=COLLECTION_KEYWORDS[COLLECTION_ID],
        extra_fields={
            "caladapt:spatial_type": "spatial-aggregate",
            "caladapt:boundary_labels": {
                b: BOUNDARY_LABELS[b] for b in VALID_BOUNDARIES
            },
        },
        description=(
            "Annual temperature and total precipitation for California regions. "
            "Projections come from bias-adjusted CMIP6 models dynamically downscaled "
            "with WRF (historical through ssp370, 1981-2099) and CMIP6 models "
            "statistically downscaled with LOCA2-Hybrid (historical through ssp245, "
            "ssp370 and ssp585, 1950-2099). Each projection CSV holds one region's "
            "annual mean, min and max across simulations, plus one column per "
            "simulation. Observed values come from the ERA5 reanalysis dynamically "
            "downscaled with WRF (1981-2019)."
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
            pystac.Provider(
                name="UCSD",
                roles=[pystac.ProviderRole.PRODUCER],
                url="https://loca.ucsd.edu/",
            ),
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[CA_BBOX]),
            temporal=pystac.TemporalExtent(
                intervals=[[LOCA2_DATE_RANGE[0], WRF_DATE_RANGE[1]]]
            ),
        ),
    )

    wrf_prefix = WRF_ANNUAL_CLIMATE_PROJECTIONS_PREFIX
    loca2_prefix = LOCA2_ANNUAL_CLIMATE_PROJECTIONS_PREFIX

    for boundary in VALID_BOUNDARIES:
        label = BOUNDARY_LABELS[boundary]
        for variable in WRF_VARIABLES:
            add_item(
                collection,
                item_id=f"{COLLECTION_ID}-wrf-{variable}-{WRF_SCENARIO}-{boundary}",
                path=f"{wrf_prefix}per_boundary/{variable}/{boundary}/{WRF_SCENARIO}/csv/",
                date_range=WRF_DATE_RANGE,
                properties={
                    "cmip6:activity_id": "WRF",
                    "cmip6:institution_id": "UCLA",
                    "cmip6:experiment_id": WRF_SCENARIO,
                    "variable_id": variable,
                    "boundary": boundary,
                    "bias_adjusted": True,
                },
                asset_title=f"{label} — WRF annual {variable}, {WRF_SCENARIO}",
            )
            add_item(
                collection,
                item_id=f"{COLLECTION_ID}-wrf-{variable}-era5-{boundary}",
                path=f"{wrf_prefix}era5_per_boundary/{variable}/{boundary}/csv/",
                date_range=ERA5_DATE_RANGE,
                properties={
                    "cmip6:activity_id": "WRF",
                    "cmip6:institution_id": "UCLA",
                    "cmip6:source_id": "ERA5",
                    "cmip6:experiment_id": "reanalysis",
                    "variable_id": variable,
                    "boundary": boundary,
                },
                asset_title=f"{label} — ERA5 annual {variable}",
            )
        for variable in LOCA2_VARIABLES:
            for scenario in LOCA2_SCENARIOS:
                add_item(
                    collection,
                    item_id=f"{COLLECTION_ID}-loca2-{variable}-{scenario}-{boundary}",
                    path=f"{loca2_prefix}per_boundary/{variable}/{boundary}/{scenario}/csv/",
                    date_range=LOCA2_DATE_RANGE,
                    properties={
                        "cmip6:activity_id": "LOCA2",
                        "cmip6:institution_id": "UCSD",
                        "cmip6:experiment_id": scenario,
                        "variable_id": variable,
                        "boundary": boundary,
                    },
                    asset_title=f"{label} — LOCA2 annual {variable}, {scenario}",
                )

    print(f"  Built {len(list(collection.get_items()))} items.")
    return collection


def main():
    print("  Building Annual Climate Projections boundary CSV collection...")
    collection = build_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
