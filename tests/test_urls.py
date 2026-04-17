"""Integration tests: verify icon and geometry URLs are publicly reachable.

Requires network access. Skip in offline environments:
    pytest -m "not integration"
"""

import pytest
import requests

from scripts.constants import (
    ICON_BASE_URL,
    CA_COUNTIES_GEOMETRIES_URL,
    HADISD_CA_STATION_COORDS_URL,
    HADISD_WECC_STATION_COORDS_URL,
    HDP_STATION_COORDS_URL,
    SEA_LEVEL_STATION_COORDS_URL,
)

ICON_FILENAMES = [
    "tmy_icon.png",
    "standard_year_icon.png",
    "hadisd_icon.png",
    "hdp_icon.png",
    "loca2_county_icon.png",
    "loca2_tasmax_2030.gif",
    "sea_level_icon.png",
    "wrf_cae_ffwi_d03_2030.gif",
    "wrf_t2_d03_2030.gif",
    "pv_cf_d03_2030.gif",
    "wind_cf_d03_2030.gif",
]

GEOMETRY_URLS = [
    CA_COUNTIES_GEOMETRIES_URL,
    HADISD_CA_STATION_COORDS_URL,
    HADISD_WECC_STATION_COORDS_URL,
    HDP_STATION_COORDS_URL,
    SEA_LEVEL_STATION_COORDS_URL,
]


@pytest.mark.integration
@pytest.mark.parametrize("filename", ICON_FILENAMES)
def test_icon_url_returns_200(filename):
    url = f"{ICON_BASE_URL}{filename}"
    response = requests.head(url, allow_redirects=True, timeout=10)
    assert response.status_code == 200, f"{url} returned {response.status_code}"


@pytest.mark.integration
@pytest.mark.parametrize("url", GEOMETRY_URLS)
def test_geometry_url_returns_200(url):
    response = requests.head(url, allow_redirects=True, timeout=10)
    assert response.status_code == 200, f"{url} returned {response.status_code}"
