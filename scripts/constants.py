"""constants.py

Shared constants for building and ingesting STAC items.

"""

import os
from datetime import datetime, timezone

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
WRF_CAE_PREFIX = "wrf/cae/"

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

# Human-readable labels for WRF (Dynamical) variable IDs.
# Sourced from climakitae/data/variable_descriptions.csv (display_name column).
WRF_VARIABLE_LABELS: dict[str, str] = {
    "t2": "Air Temperature at 2m",
    "t2max": "Maximum air temperature at 2m",
    "t2min": "Minimum air temperature at 2m",
    "t": "Air Temperature",
    "tsk": "Surface skin temperature",
    "tskin": "Surface skin temperature",
    "prec": "Precipitation (total)",
    "prec_snow": "Snowfall",
    "prec_c": "Precipitation (convective only)",
    "prec_max": "Maximum precipitation",
    "rainc": "Precipitation (cumulus portion only)",
    "rainnc": "Precipitation (grid-scale portion only)",
    "snownc": "Snowfall (snow and ice)",
    "snow": "Snow water equivalent",
    "rh": "Relative humidity",
    "rh_derived": "Relative humidity",
    "rh_max": "Maximum relative humidity",
    "rh_min": "Minimum relative humidity",
    "q2": "Water Vapor Mixing Ratio at 2m",
    "q2_derived": "Specific humidity at 2m",
    "psfc": "Surface Pressure",
    "p": "Air pressure",
    "ph": "Geopotential height perturbation",
    "u10": "West-East component of Wind at 10m",
    "v10": "North-South component of Wind at 10m",
    "u": "Zonal Wind Component at 10m",
    "v": "Meridional Wind Component at 10m",
    "wind_speed_derived": "Wind speed at 10m",
    "wind_direction_derived": "Wind direction at 10m",
    "wspd10mean": "Mean wind speed at 10m",
    "wspd10max": "Maximum wind speed at 10m",
    "lwdnb": "Instantaneous downwelling longwave flux at bottom",
    "lwdnbc": "Instantaneous downwelling clear sky longwave flux at bottom",
    "lwupb": "Instantaneous upwelling longwave flux at bottom",
    "lwupbc": "Instantaneous upwelling clear sky longwave flux at bottom",
    "lw_dwn": "Instantaneous downwelling longwave flux at bottom",
    "lw_sfc": "Longwave flux at the surface",
    "swdnb": "Instantaneous downwelling shortwave flux at bottom",
    "swdnbc": "Instantaneous downwelling clear sky shortwave flux at bottom",
    "swupb": "Instantaneous upwelling shortwave flux at bottom",
    "swupbc": "Instantaneous upwelling clear sky shortwave flux at bottom",
    "swddni": "Shortwave surface downward direct normal irradiance",
    "swddir": "Shortwave surface downward direct irradiance",
    "swddif": "Shortwave surface downward diffuse irradiance",
    "sw_dwn": "Instantaneous downwelling shortwave flux at bottom",
    "sw_sfc": "Shortwave flux at the surface",
    "sh_sfc": "Sensible heat flux at the surface",
    "lh_sfc": "Latent heat flux at the surface",
    "gh_sfc": "Ground heat flux",
    "dew_point_derived_hrly": "Dew point temperature",
    "dew_point_derived": "Dew point temperature",
    "noaa_heat_index_derived": "NOAA Heat Index",
    "effective_temp_index_derived": "Effective Temperature",
    "ffwi": "Fosberg fire weather index",
    "lwp": "Liquid water path",
    "iwp": "Ice water path",
    "pblh": "Planetary boundary layer height",
    "cape": "Convective Available Potential Energy",
    "cin": "Convective Inhibition",
    "lcl": "Lifting Condensation Level",
    "lfc": "Level of Free Convection",
    "znt": "Surface roughness length",
    "runsf": "Surface runoff",
    "runsb": "Subsurface runoff",
    "sfc_runoff": "Surface runoff",
    "subsfc_runoff": "Subsurface runoff",
    "evap_sfc": "Evaporation",
    "etrans_sfc": "Evapotranspiration",
    "cf": "Capacity factor",
    "gen": "Power generation",
}

# Human-readable labels for LOCA2 (Statistical) variable IDs.
# Sourced from climakitae/data/variable_descriptions.csv (display_name column).
LOCA2_VARIABLE_LABELS: dict[str, str] = {
    "pr": "Precipitation (total)",
    "tasmax": "Maximum air temperature at 2m",
    "tasmin": "Minimum air temperature at 2m",
    "uas": "West-East component of Wind at 10m",
    "vas": "North-South component of Wind at 10m",
    "huss": "Specific humidity at 2m",
    "hursmin": "Minimum relative humidity",
    "hursmax": "Maximum relative humidity",
    "wspeed": "Wind speed at 10m",
    "rsds": "Shortwave flux at the surface",
}
