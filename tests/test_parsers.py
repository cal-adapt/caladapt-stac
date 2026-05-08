"""Unit tests for parse functions and bbox_to_geometry. No external calls needed."""

from scripts.utils import bbox_to_geometry
from scripts.ingest_climate_profiles import parse_tmy_key, parse_smy_key
from scripts.ingest_loca2_county import parse_loca2_county_key
from scripts.ingest_loca2 import parse_loca2_gridded_store
from scripts.ingest_ren import parse_ren_store
from scripts.ingest_sea_level import parse_hmet_key, SLR_SCENARIO_LABELS
from scripts.ingest_wrf_cae import parse_wrf_cae_store
from scripts.ingest_wrf_ucla import parse_wrf_ucla_store


class TestBboxToGeometry:
    def test_five_point_closed_ring(self):
        ring = bbox_to_geometry([-124.4, 32.5, -114.1, 42.0])["coordinates"][0]
        assert len(ring) == 5
        assert ring[0] == ring[-1]

    def test_corner_order(self):
        west, south, east, north = -124.4, 32.5, -114.1, 42.0
        ring = bbox_to_geometry([west, south, east, north])["coordinates"][0]
        assert ring[0] == [west, south]
        assert ring[1] == [east, south]
        assert ring[2] == [east, north]
        assert ring[3] == [west, north]


class TestParseTmyKey:
    def test_valid_epw(self):
        key = (
            "climate-profiles/typical-met-year/sacramento/taiesm1/mid-century/file.epw"
        )
        assert parse_tmy_key(key) == {
            "location": "sacramento",
            "model": "taiesm1",
            "time_period": "mid-century",
        }

    def test_valid_csv(self):
        key = "climate-profiles/typical-met-year/los_angeles/cesm2/near-future/file.csv"
        result = parse_tmy_key(key)
        assert result["location"] == "los_angeles"
        assert result["model"] == "cesm2"
        assert result["time_period"] == "near-future"

    def test_invalid_extension(self):
        assert (
            parse_tmy_key("climate-profiles/typical-met-year/loc/model/period/file.nc")
            is None
        )


class TestParseSmyKey:
    def test_valid_csv(self):
        key = (
            "climate-profiles/standard-met-year/sacramento/dbt/p50/mid-century/file.csv"
        )
        assert parse_smy_key(key) == {
            "location": "sacramento",
            "variable": "dbt",
            "percentile": "p50",
            "time_period": "mid-century",
        }

    def test_epw_returns_none(self):
        key = (
            "climate-profiles/standard-met-year/sacramento/dbt/p50/mid-century/file.epw"
        )
        assert parse_smy_key(key) is None


class TestParseLoca2CountyKey:
    VALID_KEY = "loca2/ucb/netcdf/county/day/06115_pr_day_TaiESM1_ssp370_r1i1p1f1.nc"

    def test_valid_key(self):
        result = parse_loca2_county_key(self.VALID_KEY)
        assert result == {
            "county_code": "06115",
            "variable": "pr",
            "frequency": "day",
            "model": "TaiESM1",
            "scenario": "ssp370",
            "member_id": "r1i1p1f1",
            "key": self.VALID_KEY,
        }

    def test_wrong_extension(self):
        assert parse_loca2_county_key("loca2/ucb/netcdf/county/day/file.zarr") is None

    def test_too_few_filename_parts(self):
        assert (
            parse_loca2_county_key("loca2/ucb/netcdf/county/day/06115_pr_day.nc")
            is None
        )


class TestParseLoca2GriddedStore:
    PREFIX = "loca2/ucsd/access-cm2/historical/r1i1p1f1/day/tasmax/d03/"

    def test_fields(self):
        r = parse_loca2_gridded_store(self.PREFIX)
        assert r["source_id"] == "access-cm2"
        assert r["experiment_id"] == "historical"
        assert r["member_id"] == "r1i1p1f1"
        assert r["table_id"] == "day"
        assert r["variable_id"] == "tasmax"
        assert r["grid_label"] == "d03"

    def test_path_includes_bucket(self):
        assert (
            parse_loca2_gridded_store(self.PREFIX)["path"]
            == f"s3://cadcat/{self.PREFIX}"
        )


class TestParseRenStore:
    PREFIX = "era/pv_utility/ec-earth3/historical/1hr/cf/d03/"
    BASE = "era/pv_utility/"

    def test_fields(self):
        r = parse_ren_store(self.PREFIX, self.BASE)
        assert r["source_id"] == "ec-earth3"
        assert r["experiment_id"] == "historical"
        assert r["table_id"] == "1hr"
        assert r["variable_id"] == "cf"
        assert r["grid_label"] == "d03"

    def test_path_includes_ren_bucket(self):
        assert (
            parse_ren_store(self.PREFIX, self.BASE)["path"]
            == f"s3://wfclimres/{self.PREFIX}"
        )


VALID_STATIONS = {
    "sf",
    "lj",
    "la",
    "sb",
    "sl",
    "my",
    "pa",
    "hb",
    "cc",
    "pc",
    "al",
    "rc",
    "ri",
}


class TestParseHmetKey:
    def test_valid_key(self):
        key = "hmet/watlev.sf.low.50pctile.ssp245.wv2.nc"
        assert parse_hmet_key(key, VALID_STATIONS) == {
            "station_code": "sf",
            "slr_scenario": "low",
            "experiment_id": "ssp245",
        }

    def test_wrong_extension(self):
        assert (
            parse_hmet_key("hmet/watlev.sf.low.50pctile.ssp245.wv2.csv", VALID_STATIONS)
            is None
        )

    def test_wrong_prefix_word(self):
        assert (
            parse_hmet_key("hmet/other.sf.low.50pctile.ssp245.wv2.nc", VALID_STATIONS)
            is None
        )

    def test_unknown_station(self):
        assert (
            parse_hmet_key("hmet/watlev.zz.low.50pctile.ssp245.wv2.nc", VALID_STATIONS)
            is None
        )

    def test_unknown_slr_scenario(self):
        assert (
            parse_hmet_key(
                "hmet/watlev.sf.medium.50pctile.ssp245.wv2.nc", VALID_STATIONS
            )
            is None
        )

    def test_all_slr_scenarios_recognized(self):
        for abbrev in SLR_SCENARIO_LABELS:
            key = f"hmet/watlev.sf.{abbrev}.50pctile.ssp245.wv2.nc"
            assert parse_hmet_key(key, VALID_STATIONS) is not None


class TestParseWrfCaeStore:
    PREFIX = "wrf/cae/ec-earth3/historical/1hr/ffwi/d03/"

    def test_fields(self):
        r = parse_wrf_cae_store(self.PREFIX)
        assert r["source_id"] == "ec-earth3"
        assert r["experiment_id"] == "historical"
        assert r["table_id"] == "1hr"
        assert r["variable_id"] == "ffwi"
        assert r["grid_label"] == "d03"

    def test_path(self):
        assert parse_wrf_cae_store(self.PREFIX)["path"] == f"s3://cadcat/{self.PREFIX}"


class TestParseWrfUclaStore:
    PREFIX = "wrf/ucla/cesm2/historical/1hr/lwdnb/d03/"

    def test_fields(self):
        r = parse_wrf_ucla_store(self.PREFIX)
        assert r["source_id"] == "cesm2"
        assert r["experiment_id"] == "historical"
        assert r["table_id"] == "1hr"
        assert r["variable_id"] == "lwdnb"
        assert r["grid_label"] == "d03"

    def test_path(self):
        assert parse_wrf_ucla_store(self.PREFIX)["path"] == f"s3://cadcat/{self.PREFIX}"
