"""ingest_loca2_county.py

Ingest LOCA2 county-level NetCDF data into pgSTAC by building pystac items
from S3 keys and POSTing them to the STAC API.

Workflow:
1. List S3 keys under the LOCA2 county NetCDF prefix
2. Parse filenames into components (county, variable, frequency, model, scenario, member_id)
3. Group files by (county, frequency, model, scenario, member_id) — one item per group
4. Build pystac Items with one asset per variable
5. POST the collection to the STAC API
6. POST each item individually to the STAC API

Each item represents all variables for a given county, model, scenario,
ensemble member, and temporal frequency (day or mon).

Usage:
    uv run python scripts/ingest_loca2_county.py

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - A running STAC API at API_ENDPOINT (this can be a local endpoint
    for testing, or a deployed STAC API endpoint)

"""

from collections import defaultdict
from datetime import datetime, timezone

import requests
import pystac

from scripts.constants import (
    BUCKET_CADCAT,
    CA_BBOX,
    CA_COUNTY_FIPS,
    CA_COUNTIES_GEOMETRIES_URL,
    CALADAPT_DATA_LICENSE,
    LOCA2_COUNTY_NETCDF_PREFIX,
    PGDSN,
)
from scripts.utils import list_keys, load_direct


def parse_loca2_county_key(key):
    """
    Parse a LOCA2 county NetCDF S3 key into components.

    Parameters
    ----------
    key : str
        S3 key, e.g. loca2/ucb/netcdf/county/day/06115_pr_day_TaiESM1_ssp370_r1i1p1f1.nc

    Returns
    -------
    dict or None
        Parsed components, or None if key is not a .nc file.
    """
    if not key.endswith(".nc"):
        return None
    filename = key.split("/")[-1].replace(".nc", "")
    # filename: {county_code}_{variable}_{frequency}_{model}_{scenario}_{member_id}
    parts = filename.split("_", 5)
    if len(parts) != 6:
        return None
    county_code, variable, frequency, model, scenario, member_id = parts
    return {
        "county_code": county_code,
        "variable": variable,
        "frequency": frequency,
        "model": model,
        "scenario": scenario,
        "member_id": member_id,
        "key": key,
    }


def get_county_geometries():
    """
    Load California county geometries from S3.

    Returns
    -------
    dict
        Mapping of county name (e.g. "Yuba") to (geometry, bbox) tuples,
        where geometry is a GeoJSON-compatible dict and bbox is [west, south, east, north].
    """
    fc = requests.get(CA_COUNTIES_GEOMETRIES_URL).json()
    return {
        feature["properties"]["county_name"]: (feature["geometry"], feature["bbox"])
        for feature in fc["features"]
    }


def build_loca2_county_collection():
    """
    Build a pystac Collection for LOCA2 county-level NetCDF data.

    Groups S3 keys by (county_code, frequency, model, scenario, member_id) and builds
    one item per group with one asset per variable.

    Returns
    -------
    pystac.Collection
        Collection containing one item per county/model/scenario/frequency combination.
    """
    collection = pystac.Collection(
        id="loca2-county",
        description="County-level NetCDF data for LOCA2 statistically downscaled climate projections covering California.",
        license=CALADAPT_DATA_LICENSE,
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[CA_BBOX]),
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
    collection.add_asset(
        "item-geometries",
        pystac.Asset(
            href=CA_COUNTIES_GEOMETRIES_URL,
            media_type="application/geo+json",
            roles=["item-geometries"],
            title="Item geometries",
        ),
    )

    county_geometries = get_county_geometries()

    # Group keys by (county_code, frequency, model, scenario, member_id)
    # defaultdict(dict) is like a regular dict, but automatically creates an empty
    # dict for any new key — so we can do groups[group_key][variable] = key
    # without checking if group_key exists first
    groups = defaultdict(dict)
    for key in list_keys(LOCA2_COUNTY_NETCDF_PREFIX, BUCKET_CADCAT):
        parsed = parse_loca2_county_key(key)
        if parsed is None:
            continue
        group_key = (
            parsed["county_code"],
            parsed["frequency"],
            parsed["model"],
            parsed["scenario"],
            parsed["member_id"],
        )
        groups[group_key][parsed["variable"]] = key

    # Build one item per group with one asset per variable
    for (
        county_code,
        frequency,
        model,
        scenario,
        member_id,
    ), variables in groups.items():
        item_id = (
            f"loca2-county-{county_code}-{model}-{scenario}-{member_id}-{frequency}"
        )
        countyname = CA_COUNTY_FIPS[county_code]
        geometry, bbox = county_geometries[countyname]
        props = {
            "cmip6:source_id": model,
            "cmip6:experiment_id": scenario,
            "cmip6:member_id": member_id,
            "cmip6:table_id": frequency,
            "county_code": county_code,
            "county_name": countyname,
            "start_datetime": datetime(1950, 1, 1, tzinfo=timezone.utc).isoformat(),
            "end_datetime": datetime(2100, 12, 31, tzinfo=timezone.utc).isoformat(),
        }
        item = pystac.Item(
            id=item_id,
            geometry=geometry,
            bbox=bbox,
            datetime=datetime(1950, 1, 1, tzinfo=timezone.utc),
            properties=props,
        )
        for variable, key in variables.items():
            item.add_asset(
                variable,
                pystac.Asset(
                    href=f"s3://{BUCKET_CADCAT}/{key}",
                    media_type="application/netcdf",
                ),
            )
        collection.add_item(item)

    return collection


def main():
    print("  Building LOCA2 county collection...")
    collection = build_loca2_county_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
