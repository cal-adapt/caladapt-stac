"""utils.py

Shared utilities for building and ingesting STAC items from S3.

"""

import boto3
import pystac
from datetime import datetime, timezone

s3 = boto3.client("s3")


def bbox_to_geometry(bbox):
    """
    Convert a [west, south, east, north] bbox to a GeoJSON Polygon dict.
    """
    west, south, east, north = bbox
    return {
        "type": "Polygon",
        "coordinates": [
            [[west, south], [east, south], [east, north], [west, north], [west, south]]
        ],
    }


def list_zarr_stores(prefix, bucket, depth):
    """
    List Zarr store paths at a fixed directory depth using delimiter-based listing.

    Much faster than list_keys for Zarr data — navigates S3 "directories" level
    by level without listing individual chunk files.

    Parameters
    ----------
    prefix : str
        S3 prefix to start from, e.g. "wrf/" or "loca2/ucsd/".
    bucket : str
        S3 bucket name.
    depth : int
        Number of directory levels to descend before yielding paths.

    Yields
    ------
    str
        S3 prefix for each Zarr store, e.g. "wrf/ucla/cesm2/historical/1hr/pr/d03/".
    """
    if depth == 0:
        yield prefix
        return
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
        for cp in page.get("CommonPrefixes", []):
            yield from list_zarr_stores(cp["Prefix"], bucket, depth - 1)


def list_keys(prefix, bucket):
    """
    List all S3 keys under a prefix, yielding (key, size) tuples.

    Parameters
    ----------
    prefix : str
        S3 prefix to list.
    bucket : str
        S3 bucket name.

    Yields
    ------
    tuple[str, int]
        (S3 object key, file size in bytes)
    """
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj["Key"], obj["Size"]


def load_direct(collection, dsn):
    """Load a collection and its items directly into pgSTAC via pypgstac bulk loader.

    Much faster than post_items for large datasets — bypasses HTTP entirely and
    uses SQL COPY to insert items in bulk.

    Parameters
    ----------
    collection : pystac.Collection
    dsn : str
        PostgreSQL DSN, e.g. postgresql://user:pass@host:5432/db?sslmode=require
    """
    from pypgstac.db import PgstacDB
    from pypgstac.load import Loader, Methods

    collection_dict = collection.to_dict()
    collection_dict["links"] = [
        l for l in collection_dict.get("links", []) if l.get("href")
    ]
    collection_dict["features"] = []

    items = list(collection.get_items())
    print(f"  Loading {len(items)} items directly into pgSTAC...")

    def _iter_items():
        for item in items:
            d = item.to_dict()
            if "links" in d:
                d["links"] = [l for l in d["links"] if l.get("href") is not None]
            yield d

    with PgstacDB(dsn=dsn) as db:
        loader = Loader(db=db)
        loader.load_collections(iter([collection_dict]), insert_mode=Methods.upsert)
        loader.load_items(_iter_items(), insert_mode=Methods.upsert)
        db.run_queued()

    print(f"  Done — {len(items)} items loaded.")


def build_item(
    item_id,
    props,
    href,
    bucket,
    media_type,
    geometry=None,
    bbox=None,
    item_datetime=None,
    asset_key="data",
    file_size=None,
):
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
    if file_size is not None:
        props["file:size"] = file_size

    item = pystac.Item(
        id=item_id,
        geometry=geometry,
        bbox=bbox,
        datetime=item_datetime or datetime.now(timezone.utc),
        properties=props,
    )
    item.add_asset(
        asset_key,
        pystac.Asset(href=f"s3://{bucket}/{href}", media_type=media_type),
    )
    return item
