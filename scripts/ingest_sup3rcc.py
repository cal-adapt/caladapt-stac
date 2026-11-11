"""ingest_sup3rcc.py

Ingest NLR Sup3rCC (Super-Resolution for Renewable Energy Resource Data with
Climate Change Impacts) zarr data into pgSTAC.

Sup3rCC is ~4 km hourly meteorology for the contiguous United States,
downscaled from CMIP6 Earth System Models by the National Laboratory of the
Rockies (NLR) with generative machine learning. Cal-Adapt hosts a copy of the
v0.2.2 release. See s3://cadcat/sup3r/README_sup3rcc.md.

Workflow:
1. List zarr store prefixes under the Sup3rCC prefix in cadcat
2. Parse store paths into metadata components
3. Build one pystac Item per zarr store
4. Load directly into pgSTAC

S3 path structure:
    sup3r/nlr/{source_id}/{experiment_id}/{table_id}/{variable_id}/{grid_label}/
    e.g. sup3r/nlr/ec-earth3-cc/historical/1hr/rh/conus4km/

    source_id: ec-earth3-cc, ec-earth3-veg, gfdl-cm4, mpi-esm1-2-hr, taiesm1
    experiment_id: historical (2000-2014), ssp245 (2015-2059; TaiESM1 hourly to 2099)
    table_id: 1hr (all variables except prec), day (prec only)
    grid_label: conus4km (lat/lon grid; extent differs slightly by source model)

Usage:
    uv run python -m scripts.ingest_sup3rcc

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - PGDSN environment variable with a valid PostgreSQL DSN
"""

from datetime import datetime, timezone

import pystac
from pystac.extensions.scientific import Publication, ScientificExtension

from scripts.constants import (
    BUCKET_CADCAT,
    CALADAPT_DATA_LICENSE,
    COLLECTION_KEYWORDS,
    ICON_BASE_URL,
    PGDSN,
    SUP3RCC_PREFIX,
    SUP3RCC_VARIABLE_LABELS,
)
from scripts.utils import (
    add_related_links,
    bbox_to_geometry,
    list_zarr_stores,
    load_direct,
)

# Lat/lon extent of each source model's grid, read from the zarr lat/lon arrays
SOURCE_BBOXES = {
    "ec-earth3-cc": [-129.009, 23.172, -64.35, 51.214],
    "ec-earth3-veg": [-129.009, 23.172, -64.35, 51.214],
    "gfdl-cm4": [-129.975, 23.02, -65.025, 51.98],
    "mpi-esm1-2-hr": [-129.825, 22.46, -64.238, 51.41],
    "taiesm1": [-129.35, 22.637, -64.4, 51.814],
}
COLLECTION_BBOX = [
    min(b[0] for b in SOURCE_BBOXES.values()),
    min(b[1] for b in SOURCE_BBOXES.values()),
    max(b[2] for b in SOURCE_BBOXES.values()),
    max(b[3] for b in SOURCE_BBOXES.values()),
]

SCENARIO_DATE_RANGES = {
    "historical": (
        datetime(2000, 1, 1, tzinfo=timezone.utc),
        datetime(2014, 12, 31, 23, tzinfo=timezone.utc),
    ),
    "ssp245": (
        datetime(2015, 1, 1, tzinfo=timezone.utc),
        datetime(2059, 12, 31, 23, tzinfo=timezone.utc),
    ),
}
# TaiESM1 hourly SSP2-4.5 runs to 2099; its daily precipitation stops at 2059
# like the other models.
TAIESM1_SSP245_1HR_END = datetime(2099, 12, 31, 23, tzinfo=timezone.utc)

RELATED_LINKS = [
    (
        "Sup3r GitHub repository",
        "https://github.com/NatLabRockies/sup3r",
        "text/html",
    ),
    (
        "Sup3rCC data access examples",
        "https://github.com/NatLabRockies/sup3r/tree/main/examples/sup3rcc",
        "text/html",
    ),
    (
        "Sup3r (NLR)",
        "https://www.nlr.gov/analysis/sup3r",
        "text/html",
    ),
]

PUBLICATIONS = [
    Publication(
        doi="10.1038/s41560-024-01507-9",
        citation="Buster, G., Benton, B., Glaws, A., and King, R. (2024): High-Resolution Meteorology with Climate Change Impacts from Global Climate Model Data Using Generative Machine Learning. Nature Energy.",
    ),
    Publication(
        doi="10.1016/j.dib.2025.111774",
        citation="Buster, G., et al. (2025): Second-Generation Downscaled Earth System Model Data using Generative Machine Learning. Data in Brief.",
    ),
]
DATASET_DOI = "10.25984/1970814"


def parse_sup3rcc_store(store_prefix):
    """
    Parse a Sup3rCC zarr store S3 prefix into components.

    Parameters
    ----------
    store_prefix : str
        S3 prefix for a zarr store,
        e.g. sup3r/nlr/ec-earth3-cc/historical/1hr/rh/conus4km/

    Returns
    -------
    dict
        Parsed components: source_id, experiment_id, table_id, variable_id, grid_label, path.
    """
    inner = store_prefix.removeprefix(SUP3RCC_PREFIX)
    source_id, experiment_id, table_id, variable_id, grid_label, *_ = inner.split("/")
    return {
        "source_id": source_id,
        "experiment_id": experiment_id,
        "table_id": table_id,
        "variable_id": variable_id,
        "grid_label": grid_label,
        "path": f"s3://{BUCKET_CADCAT}/{store_prefix}",
    }


def build_sup3rcc_collection():
    """
    Build a pystac Collection for Sup3rCC, one item per zarr store.

    Returns
    -------
    pystac.Collection
    """
    collection = pystac.Collection(
        id="sup3rcc",
        title="Sup3rCC downscaled meteorology for renewable energy",
        keywords=COLLECTION_KEYWORDS["sup3rcc"],
        extra_fields={
            "caladapt:spatial_type": "grid",
            "caladapt:source": "other",
        },
        description=(
            "Super-Resolution for Renewable Energy Resource Data with Climate Change Impacts (Sup3rCC): "
            "4 km hourly wind, solar irradiance, temperature, humidity and pressure, and 4 km daily "
            "precipitation, for the contiguous United States. Downscaled by the National Laboratory of "
            "the Rockies (NLR) from five CMIP6 Earth System Models under historical and SSP2-4.5 "
            "scenarios using generative machine learning (version 0.2.2). Historical years represent "
            "the historical climate, not observed weather, so the data cannot be used to study "
            "specific past weather events. Pressure is interpolated from the source model rather "
            "than super-resolved. Cal-Adapt hosts a copy of the data."
        ),
        license=CALADAPT_DATA_LICENSE,
        providers=[
            pystac.Provider(
                name="National Laboratory of the Rockies",
                roles=[pystac.ProviderRole.PRODUCER],
                url="https://www.nlr.gov/index",
            ),
            pystac.Provider(
                name="Cal-Adapt",
                roles=[pystac.ProviderRole.HOST],
                url="https://cal-adapt.org/",
            ),
        ],
        extent=pystac.Extent(
            spatial=pystac.SpatialExtent(bboxes=[COLLECTION_BBOX]),
            temporal=pystac.TemporalExtent(
                intervals=[
                    [
                        SCENARIO_DATE_RANGES["historical"][0],
                        TAIESM1_SSP245_1HR_END,
                    ]
                ]
            ),
        ),
    )
    collection.add_asset(
        "thumbnail",
        pystac.Asset(
            href=f"{ICON_BASE_URL}sup3rcc_ws100_2030.gif",
            media_type="image/gif",
            roles=["thumbnail"],
            title="Sup3rCC 100 m wind speed animated preview",
        ),
    )
    add_related_links(collection, RELATED_LINKS)
    sci_ext = ScientificExtension.ext(collection, add_if_missing=True)
    sci_ext.doi = DATASET_DOI
    sci_ext.publications = PUBLICATIONS

    seen_variables: set[str] = set()
    for store_prefix in list_zarr_stores(SUP3RCC_PREFIX, BUCKET_CADCAT, depth=5):
        parsed = parse_sup3rcc_store(store_prefix)
        source_id = parsed["source_id"]
        experiment_id = parsed["experiment_id"]
        table_id = parsed["table_id"]
        variable_id = parsed["variable_id"]
        grid_label = parsed["grid_label"]
        seen_variables.add(variable_id)

        start_dt, end_dt = SCENARIO_DATE_RANGES[experiment_id]
        if (source_id, experiment_id, table_id) == ("taiesm1", "ssp245", "1hr"):
            end_dt = TAIESM1_SSP245_1HR_END

        bbox = SOURCE_BBOXES[source_id]
        item = pystac.Item(
            id=f"sup3rcc-{source_id}-{experiment_id}-{table_id}-{variable_id}-{grid_label}",
            geometry=bbox_to_geometry(bbox),
            bbox=bbox,
            datetime=None,
            properties={
                "cmip6:source_id": source_id,
                "cmip6:experiment_id": experiment_id,
                "cmip6:table_id": table_id,
                "variable_id": variable_id,
                "cmip6:grid_label": grid_label,
                "start_datetime": start_dt.isoformat(),
                "end_datetime": end_dt.isoformat(),
            },
        )
        item.add_asset(
            "data",
            pystac.Asset(href=parsed["path"], media_type="application/vnd+zarr"),
        )
        collection.add_item(item)

    collection.extra_fields["caladapt:variable_labels"] = {
        var: SUP3RCC_VARIABLE_LABELS.get(var, var) for var in sorted(seen_variables)
    }
    return collection


def main():
    print("  Building Sup3rCC collection...")
    collection = build_sup3rcc_collection()
    print("  Loading directly into pgSTAC...")
    load_direct(collection, PGDSN)


if __name__ == "__main__":
    main()
