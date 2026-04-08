import os
import asyncio
from functools import lru_cache

import attr
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse
from stac_fastapi.api.app import StacApi
from stac_fastapi.api.models import create_get_request_model, create_post_request_model
from stac_fastapi.extensions.core.filter.request import FilterExtensionGetRequest, FilterLang
from stac_fastapi.pgstac.core import CoreCrudClient
from stac_fastapi.pgstac.config import Settings
from stac_fastapi.pgstac.db import DB, get_connection
from stac_fastapi.pgstac.extensions.filter import FiltersClient
from stac_fastapi.pgstac.types.search import PgstacSearch
from stac_fastapi.extensions.core import (
    FieldsExtension,
    FilterExtension,
    QueryExtension,
    SortExtension,
    TokenPaginationExtension,
)
from starlette.middleware.cors import CORSMiddleware
from mangum import Mangum

async def connect_pool(app: FastAPI) -> None:
    db = DB()
    readpool = settings.reader_connection_string
    app.state.readpool = await db.create_pool(readpool, settings)


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
EXTENSIONS = [
    QueryExtension(),
    SortExtension(),
    FieldsExtension(),
    FilterExtension(client=FiltersClient()),
    TokenPaginationExtension(),
]
SearchGETRequest = create_get_request_model(EXTENSIONS)
SearchPOSTRequest = create_post_request_model(EXTENSIONS, base_model=PgstacSearch)

app = FastAPI(title='Cal-Adapt STAC API', default_response_class=ORJSONResponse)
app.state.get_connection = get_connection

@app.on_event('startup')
async def startup_event():
    await connect_pool(app)

api = StacApi(
    app=app,
    title=app.title,
    description='Searchable spatiotemporal catalog describing datasets hosted on Cal-Adapt',
    settings=settings,
    client=CoreCrudClient(post_request_model=SearchPOSTRequest),
    extensions=EXTENSIONS,
    search_get_request_model=SearchGETRequest,
    search_post_request_model=SearchPOSTRequest,
    response_class=ORJSONResponse,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['GET', 'POST', 'OPTIONS'],
    allow_headers=['*']
)
handler = Mangum(app, lifespan='off')

if 'AWS_EXECUTION_ENV' in os.environ:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(app.router.startup())
