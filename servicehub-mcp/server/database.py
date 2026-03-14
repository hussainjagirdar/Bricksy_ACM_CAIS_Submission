"""
Database connection management for ServiceHub.

Uses psycopg3 ConnectionPool with Databricks LakeBase OAuth authentication.
Falls back to PGPASSWORD for local development.
"""

import os
from contextlib import contextmanager

import psycopg
from psycopg_pool import ConnectionPool


_pool: ConnectionPool | None = None


def _create_pool() -> ConnectionPool:
    endpoint = os.getenv("PGENDPOINT", "")

    if endpoint:
        # Databricks Lakebase Autoscaling — use SDK OAuth token
        from databricks.sdk import WorkspaceClient
        ws = WorkspaceClient()

        # Resolve PGUSER from SDK if not explicitly set
        pg_user = os.getenv("PGUSER", "")
        if not pg_user:
            pg_user = ws.current_user.me().user_name

        conn_string = " ".join(filter(None, [
            f"dbname={os.getenv('PGDATABASE', 'databricks_postgres')}",
            f"user={pg_user}",
            f"host={os.getenv('PGHOST', 'localhost')}",
            f"port={os.getenv('PGPORT', '5432')}",
            f"sslmode={os.getenv('PGSSLMODE', 'require')}",
            f"application_name={os.getenv('PGAPPNAME', 'servicehub')}",
        ]))

        class OAuthConnection(psycopg.Connection):
            @classmethod
            def connect(cls, conninfo="", **kwargs):
                credential = ws.postgres.generate_database_credential(endpoint=endpoint)
                kwargs["password"] = credential.token
                return super().connect(conninfo, **kwargs)

        return ConnectionPool(conn_string, connection_class=OAuthConnection, min_size=2, max_size=10, open=True)

    # Local dev — use PGPASSWORD if set
    conn_string = " ".join(filter(None, [
        f"dbname={os.getenv('PGDATABASE', 'databricks_postgres')}",
        f"user={os.getenv('PGUSER', 'servicehub')}",
        f"host={os.getenv('PGHOST', 'localhost')}",
        f"port={os.getenv('PGPORT', '5432')}",
        f"sslmode={os.getenv('PGSSLMODE', 'require')}",
        f"application_name={os.getenv('PGAPPNAME', 'servicehub')}",
    ]))
    password = os.getenv("PGPASSWORD", "")
    if password:
        conn_string += f" password={password}"

    return ConnectionPool(conn_string, min_size=1, max_size=5, open=True)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = _create_pool()
    return _pool


@contextmanager
def get_connection():
    """Context manager that yields a psycopg3 connection from the pool."""
    with get_pool().connection() as conn:
        yield conn
