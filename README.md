# caladapt-stac

STAC API for Cal-Adapt climate datasets, built with [stac-fastapi](https://github.com/stac-utils/stac-fastapi) and [pgSTAC](https://github.com/stac-utils/pgstac).

## Setup

Install dependencies with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

## Local Testing

Local testing requires [Docker](https://docs.docker.com/get-docker/) to run a pgSTAC Postgres database. In production, this is replaced by RDS.

**1. Start the database**

```bash
docker run -p 5432:5432 \
  -e POSTGRES_PASSWORD=password \
  ghcr.io/stac-utils/pgstac:latest
```

**2. Run the API**

```bash
uvicorn app.main:app --reload
```

API will be available at `http://localhost:8000`.

**3. Ingest data**

```bash
uv run python scripts/ingest_climate_profiles.py
```

**4. Browse**

Point [STAC Browser](https://radiantearth.github.io/stac-browser/) at your local API:

```
https://radiantearth.github.io/stac-browser/#/external/localhost:8000
```
