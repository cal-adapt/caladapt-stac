"""ingest_ren.py

Ingest Photovoltaic (PV) and Wind Power Generation Profile zarr data
into pgSTAC.

Workflow:
1. List S3 zarr store prefixes under the PV and Wind prefixes in wfclimres
2. Parse store paths into metadata components
3. Build one pystac Item per zarr store
4. Load directly into pgSTAC

S3 path structure:
    era/{resource}_{module}/{simulation}/{scenario}/{frequency}/{variable}/{domain}/

Collections:
    - pv-generation: utility and distributed solar PV
    - wind-generation: onshore and offshore wind power

Usage:
    uv run python -m scripts.ingest_ren

Requires:
    - AWS credentials with read access to the wfclimres S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

import pystac

from scripts.constants import (
    BUCKET_REN,
    CALADAPT_DATA_LICENSE,
    PGDSN,
    WRF_UCLA_GRID_BBOXES,
    WRF_UCSD_GRID_BBOXES,
)
from scripts.utils import bbox_to_geometry, list_zarr_stores, load_direct

SCENARIO_DATE_RANGES = {
    "historical": (
        datetime(1981, 1, 1, tzinfo=timezone.utc),
        datetime(2013, 12, 31, tzinfo=timezone.utc),
    ),
    "ssp370": (
        datetime(2015, 1, 1, tzinfo=timezone.utc),
        datetime(2098, 12, 31, tzinfo=timezone.utc),
    ),
    "reanalysis": (
        datetime(1981, 1, 1, tzinfo=timezone.utc),
        datetime(2019, 12, 31, tzinfo=timezone.utc),
    ),
}

DOMAIN_BBOXES = {
    "d03": WRF_UCSD_GRID_BBOXES["d03"],
    "d02": WRF_UCLA_GRID_BBOXES["d02"],
}

# S3 prefixes: era/{resource}_{module}/
PV_MODULE_PREFIXES = {
    "pv_utility": "era/pv_utility/",
    "pv_distributed": "era/pv_distributed/",
}
WIND_MODULE_PREFIXES = {
    "windpower_onshore": "era/windpower_onshore/",
    "windpower_offshore": "era/windpower_offshore/",
}


def parse_ren_store(store_prefix, base_prefix):
    """
    Parse a renewable energy zarr store S3 prefix into components.

    Parameters
    ----------
    store_prefix : str
        S3 prefix for a zarr store,
        e.g. era/pv_utility/ec-earth3/historical/1hr/cf/d03/
    base_prefix : str
        The base prefix to strip, e.g. "era/pv_utility/"

    Returns
    -------
    dict
        Parsed components: source_id, experiment_id, table_id, variable_id, grid_label, path.
    """
    inner = store_prefix.removeprefix(base_prefix)
    source_id, experiment_id, table_id, variable_id, grid_label, *_ = inner.split("/")
    return {
        "source_id": source_id,
        "experiment_id": experiment_id,
        "table_id": table_id,
        "variable_id": variable_id,
        "grid_label": grid_label,
        "path": f"s3://{BUCKET_REN}/{store_prefix}",
    }


def _build_ren_items(collection, resource, module_prefixes):
    """
    List zarr stores, build items, and add them to the collection.

    Parameters
    ----------
    collection : pystac.Collection
    resource : str
        "pv" or "wind"
    module_prefixes : dict
        Mapping of module name to S3 prefix.
    """
    count = 0
    for installation, prefix in module_prefixes.items():
        print(f"  Listing {resource}/{installation} zarr stores...")
        for store_prefix in list_zarr_stores(prefix, BUCKET_REN, depth=5):
            parsed = parse_ren_store(store_prefix, prefix)
            source_id = parsed["source_id"]
            experiment_id = parsed["experiment_id"]
            table_id = parsed["table_id"]
            variable_id = parsed["variable_id"]
            grid_label = parsed["grid_label"]

            item_id = f"{resource}-{installation}-{source_id}-{experiment_id}-{table_id}-{variable_id}-{grid_label}"

            start_dt, end_dt = SCENARIO_DATE_RANGES.get(
                experiment_id,
                (
                    datetime(1981, 1, 1, tzinfo=timezone.utc),
                    datetime(2098, 12, 31, tzinfo=timezone.utc),
                ),
            )

            bbox = DOMAIN_BBOXES.get(grid_label, DOMAIN_BBOXES["d03"])
            item = pystac.Item(
                id=item_id,
                geometry=bbox_to_geometry(bbox),
                bbox=bbox,
                datetime=None,
                properties={
                    "installation": installation,
                    "source_id": source_id,
                    "experiment_id": experiment_id,
                    "table_id": table_id,
                    "variable_id": variable_id,
                    "grid_label": grid_label,
                    "start_datetime": start_dt.isoformat(),
                    "end_datetime": end_dt.isoformat(),
                },
            )
            item.add_asset(
                "data",
                pystac.Asset(href=parsed["path"], media_type="application/vnd+zarr"),
            )
            collection.add_item(item)
            count += 1
            if count % 50 == 0:
                print(f"  {count} stores found...")
    return count


def build_pv_collection():
    """
    Build a pystac Collection for PV Power Generation Profiles.

    Builds one item per zarr store with module and variable as queryable
    properties.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="pv-generation",
        title="Photovoltaic power generation profiles",
        extra_fields={"caladapt:spatial_type": "grid"},
        description="Photovoltaic power generation profiles (capacity factor and power output) for utility-scale and distributed solar PV, covering California (3 km) and WECC (9 km).",
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Eagle Rock Analytics",
                roles=[pystac.ProviderRole.PRODUCER, pystac.ProviderRole.PROCESSOR],
                url="https://eaglerockanalytics.com/",
            ),
            pystac.Provider(
                name="Cal-Adapt",
                roles=[
                    pystac.ProviderRole.HOST,
                ],
                url="https://cal-adapt.org/",
            ),
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[DOMAIN_BBOXES["d02"]]),
            temporal=pystac.TemporalExtent(
                intervals=[
                    [
                        datetime(1981, 1, 1, tzinfo=timezone.utc),
                        datetime(2098, 12, 31, tzinfo=timezone.utc),
                    ]
                ]
            ),
        ),
    )
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href="https://raw.githubusercontent.com/cal-adapt/caladapt-stac/main/images/icons/pv_cf_d03_2030.gif",
            media_type="image/gif",
            roles=["thumbnail"],
            title="PV capacity factor animated preview",
        ),
    )
    _build_ren_items(collection, "pv", PV_MODULE_PREFIXES)
    return collection


def build_wind_collection():
    """
    Build a pystac Collection for Wind Power Generation Profiles.

    Builds one item per zarr store with module and variable as queryable
    properties.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="wind-generation",
        title="Wind power generation profiles",
        extra_fields={"caladapt:spatial_type": "grid"},
        description="Wind power generation profiles (capacity factor and power output) for onshore and offshore wind, covering California (3 km) and WECC (9 km).",
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="Eagle Rock Analytics",
                roles=[pystac.ProviderRole.PRODUCER, pystac.ProviderRole.PROCESSOR],
                url="https://eaglerockanalytics.com/",
            ),
            pystac.Provider(
                name="Cal-Adapt",
                roles=[
                    pystac.ProviderRole.HOST,
                ],
                url="https://cal-adapt.org/",
            ),
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[DOMAIN_BBOXES["d02"]]),
            temporal=pystac.TemporalExtent(
                intervals=[
                    [
                        datetime(1981, 1, 1, tzinfo=timezone.utc),
                        datetime(2098, 12, 31, tzinfo=timezone.utc),
                    ]
                ]
            ),
        ),
    )
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href="https://raw.githubusercontent.com/cal-adapt/caladapt-stac/main/images/icons/wind_cf_d03_2030.gif",
            media_type="image/gif",
            roles=["thumbnail"],
            title="Wind capacity factor animated preview",
        ),
    )
    _build_ren_items(collection, "wind", WIND_MODULE_PREFIXES)
    return collection


def main():
    print("  Building PV generation collection...")
    pv_collection = build_pv_collection()
    print("  Loading PV directly into pgSTAC...")
    load_direct(pv_collection, PGDSN)

    print("  Building wind generation collection...")
    wind_collection = build_wind_collection()
    print("  Loading wind directly into pgSTAC...")
    load_direct(wind_collection, PGDSN)


if __name__ == "__main__":
    main()
