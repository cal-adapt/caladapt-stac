format:
	uv run black .

build:
	uv export --no-dev --no-hashes -o app/requirements.txt
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
	$(MAKE) wrf-extreme-heat-tool-county
	$(MAKE) wrf-extreme-heat-tool-county-csv
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

loca2-county:
	uv run python -m scripts.ingest_loca2_county
	uv run python -m scripts.register_queryables --collection loca2-county

loca2:
	uv run python -m scripts.ingest_loca2
	uv run python -m scripts.register_queryables --collection loca2

wrf-ucla:
	uv run python -m scripts.ingest_wrf_ucla
	uv run python -m scripts.register_queryables --collection wrf-ucla

wrf-extreme-heat-tool-county:
	uv run python -m scripts.ingest_wrf_extreme_heat_tool
	uv run python -m scripts.register_queryables --collection wrf-extreme-heat-tool-county

wrf-extreme-heat-tool-county-csv:
	uv run python -m scripts.ingest_wrf_extreme_heat_tool_county_csv
	uv run python -m scripts.register_queryables --collection wrf-extreme-heat-tool-county-csv

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
