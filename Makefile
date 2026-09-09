format:
	uv run black .

build:
	uv export --no-group dev --no-group ingestion --no-hashes -o app/requirements.txt
	sam build --use-container --cached --parallel

deploy: build
	sam deploy --profile era-de

run:
	uv run python -m uvicorn app.main:app --reload

ingest-all:
	$(MAKE) clim-prof
	$(MAKE) loca2-county
	$(MAKE) loca2
	$(MAKE) wrf-ucla
	$(MAKE) eh-metrics-mm-boundary-csv
	$(MAKE) hdd-cdd-metrics-mm-boundary-csv
	$(MAKE) wrf-derived-vars
	$(MAKE) wrf-climate-metrics-map
	$(MAKE) hadisd
	$(MAKE) hdp
	$(MAKE) ren
	$(MAKE) slr

queryables:
	uv run python -m scripts.register_queryables

clim-prof:
	uv run python -m scripts.ingest_climate_profiles
	uv run python -m scripts.register_queryables --collection typical-met-year
	uv run python -m scripts.register_queryables --collection standard-year
	uv run python -m scripts.register_queryables --collection xmy-persist
	uv run python -m scripts.register_queryables --collection xmy-shock

loca2-county:
	uv run python -m scripts.ingest_loca2_county
	uv run python -m scripts.register_queryables --collection loca2-county

loca2:
	uv run python -m scripts.ingest_loca2
	uv run python -m scripts.register_queryables --collection loca2

wrf-ucla:
	uv run python -m scripts.ingest_wrf_ucla
	uv run python -m scripts.register_queryables --collection wrf-ucla

# CloudFront distribution fronting stac.cal-adapt.org. Its cache policy
# (CachingOptimizedQueryParams) caches /search responses for up to 7 days
# keyed on the full query string, including ones with 0 results. Ingesting
# a brand-new collection after a client has already searched for it (and
# gotten cached as empty) leaves that exact query stuck returning nothing
# until this is invalidated. Only wired into the ingest targets that back a
# live web tool doing on-demand STAC searches (extreme heat, hdd/cdd) --
# not the other collections, which aren't queried this way.
STAC_CLOUDFRONT_DISTRIBUTION_ID := E2ON6INEGWTHQ1

invalidate-search-cache:
	aws cloudfront create-invalidation \
		--distribution-id $(STAC_CLOUDFRONT_DISTRIBUTION_ID) \
		--paths "/search*" \
		--profile era-de

eh-metrics-mm-boundary-csv:
	uv run python -m scripts.ingest_wrf_extreme_heat_tool_boundary_csv
	uv run python -m scripts.register_queryables --collection eh-metrics-mm-boundary-csv
	$(MAKE) invalidate-search-cache

hdd-cdd-metrics-mm-boundary-csv:
	uv run python -m scripts.ingest_wrf_hdd_cdd_tool_boundary_csv
	uv run python -m scripts.register_queryables --collection hdd-cdd-metrics-mm-boundary-csv
	$(MAKE) invalidate-search-cache

wrf-derived-vars:
	uv run python -m scripts.ingest_wrf_derived_vars
	uv run python -m scripts.register_queryables --collection wrf-derived-vars

wrf-climate-metrics-map:
	uv run python -m scripts.ingest_wrf_climate_metrics_map
	uv run python -m scripts.register_queryables --collection wrf-climate-metrics-map

hadisd:
	uv run python -m scripts.ingest_hadisd
	uv run python -m scripts.register_queryables --collection hadisd

hdp:
	uv run python -m scripts.ingest_hdp
	uv run python -m scripts.register_queryables --collection historical-data-platform

ren:
	uv run python -m scripts.ingest_ren
	uv run python -m scripts.register_queryables --collection pv-generation
	uv run python -m scripts.register_queryables --collection wind-generation

slr:
	uv run python -m scripts.ingest_sea_level
	uv run python -m scripts.register_queryables --collection sea-level-projections

geometries:
	uv run python -m scripts.generate_geometries
