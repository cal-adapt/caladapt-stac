"""register_queryables.py

Register queryable properties in pgSTAC scoped to each collection, by discovering
all unique property keys from items already in the database.

Queryables tell the STAC API (and STAC Browser) which item properties can be
used as filters in search queries (e.g. countyname, cmip6:source_id).

This script should be run after ingestion so all item properties are present.

Usage:
    uv run python -m scripts.register_queryables

Requires:
    - PGDSN environment variable with a valid PostgreSQL DSN, e.g.:
      postgresql://postgres:password@host:5432/caladapt?sslmode=require

"""

import argparse
import json
import psycopg

from scripts.constants import PGDSN

# Built-in STAC properties handled natively by pgSTAC — skip these
BUILTIN_PROPERTIES = {
    "datetime",
    "start_datetime",
    "end_datetime",
    "created",
    "updated",
}


MAX_ENUM_VALUES = 200  # Register as enum if distinct value count is at or below this


def get_collection_property_keys(conn):
    """Return a dict mapping collection_id to its list of unique property keys."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT i.collection, key
            FROM pgstac.items i,
            jsonb_object_keys(i.content->'properties') AS key
        """)
        result = {}
        for collection_id, key in cur.fetchall():
            result.setdefault(collection_id, []).append(key)
        return result


def get_distinct_values(conn, collection_id, key):
    """Return sorted list of distinct values for a property, or None if too many."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(DISTINCT i.content->'properties'->>%s)
            FROM pgstac.items i
            WHERE i.collection = %s
        """,
            (key, collection_id),
        )
        count = cur.fetchone()[0]
        if count > MAX_ENUM_VALUES:
            return None
        cur.execute(
            """
            SELECT DISTINCT i.content->'properties'->>%s AS val
            FROM pgstac.items i
            WHERE i.collection = %s
              AND i.content->'properties'->>%s IS NOT NULL
            ORDER BY val
        """,
            (key, collection_id, key),
        )
        return [row[0] for row in cur.fetchall()]


def clear_queryables(conn, collection_id=None):
    """Remove registered queryables — scoped to one collection or all."""
    with conn.cursor() as cur:
        cur.execute("SET search_path TO pgstac, public")
        if collection_id:
            cur.execute(
                "DELETE FROM queryables WHERE collection_ids @> %s::text[]",
                ([collection_id],),
            )
        else:
            cur.execute("DELETE FROM queryables")
    conn.commit()


def register_queryables(conn, collection_keys):
    """Insert per-collection queryable definitions with enum values where available."""
    with conn.cursor() as cur:
        cur.execute("SET search_path TO pgstac, public")
        for collection_id, keys in collection_keys.items():
            filtered = [k for k in keys if k not in BUILTIN_PROPERTIES]
            for key in filtered:
                values = get_distinct_values(conn, collection_id, key)
                if values:
                    schema = {"type": "string", "enum": values}
                else:
                    schema = {"type": "string"}
                cur.execute(
                    """
                    INSERT INTO queryables (name, collection_ids, definition)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT DO NOTHING
                """,
                    (key, [collection_id], json.dumps(schema)),
                )
            print(f"  {collection_id}: {filtered}")
    conn.commit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--collection",
        help="Only re-register queryables for this collection ID. Omit to update all.",
    )
    args = parser.parse_args()

    if not PGDSN:
        raise RuntimeError("PGDSN environment variable is required")

    with psycopg.connect(PGDSN) as conn:
        print("  Clearing queryables...")
        clear_queryables(conn, collection_id=args.collection)
        collection_keys = get_collection_property_keys(conn)
        if args.collection:
            collection_keys = {
                k: v for k, v in collection_keys.items() if k == args.collection
            }
        print(f"  Registering queryables for {len(collection_keys)} collections...")
        register_queryables(conn, collection_keys)


if __name__ == "__main__":
    main()
