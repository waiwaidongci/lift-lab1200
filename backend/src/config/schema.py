"""Additive schema compatibility for databases created before strata registration.

``Base.metadata.create_all`` never alters an existing table, so a database
seeded before this feature would miss ``experiments.strata_bounds``. Startup
applies only this reviewed, additive column (never destructive changes); larger
schema changes still belong in reviewed migration files. Existing rows receive
NULL, which the analysis treats as "keep the original unstratified method".
"""
import logging
from sqlalchemy import inspect, text
from .database import engine

ADDITIVE_COLUMNS = {"experiments": [("strata_bounds", "JSON")]}


def ensure_schema():
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    for table, columns in ADDITIVE_COLUMNS.items():
        if table not in tables:
            continue
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, ddl_type in columns:
            if name in existing:
                continue
            clause = "ADD COLUMN IF NOT EXISTS" if engine.dialect.name == "postgresql" else "ADD COLUMN"
            try:
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE {table} {clause} {name} {ddl_type}"))
            except Exception:
                # Another process may have added it concurrently; verify before failing.
                inspector = inspect(engine)
                if name not in {column["name"] for column in inspector.get_columns(table)}:
                    raise
                logging.info("column %s.%s already added concurrently", table, name)
