"""ingest_loca2_county.py

Ingest LOCA2 county-level NetCDF data into pgSTAC.

Each STAC item represents one county × model × scenario × member_id × frequency
combination, with one asset per variable. This keeps item count manageable
(~1-2K items) while preserving full queryability by county, model, and scenario.

S3 path structure:
    loca2/ucb/netcdf/county/{frequency}/{county_code}_{variable}_{frequency}_{model}_{scenario}_{member_id}.nc

Usage:
    uv run python -m scripts.ingest_loca2_county

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
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
    ICON_BASE_URL,
    LOCA2_COUNTY_NETCDF_PREFIX,
    LOCA2_VARIABLE_LABELS,
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
        Mapping of county name to (geometry, bbox) tuples.
    """
    fc = requests.get(CA_COUNTIES_GEOMETRIES_URL).json()
    return {
        feature["properties"]["county_name"]: (feature["geometry"], feature["bbox"])
        for feature in fc["features"]
    }


def build_loca2_county_collection():
    """
    Build a pystac Collection for LOCA2 county-level NetCDF data.

    One item per county × model × scenario × member_id × frequency,
    with one asset per variable.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="loca2-county",
        title="LOCA2 county",
        keywords=[
            "climate model",
            "California",
            "geospatial",
            "counties",
            "future projections",
            "statistical",
        ],
        extra_fields={"caladapt:spatial_type": "county"},
        description="LOCA2 hybrid-statistically downscaled climate projections aggregated by California counties.",
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Cal-Adapt",
                roles=[pystac.ProviderRole.HOST, pystac.ProviderRole.PROCESSOR],
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
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}loca2_county_icon.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="LOCA2 county preview",
        ),
    )

    county_geometries = get_county_geometries()

    # Group files by (county_code, model, scenario, member_id, frequency)
    # Each group becomes one item; each variable becomes one asset.
    groups = defaultdict(dict)  # group_key → {variable: (key, size)}
    for key, size in list_keys(LOCA2_COUNTY_NETCDF_PREFIX, BUCKET_CADCAT):
        parsed = parse_loca2_county_key(key)
        if parsed is None:
            continue
        group_key = (
            parsed["county_code"],
            parsed["model"],
            parsed["scenario"],
            parsed["member_id"],
            parsed["frequency"],
        )
        groups[group_key][parsed["variable"]] = (key, size)

    print(f"  Building {len(groups)} items...")
    for group_key, variables in groups.items():
        county_code, model, scenario, member_id, frequency = group_key
        countyname = CA_COUNTY_FIPS[county_code]
        geometry, bbox = county_geometries[countyname]

        item_id = (
            f"loca2-county-{county_code}-{model}-{scenario}-{member_id}-{frequency}"
        )
        item = pystac.Item(
            id=item_id,
            geometry=geometry,
            bbox=bbox,
            datetime=None,
            properties={
                "title": item_id,
                "cmip6:source_id": model,
                "cmip6:experiment_id": scenario,
                "cmip6:member_id": member_id,
                "cmip6:table_id": frequency,
                "county_code": county_code,
                "county_name": countyname,
                "start_datetime": datetime(1950, 1, 1, tzinfo=timezone.utc).isoformat(),
                "end_datetime": datetime(2100, 12, 31, tzinfo=timezone.utc).isoformat(),
            },
        )
        for variable, (key, size) in variables.items():
            item.add_asset(
                variable,
                pystac.Asset(
                    href=f"s3://{BUCKET_CADCAT}/{key}",
                    media_type="application/netcdf",
                    title=LOCA2_VARIABLE_LABELS.get(variable, variable),
                    extra_fields={
                        "file:size": size,
                        "variable_label": LOCA2_VARIABLE_LABELS.get(variable, variable),
                    },
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
