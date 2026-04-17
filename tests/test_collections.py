"""Tests for build_*_collection() functions — S3 and HTTP calls are mocked.

Each test verifies collection-level metadata (id, license, description,
keywords, thumbnail, providers) without touching S3 or the network.
"""

import pandas as pd
import pystac
from unittest.mock import patch, MagicMock

from scripts.ingest_climate_profiles import build_tmy_collection, build_smy_collection
from scripts.ingest_hadisd import build_hadisd_collection
from scripts.ingest_hdp import build_hdp_collection
from scripts.ingest_loca2_county import build_loca2_county_collection
from scripts.ingest_loca2 import build_loca2_gridded_collection
from scripts.ingest_sea_level import build_sea_level_collection
from scripts.ingest_wrf_cae import build_wrf_cae_collection
from scripts.ingest_wrf_ucla import build_wrf_ucla_collection
from scripts.ingest_ren import build_pv_collection, build_wind_collection


MOCK_ONE_FEATURE = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "properties": {
                "location": "test_loc",
                "station_code": "sf",
                "station_name": "San Francisco",
                "station_id": "999999-99999",
                "elevation": 5.0,
            },
            "geometry": {"type": "Point", "coordinates": [-122.4, 37.7]},
        }
    ],
}

MOCK_EMPTY_FC = {"type": "FeatureCollection", "features": []}


def _mock_response(data):
    m = MagicMock()
    m.json.return_value = data
    return m


def _check_metadata(collection, expected_id, expected_license="CC-BY-4.0"):
    assert collection.id == expected_id
    assert collection.license == expected_license
    assert collection.description
    assert collection.keywords
    assert collection.providers
    assert "thumbnail" in collection.assets


class TestBuildTmyCollection:
    @patch("scripts.ingest_climate_profiles.list_keys", return_value=[])
    @patch("scripts.ingest_climate_profiles.requests.get")
    def test_metadata(self, mock_get, _):
        mock_get.return_value = _mock_response(MOCK_EMPTY_FC)
        _check_metadata(build_tmy_collection(), "typical-met-year")

    @patch("scripts.ingest_climate_profiles.list_keys", return_value=[])
    @patch("scripts.ingest_climate_profiles.requests.get")
    def test_item_geometries_asset(self, mock_get, _):
        mock_get.return_value = _mock_response(MOCK_EMPTY_FC)
        assert "item-geometries" in build_tmy_collection().assets


class TestBuildSmyCollection:
    @patch("scripts.ingest_climate_profiles.list_keys", return_value=[])
    @patch("scripts.ingest_climate_profiles.requests.get")
    def test_metadata(self, mock_get, _):
        mock_get.return_value = _mock_response(MOCK_EMPTY_FC)
        _check_metadata(build_smy_collection(), "standard-year")


class TestBuildHadisdCollection:
    @patch("scripts.ingest_hadisd.requests.get")
    def test_metadata(self, mock_get):
        mock_get.return_value = _mock_response(MOCK_ONE_FEATURE)
        col = build_hadisd_collection()
        assert col.id == "hadisd"
        assert col.license == "proprietary"
        assert col.description
        assert col.keywords
        assert "thumbnail" in col.assets

    @patch("scripts.ingest_hadisd.requests.get")
    def test_builds_one_item_per_feature(self, mock_get):
        mock_get.return_value = _mock_response(MOCK_ONE_FEATURE)
        items = list(build_hadisd_collection().get_items())
        assert len(items) == 1
        assert items[0].id == "hadisd-999999-99999"


class TestBuildHdpCollection:
    @patch("scripts.ingest_hdp.pd.read_csv", return_value=pd.DataFrame())
    def test_metadata(self, _):
        _check_metadata(build_hdp_collection(), "historical-data-platform")

    @patch("scripts.ingest_hdp.pd.read_csv", return_value=pd.DataFrame())
    def test_item_geometries_asset(self, _):
        assert "item-geometries" in build_hdp_collection().assets


class TestBuildLoca2CountyCollection:
    @patch("scripts.ingest_loca2_county.list_keys", return_value=[])
    @patch("scripts.ingest_loca2_county.requests.get")
    def test_metadata(self, mock_get, _):
        mock_get.return_value = _mock_response(MOCK_EMPTY_FC)
        _check_metadata(build_loca2_county_collection(), "loca2-county")

    @patch("scripts.ingest_loca2_county.list_keys", return_value=[])
    @patch("scripts.ingest_loca2_county.requests.get")
    def test_item_geometries_asset(self, mock_get, _):
        mock_get.return_value = _mock_response(MOCK_EMPTY_FC)
        assert "item-geometries" in build_loca2_county_collection().assets


class TestBuildLoca2GriddedCollection:
    @patch("scripts.ingest_loca2.list_zarr_stores", return_value=[])
    def test_metadata(self, _):
        _check_metadata(build_loca2_gridded_collection(), "loca2")


class TestBuildSeaLevelCollection:
    @patch("scripts.ingest_sea_level.list_keys", return_value=[])
    @patch("scripts.ingest_sea_level.requests.get")
    def test_metadata(self, mock_get, _):
        mock_get.return_value = _mock_response(MOCK_EMPTY_FC)
        _check_metadata(build_sea_level_collection(), "sea-level-projections")

    @patch("scripts.ingest_sea_level.list_keys", return_value=[])
    @patch("scripts.ingest_sea_level.requests.get")
    def test_item_geometries_asset(self, mock_get, _):
        mock_get.return_value = _mock_response(MOCK_EMPTY_FC)
        assert "item-geometries" in build_sea_level_collection().assets


class TestBuildWrfCaeCollection:
    @patch("scripts.ingest_wrf_cae.list_zarr_stores", return_value=[])
    def test_metadata(self, _):
        _check_metadata(build_wrf_cae_collection(), "wrf-cae")


class TestBuildWrfUclaCollection:
    @patch("scripts.ingest_wrf_ucla.list_zarr_stores", return_value=[])
    def test_metadata(self, _):
        _check_metadata(build_wrf_ucla_collection(), "wrf-ucla")


class TestBuildPvCollection:
    @patch("scripts.ingest_ren.list_zarr_stores", return_value=[])
    def test_metadata(self, _):
        _check_metadata(build_pv_collection(), "pv-generation")


class TestBuildWindCollection:
    @patch("scripts.ingest_ren.list_zarr_stores", return_value=[])
    def test_metadata(self, _):
        _check_metadata(build_wind_collection(), "wind-generation")
