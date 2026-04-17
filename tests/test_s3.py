"""Integration tests: verify each collection's S3 prefix contains at least one object.

Requires AWS credentials with read access to cadcat and wfclimres buckets.
Skip in offline or un-credentialed environments:
    pytest -m "not integration"
"""

import boto3
import pytest

from scripts.constants import (
    BUCKET_CADCAT,
    BUCKET_REN,
    HADISD_PREFIX,
    HDP_PREFIX,
    HMET_PREFIX,
    LOCA2_COUNTY_NETCDF_PREFIX,
    LOCA2_GRIDDED_PREFIX,
    SMY_PREFIX,
    TMY_PREFIX,
    WRF_CAE_PREFIX,
    WRF_UCLA_PREFIX,
)
from scripts.ingest_ren import PV_MODULE_PREFIXES, WIND_MODULE_PREFIXES

CADCAT_PREFIXES = [
    TMY_PREFIX,
    SMY_PREFIX,
    LOCA2_COUNTY_NETCDF_PREFIX,
    LOCA2_GRIDDED_PREFIX,
    WRF_UCLA_PREFIX,
    WRF_CAE_PREFIX,
    HDP_PREFIX,
    HADISD_PREFIX,
    HMET_PREFIX,
]

REN_PREFIXES = list(PV_MODULE_PREFIXES.values()) + list(WIND_MODULE_PREFIXES.values())


@pytest.fixture(scope="module")
def s3_client():
    return boto3.client("s3")


@pytest.mark.integration
@pytest.mark.parametrize("prefix", CADCAT_PREFIXES, ids=CADCAT_PREFIXES)
def test_cadcat_prefix_non_empty(s3_client, prefix):
    response = s3_client.list_objects_v2(Bucket=BUCKET_CADCAT, Prefix=prefix, MaxKeys=1)
    assert response.get("KeyCount", 0) > 0, f"No objects under s3://{BUCKET_CADCAT}/{prefix}"


@pytest.mark.integration
@pytest.mark.parametrize("prefix", REN_PREFIXES, ids=REN_PREFIXES)
def test_ren_prefix_non_empty(s3_client, prefix):
    response = s3_client.list_objects_v2(Bucket=BUCKET_REN, Prefix=prefix, MaxKeys=1)
    assert response.get("KeyCount", 0) > 0, f"No objects under s3://{BUCKET_REN}/{prefix}"
