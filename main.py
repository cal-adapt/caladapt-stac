import attr
from fastapi import FastAPI
from stac_fastapi.api.app import StacApi
from stac_fastapi.api.models import create_get_request_model, create_post_request_model
from stac_fastapi.extensions.core.filter.request import FilterExtensionGetRequest, FilterLang
from stac_fastapi.pgstac.core import CoreCrudClient
from stac_fastapi.pgstac.config import Settings
from stac_fastapi.pgstac.db import close_db_connection, connect_to_db
from stac_fastapi.pgstac.extensions.filter import FiltersClient
from stac_fastapi.pgstac.types.search import PgstacSearch
from stac_fastapi.types import config, core
from stac_fastapi.extensions.core import (
    FieldsExtension,
    FilterExtension,
    QueryExtension,
    SortExtension,
    TokenPaginationExtension,
)
from stac_fastapi.extensions.core.filter.filter import FilterConformanceClasses

EXTENSIONS = [
    QueryExtension(),
    SortExtension(),
    FieldsExtension(),
    FilterExtension(
        client=FiltersClient(),
    ),
    TokenPaginationExtension(),
]
search_get_request_model = create_get_request_model(EXTENSIONS)
search_post_request_model = create_post_request_model(EXTENSIONS, base_model=PgstacSearch)


@attr.s
class FilterExtensionGetRequest(FilterExtensionGetRequest):
    filter_lang: str | None = attr.ib(default='cql2-text')


FilterExtension.GET = FilterExtensionGetRequest

api = StacApi(
    title='Cal-Adapt STAC API',
    description='Searchable spatiotemporal catalog describing datasets hosted on Cal-Adapt',
    settings=Settings(debug=True),
    client=CoreCrudClient(post_request_model=search_post_request_model),
    extensions=EXTENSIONS,
    search_get_request_model=search_get_request_model,
    search_post_request_model=search_post_request_model,
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
