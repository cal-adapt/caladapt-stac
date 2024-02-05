CalAdapt-STAC
=============
CalAdapt-STAC is a SpatioTemporal Asset Catalog (STAC) compliant web API built with [stac-fastapi](https://stac-utils.github.io/stac-fastapi/) to serve the latest catalog of gridded climate data for Cal-Adapt, namely LOCA2 and WRF-CMIP6.


Installation
------------
Create a virtualenv first, and then install project dependencies with pip:

    pip install -r app/requirements.txt


Basic Usage
-----------
Run a local development server with uvicorn:
    
	uvicorn app.main:app --reload

Point your browser to  the interactive, OpenAPI-based, API documentation with a list of endpoints and filtering capabilities at http://localhost:8000/docs.
