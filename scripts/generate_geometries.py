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

from scripts.constants import CA_COUNTY_FIPS

NAME_TO_FIPS = {v: k for k, v in CA_COUNTY_FIPS.items()}

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
        fips = NAME_TO_FIPS.get(county_name)
        features.append(
            {
                "type": "Feature",
                "bbox": list(row.geometry.bounds),  # [west, south, east, north]
                "geometry": row.geometry.__geo_interface__,
                "properties": {"county_name": county_name, "fips": fips},
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
                "properties": {"location": location, "station_name": row["station"]},
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
                "properties": {"era_id": row["era-id"], "network": row["network"]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def generate_sea_level_stations():
    """
    Return NOAA tide gauge station coordinates for sea level projection sites
    as a GeoJSON FeatureCollection.

    Coordinates are from NOAA Tides and Currents (tidesandcurrents.noaa.gov).
    Each feature is a Point with station_code and station_name properties.
    """
    stations = [
        {
            "code": "lj",
            "name": "La Jolla",
            "noaa_id": "9410230",
            "lon": -117.2571,
            "lat": 32.8669,
        },
        {
            "code": "la",
            "name": "Los Angeles",
            "noaa_id": "9410660",
            "lon": -118.2720,
            "lat": 33.7200,
        },
        {
            "code": "sb",
            "name": "Santa Barbara",
            "noaa_id": "9411340",
            "lon": -119.6925,
            "lat": 34.4046,
        },
        {
            "code": "sl",
            "name": "San Luis",
            "noaa_id": "9412110",
            "lon": -120.7542,
            "lat": 35.1689,
        },
        {
            "code": "my",
            "name": "Monterey",
            "noaa_id": "9413450",
            "lon": -121.8914,
            "lat": 36.6089,
        },
        {
            "code": "sf",
            "name": "San Francisco",
            "noaa_id": "9414290",
            "lon": -122.4659,
            "lat": 37.8063,
        },
        {
            "code": "pa",
            "name": "Point Arena",
            "noaa_id": "9416841",
            "lon": -123.7111,
            "lat": 38.9146,
        },
        {
            "code": "hb",
            "name": "Humboldt Bay",
            "noaa_id": "9418767",
            "lon": -124.2173,
            "lat": 40.7669,
        },
        {
            "code": "cc",
            "name": "Crescent City",
            "noaa_id": "9419750",
            "lon": -124.1844,
            "lat": 41.7456,
        },
        {
            "code": "pc",
            "name": "Port Chicago",
            "noaa_id": "9415144",
            "lon": -122.0395,
            "lat": 38.0560,
        },
        {
            "code": "al",
            "name": "Alameda",
            "noaa_id": "9414750",
            "lon": -122.3003,
            "lat": 37.7720,
        },
        {
            "code": "rc",
            "name": "Redwood City",
            "noaa_id": "9414523",
            "lon": -122.2119,
            "lat": 37.5068,
        },
        {
            "code": "ri",
            "name": "Richmond",
            "noaa_id": "9414849",
            "lon": -122.3580,
            "lat": 37.9100,
        },
    ]
    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            "properties": {
                "station_code": s["code"],
                "station_name": s["name"],
                "noaa_id": s["noaa_id"],
            },
        }
        for s in stations
    ]
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

    sea_level = generate_sea_level_stations()
    path = DATA_DIR / "sea-level-station-coords.geojson"
    with open(path, "w") as f:
        json.dump(sea_level, f)
    print(f"  Wrote {len(sea_level['features'])} stations to {path}")


if __name__ == "__main__":
    main()
