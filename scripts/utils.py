"""utils.py

Shared utilities for building and ingesting STAC items from S3.

"""

import boto3
import pystac
import requests
from datetime import datetime, timezone

s3 = boto3.client("s3")

def post_or_put(url: str, data: dict):
    """Post or put data to url."""
    # pystac generates links with null hrefs when items are added to a collection;
    # the API rejects these, so strip them before posting
    if "links" in data:
        data["links"] = [l for l in data["links"] if l.get("href") is not None]
    res = requests.post(url, json=data, timeout=500)
    if res.status_code == 409:
        new_url = url + f"/{data['id']}"
        # Exists, so update
        res = requests.put(new_url, json=data, timeout=500)
        # Unchanged may throw a 404
        if not res.status_code == 404:
            if not res.ok:
                raise Exception(f"PUT {new_url} failed {res.status_code}: {res.text}")
    elif not res.ok:
        raise Exception(f"POST {url} failed {res.status_code}: {res.text}")
    else:
        res.raise_for_status()


def list_keys(prefix, bucket):
    """
    List all S3 keys under a prefix.

    Parameters
    ----------
    prefix : str
        S3 prefix to list.
    bucket : str
        S3 bucket name.

    Yields
    ------
    str
        S3 object key.
    """
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj["Key"]


def build_item(item_id, props, href, bucket, media_type, geometry=None, bbox=None, item_datetime=None):
    """
    Build a pystac Item.

    Parameters
    ----------
    item_id : str
        Unique item ID.
    props : dict
        Item properties.
    href : str
        S3 key for the asset.
    bucket : str
        S3 bucket name.
    media_type : str
        Media type of the asset (e.g. "text/csv", "application/octet-stream",
        "application/netcdf", "application/vnd+zarr").
    geometry : dict, optional
        GeoJSON geometry. Defaults to None for point/station-based data.
    bbox : list, optional
        Bounding box [west, south, east, north]. Defaults to None.
    item_datetime : datetime or None, optional
        Item datetime. Defaults to current UTC time if not provided. Pass None
        explicitly when start_datetime/end_datetime are set in props instead.

    Returns
    -------
    pystac.Item
    """
    item = pystac.Item(
        id=item_id,
        geometry=geometry,
        bbox=bbox,
        datetime=item_datetime or datetime.now(timezone.utc),
        properties=props,
    )
    item.add_asset(
        "data",
        pystac.Asset(href=f"s3://{bucket}/{href}", media_type=media_type),
    )
    return item
