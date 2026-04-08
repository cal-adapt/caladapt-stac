"""ingest_hadisd.py

Ingest HadISD station Zarr data into pgSTAC.

HadISD.3.3.1.202312p data obtained from the Met Office Hadley Centre.
One item per station with a point geometry.

Workflow:
1. Read station coordinates from hadisd-wecc-station-coords.geojson
2. Build one pystac Item per station
3. Load directly into pgSTAC

S3 path structure:
    hadisd/HadISD_{station_id}.zarr

Usage:
    uv run python -m scripts.ingest_hadisd

Requires:
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

import requests
import pystac

from scripts.constants import (
    BUCKET_CADCAT,
    HADISD_PREFIX,
    HADISD_WECC_STATION_COORDS_URL,
    PGDSN,
)
from scripts.utils import load_direct

HADISD_LICENSE = "Non-Commercial-Government-Licence-v2.0"
HADISD_LICENSE_URL = "https://www.nationalarchives.gov.uk/doc/non-commercial-government-licence/version/2/"

# HadISD version and date range (v3.3.1.202312p covers 1931–2023)
HADISD_VERSION = "3.3.1.202312p"
HADISD_START = datetime(1931, 1, 1, tzinfo=timezone.utc)
HADISD_END = datetime(2023, 12, 31, tzinfo=timezone.utc)


def build_hadisd_collection():
    """
    Build a pystac Collection for HadISD station Zarr data.

    Reads station coordinates from hadisd-wecc-station-coords.geojson and builds
    one item per station with a point geometry.

    Returns
    -------
    pystac.Collection
        Collection containing one item per HadISD station.
    """
    fc = requests.get(HADISD_WECC_STATION_COORDS_URL).json()
    features = fc["features"]

    lons = [f["geometry"]["coordinates"][0] for f in features]
    lats = [f["geometry"]["coordinates"][1] for f in features]
    bbox = [min(lons), min(lats), max(lons), max(lats)]

    collection = pystac.Collection(
        id="hadisd-station-zarrs",
        title="HadISD (zarr)",
        description=("Met Office HadISD sub-daily station data for the WECC region."),
        license=HADISD_LICENSE,
        providers=[
            pystac.Provider(
                name="Met Office Hadley Centre",
                roles=[pystac.ProviderRole.PRODUCER],
                url="https://www.metoffice.gov.uk/hadobs/hadisd/",
            ),
            pystac.Provider(
                name="Cal-Adapt",
                roles=[pystac.ProviderRole.HOST],
                url="https://cal-adapt.org/",
            ),
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[bbox]),
            temporal=pystac.TemporalExtent(intervals=[[HADISD_START, HADISD_END]]),
        ),
    )
    collection.add_link(pystac.Link(rel="license", target=HADISD_LICENSE_URL))
    collection.add_asset(
        "item-geometries",
        pystac.Asset(
            href=HADISD_WECC_STATION_COORDS_URL,
            media_type="application/geo+json",
            roles=["item-geometries"],
            title="Item geometries",
        ),
    )

    for feature in features:
        props_in = feature["properties"]
        station_id = props_in["station_id"]
        lon, lat = feature["geometry"]["coordinates"]

        item = pystac.Item(
            id=f"hadisd-{station_id}",
            geometry={"type": "Point", "coordinates": [lon, lat]},
            bbox=[lon, lat, lon, lat],
            datetime=None,
            properties={
                "station_id": station_id,
                "elevation": props_in.get("elevation"),
                "version": HADISD_VERSION,
                "start_datetime": HADISD_START.isoformat(),
                "end_datetime": HADISD_END.isoformat(),
            },
        )
        item.add_asset(
            "data",
            pystac.Asset(
                href=f"s3://{BUCKET_CADCAT}/{HADISD_PREFIX}HadISD_{station_id}.zarr",
                media_type="application/vnd+zarr",
            ),
        )
        collection.add_item(item)

    return collection


def main():
    print("  Building HadISD collection...")
    collection = build_hadisd_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
