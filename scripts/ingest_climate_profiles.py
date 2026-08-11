"""ingest_climate_profiles.py

Ingest TMY, SMY, and XMY (persist/shock) climate profile collections into
pgSTAC by building pystac items from S3 keys and POSTing them to the STAC API.

Workflow:
1. Parse S3 keys under the TMY, SMY, and XMY prefixes into pystac items
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

import re

import pystac
import requests
from datetime import datetime, timezone
from pystac.extensions.scientific import ScientificExtension

from scripts.constants import (
    BUCKET_CADCAT,
    CA_BBOX,
    CALADAPT_DATA_LICENSE,
    CLIM_PROF_DOI,
    CLIM_PROF_GWL_PERIOD_DATES,
    HADISD_CA_STATION_COORDS_URL,
    ICON_BASE_URL,
    PGDSN,
    SMY_PREFIX,
    TMY_PREFIX,
    WRF_VARIABLE_LABELS,
    XMY_PERSIST_PREFIX,
    XMY_SHOCK_PREFIX,
)
from scripts.utils import build_item, list_keys, load_direct


def parse_tmy_key(key):
    """
    Parse TMY S3 key into item properties.

    Parameters
    ----------
    key : str
        S3 key, e.g. climate-profiles/typical-met-year/sacramento/taiesm1/mid-century/file.csv
        era5 has no GWL period dir, e.g.
        climate-profiles/typical-met-year/sacramento/era5/file.csv

    Returns
    -------
    dict or None
        Parsed properties, or None if key is not a CSV file.
    """
    if not key.endswith((".csv", ".epw")):
        return None
    parts = key.split("/")
    # parts: [climate-profiles, typical-met-year, location, model, time_period, filename]
    if parts[3] == "era5":
        return {"location": parts[2], "model": "era5", "time_period": "historical"}
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
        time-based periods (50ptile only) have a centered year in the filename
        instead of a named GWL period, e.g.
        climate-profiles/standard-met-year/sacramento/t2/50ptile/time-based/stdyr_t2_50ptile_sacramento_30yr_window_time_2015_ssp370.csv

    Returns
    -------
    dict or None
        Parsed properties, or None if key is not a CSV file, or a time-based
        key has no parseable centered year.
    """
    if not key.endswith(".csv"):
        return None
    parts = key.split("/")
    # parts: [climate-profiles, standard-met-year, location, variable, percentile, time_period, filename]
    # S3 folder names zero-pad the percentile (e.g. "05ptile"); strip the
    # leading zero so items read "5ptile" without touching the source data.
    percentile = re.sub(r"^0+(?=\d)", "", parts[4])
    props = {
        "location": parts[2],
        "variable": parts[3],
        "percentile": percentile,
        "time_period": parts[5],
    }
    if props["time_period"] == "time-based":
        match = re.search(r"time_(\d{4})", parts[-1])
        if match is None:
            return None
        props["centered_year"] = int(match.group(1))
    return props


def parse_xmy_persist_key(key):
    """
    Parse XMY persistence S3 key into item properties.

    Parameters
    ----------
    key : str
        S3 key, e.g.
        climate-profiles/extreme-met-year-persist/sacramento/taiesm1/mid-century/95ptile/file.csv

    Returns
    -------
    dict or None
        Parsed properties, or None if key is not a CSV/EPW file.
    """
    if not key.endswith((".csv", ".epw")):
        return None
    parts = key.split("/")
    # parts: [climate-profiles, extreme-met-year-persist, location, model, time_period, percentile, filename]
    return {
        "location": parts[2],
        "model": parts[3],
        "time_period": parts[4],
        "percentile": parts[5],
    }


def parse_xmy_shock_key(key):
    """
    Parse XMY shock S3 key into item properties.

    Parameters
    ----------
    key : str
        S3 key, e.g.
        climate-profiles/extreme-met-year-shock/sacramento/taiesm1/mid-century/hot_shock_xmy_sacramento_wrf_taiesm1_r1i1p1f1_mid-century.csv

    Returns
    -------
    dict or None
        Parsed properties, or None if key is not a CSV/EPW file or the
        filename doesn't start with a recognized shock type.
    """
    if not key.endswith((".csv", ".epw")):
        return None
    parts = key.split("/")
    filename = parts[-1]
    if filename.startswith("hot_shock"):
        shock_type = "hot"
    elif filename.startswith("cold_shock"):
        shock_type = "cold"
    else:
        return None
    # parts: [climate-profiles, extreme-met-year-shock, location, model, time_period, filename]
    return {
        "location": parts[2],
        "model": parts[3],
        "time_period": parts[4],
        "shock_type": shock_type,
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
        keywords=[
            "climate profiles",
            "global warming levels",
            "climate models",
            "future projections",
            "CMIP6",
            "building standards",
            "energy efficiency",
        ],
        extra_fields={"caladapt:spatial_type": "point"},
        description="Typical Meteorological Year climate profiles (8760) generated with dynamically-downscaled (WRF) global climate models at weather station locations for 50th percentile (p50) and 4 warming level planning horizons. A climate profile represents every hour of a 1-year period (e.g., 8760 hours). TMY profiles are in the time zone of the selected station.",
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
    ScientificExtension.ext(collection, add_if_missing=True).doi = CLIM_PROF_DOI

    station_coords, station_names = get_station_data()
    station_labels = {}
    for key, size in list_keys(TMY_PREFIX, BUCKET_CADCAT):
        props = parse_tmy_key(key)
        if props is None:
            continue
        ext = "epw" if key.endswith(".epw") else "csv"
        media_type = "application/octet-stream" if ext == "epw" else "text/csv"
        item_id = (
            f"tmy-{props['location']}-era5-{ext}"
            if props["model"] == "era5"
            else f"tmy-{props['location']}-{props['model']}-{props['time_period']}-{ext}"
        )

        station_labels[props["location"]] = station_names.get(props["location"], props["location"])

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

    collection.extra_fields["caladapt:station_labels"] = station_labels
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
        keywords=[
            "climate profiles",
            "global warming levels",
            "climate models",
            "future projections",
            "CMIP6",
        ],
        extra_fields={"caladapt:spatial_type": "point"},
        description="Standard Year climate profiles (8760) generated with dynamically downscaled (WRF) global climate models at weather station locations for 50th, 5th, and 95th percentiles and 4 warming level planning horizons. A climate profile represents every hour of a 1-year period (e.g., 8760 hours). Standard Year profiles are in the time zone of the selected station.",
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
    ScientificExtension.ext(collection, add_if_missing=True).doi = CLIM_PROF_DOI

    station_coords, station_names = get_station_data()
    station_labels = {}
    variable_labels = {}
    for key, size in list_keys(SMY_PREFIX, BUCKET_CADCAT):
        props = parse_smy_key(key)
        if props is None:
            continue
        if props["time_period"] == "time-based":
            item_id = f"smy-{props['location']}-{props['variable']}-{props['percentile']}-time-{props['centered_year']}"
            centered_year = props["centered_year"]
            start = datetime(centered_year - 15, 1, 1, tzinfo=timezone.utc)
            end = datetime(centered_year + 15, 12, 31, tzinfo=timezone.utc)
        else:
            item_id = f"smy-{props['location']}-{props['variable']}-{props['percentile']}-{props['time_period']}"
            start, end = CLIM_PROF_GWL_PERIOD_DATES[props["time_period"]]
        props["start_datetime"] = start.isoformat()
        props["end_datetime"] = end.isoformat()

        station_labels[props["location"]] = station_names.get(props["location"], props["location"])
        variable_labels[props["variable"]] = WRF_VARIABLE_LABELS.get(
            props["variable"], props["variable"]
        )

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

    collection.extra_fields["caladapt:variable_labels"] = variable_labels
    collection.extra_fields["caladapt:station_labels"] = station_labels
    return collection


def build_xmy_persist_collection():
    """
    Build pystac Collection for XMY persistence profiles.

    Returns
    -------
    pystac.Collection
        Collection containing one item per XMY persistence CSV/EPW file in S3.
    """
    collection = pystac.Collection(
        id="xmy-persist",
        title="Extreme Year (Persistence)",
        keywords=[
            "climate profiles",
            "global warming levels",
            "climate models",
            "future projections",
            "CMIP6",
            "extreme events",
        ],
        extra_fields={"caladapt:spatial_type": "point"},
        description="Extreme Meteorological Year (XMY) persistence climate profiles (8760) generated with dynamically-downscaled (WRF) global climate models at weather station locations, representing sustained extremes at 5th, 10th, 40th, 60th, 90th, and 95th percentiles across 4 warming level planning horizons. A climate profile represents every hour of a 1-year period (e.g., 8760 hours). XMY persistence profiles are in the time zone of the selected station.",
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
            href=f"{ICON_BASE_URL}xmy_persist_icon.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="XMY persistence preview",
        ),
    )
    ScientificExtension.ext(collection, add_if_missing=True).doi = CLIM_PROF_DOI

    station_coords, station_names = get_station_data()
    station_labels = {}
    for key, size in list_keys(XMY_PERSIST_PREFIX, BUCKET_CADCAT):
        props = parse_xmy_persist_key(key)
        if props is None:
            continue
        ext = "epw" if key.endswith(".epw") else "csv"
        media_type = "application/octet-stream" if ext == "epw" else "text/csv"
        item_id = f"xmy-persist-{props['location']}-{props['model']}-{props['time_period']}-{props['percentile']}-{ext}"

        station_labels[props["location"]] = station_names.get(props["location"], props["location"])

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

    collection.extra_fields["caladapt:station_labels"] = station_labels
    return collection


def build_xmy_shock_collection():
    """
    Build pystac Collection for XMY shock profiles.

    Returns
    -------
    pystac.Collection
        Collection containing one item per XMY shock CSV/EPW file in S3.
    """
    collection = pystac.Collection(
        id="xmy-shock",
        title="Extreme Year (Shock)",
        keywords=[
            "climate profiles",
            "global warming levels",
            "climate models",
            "future projections",
            "CMIP6",
            "extreme events",
        ],
        extra_fields={"caladapt:spatial_type": "point"},
        description="Extreme Meteorological Year (XMY) shock climate profiles (8760) generated with dynamically-downscaled (WRF) global climate models at weather station locations, representing short-duration hot and cold shock extremes across 4 warming level planning horizons. A climate profile represents every hour of a 1-year period (e.g., 8760 hours). XMY shock profiles are in the time zone of the selected station.",
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
            href=f"{ICON_BASE_URL}xmy_shock_icon.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="XMY shock preview",
        ),
    )
    ScientificExtension.ext(collection, add_if_missing=True).doi = CLIM_PROF_DOI

    station_coords, station_names = get_station_data()
    station_labels = {}
    for key, size in list_keys(XMY_SHOCK_PREFIX, BUCKET_CADCAT):
        props = parse_xmy_shock_key(key)
        if props is None:
            continue
        ext = "epw" if key.endswith(".epw") else "csv"
        media_type = "application/octet-stream" if ext == "epw" else "text/csv"
        item_id = f"xmy-shock-{props['location']}-{props['model']}-{props['time_period']}-{props['shock_type']}-{ext}"

        station_labels[props["location"]] = station_names.get(props["location"], props["location"])

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

    collection.extra_fields["caladapt:station_labels"] = station_labels
    return collection


def get_station_data():
    """
    Load HadISD station coordinates and names from S3.

    Returns
    -------
    tuple[dict, dict]
        coords: location -> [lon, lat]
        names: location -> readable station name
    """
    fc = requests.get(HADISD_CA_STATION_COORDS_URL).json()
    coords = {}
    names = {}
    for feature in fc["features"]:
        loc = feature["properties"]["location"]
        coords[loc] = feature["geometry"]["coordinates"]
        names[loc] = feature["properties"].get("station_name", loc)
    return coords, names


def main():
    print("  Building TMY collection...")
    tmy_collection = build_tmy_collection()
    print("  Loading TMY directly into pgSTAC...")
    load_direct(tmy_collection, PGDSN)

    print("  Building SMY collection...")
    smy_collection = build_smy_collection()
    print("  Loading SMY directly into pgSTAC...")
    load_direct(smy_collection, PGDSN)

    print("  Building XMY persist collection...")
    xmy_persist_collection = build_xmy_persist_collection()
    print("  Loading XMY persist directly into pgSTAC...")
    load_direct(xmy_persist_collection, PGDSN)

    print("  Building XMY shock collection...")
    xmy_shock_collection = build_xmy_shock_collection()
    print("  Loading XMY shock directly into pgSTAC...")
    load_direct(xmy_shock_collection, PGDSN)


if __name__ == "__main__":
    main()
