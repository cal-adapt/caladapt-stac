# Development Guide

## Architecture Overview

The Cal-Adapt STAC backend is two separate services:

1. **STAC API** (`stac.cal-adapt.org`) — metadata/discovery layer. Clients query it to find datasets. Built with `stac-fastapi` + `pgstac`.
2. **CalAdapt-Tiler** (`map.cal-adapt.org`) — data serving layer. Takes a Zarr S3 href from STAC and renders map tiles / extracts point data and statistics. Built on TiTiler/xarray. Lives in a separate repo.

Intended workflow: query STAC `/search` → get asset href (`s3://cadcat/...`) → pass to Tiler API → get tiles/data.

## How the pieces fit together

```
S3 keys → parse → pystac items → pypgstac → Postgres (pgSTAC) → stac-fastapi → HTTP API
```

| Piece | What it does | Local equivalent | AWS equivalent |
|---|---|---|---|
| pgSTAC (Postgres) | Stores STAC items/collections | Docker container | RDS |
| stac-fastapi | Serves the STAC API over HTTP | uvicorn | Lambda or ECS |
| pypgstac | Loads data into pgSTAC | same | same |

## Local Development

### 1. Start the database

Runs a local Postgres instance with pgSTAC pre-installed:

```bash
docker run -p 5432:5432 \
  -e POSTGRES_PASSWORD=password \
  ghcr.io/stac-utils/pgstac:latest
```

Local connection string: `postgresql://postgres:password@localhost:5432/pgstac`

### 2. Run the API

```bash
uv sync
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`.

### 3. Ingest data

Run the ingestion script to load climate profile collections into your local pgSTAC database:

```bash
uv run python scripts/ingest_climate_profiles.py
```

### 4. Browse

Point STAC Browser at your local API:

```
https://radiantearth.github.io/stac-browser/#/external/localhost:8000
```

## Production (AWS)

- **Database**: RDS Postgres in `us-west-2` with pgSTAC installed
- **API**: AWS Lambda (`CalAdaptStacApi`) via AWS SAM
- **Deployment**: `make deploy` (runs `sam build` + `sam deploy`)

The DB connection is configured via Lambda environment variables (not in the repo):
- `POSTGRES_HOST_READER`
- `POSTGRES_HOST_WRITER`
- `POSTGRES_USER`
- `POSTGRES_PASS`
- `POSTGRES_DBNAME`
- `POSTGRES_PORT`
