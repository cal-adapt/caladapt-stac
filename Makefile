format:
	uv run black .

build:
	uv export --no-dev --no-hashes -o app/requirements.txt
	sam build --cached --parallel

deploy: build
	sam deploy --profile era-de

run:
	uvicorn app.main:app --reload

ingest:
	uv run python -m scripts.ingest_all

geometries:
	uv run python -m scripts.generate_geometries
