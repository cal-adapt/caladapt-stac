"""ingest_hdp.py

Ingest Historical Data Platform (HDP) weather station data into pgSTAC.

This collection contains cloud-optimized, standardized, and quality-controlled
historical weather station data for the U.S. Western Electricity Coordinating
Council (WECC) region, covering the period from 1980 to 2022. Methods documented
at https://github.com/Eagle-Rock-Analytics/historical-obs-platform.

Station data are stored as Zarr archives at s3://cadcat/histwxstns/{network}/{era_id}.
There are 27 networks totaling 14,927 stations.

Workflow:
1. Read station metadata from historical_wx_stations.csv in S3
2. Build one pystac Item per station with a Zarr asset
3. Load directly into pgSTAC

Usage:
    uv run python -m scripts.ingest_hdp

Requires:
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

import pandas as pd
import pystac
from datetime import datetime, timezone

from scripts.constants import BUCKET_CADCAT, HDP_PREFIX, PGDSN
from scripts.utils import load_direct

HDP_STATIONS_CSV_URL = f"https://{BUCKET_CADCAT}.s3.amazonaws.com/{HDP_PREFIX}historical_wx_stations.csv"


def build_hdp_collection():
    """
    Build a pystac Collection for HDP weather station Zarr data.

    Reads station metadata from historical_wx_stations.csv and builds
    one item per station.

    Returns
    -------
    pystac.Collection
        Collection containing one item per weather station.
    """
    collection = pystac.Collection(
        id="hdp",
        description=(
            "Cloud-optimized, standardized, and quality-controlled historical weather "
            "station data for the U.S. Western Electricity Coordinating Council (WECC) "
            "region, covering the period from 1980 to 2022. Methods documented at "
            "https://github.com/Eagle-Rock-Analytics/historical-obs-platform."
        ),
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[[-125.0, 25.0, -100.0, 52.0]]),
            temporal=pystac.TemporalExtent(
                intervals=[[
                    datetime(1980, 1, 1, tzinfo=timezone.utc),
                    datetime(2022, 12, 31, tzinfo=timezone.utc),
                ]]
            ),
        ),
    )

    df = pd.read_csv(HDP_STATIONS_CSV_URL, parse_dates=["start-date", "end-date"])

    for _, row in df.iterrows():
        era_id = row["era-id"]
        network = row["network"]
        lat, lon = float(row["latitude"]), float(row["longitude"])

        start = pd.Timestamp(row["start-date"]).to_pydatetime()
        end = pd.Timestamp(row["end-date"]).to_pydatetime()
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        props = {
            "era_id": era_id,
            "source_id": row["source-id"],
            "network": network,
            "state": row["state"],
            "elevation": float(row["elevation"]) if pd.notna(row["elevation"]) else None,
            "total_nobs": int(row["total_nobs"]) if pd.notna(row["total_nobs"]) else None,
            "start_datetime": start.isoformat(),
            "end_datetime": end.isoformat(),
        }

        item = pystac.Item(
            id=era_id,
            geometry={"type": "Point", "coordinates": [lon, lat]},
            bbox=[lon, lat, lon, lat],
            datetime=None,
            properties=props,
        )
        item.add_asset(
            "data",
            pystac.Asset(
                href=f"s3://{BUCKET_CADCAT}/{HDP_PREFIX}{network}/{era_id}",
                media_type="application/vnd+zarr",
            ),
        )
        collection.add_item(item)

    return collection


def main():
    print("  Building HDP collection...")
    collection = build_hdp_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
