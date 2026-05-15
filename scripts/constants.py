"""constants.py

Shared constants for building and ingesting STAC items.

"""

import csv
import os
from datetime import datetime, timezone
from pathlib import Path

import pystac

# S3 buckets
BUCKET_CADCAT = "cadcat"
BUCKET_REN = "wfclimres"  # renewable data

# STAC API endpoint
API_ENDPOINT = os.environ.get("STAC_API_ENDPOINT", "http://localhost:8082")

# PostgreSQL DSN for direct DB access
PGDSN = os.environ.get("PGDSN")

# S3 HTTPS URL for collection thumbnail icons
ICON_BASE_URL = "https://cadcat.s3.amazonaws.com/figures/icons/"

# S3 HTTPS URLs for geometry GeoJSON files (upload manually after running generate_geometries.py)
CA_COUNTIES_GEOMETRIES_URL = (
    "https://cadcat.s3.amazonaws.com/geometries/ca-counties-geometries.geojson"
)
HADISD_CA_STATION_COORDS_URL = (
    "https://cadcat.s3.amazonaws.com/geometries/hadisd-ca-station-coords.geojson"
)
HADISD_WECC_STATION_COORDS_URL = (
    "https://cadcat.s3.amazonaws.com/geometries/hadisd-wecc-station-coords.geojson"
)
HADISD_STATIONS_CSV_URL = "https://cadcat.s3.amazonaws.com/hadisd/hadisd_stations.csv"
HDP_STATION_COORDS_URL = (
    "https://cadcat.s3.amazonaws.com/geometries/hdp-station-coords.geojson"
)
SEA_LEVEL_STATION_COORDS_URL = (
    "https://cadcat.s3.amazonaws.com/geometries/sea-level-station-coords.geojson"
)


# S3 prefixes for collections
TMY_PREFIX = "climate-profiles/typical-met-year/"
SMY_PREFIX = "climate-profiles/standard-met-year/"
LOCA2_COUNTY_NETCDF_PREFIX = "loca2/ucb/netcdf/county/"
LOCA2_GRIDDED_PREFIX = "loca2/ucsd/"
WRF_UCLA_PREFIX = "wrf/ucla/"
WRF_UCSD_PREFIX = "wrf/ucsd/"
WRF_EXTREME_HEAT_TOOL_PREFIX = "wrf/extreme-heat-tool/"
WRF_DERIVED_VARS_PREFIX = "wrf/derived-vars/"
WRF_CLIMATE_METRICS_MAP_PREFIX = "wrf/climate-metrics-map/"

HDP_PREFIX = "histwxstns/"
HADISD_PREFIX = "hadisd/"
HMET_PREFIX = "hmet/"

# License for all Cal-Adapt data (CMIP6-derived products)
CALADAPT_DATA_LICENSE = "CC-BY-4.0"
CALADAPT_DATA_LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"

# Mapping of California county FIPS codes to county names (without "County" suffix)
# Matches the countyname property used in STAC items and the cal-adapt-de-website data download tool
CA_COUNTY_FIPS = {
    "06001": "Alameda",
    "06003": "Alpine",
    "06005": "Amador",
    "06007": "Butte",
    "06009": "Calaveras",
    "06011": "Colusa",
    "06013": "Contra Costa",
    "06015": "Del Norte",
    "06017": "El Dorado",
    "06019": "Fresno",
    "06021": "Glenn",
    "06023": "Humboldt",
    "06025": "Imperial",
    "06027": "Inyo",
    "06029": "Kern",
    "06031": "Kings",
    "06033": "Lake",
    "06035": "Lassen",
    "06037": "Los Angeles",
    "06039": "Madera",
    "06041": "Marin",
    "06043": "Mariposa",
    "06045": "Mendocino",
    "06047": "Merced",
    "06049": "Modoc",
    "06051": "Mono",
    "06053": "Monterey",
    "06055": "Napa",
    "06057": "Nevada",
    "06059": "Orange",
    "06061": "Placer",
    "06063": "Plumas",
    "06065": "Riverside",
    "06067": "Sacramento",
    "06069": "San Benito",
    "06071": "San Bernardino",
    "06073": "San Diego",
    "06075": "San Francisco",
    "06077": "San Joaquin",
    "06079": "San Luis Obispo",
    "06081": "San Mateo",
    "06083": "Santa Barbara",
    "06085": "Santa Clara",
    "06087": "Santa Cruz",
    "06089": "Shasta",
    "06091": "Sierra",
    "06093": "Siskiyou",
    "06095": "Solano",
    "06097": "Sonoma",
    "06099": "Stanislaus",
    "06101": "Sutter",
    "06103": "Tehama",
    "06105": "Trinity",
    "06107": "Tulare",
    "06109": "Tuolumne",
    "06111": "Ventura",
    "06113": "Yolo",
    "06115": "Yuba",
}

# 30-year period date ranges for climate profiles, keyed by GWL period name
# centered_year ± 15 years
CLIM_PROF_GWL_PERIOD_DATES = {
    "present-day": (
        datetime(2014, 1, 1, tzinfo=timezone.utc),
        datetime(2044, 12, 31, tzinfo=timezone.utc),
    ),  # centered_year=2029
    "near-future": (
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        datetime(2055, 12, 31, tzinfo=timezone.utc),
    ),  # centered_year=2040
    "mid-century": (
        datetime(2038, 1, 1, tzinfo=timezone.utc),
        datetime(2068, 12, 31, tzinfo=timezone.utc),
    ),  # centered_year=2053
    "mid-late-century": (
        datetime(2054, 1, 1, tzinfo=timezone.utc),
        datetime(2084, 12, 31, tzinfo=timezone.utc),
    ),  # centered_year=2069
}

# Spatial extents
CA_BBOX = [-124.4, 32.5, -114.1, 42.0]
WECC_BBOX = [-125.0, 25.0, -100.0, 52.0]

# Per-grid bboxes derived from actual zarr lat/lon arrays
LOCA2_GRIDDED_BBOX = [-128.4219, 29.5781, -110.9844, 45.0156]  # d03 only
WRF_UCSD_GRID_BBOXES = {
    "d03": [-128.4219, 29.5781, -110.9844, 45.0156],
}
WRF_UCLA_GRID_BBOXES = {
    "d01": [-154.6164, 9.4756, -87.2352, 64.4245],
    "d02": [-136.3039, 22.2671, -96.2959, 55.1834],
    "d03": [-127.9559, 29.9789, -111.2325, 44.8999],
}

_VAR_MAPPING_DIR = Path(__file__).parent.parent / "data" / "variable_mapping"


def _load_variable_labels(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8") as f:
        return {row["variable_id"]: row["variable_label"] for row in csv.DictReader(f)}


WRF_VARIABLE_LABELS: dict[str, str] = _load_variable_labels(
    _VAR_MAPPING_DIR / "wrf.csv"
)
LOCA2_VARIABLE_LABELS: dict[str, str] = _load_variable_labels(
    _VAR_MAPPING_DIR / "loca2.csv"
)
RENEWABLES_VARIABLE_LABELS: dict[str, str] = _load_variable_labels(
    _VAR_MAPPING_DIR / "renewables.csv"
)
