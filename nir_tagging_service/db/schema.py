from __future__ import annotations

from sqlalchemy import inspect
from sqlalchemy.engine import Connection


def ensure_runtime_schema(connection: Connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    if "tagging_jobs" not in tables:
        return

    columns = {column["name"] for column in inspector.get_columns("tagging_jobs")}
    if "progress_json" not in columns:
        connection.exec_driver_sql(
            "ALTER TABLE tagging_jobs ADD COLUMN progress_json JSON NOT NULL DEFAULT '{}'"
        )
