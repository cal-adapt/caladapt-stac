"""constants.py

Shared constants for building and ingesting STAC items.

"""

import os
from datetime import datetime, timezone

import pystac

# S3 buckets
BUCKET_CADCAT = "cadcat"

# STAC API endpoint
API_ENDPOINT = os.environ.get("STAC_API_ENDPOINT", "http://localhost:8082")

# PostgreSQL DSN for direct DB access
PGDSN = os.environ.get("PGDSN")

# S3 HTTPS URLs for geometry GeoJSON files (upload manually after running generate_geometries.py)
CA_COUNTIES_GEOMETRIES_URL = (
    "https://cadcat.s3.amazonaws.com/geometries/ca-counties-geometries.geojson"
)
HADISD_STATION_COORDS_URL = (
    "https://cadcat.s3.amazonaws.com/geometries/hadisd-station-coords.geojson"
)
HDP_STATION_COORDS_URL = (
    "https://cadcat.s3.amazonaws.com/geometries/hdp-station-coords.geojson"
)


# S3 prefixes for collections
TMY_PREFIX = "climate-profiles/typical-met-year/"
SMY_PREFIX = "climate-profiles/standard-met-year/"
LOCA2_COUNTY_NETCDF_PREFIX = "loca2/ucb/netcdf/county/"
LOCA2_GRIDDED_PREFIX = "loca2/ucsd/"
WRF_UCLA_PREFIX = "wrf/ucla/"
WRF_UCSD_PREFIX = "wrf/ucsd/"

HDP_PREFIX = "histwxstns/"

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
# Derived from lat/lon coordinate arrays in representative Zarr stores
LOCA2_GRIDDED_BBOX = [-128.4219, 29.5781, -110.9844, 45.0156]

# WRF d01 bounds (outermost domain, covers full simulation extent)
WRF_BBOX = [-156.8232, 9.4756, -84.187, 67.3287]
