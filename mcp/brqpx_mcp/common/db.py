from contextlib import contextmanager
from typing import Any

import pyodbc

from brqpx_mcp.common.settings import settings


class DatabaseNotConfiguredError(RuntimeError):
    pass


@contextmanager
def connect():
    if not settings.portal_bau_connection_string:
        raise DatabaseNotConfiguredError(
            "PORTAL_BAU_STAGING_CONNECTION_STRING is not configured"
        )

    connection = pyodbc.connect(settings.portal_bau_connection_string, timeout=10)
    try:
        yield connection
    finally:
        connection.close()


def fetch_one(query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(query, params)
        row = cursor.fetchone()
        if row is None:
            return None
        columns = [column[0] for column in cursor.description]
        return dict(zip(columns, row))


def fetch_all(query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    with connect() as connection:
        cursor = connection.cursor()
        cursor.execute(query, params)
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def ping() -> dict[str, Any]:
    row = fetch_one("SELECT DB_NAME() AS database_name, @@SERVERNAME AS server_name")
    return {"ok": True, **(row or {})}
