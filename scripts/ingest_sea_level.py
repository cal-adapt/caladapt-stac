"""ingest_sea_level.py

Ingest hourly sea level projection NetCDF files into pgSTAC.

Workflow:
1. List S3 keys under the hmet/ prefix
2. Parse filenames into components (station, SLR scenario, SSP)
3. Build one pystac Item per file
4. Load directly into pgSTAC

Each file contains hourly sea level projections for a particular tide station,
SLR scenario, and SSP emission trajectory (117 files total:
13 sites x 3 SLR scenarios x 3 SSPs).

S3 path structure:
    hmet/watlev.SS.RRR.50pctile.sspXXX.wv2.nc

File naming:
    SS  = tide station code (e.g. sf, lj)
    RRR = SLR scenario (low, int, hig)
    XXX = SSP scenario (245, 370, 585)

Tide station coordinates are sourced from NOAA Tides and Currents:
    https://tidesandcurrents.noaa.gov/tide_predictions.html?gid=1393

Usage:
    uv run python -m scripts.ingest_sea_level

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

import requests
import pystac

from scripts.constants import (
    BUCKET_CADCAT,
    CALADAPT_DATA_LICENSE,
    HMET_PREFIX,
    ICON_BASE_URL,
    PGDSN,
    SEA_LEVEL_STATION_COORDS_URL,
)
from scripts.utils import list_keys, load_direct

SLR_SCENARIO_LABELS = {
    "low": "low",
    "int": "intermediate",
    "hig": "high",
}


def get_station_coords():
    """
    Load sea level station coordinates from the GeoJSON geometry file in S3.

    Returns
    -------
    dict
        Mapping of station_code (e.g. "sf") to {"name": ..., "lon": ..., "lat": ...}.
    """
    fc = requests.get(SEA_LEVEL_STATION_COORDS_URL).json()
    return {
        f["properties"]["station_code"]: {
            "name": f["properties"]["station_name"],
            "lon": f["geometry"]["coordinates"][0],
            "lat": f["geometry"]["coordinates"][1],
        }
        for f in fc["features"]
    }


def parse_hmet_key(key, valid_stations):
    """
    Parse a sea level projection S3 key into components.

    Parameters
    ----------
    key : str
        S3 key, e.g. hmet/watlev.sf.low.50pctile.ssp245.wv2.nc
    valid_stations : set
        Set of known station codes.

    Returns
    -------
    dict or None
        Parsed components, or None if key is not a matching .nc file.
    """
    if not key.endswith(".nc"):
        return None
    filename = key.split("/")[-1]
    parts = filename.split(".")
    # watlev.SS.RRR.50pctile.sspXXX.wv2.nc
    if len(parts) != 7 or parts[0] != "watlev":
        return None
    station_code = parts[1]
    slr_scenario = parts[2]
    experiment_id = parts[4]  # e.g. ssp245
    if station_code not in valid_stations or slr_scenario not in SLR_SCENARIO_LABELS:
        return None
    return {
        "station_code": station_code,
        "slr_scenario": slr_scenario,
        "experiment_id": experiment_id,
    }


def build_sea_level_collection():
    """
    Build a pystac Collection for hourly sea level projections.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="sea-level-projections",
        title="Sea level projections",
        keywords=["climate model"],
        extra_fields={"caladapt:spatial_type": "point"},
        description=(
            "Hourly sea level projections for 13 NOAA tide stations along the California "
            "coast and San Francisco Bay across low, intermediate, and high "
            "SLR scenarios and three SSP emission trajectories."
        ),
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Cal-Adapt",
                roles=[pystac.ProviderRole.HOST],
                url="https://cal-adapt.org/",
            ),
            pystac.Provider(
                name="Scripps Institution of Oceanography",
                roles=[pystac.ProviderRole.PRODUCER],
                url="https://scripps.ucsd.edu/",
            ),
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[[-124.5, 32.5, -117.0, 42.0]]),
            temporal=pystac.TemporalExtent(
                intervals=[
                    [
                        datetime(1950, 1, 1, tzinfo=timezone.utc),
                        datetime(2100, 12, 31, tzinfo=timezone.utc),
                    ]
                ]
            ),
        ),
    )
    collection.add_link(
        pystac.Link(
            rel="related",
            target="https://tidesandcurrents.noaa.gov/tide_predictions.html?gid=1393",
            title="NOAA Tides and Currents — California tide predictions",
        )
    )
    collection.add_link(
        pystac.Link(
            rel="related",
            target="https://digitalcommons.humboldt.edu/cgi/viewcontent.cgi?article=1062&context=hsuslri_state",
            title="California Sea Level Rise Guidance: 2024 Science and Policy Update",
        )
    )
    collection.add_link(
        pystac.Link(
            rel="related",
            target="https://www.energy.ca.gov/sites/default/files/2019-11/Projections_CCCA4-CEC-2018-006_ADA.pdf",
            title="Pierce et al. (2018). Climate, Drought, and Sea Level Rise Scenarios for the Fourth California Climate Assessment. CEC Publication CCCA4-CEC-2018-006.",
        )
    )

    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}sea_level_icon.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="Sea level projections preview",
        ),
    )
    collection.add_asset(
        "item-geometries",
        pystac.Asset(
            href=SEA_LEVEL_STATION_COORDS_URL,
            media_type="application/geo+json",
            roles=["item-geometries"],
            title="Item geometries",
        ),
    )

    station_coords = get_station_coords()

    for key, size in list_keys(HMET_PREFIX, BUCKET_CADCAT):
        parsed = parse_hmet_key(key, valid_stations=set(station_coords))
        if parsed is None:
            continue

        station_code = parsed["station_code"]
        slr_scenario = parsed["slr_scenario"]
        experiment_id = parsed["experiment_id"]
        station = station_coords[station_code]

        item_id = f"sea-level-{station_code}-{slr_scenario}-{experiment_id}"
        lon, lat = station["lon"], station["lat"]

        item = pystac.Item(
            id=item_id,
            geometry={"type": "Point", "coordinates": [lon, lat]},
            bbox=[lon, lat, lon, lat],
            datetime=None,
            properties={
                "station_id": station_code,
                "station_name": station["name"],
                "slr_scenario": SLR_SCENARIO_LABELS[slr_scenario],
                "cmip6:experiment_id": experiment_id,
                "file:size": size,
                "start_datetime": datetime(1950, 1, 1, tzinfo=timezone.utc).isoformat(),
                "end_datetime": datetime(2100, 12, 31, tzinfo=timezone.utc).isoformat(),
            },
        )
        item.add_asset(
            "data",
            pystac.Asset(
                href=f"s3://{BUCKET_CADCAT}/{key}",
                media_type="application/netcdf",
            ),
        )
        collection.add_item(item)

    return collection


def main():
    print("  Building sea level projections collection...")
    collection = build_sea_level_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
