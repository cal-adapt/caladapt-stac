"""ingest_loca2_county.py

Ingest LOCA2 county-level NetCDF data into pgSTAC by building pystac items
from S3 keys and loading them directly into pgSTAC.

Workflow:
1. List S3 keys under the LOCA2 county NetCDF prefix
2. Parse filenames into components (county, variable, frequency, model, scenario, member_id)
3. Build one pystac Item per file (one per variable)
4. Load directly into pgSTAC

Each item represents one variable for a given county, model, scenario,
ensemble member, and temporal frequency (day or mon).

Usage:
    uv run python -m scripts.ingest_loca2_county

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN

"""

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

    Builds one item per NetCDF file (one per variable) with variable as a
    queryable property.

    Returns
    -------
    pystac.Collection
        Collection containing one item per county/variable/model/scenario/frequency combination.
    """
    collection = pystac.Collection(
        id="loca2-county",
        title="LOCA2 county (NetCDF)",
        description="County-level NetCDF data for LOCA2 statistically downscaled climate projections covering California.",
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Cal-Adapt",
                roles=[
                    pystac.ProviderRole.HOST,
                    pystac.ProviderRole.PROCESSOR,
                ],
                url="https://cal-adapt.org/",
            ),
            pystac.Provider(
                name="UCSD",
                roles=[pystac.ProviderRole.PRODUCER],
                url="https://loca.ucsd.edu/",
            ),
        ],
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

    for key in list_keys(LOCA2_COUNTY_NETCDF_PREFIX, BUCKET_CADCAT):
        parsed = parse_loca2_county_key(key)
        if parsed is None:
            continue
        county_code = parsed["county_code"]
        variable = parsed["variable"]
        frequency = parsed["frequency"]
        model = parsed["model"]
        scenario = parsed["scenario"]
        member_id = parsed["member_id"]

        countyname = CA_COUNTY_FIPS[county_code]
        geometry, bbox = county_geometries[countyname]

        item_id = f"loca2-county-{county_code}-{model}-{scenario}-{member_id}-{frequency}-{variable}"
        item = pystac.Item(
            id=item_id,
            geometry=geometry,
            bbox=bbox,
            datetime=None,
            properties={
                "title": f"{countyname} — {model} — {scenario} — {member_id} — {frequency} — {variable}",
                "cmip6:source_id": model,
                "cmip6:experiment_id": scenario,
                "cmip6:member_id": member_id,
                "cmip6:table_id": frequency,
                "county_code": county_code,
                "county_name": countyname,
                "variable": variable,
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
    print("  Building LOCA2 county collection...")
    collection = build_loca2_county_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
