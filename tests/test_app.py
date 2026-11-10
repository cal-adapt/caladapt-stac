"""Tests for the API routes that don't need a database."""

from app.main import SPATIAL_TYPES, app, collection_queryables
from tests.test_collections import SPATIAL_TYPES as COLLECTION_SPATIAL_TYPES


def test_collection_queryables_route_comes_before_collection_route():
    # Otherwise /collections/queryables is read as a collection called "queryables"
    paths = [route.path for route in app.router.routes]
    assert paths.index("/collections/queryables") < paths.index(
        "/collections/{collection_id}"
    )


def test_collection_queryables():
    schema = collection_queryables("https://stac.cal-adapt.org/")
    assert schema["$id"] == "https://stac.cal-adapt.org/collections/queryables"
    assert schema["properties"]["caladapt:spatial_type"]["enum"] == SPATIAL_TYPES


def test_queryables_list_every_spatial_type():
    # The ingest tests check each collection's type against this set
    assert set(SPATIAL_TYPES) == COLLECTION_SPATIAL_TYPES
