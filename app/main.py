"""FastAPI application using PGStac, modified for AWS Lambda deployment.

Enables the extensions specified as a comma-delimited list in
the ENABLED_EXTENSIONS environment variable (e.g. `transactions,sort,query`).
If the variable is not set, enables all extensions.

Modified from:
https://github.com/stac-utils/stac-fastapi-pgstac/blob/main/stac_fastapi/pgstac/app.py

Changes from source:
- Added LambdaSettings with single DB connection size
- Disabled lifespan on Lambda; DB startup handled manually on cold start
- Added Mangum handler for Lambda
- Replaced ORJSONResponse with stac_fastapi JSONResponse
"""

import asyncio
import os
from contextlib import asynccontextmanager
from typing import cast

from fastapi import APIRouter, FastAPI
from mangum import Mangum
from stac_fastapi.api.app import StacApi
from stac_fastapi.api.middleware import ProxyHeaderMiddleware
from stac_fastapi.api.models import (
    EmptyRequest,
    ItemCollectionUri,
    JSONResponse,
    create_get_request_model,
    create_post_request_model,
    create_request_model,
)
from stac_fastapi.extensions.core import (
    CollectionSearchExtension,
    CollectionSearchFilterExtension,
    FieldsExtension,
    ItemCollectionFilterExtension,
    OffsetPaginationExtension,
    SearchFilterExtension,
    SortExtension,
    TokenPaginationExtension,
    TransactionExtension,
)
from stac_fastapi.extensions.core.fields import FieldsConformanceClasses
from stac_fastapi.extensions.core.free_text import FreeTextConformanceClasses
from stac_fastapi.extensions.core.query import QueryConformanceClasses
from stac_fastapi.extensions.core.sort import SortConformanceClasses
from stac_fastapi.extensions.third_party import BulkTransactionExtension
from stac_fastapi.types.extension import ApiExtension
from stac_fastapi.types.search import APIRequest
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from stac_fastapi.pgstac.config import Settings
from stac_fastapi.pgstac.core import CoreCrudClient, health_check
from stac_fastapi.pgstac.db import close_db_connection, connect_to_db

# Additional links shown under "Additional Resources" in STAC Browser
EXTRA_LINKS = [
    {
        "rel": "related",
        "href": "https://cal-adapt.org",
        "title": "Cal-Adapt website",
        "type": "text/html",
    },
    {
        "rel": "related",
        "href": "https://analytics.cal-adapt.org/",
        "title": "Cal-Adapt: Analytics Engine website",
        "type": "text/html",
    },
]


class CalAdaptCrudClient(CoreCrudClient):
    async def landing_page(self, **kwargs):
        # Extend the default landing page links with Cal-Adapt specific resources
        response = await super().landing_page(**kwargs)
        response["links"].extend(EXTRA_LINKS)
        return response


from stac_fastapi.pgstac.extensions import FreeTextExtension, QueryExtension
from stac_fastapi.pgstac.extensions.filter import FiltersClient
from stac_fastapi.pgstac.transactions import BulkTransactionsClient, TransactionsClient
from stac_fastapi.pgstac.types.search import PgstacSearch


# Lambda-specific settings: single connection per request
class LambdaSettings(Settings):
    db_max_conn_size: int = 1
    db_min_conn_size: int = 1
    stac_fastapi_title: str = "Cal-Adapt STAC API"
    stac_fastapi_description: str = (
        "Searchable spatiotemporal catalog of climate datasets hosted on Cal-Adapt."
    )
    openapi_url: str = "/openapi.json"
    docs_url: str = "/docs"


IS_LAMBDA = "AWS_EXECUTION_ENV" in os.environ
settings = LambdaSettings() if IS_LAMBDA else Settings()

# search extensions
search_extensions_map: dict[str, ApiExtension] = {
    "query": QueryExtension(),
    "sort": SortExtension(),
    "fields": FieldsExtension(),
    "filter": SearchFilterExtension(client=FiltersClient()),
    "pagination": TokenPaginationExtension(),
}

# collection_search extensions
cs_extensions_map: dict[str, ApiExtension] = {
    "query": QueryExtension(conformance_classes=[QueryConformanceClasses.COLLECTIONS]),
    "sort": SortExtension(conformance_classes=[SortConformanceClasses.COLLECTIONS]),
    "fields": FieldsExtension(
        conformance_classes=[FieldsConformanceClasses.COLLECTIONS]
    ),
    "filter": CollectionSearchFilterExtension(client=FiltersClient()),
    "free_text": FreeTextExtension(
        conformance_classes=[FreeTextConformanceClasses.COLLECTIONS],
    ),
    "pagination": OffsetPaginationExtension(),
}

# item_collection extensions
itm_col_extensions_map: dict[str, ApiExtension] = {
    "query": QueryExtension(
        conformance_classes=[QueryConformanceClasses.ITEMS],
    ),
    "sort": SortExtension(
        conformance_classes=[SortConformanceClasses.ITEMS],
    ),
    "fields": FieldsExtension(conformance_classes=[FieldsConformanceClasses.ITEMS]),
    "filter": ItemCollectionFilterExtension(client=FiltersClient()),
    "pagination": TokenPaginationExtension(),
}

enabled_extensions: set[str] = {
    *search_extensions_map.keys(),
    *cs_extensions_map.keys(),
    *itm_col_extensions_map.keys(),
    "collection_search",
}

if ext := os.environ.get("ENABLED_EXTENSIONS"):
    enabled_extensions = set(ext.split(","))

application_extensions: list[ApiExtension] = []

with_transactions = (
    os.environ.get("ENABLE_TRANSACTIONS_EXTENSIONS", "").upper() == "TRUE"
)
if with_transactions:
    application_extensions.append(
        TransactionExtension(
            client=TransactionsClient(),
            settings=settings,
            response_class=JSONResponse,
        ),
    )
    application_extensions.append(
        BulkTransactionExtension(client=BulkTransactionsClient()),
    )

# /search models
search_extensions = [
    extension
    for key, extension in search_extensions_map.items()
    if key in enabled_extensions
]
post_request_model = create_post_request_model(
    search_extensions, base_model=PgstacSearch
)
get_request_model = create_get_request_model(search_extensions)
application_extensions.extend(search_extensions)

# /collections/{collectionId}/items model
items_get_request_model: type[APIRequest] = ItemCollectionUri
itm_col_extensions = [
    extension
    for key, extension in itm_col_extensions_map.items()
    if key in enabled_extensions
]
if itm_col_extensions:
    items_get_request_model = cast(
        type[APIRequest],
        create_request_model(
            model_name="ItemCollectionUri",
            base_model=ItemCollectionUri,
            extensions=itm_col_extensions,
            request_type="GET",
        ),
    )
    application_extensions.extend(itm_col_extensions)

# /collections model
collections_get_request_model: type[APIRequest] = EmptyRequest
if "collection_search" in enabled_extensions:
    cs_extensions = [
        extension
        for key, extension in cs_extensions_map.items()
        if key in enabled_extensions
    ]
    collection_search_extension = CollectionSearchExtension.from_extensions(
        cs_extensions
    )
    collections_get_request_model = collection_search_extension.GET
    application_extensions.append(collection_search_extension)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: open and close DB connection pool."""
    await connect_to_db(app, add_write_connection_pool=with_transactions)
    yield
    await close_db_connection(app)


api = StacApi(
    app=FastAPI(
        openapi_url=settings.openapi_url,
        docs_url=settings.docs_url,
        redoc_url=None,
        root_path=settings.root_path,
        title=settings.stac_fastapi_title,
        version=settings.stac_fastapi_version,
        description=settings.stac_fastapi_description,
        # Disable lifespan for Lambda; startup is handled manually below
        lifespan=None if IS_LAMBDA else lifespan,
        default_response_class=JSONResponse,
    ),
    router=APIRouter(prefix=settings.prefix_path),
    settings=settings,
    extensions=application_extensions,
    client=CalAdaptCrudClient(pgstac_search_model=post_request_model),  # type: ignore [arg-type]
    response_class=JSONResponse,
    items_get_request_model=items_get_request_model,
    search_get_request_model=get_request_model,
    search_post_request_model=post_request_model,
    collections_get_request_model=collections_get_request_model,
    middlewares=[
        Middleware(ProxyHeaderMiddleware),
        Middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_origin_regex=settings.cors_origin_regex,
            allow_methods=settings.cors_methods,
            allow_credentials=settings.cors_credentials,
            allow_headers=settings.cors_headers,
            max_age=600,
        ),
    ],
    health_check=health_check,  # type: ignore [arg-type]
)
app = api.app

# Lambda: manually trigger startup on cold start
if IS_LAMBDA:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(
        connect_to_db(app, add_write_connection_pool=with_transactions)
    )

# Lambda handler — lifespan="off" since startup is managed manually above
handler = Mangum(app, lifespan="off")
