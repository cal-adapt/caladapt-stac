check:
	python -Wall -m unittest -v

build:
	sam build --cached --parallel

deploy: build
	sam deploy

run:
	uvicorn app.main:app --reload
