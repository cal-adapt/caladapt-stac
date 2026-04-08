"""generate_geometries.py

Generate GeoJSON geometry files for STAC collection assets.

Reads California county boundaries from S3 parquet and HadISD station
coordinates from S3 CSV, then writes GeoJSON files to data/geometries/.

These files are:
- Committed to the repo for use by ingestion scripts (geometry lookups)
- Manually uploaded to s3://cadcat/geometries/ for use as collection assets

Usage:
    uv run python -m scripts.generate_geometries

Requires:
    - AWS credentials with read access to the cadcat S3 bucket (for parquet)
"""

import json
import struct
from pathlib import Path

import boto3
import geopandas as gpd
import pandas as pd

s3 = boto3.client("s3")

DATA_DIR = Path(__file__).parent.parent / "data" / "geometries"

CA_COUNTIES_URL = "s3://cadcat/parquet/ca_counties.parquet"
HADISD_STATIONS_URL = "https://cadcat.s3.amazonaws.com/hadisd/hadisd_stations.csv"
HDP_STATIONS_CSV_URL = (
    "https://cadcat.s3.amazonaws.com/histwxstns/historical_wx_stations.csv"
)


def generate_ca_counties():
    """
    Load CA county geometries from S3 parquet and return as a GeoJSON FeatureCollection.

    Each feature includes a bbox and county_name property (without "County" suffix).
    """
    print("  Loading CA county geometries from S3...")
    gdf = gpd.read_parquet(CA_COUNTIES_URL)
    features = []
    for _, row in gdf.iterrows():
        county_name = row["NAME"].replace(" County", "")
        features.append(
            {
                "type": "Feature",
                "bbox": list(row.geometry.bounds),  # [west, south, east, north]
                "geometry": row.geometry.__geo_interface__,
                "properties": {"county_name": county_name},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def generate_hadisd_ca_stations():
    """
    Load CA HadISD station coordinates from S3 CSV and return as a GeoJSON FeatureCollection.

    These are the CA-only stations used by TMY/SMY climate profiles.
    Each feature is a Point with a location property matching the naming convention
    used in climate profile S3 keys (lowercase, spaces replaced with underscores,
    punctuation removed).
    """
    print("  Loading CA HadISD station coordinates from S3 CSV...")
    df = pd.read_csv(HADISD_STATIONS_URL, index_col=[0])
    df["location"] = (
        df["station"]
        .str.replace(r"[^\w\s-]", "", regex=True)
        .str.lower()
        .str.replace(" ", "_")
    )
    features = []
    seen = set()
    for _, row in df.iterrows():
        location = row["location"]
        if location in seen:
            continue
        seen.add(location)
        lon, lat = float(row["LON_X"]), float(row["LAT_Y"])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"location": location},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def generate_hadisd_wecc_stations():
    """
    Load WECC-wide HadISD station coordinates from zarr stores in S3 and return as a GeoJSON FeatureCollection.

    Lists all HadISD_*.zarr stores, reads lat/lon scalar variables from each,
    and returns one Point feature per station with a station_id property.
    """
    print("  Listing HadISD zarr stores in S3...")
    paginator = s3.get_paginator("list_objects_v2")
    features = []
    for page in paginator.paginate(Bucket="cadcat", Prefix="hadisd/", Delimiter="/"):
        for cp in page.get("CommonPrefixes", []):
            store_prefix = cp["Prefix"]
            filename = store_prefix.rstrip("/").split("/")[-1]
            if not (filename.startswith("HadISD_") and filename.endswith(".zarr")):
                continue
            station_id = filename.removeprefix("HadISD_").removesuffix(".zarr")
            lat = struct.unpack(
                "<d",
                s3.get_object(Bucket="cadcat", Key=f"{store_prefix}latitude/0")[
                    "Body"
                ].read(),
            )[0]
            lon = struct.unpack(
                "<d",
                s3.get_object(Bucket="cadcat", Key=f"{store_prefix}longitude/0")[
                    "Body"
                ].read(),
            )[0]
            elev = struct.unpack(
                "<d",
                s3.get_object(Bucket="cadcat", Key=f"{store_prefix}elevation/0")[
                    "Body"
                ].read(),
            )[0]
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {"station_id": station_id, "elevation": elev},
                }
            )
    return {"type": "FeatureCollection", "features": features}


def generate_hdp_stations():
    """
    Load HDP weather station coordinates from S3 CSV and return as a GeoJSON FeatureCollection.

    Each feature is a Point with an era_id property uniquely identifying the station.
    """
    print("  Loading HDP station coordinates from S3...")
    df = pd.read_csv(HDP_STATIONS_CSV_URL)
    features = []
    for _, row in df.iterrows():
        lon, lat = float(row["longitude"]), float(row["latitude"])
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {"era_id": row["era-id"]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    counties = generate_ca_counties()
    path = DATA_DIR / "ca-counties-geometries.geojson"
    with open(path, "w") as f:
        json.dump(counties, f)
    print(f"  Wrote {len(counties['features'])} counties to {path}")

    ca_stations = generate_hadisd_ca_stations()
    path = DATA_DIR / "hadisd-ca-station-coords.geojson"
    with open(path, "w") as f:
        json.dump(ca_stations, f)
    print(f"  Wrote {len(ca_stations['features'])} CA stations to {path}")

    wecc_stations = generate_hadisd_wecc_stations()
    path = DATA_DIR / "hadisd-wecc-station-coords.geojson"
    with open(path, "w") as f:
        json.dump(wecc_stations, f)
    print(f"  Wrote {len(wecc_stations['features'])} WECC stations to {path}")

    hdp = generate_hdp_stations()
    path = DATA_DIR / "hdp-station-coords.geojson"
    with open(path, "w") as f:
        json.dump(hdp, f)
    print(f"  Wrote {len(hdp['features'])} stations to {path}")


if __name__ == "__main__":
    main()
