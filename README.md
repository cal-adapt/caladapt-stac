CalAdapt-STAC
=============
CalAdapt-STAC is a SpatioTemporal Asset Catalog (STAC) compliant [web API](https://stac.cal-adapt.org/docs) built with [stac-fastapi](https://stac-utils.github.io/stac-fastapi/) to serve the latest catalog of gridded climate data for Cal-Adapt, namely LOCA2 and WRF-CMIP6.


**README last updated:** April 2026

## Vocabulary

| Term | Meaning |
|---|---|
| **STAC** | SpatioTemporal Asset Catalog: a standard for describing geospatial datasets so they're searchable and interoperable. |
| **Collection** | A group of related STAC items (e.g. all LOCA2 county datasets). |
| **Item** | A single STAC record representing one dataset, with a location, time range, and links to the actual files (assets). |
| **Asset** | A file attached to a STAC item: e.g. a Zarr store or NetCDF file on S3. |
| **Queryable** | An item property registered in pgSTAC as a filterable field, enabling CQL2 search queries (e.g. `cmip6:source_id=CESM2`). |
| **pgSTAC** | A Postgres schema (tables, indexes, functions) designed for storing STAC catalogs. Installed into the database via `pypgstac migrate`. |
| **PGDSN** | PostgreSQL Data Source Name: a connection string of the form `postgresql://user:password@host:port/dbname`. Used by ingestion scripts to connect directly to RDS. |
| **RDS** | AWS Relational Database Service: managed cloud Postgres hosting. |
| **Lambda** | AWS serverless compute. The STAC API runs as a Lambda function, waking on demand to handle requests. |
| **SAM** | AWS Serverless Application Model: the tool used to build and deploy the Lambda function (`template.yaml`). |

## Architecture

```
Client → API Gateway → Lambda (stac-fastapi) → RDS Postgres (pgSTAC)
```

**API Gateway:** Public HTTPS endpoint. Forwards requests to Lambda and returns responses.

**Lambda** (`app/main.py`)**:** Runs stac-fastapi on demand. Handles STAC requests, queries the database, and returns results. Wrapped for Lambda using [Mangum](https://mangum.fastapiexpert.com/).

![Lambda functions](images/README/lambda_functions.png)
> To find the Cal-Adapt Lambda functions in the AWS console, make sure you're in the **us-west-2** region and then go to Lambda. The STAC API function appears here.

![main.py](images/README/code_source_main.png)
> The Lambda function runs `app/main.py`, which sets up the stac-fastapi application. It configures extensions, connects to the database, and wraps the app with Mangum so it can run inside Lambda.

**RDS Postgres:** Cloud-hosted Postgres with the pgSTAC schema installed: tables, spatial indexes, and functions for storing and querying STAC collections and items.

![RDS Database](images/README/rds_db.png)
> The RDS database can be found in the AWS console under RDS → Databases (make sure you're in **us-west-2**). It runs on a `db.t3.micro` instance. This is the smallest available tier and defines the CPU and memory allocated to the database. Costs ~$13/month.

![RDS Endpoint](images/README/endpoint.png)
> The RDS endpoint can be found under the **Connectivity & security** tab → **Additional configurations** → **Endpoint & port**.

The live API is at `https://stac.cal-adapt.org`. The raw API Gateway URL `https://8dawjspn5g.execute-api.us-west-2.amazonaws.com` redirects to `https://stac.cal-adapt.org`.

## Prerequisites

- [uv](https://docs.astral.sh/uv/): Python package manager
- [Docker](https://docs.docker.com/get-docker/): required for local development and SAM builds
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html): required for deployment and ingestion
- [AWS SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html): required for deployment
- [libpq](https://formulae.brew.sh/formula/libpq) (`brew install libpq`): required for direct database access via `psql`

  After installing, add it to your PATH:
  ```bash
  echo 'export PATH="/opt/homebrew/opt/libpq/bin:$PATH"' >> ~/.zshrc && source ~/.zshrc
  ```

You'll also need an AWS profile named `era-de` configured in `~/.aws/credentials` with access to the ERA AWS account.

## Setup

Install dependencies:

```bash
uv sync --all-groups
```

This installs all dependency groups defined in `pyproject.toml`:
- **default**: API runtime dependencies (`stac-fastapi-pgstac`, `mangum`, `psycopg`)
- **ingestion**: ingestion script dependencies (`pystac`, `pypgstac`, `boto3`, etc.)
- **dev**: development tools (`black`)

## Deployment

The API is deployed to AWS Lambda using [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html). SAM builds inside a Docker container to match Lambda's Linux runtime so native packages compile correctly on a Mac. Make sure Docker is running before deploying.

```bash
make deploy
```

This runs `sam build` (exports requirements, builds in Docker) followed by `sam deploy --profile era-de`. Deploy config is saved in `samconfig.toml` so no prompts are needed.

To get the deployed API URL:

```bash
aws cloudformation describe-stacks --stack-name caladapt-stac-v2 \
  --profile era-de --region us-west-2 \
  --query 'Stacks[0].Outputs'
```

## Ingestion

Ingestion scripts crawl S3, build pystac items, and load them directly into RDS via `pypgstac`. Direct loading uses SQL `COPY` (bulk insert) and bypasses the HTTP API entirely. This avoids API Gateway's 29-second timeout and is orders of magnitude faster for large collections.

All ingestion scripts require a `PGDSN` environment variable pointing at the RDS instance.

Retrieve the DB password and RDS endpoint from SSM:

```bash
aws ssm get-parameter --name /caladapt-stac/db-password \
  --with-decryption --profile era-de \
  --query Parameter.Value --output text

aws ssm get-parameter --name /caladapt-stac/db-host \
  --profile era-de \
  --query Parameter.Value --output text
```

If you don't have SSM access, request the values from a project maintainer. The RDS endpoint can also be found in the AWS Console under **RDS → Databases** (make sure you're in **us-west-2**). See the [architecture diagram](#architecture) above for reference.

Export `PGDSN` for your session (replace `PASSWORD` and `<RDS_ENDPOINT>` with the values from above):

```bash
export PGDSN='postgresql://postgres:PASSWORD@<RDS_ENDPOINT>:5432/caladapt?sslmode=require'
```

Ingest all collections:

```bash
make ingest-all
```

Or ingest a single collection (also registers queryables):

```bash
make clim-prof                  # typical-met-year, standard-year, xmy-persist, xmy-shock
make loca2-county               # LOCA2 county NetCDF
make loca2                      # LOCA2 gridded Zarr
make wrf-ucla                   # WRF UCLA
make eh-metrics-mm-boundary-csv # WRF extreme heat tool boundary CSV
make wrf-derived-vars           # WRF-derived climate metrics
make wrf-climate-metrics-map    # WRF climate metrics map
make hadisd                     # HadISD station Zarrs
make hdp                        # Historical Data Platform
make ren                        # PV + wind generation
make slr                        # Sea level projections
```

Queryables are item properties registered in pgSTAC as filterable fields. They tell the STAC API (and STAC Browser) which properties can be used in search queries (e.g. `countyname=Sacramento` or `cmip6:source_id=CESM2`). Each `make` target above registers queryables automatically after ingestion. To re-register without re-ingesting:

```bash
make queryables
```

## Operations

**Link checker:**

A GitHub Actions workflow (`.github/workflows/check-links.yml`) runs every Monday at 9am UTC and on every push to `main`. It fetches all collections from the live API and checks that every `related` link returns a valid response. Failed checks are reported in the Actions tab. You can also trigger it manually via `workflow_dispatch`.

**Delete a collection:**

If you change the structure of a collection (item IDs, properties, or asset keys), delete it before re-ingesting. Ingestion uses upsert, so stale items with old IDs or fields will remain alongside new ones unless the collection is cleared first.

Write endpoints are disabled on the public API, so deletion must be done directly via `psql` (requires `libpq` — see [Prerequisites](#prerequisites)):

```bash
psql $PGDSN -c "SELECT pgstac.delete_collection('{collection-id}');"
```

**Enable item count in search responses:**

pgSTAC's context setting controls whether the API returns `numberMatched` (total items matching a query) in search responses. This is a database-level setting and must be configured directly via `psql`:

```bash
psql $PGDSN -c "INSERT INTO pgstac.pgstac_settings (name, value) VALUES ('context', 'auto') ON CONFLICT (name) DO UPDATE SET value = 'auto';"
```

`'auto'` uses estimated counts (fast). This only needs to be run once after the database is created.

**Update collection icons:**

Icons in `images/icons/` are used as `thumbnail` assets on STAC collections and displayed in STAC Browser. They're served directly from GitHub via raw URLs, so they must be committed and pushed to `main` to take effect. Re-run the relevant ingestion script after updating an icon to push the new URL to the database.

These icons were generated in the AE Jupyter Hub because the scripts rely on `climakitae`, which wasn't included as a dependency of this repository. 

**Regenerate item geometry GeoJSON files:**

Some collections (county, station-based) attach a GeoJSON file as a collection-level `item-geometries` asset, hosted on S3. It contains the geometries (county boundaries or station coordinates) associated with the items in that collection.

`make geometries` regenerates these files from source data (S3 parquet/CSVs) and writes them to `data/geometries/`. After running it, upload the files to `s3://cadcat/geometries/` so the live URLs stay current:

```bash
make geometries
aws s3 cp data/geometries/ s3://cadcat/geometries/ --recursive --profile era-de
```

## Database setup (first time only)

Use the CLI for these steps. The AWS console had a bug that prevented RDS from being configured correctly.

Create the RDS instance:

```bash
aws --profile era-de rds create-db-instance \
  --db-instance-identifier caladapt-stac-v2 \
  --db-instance-class db.t3.micro \
  --engine postgres --engine-version 16 \
  --master-username postgres --master-user-password "PASSWORD" \
  --db-name caladapt --allocated-storage 20 --storage-type gp2 \
  --no-multi-az --region us-west-2
```

Store the password in SSM:

```bash
aws --profile era-de ssm put-parameter \
  --name /caladapt-stac/db-password \
  --value "PASSWORD" --type SecureString --region us-west-2
```

Install the pgSTAC schema:

```bash
uv run pypgstac migrate --dsn 'postgresql://postgres:PASSWORD@<host>:5432/caladapt?sslmode=require'
```

## Local Development

Local development is only needed for testing changes to `app/main.py`. Ingestion and queryable scripts always run against the live RDS instance via `PGDSN`. There is no local equivalent for those.

The local database DSN is:

```bash
export PGDSN='postgresql://postgres@localhost:5432/postgis'
```

Export this before running any ingestion commands.

    make run

```bash
docker run -p 5432:5432 \
  -e POSTGRES_HOST_AUTH_METHOD=trust \
  ghcr.io/stac-utils/pgstac:latest
```

**2. Run the pgSTAC migration**

```bash
uv run pypgstac migrate --dsn $PGDSN
```

**3. Run the API**

```bash
make run
```


**4. Ingest data**

```bash
make clim-prof
```

**5. Browse**

Point [STAC Browser](https://stac-browser.cal-adapt.org) at your local API:

```
https://stac-browser.cal-adapt.org/#/external/localhost:8000
```
