from functools import lru_cache

import attr
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from stac_fastapi.api.app import StacApi
from stac_fastapi.api.models import create_get_request_model, create_post_request_model
from stac_fastapi.extensions.core.filter.request import FilterExtensionGetRequest, FilterLang
from stac_fastapi.pgstac.core import CoreCrudClient
from stac_fastapi.pgstac.config import Settings
from stac_fastapi.pgstac.db import close_db_connection, connect_to_db
from stac_fastapi.pgstac.extensions.filter import FiltersClient
from stac_fastapi.pgstac.types.search import PgstacSearch
from stac_fastapi.extensions.core import (
    FieldsExtension,
    FilterExtension,
    QueryExtension,
    SortExtension,
    TokenPaginationExtension,
)
from mangum import Mangum


class _Settings(Settings):
    # Use single connections for lambdas, one per request
    db_max_conn_size: int = 1
    db_min_conn_size: int = 1


@lru_cache
def Settings() -> _Settings:
    return _Settings()

settings = _Settings()


@attr.s
class FilterExtensionGetRequest(FilterExtensionGetRequest):
    filter_lang: str | None = attr.ib(default='cql2-text')


FilterExtension.GET = FilterExtensionGetRequest

EXTENSIONS = (
    QueryExtension(),
    SortExtension(),
    FieldsExtension(),
    FilterExtension(client=FiltersClient()),
    TokenPaginationExtension(),
)
SearchGETRequest = create_get_request_model(EXTENSIONS)
SearchPOSTRequest = create_post_request_model(EXTENSIONS, base_model=PgstacSearch)

api = StacApi(
    title='Cal-Adapt STAC API',
    description='Searchable spatiotemporal catalog describing datasets hosted on Cal-Adapt',
    settings=settings,
    client=CoreCrudClient(post_request_model=SearchPOSTRequest),
    extensions=EXTENSIONS,
    search_get_request_model=SearchGETRequest,
    search_post_request_model=SearchPOSTRequest,
)
app = api.app

@app.on_event('startup')
async def startup_event() -> None:
    """Connect to database on startup."""
    await connect_to_db(app)

@app.on_event('shutdown')
async def shutdown_event() -> None:
    """Close database connection."""
    await close_db_connection(app)

handler = Mangum(app)
