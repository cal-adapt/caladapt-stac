"""constants.py

Shared constants for building and ingesting STAC items.

"""
import os 

# S3 buckets
BUCKET_CADCAT = "cadcat"

# STAC API endpoint
API_ENDPOINT = os.environ.get("STAC_API_ENDPOINT", "http://localhost:8082")

# S3 prefixes for collections
TMY_PREFIX = "climate-profiles/typical-met-year/"
SMY_PREFIX = "climate-profiles/standard-met-year/"
LOCA2_COUNTY_NETCDF_PREFIX = "loca2/ucb/netcdf/county/"

# California spatial extent — used as a placeholder geometry for non-spatial datasets
CA_BBOX = [-124.4, 32.5, -114.1, 42.0]
CA_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[
        [-124.4, 32.5],
        [-114.1, 32.5],
        [-114.1, 42.0],
        [-124.4, 42.0],
        [-124.4, 32.5],
    ]],
}
