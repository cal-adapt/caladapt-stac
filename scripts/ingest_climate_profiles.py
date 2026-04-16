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
import requests
from datetime import datetime, timezone
from pystac.extensions.scientific import ScientificExtension

from scripts.constants import (
    BUCKET_CADCAT,
    CA_BBOX,
    CALADAPT_DATA_LICENSE,
    CLIM_PROF_GWL_PERIOD_DATES,
    HADISD_CA_STATION_COORDS_URL,
    ICON_BASE_URL,
    PGDSN,
    SMY_PREFIX,
    TMY_PREFIX,
    WRF_VARIABLE_LABELS,
)
from scripts.utils import build_item, list_keys, load_direct


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
        id="typical-met-year",
        title="Typical meteorological year",
        keywords=["climate profiles"],
        extra_fields={"caladapt:spatial_type": "point"},
        description="Typical Meteorological Year climate profiles (8760) at weather station locations for p50 warming level planning horizons.",
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Cal-Adapt",
                roles=[
                    pystac.ProviderRole.HOST,
                    pystac.ProviderRole.PRODUCER,
                ],
                url="https://cal-adapt.org/",
            )
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[CA_BBOX]),  # CA spatial extent
            temporal=pystac.TemporalExtent(
                intervals=[
                    [
                        datetime(1980, 1, 1, tzinfo=timezone.utc),
                        datetime(2100, 12, 31, tzinfo=timezone.utc),
                    ]
                ]
            ),  # WRF time extent
        ),
    )
    collection.add_asset(
        "item-geometries",
        pystac.Asset(
            href=HADISD_CA_STATION_COORDS_URL,
            media_type="application/geo+json",
            roles=["item-geometries"],
            title="Item geometries",
        ),
    )
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}tmy_icon.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="TMY preview",
        ),
    )
    ScientificExtension.ext(collection, add_if_missing=True).doi = (
        "10.5281/zenodo.18135273"
    )

    station_coords = get_station_coords()
    for key, size in list_keys(TMY_PREFIX, BUCKET_CADCAT):
        props = parse_tmy_key(key)
        if props is None:
            continue
        ext = "epw" if key.endswith(".epw") else "csv"
        media_type = "application/octet-stream" if ext == "epw" else "text/csv"
        item_id = (
            f"tmy-{props['location']}-{props['model']}-{props['time_period']}-{ext}"
        )

        # Get the time period from the profiles lookup table
        start, end = CLIM_PROF_GWL_PERIOD_DATES[props["time_period"]]
        props["start_datetime"] = start.isoformat()
        props["end_datetime"] = end.isoformat()

        lon, lat = station_coords[props["location"]]
        props["lat"] = lat
        props["lon"] = lon
        geometry = {"type": "Point", "coordinates": [lon, lat]}
        bbox = [lon, lat, lon, lat]

        item = build_item(
            item_id,
            props,
            key,
            BUCKET_CADCAT,
            media_type,
            geometry=geometry,
            bbox=bbox,
            item_datetime=start,
            asset_key=ext,
            file_size=size,
        )
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
        id="standard-year",
        title="Standard year",
        keywords=["climate profiles"],
        extra_fields={"caladapt:spatial_type": "point"},
        description="Standard Year climate profiles (8760) at weather station locations for p50, p5, p95 warming level planning horizons.",
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Cal-Adapt",
                roles=[
                    pystac.ProviderRole.HOST,
                    pystac.ProviderRole.PRODUCER,
                ],
                url="https://cal-adapt.org/",
            )
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[CA_BBOX]),  # CA spatial extent
            temporal=pystac.TemporalExtent(
                intervals=[
                    [
                        datetime(1980, 1, 1, tzinfo=timezone.utc),
                        datetime(2100, 12, 31, tzinfo=timezone.utc),
                    ]
                ]
            ),  # WRF time extent
        ),
    )
    collection.add_asset(
        "item-geometries",
        pystac.Asset(
            href=HADISD_CA_STATION_COORDS_URL,
            media_type="application/geo+json",
            roles=["item-geometries"],
            title="Item geometries",
        ),
    )
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}standard_year_icon.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="SMY preview",
        ),
    )
    ScientificExtension.ext(collection, add_if_missing=True).doi = (
        "10.5281/zenodo.18135273"
    )

    station_coords = get_station_coords()
    for key, size in list_keys(SMY_PREFIX, BUCKET_CADCAT):
        props = parse_smy_key(key)
        if props is None:
            continue
        item_id = f"smy-{props['location']}-{props['variable']}-{props['percentile']}-{props['time_period']}"

        # Get the time period from the profiles lookup table
        start, end = CLIM_PROF_GWL_PERIOD_DATES[props["time_period"]]
        props["start_datetime"] = start.isoformat()
        props["end_datetime"] = end.isoformat()
        props["variable_label"] = WRF_VARIABLE_LABELS.get(props["variable"], props["variable"])

        lon, lat = station_coords[props["location"]]
        props["lat"] = lat
        props["lon"] = lon
        geometry = {"type": "Point", "coordinates": [lon, lat]}
        bbox = [lon, lat, lon, lat]

        item = build_item(
            item_id,
            props,
            key,
            BUCKET_CADCAT,
            "text/csv",
            geometry=geometry,
            bbox=bbox,
            item_datetime=start,
            file_size=size,
        )
        collection.add_item(item)
    return collection


def get_station_coords():
    """
    Load HadISD station coordinates from S3.

    Returns
    -------
    dict
        Mapping of location name (e.g. "sacramento") to [lon, lat].
    """
    fc = requests.get(HADISD_CA_STATION_COORDS_URL).json()
    return {
        feature["properties"]["location"]: feature["geometry"]["coordinates"]
        for feature in fc["features"]
    }


def main():
    print("  Building TMY collection...")
    tmy_collection = build_tmy_collection()
    print("  Loading TMY directly into pgSTAC...")
    load_direct(tmy_collection, PGDSN)

    print("  Building SMY collection...")
    smy_collection = build_smy_collection()
    print("  Loading SMY directly into pgSTAC...")
    load_direct(smy_collection, PGDSN)


if __name__ == "__main__":
    main()
