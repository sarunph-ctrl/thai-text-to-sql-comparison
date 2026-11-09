"""Real PostgreSQL tests in disposable schemas, using the local demo cluster.

No pgserver dependency and no writes to the presentation database.
"""
from __future__ import annotations
import pathlib
from uuid import uuid4
import psycopg
from psycopg import sql

from scripts.local_demo import connection_string

ROOT = pathlib.Path(__file__).resolve().parent.parent


class TestConnection(psycopg.Connection):
    def close(self):
        if not self.closed:
            try:
                self.rollback()
                if getattr(self, "test_schema", None):
                    self.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(self.test_schema)))
            finally:
                super().close()


def fresh_conn(*, demo: bool = False) -> psycopg.Connection:
    """Every test gets a disposable schema in seminar_tests, never demo data."""
    conn = TestConnection.connect(connection_string(admin=True, database="seminar_tests"), autocommit=True)
    conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public")
    conn.test_schema = "test_" + uuid4().hex
    conn.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(conn.test_schema)))
    conn.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(conn.test_schema)))
    prefix = "demo_" if demo else ""
    try:
        conn.execute((ROOT / "db" / f"{prefix}schema.sql").read_text(encoding="utf-8"))
        conn.execute((ROOT / "db" / f"{prefix}seed.sql").read_text(encoding="utf-8"))
        if demo:
            conn.execute((ROOT / "db/demo_inventory_seed.sql").read_text(encoding="utf-8"))
    except Exception:
        conn.close()
        raise
    return conn
