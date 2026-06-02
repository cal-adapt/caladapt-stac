"""ingest_wrf_extreme_heat_tool_county_csv.py

Ingest WRF extreme heat tool per-county CSV data into pgSTAC.

Pre-processed summary CSVs with exceedance counts at each global warming level,
one file per California county (58 total). Each CSV contains all three heat
metrics (t2max_99pctl, t2max_ge100F, t2max_ge105F) across all warming levels.

S3 path structure:
    wrf/extreme-heat-tool/county-csv/{County_Name}.csv

Usage:
    uv run python -m scripts.ingest_wrf_extreme_heat_tool_county_csv

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

import pystac
import requests

from scripts.constants import (
    API_ENDPOINT,
    BUCKET_CADCAT,
    CA_BBOX,
    CA_COUNTIES_GEOMETRIES_URL,
    CA_COUNTY_FIPS,
    CALADAPT_DATA_LICENSE,
    ICON_BASE_URL,
    PGDSN,
    WRF_EXTREME_HEAT_TOOL_PREFIX,
    WRF_VARIABLE_LABELS,
)
from scripts.utils import list_keys, load_direct

COUNTY_CSV_PREFIX = WRF_EXTREME_HEAT_TOOL_PREFIX + "county-csv/"

# Reverse lookup: county name (without "County") → FIPS code
_FIPS_BY_NAME = {name: code for code, name in CA_COUNTY_FIPS.items()}


def parse_county_csv_key(key):
    """
    Parse a county CSV S3 key into components.

    Parameters
    ----------
    key : str
        S3 key, e.g. wrf/extreme-heat-tool/county-csv/Santa_Barbara_County.csv

    Returns
    -------
    dict or None
        Parsed components, or None if not a .csv file.
    """
    if not key.endswith(".csv"):
        return None
    filename = key.split("/")[-1].replace(".csv", "")
    # e.g. "Santa_Barbara_County" → "Santa Barbara"
    county_name = filename.replace("_County", "").replace("_", " ")
    county_code = _FIPS_BY_NAME.get(county_name)
    if county_code is None:
        return None
    return {
        "county_name": county_name,
        "county_code": county_code,
        "path": f"s3://{BUCKET_CADCAT}/{key}",
    }


def get_county_geometries():
    """
    Load California county geometries from S3.

    Returns
    -------
    dict
        Mapping of county name (without "County") to (geometry, bbox).
    """
    fc = requests.get(CA_COUNTIES_GEOMETRIES_URL).json()
    return {
        feature["properties"]["county_name"]: (feature["geometry"], feature["bbox"])
        for feature in fc["features"]
    }


def build_wrf_extreme_heat_tool_county_csv_collection():
    """
    Build a pystac Collection for WRF extreme heat tool county CSV data.

    One item per county (58 total), each with a single CSV asset.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="wrf-extreme-heat-tool-county-csv",
        title="Cal Adapt extreme heat metrics tool (county CSV)",
        keywords=[
            "climate model",
            "California",
            "CMIP6",
            "dynamical",
            "extreme heat",
            "global warming levels",
            "counties",
            "CSV",
        ],
        extra_fields={"caladapt:spatial_type": "county"},
        description=(
            "Per-county summary CSV files of WRF extreme heat projections for California at global warming levels "
            "(0.8°C–3.0°C), supporting the Cal-Adapt Extreme Heat Tool. "
            "Each file contains exceedance counts for three heat metrics across all warming levels."
        ),
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Cal-Adapt",
                roles=[pystac.ProviderRole.HOST, pystac.ProviderRole.PROCESSOR],
                url="https://cal-adapt.org/",
            ),
            pystac.Provider(
                name="UCLA",
                roles=[pystac.ProviderRole.PRODUCER],
                url="https://www.energy.ca.gov/sites/default/files/2024-06/02_DynamicalDownscaling_DataJustificationMemo_Rahimi_Adopted_v2May2024_ada.pdf",
            ),
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[CA_BBOX]),
            temporal=pystac.TemporalExtent(
                intervals=[
                    [
                        datetime(2015, 1, 1, tzinfo=timezone.utc),
                        datetime(2100, 12, 31, tzinfo=timezone.utc),
                    ]
                ]
            ),
        ),
    )
    collection.extra_fields["caladapt:variable_labels"] = {
        var: WRF_VARIABLE_LABELS.get(var, var)
        for var in ("t2max_99pctl", "t2max_ge100F", "t2max_ge105F")
    }
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}wrf_extreme_heat_ridgeplot.png",
            media_type="image/png",
            roles=["thumbnail"],
            title="WRF extreme heat tool preview",
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
    collection.add_link(
        pystac.Link(
            rel="related",
            target=f"{API_ENDPOINT}/collections/wrf-extreme-heat-tool-county",
            media_type="application/json",
            title="WRF extreme heat tool county Zarr",
        )
    )

    print("  Loading county geometries...")
    county_geometries = get_county_geometries()

    print("  Listing county CSV files...")
    for key, size in list_keys(COUNTY_CSV_PREFIX, BUCKET_CADCAT):
        parsed = parse_county_csv_key(key)
        if parsed is None:
            continue

        county_name = parsed["county_name"]
        county_code = parsed["county_code"]
        geometry, bbox = county_geometries[county_name]

        item_id = f"wrf-extreme-heat-tool-county-csv-{county_code}"
        item = pystac.Item(
            id=item_id,
            geometry=geometry,
            bbox=bbox,
            datetime=None,
            properties={
                "title": item_id,
                "county_code": county_code,
                "county_name": county_name,
                "cmip6:activity_id": "WRF",
                "cmip6:institution_id": "CAE",
                "cmip6:experiment_id": "ssp370",
                "caladapt:spatial_type": "county",
                "bias_adjusted": True,
                "start_datetime": datetime(2015, 1, 1, tzinfo=timezone.utc).isoformat(),
                "end_datetime": datetime(2100, 12, 31, tzinfo=timezone.utc).isoformat(),
            },
        )
        item.add_asset(
            "data",
            pystac.Asset(
                href=parsed["path"],
                media_type="text/csv",
                title=f"{county_name} County extreme heat CSV",
                extra_fields={"file:size": size},
            ),
        )
        collection.add_item(item)

    return collection


def main():
    print("  Building WRF extreme heat tool county CSV collection...")
    collection = build_wrf_extreme_heat_tool_county_csv_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
