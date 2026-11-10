"""Tests for the API routes that don't need a database."""

from app.main import COLLECTION_QUERYABLES, app
from tests.test_collections import SPATIAL_TYPES


def test_collection_queryables_route_comes_before_collection_route():
    # Otherwise /collections/queryables is read as a collection called "queryables"
    paths = [route.path for route in app.router.routes]
    assert paths.index("/collections/queryables") < paths.index(
        "/collections/{collection_id}"
    )


def test_queryables_list_every_spatial_type():
    spatial_type = COLLECTION_QUERYABLES["properties"]["caladapt:spatial_type"]
    assert set(spatial_type["enum"]) == SPATIAL_TYPES
