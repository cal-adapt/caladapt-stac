"""ingest_all.py

Run all ingestion scripts to populate the STAC API with all collections.

Usage:
    uv run python scripts/ingest_all.py

Requires:
    - AWS credentials with read access to the cadcat S3 bucket
    - A running STAC API at STAC_API_ENDPOINT (defaults to http://localhost:8000)

"""

from scripts.ingest_climate_profiles import main as ingest_climate_profiles
from scripts.ingest_hadisd import main as ingest_hadisd
from scripts.ingest_hdp import main as ingest_hdp
from scripts.ingest_loca2_county import main as ingest_loca2_county
from scripts.register_queryables import main as register_queryables


def main():
    print("Ingesting climate profiles...")
    ingest_climate_profiles()
    print("Climate profiles complete.")

    print("Ingesting LOCA2 county...")
    ingest_loca2_county()
    print("LOCA2 county complete.")

    print("Ingesting HDP...")
    ingest_hdp()
    print("HDP complete.")

    print("Ingesting HadISD...")
    ingest_hadisd()
    print("HadISD complete.")

    print("Registering queryables...")
    register_queryables()
    print("Done.")


if __name__ == "__main__":
    main()
