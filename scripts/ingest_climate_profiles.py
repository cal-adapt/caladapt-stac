"""ingest_climate_profiles.py

Ingest TMY and SMY climate profile collections into pgSTAC by building pystac
items from S3 keys and POSTing them to the STAC API.

Workflow:
1. Parse S3 keys under the TMY and SMY prefixes into pystac items
2. Build pystac Collections containing those items
3. POST each collection to the STAC API
4. POST each item individually to the STAC API

Each item represents a single climate profile file (CSV or EPW) in S3.

Usage:
    uv run python scripts/ingest_climate_profiles.py

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - A running STAC API at API_ENDPOINT (this can be a local endpoint 
    for testing, or a a deployed STAC API endpoint)

"""

import pystac
from datetime import datetime, timezone
from urllib.parse import urljoin

from scripts.constants import API_ENDPOINT, BUCKET_CADCAT, CA_BBOX, CA_GEOMETRY, SMY_PREFIX, TMY_PREFIX
from scripts.utils import build_item, list_keys, post_or_put

def parse_tmy_key(key):
    """
    Parse TMY S3 key into item properties.

    Parameters
    ----------
    key : str
        S3 key, e.g. climate-profiles/typical-met-year/sacramento/taiesm1/mid-century/file.csv

    Returns
    -------
    dict or None
        Parsed properties, or None if key is not a CSV file.
    """
    if not key.endswith((".csv", ".epw")):
        return None
    parts = key.split("/")
    # parts: [climate-profiles, typical-met-year, location, model, time_period, filename]
    return {
        "location": parts[2],
        "model": parts[3],
        "time_period": parts[4],
        "profile_type": "tmy",
    }


def parse_smy_key(key):
    """
    Parse SMY S3 key into item properties.

    Parameters
    ----------
    key : str
        S3 key, e.g. climate-profiles/standard-met-year/sacramento/tasmax/p95/mid-century/file.csv

    Returns
    -------
    dict or None
        Parsed properties, or None if key is not a CSV file.
    """
    if not key.endswith(".csv"):
        return None
    parts = key.split("/")
    # parts: [climate-profiles, standard-met-year, location, variable, percentile, time_period, filename]
    return {
        "location": parts[2],
        "variable": parts[3],
        "percentile": parts[4],
        "time_period": parts[5],
        "profile_type": "smy",
    }



def build_tmy_collection():
    """
    Build pystac Collection for TMY profiles.

    Returns
    -------
    pystac.Collection
        Collection containing one item per TMY CSV file in S3.
    """
    collection = pystac.Collection(
        id="climate-profiles-tmy",
        description="Typical Meteorological Year climate profiles",
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[[-124.4, 32.5, -114.1, 42.0]]), # CA spatial extent
            temporal=pystac.TemporalExtent(intervals=[[datetime(1980, 1, 1, tzinfo=timezone.utc), datetime(2100, 12, 31, tzinfo=timezone.utc)]]), # WRF time extent
        ),
    )
    for key in list_keys(TMY_PREFIX, BUCKET_CADCAT):
        props = parse_tmy_key(key)
        if props is None:
            continue
        ext = "epw" if key.endswith(".epw") else "csv"
        media_type = "application/octet-stream" if ext == "epw" else "text/csv"
        item_id = f"tmy-{props['location']}-{props['model']}-{props['time_period']}-{ext}"
        item = build_item(item_id, props, key, BUCKET_CADCAT, media_type, geometry=CA_GEOMETRY, bbox=CA_BBOX)
        collection.add_item(item)
    return collection


def build_smy_collection():
    """
    Build pystac Collection for SMY profiles.

    Returns
    -------
    pystac.Collection
        Collection containing one item per SMY CSV file in S3.
    """
    collection = pystac.Collection(
        id="climate-profiles-smy",
        description="Standard Meteorological Year climate profiles",
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[[-124.4, 32.5, -114.1, 42.0]]), # CA spatial extent
            temporal=pystac.TemporalExtent(intervals=[[datetime(1980, 1, 1, tzinfo=timezone.utc), datetime(2100, 12, 31, tzinfo=timezone.utc)]]), # WRF time extent
        ),
    )
    for key in list_keys(SMY_PREFIX, BUCKET_CADCAT):
        props = parse_smy_key(key)
        if props is None:
            continue
        item_id = f"smy-{props['location']}-{props['variable']}-{props['percentile']}-{props['time_period']}"
        item = build_item(item_id, props, key, BUCKET_CADCAT, "text/csv", geometry=CA_GEOMETRY, bbox=CA_BBOX)
        collection.add_item(item)
    return collection

def main(): 

    # Parse thru s3 catalog and build pystac items for each TMY and SMY profile
    # Returns a psytac collection object for each profile type, which we can then POST to the API
    tmy_collection = build_tmy_collection()
    smy_collection = build_smy_collection() 

    # POST collections to API
    post_or_put(urljoin(API_ENDPOINT, "/collections"), tmy_collection.to_dict())
    post_or_put(urljoin(API_ENDPOINT, "/collections"), smy_collection.to_dict())

    # POST items from each collection to API individually
    # Each item is a pystac Item representing a single climate profile CSV or EPW file in S3
    # By calling item.to_dict(), we convert the pystac Item to a dict that can be JSON-serialized and sent in the POST request body
    for item in tmy_collection.get_items():
        post_or_put(urljoin(API_ENDPOINT, f"/collections/{tmy_collection.id}/items"), item.to_dict())
    for item in smy_collection.get_items():
        post_or_put(urljoin(API_ENDPOINT, f"/collections/{smy_collection.id}/items"), item.to_dict())

if __name__ == "__main__":
    main()