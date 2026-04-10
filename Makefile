format:
	uv run black .

build:
	uv export --no-dev --no-hashes -o app/requirements.txt
	sam build --use-container --cached --parallel

deploy: build
	sam deploy --profile era-de

run:
	uv run python -m uvicorn app.main:app --reload

ingest:
	$(MAKE) typical-met-year
	$(MAKE) standard-met-year
	$(MAKE) loca2-county
	$(MAKE) loca2-gridded
	$(MAKE) wrf-ucla
	$(MAKE) hadisd
	$(MAKE) hdp
	$(MAKE) renewables

queryables:
	uv run python -m scripts.register_queryables

typical-met-year:
	uv run python -m scripts.ingest_climate_profiles
	uv run python -m scripts.register_queryables --collection typical-met-year

standard-met-year:
	uv run python -m scripts.ingest_climate_profiles
	uv run python -m scripts.register_queryables --collection standard-met-year

loca2-county:
	uv run python -m scripts.ingest_loca2_county
	uv run python -m scripts.register_queryables --collection loca2-county

loca2-gridded:
	uv run python -m scripts.ingest_loca2
	uv run python -m scripts.register_queryables --collection loca2-gridded

wrf-ucla:
	uv run python -m scripts.ingest_wrf_ucla
	uv run python -m scripts.register_queryables --collection wrf-ucla

hadisd:
	uv run python -m scripts.ingest_hadisd
	uv run python -m scripts.register_queryables --collection hadisd-station-zarrs

hdp:
	uv run python -m scripts.ingest_hdp
	uv run python -m scripts.register_queryables --collection historical-data-platform

renewables:
	uv run python -m scripts.ingest_ren
	uv run python -m scripts.register_queryables --collection pv-generation
	uv run python -m scripts.register_queryables --collection wind-generation

geometries:
	uv run python -m scripts.generate_geometries
