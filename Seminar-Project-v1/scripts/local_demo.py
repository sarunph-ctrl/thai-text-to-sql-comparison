"""Manage ONLY the isolated PostgreSQL cluster in this project's .local folder.

python -m scripts.local_demo start|upgrade-inventory|reset|add-sale|status|stop
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from datetime import datetime

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / ".local"
DATA = LOCAL / "postgres"
CONFIG = LOCAL / "connection.json"


def settings() -> dict:
    if not CONFIG.exists():
        raise RuntimeError("Run: python -m scripts.local_demo start")
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def connection_string(*, admin: bool = False, database: str = "seminar_demo") -> str:
    c = settings()
    return make_conninfo(host="127.0.0.1", port=c["port"], dbname=database,
                         user="seminar_admin" if admin else "seminar_reader",
                         password=c["admin_password"] if admin else c["reader_password"],
                         connect_timeout=5, options="-c timezone=Asia/Bangkok")


def pg_bin() -> Path:
    if os.environ.get("PG_BIN"):
        return Path(os.environ["PG_BIN"])
    candidates = list(Path(r"C:\Program Files\PostgreSQL").glob("*/bin"))
    candidates.sort(key=lambda p: int(p.parent.name), reverse=True)
    if not candidates:
        raise RuntimeError("PostgreSQL binaries missing. Set PG_BIN to the bin folder.")
    return candidates[0]


def pg_run(program: str, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    # Real files avoid a Windows pg_ctl child inheriting a PIPE and preventing
    # communicate() from returning after the server has successfully started.
    with tempfile.TemporaryFile() as output:
        raw = subprocess.run([str(pg_bin() / f"{program}.exe"), *args],
                             stdout=output, stderr=output, timeout=60,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        output.seek(0)
        result = subprocess.CompletedProcess(raw.args, raw.returncode,
                                             output.read().decode("utf-8", errors="replace"), "")
    if check and result.returncode:
        raise RuntimeError(f"{program} failed:\n{result.stdout}\n{result.stderr}")
    return result


def start() -> None:
    LOCAL.mkdir(exist_ok=True)
    if not CONFIG.exists():
        if DATA.exists():
            raise RuntimeError("Existing cluster has no connection config; preserve it and investigate.")
        CONFIG.write_text(json.dumps({"port": 55439, "admin_password": secrets.token_urlsafe(24),
                                      "reader_password": secrets.token_urlsafe(24)}), encoding="utf-8")
    if not (DATA / "PG_VERSION").exists():
        pwfile = LOCAL / "init-password.txt"
        pwfile.write_text(settings()["admin_password"] + "\n", encoding="utf-8")
        try:
            pg_run("initdb", "-D", str(DATA), "-U", "seminar_admin", "-A", "scram-sha-256",
                   "--pwfile", str(pwfile), "--encoding=UTF8", "--locale=C")
        finally:
            pwfile.unlink(missing_ok=True)
    # Probe the authenticated endpoint rather than inspecting a Windows
    # process owned by another token (e.g. the desktop sandbox account).
    running = False
    try:
        with psycopg.connect(connection_string(admin=True, database="postgres")) as probe:
            probe.execute("SELECT 1")
            running = True
    except psycopg.OperationalError:
        pass
    if not running:
        pg_run("pg_ctl", "-D", str(DATA), "-l", str(LOCAL / "postgres.log"),
               "-o", f"-h 127.0.0.1 -p {settings()['port']}", "-w", "-t", "30", "start")
    with psycopg.connect(connection_string(admin=True, database="postgres"), autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname = 'seminar_reader'").fetchone():
            conn.execute(sql.SQL("CREATE ROLE seminar_reader LOGIN PASSWORD {}").format(
                sql.Literal(settings()["reader_password"])))
        for name in ("seminar_demo", "seminar_tests"):
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
                conn.execute(sql.SQL("CREATE DATABASE {} OWNER seminar_admin").format(sql.Identifier(name)))
        conn.execute("ALTER ROLE seminar_reader SET default_transaction_read_only = on")
    with psycopg.connect(connection_string(admin=True), autocommit=True) as conn:
        if not conn.execute("SELECT to_regclass('public.products')").fetchone()[0]:
            reset()
        elif not conn.execute("SELECT to_regclass('public.stock_movements')").fetchone()[0]:
            upgrade_inventory()
    print("PostgreSQL demo ready: 127.0.0.1:55439 / seminar_demo")


def reset() -> None:
    # Called only against the named database in our own cluster. SQL truncates
    # only its five demo tables; the user's existing PostgreSQL is untouched.
    with psycopg.connect(connection_string(admin=True)) as conn:
        conn.execute((ROOT / "db/demo_schema.sql").read_text(encoding="utf-8"))
        conn.execute((ROOT / "db/demo_seed.sql").read_text(encoding="utf-8"))
        conn.execute((ROOT / "db/demo_inventory_seed.sql").read_text(encoding="utf-8"))
        conn.execute("GRANT USAGE ON SCHEMA public TO seminar_reader")
        conn.execute("GRANT SELECT ON products, orders, order_items, warehouses, stock_movements TO seminar_reader")
    print("Demo reset: 5 products, 10 orders, 19 items, 2 warehouses, 29 movements. September revenue = 1250.00 THB")


def upgrade_inventory() -> None:
    """Backup first, then add inventory without replacing any sales rows."""
    backups = LOCAL / "backups"
    backups.mkdir(exist_ok=True)
    backup = backups / f"before-inventory-{datetime.now():%Y%m%d-%H%M%S-%f}.sql"
    env = dict(os.environ, PGPASSWORD=settings()["admin_password"])
    result = subprocess.run(
        [str(pg_bin() / "pg_dump.exe"), "-h", "127.0.0.1", "-p", str(settings()["port"]),
         "-U", "seminar_admin", "-d", "seminar_demo", "--no-owner", "--no-privileges", "-f", str(backup)],
        env=env, capture_output=True, text=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0), timeout=60,
    )
    if result.returncode or not backup.exists() or backup.stat().st_size == 0:
        raise RuntimeError("Backup failed; database not modified. " + result.stderr)
    with psycopg.connect(connection_string(admin=True)) as conn:
        conn.execute((ROOT / "db/demo_schema.sql").read_text(encoding="utf-8"))
        counts = conn.execute("SELECT (SELECT count(*) FROM warehouses), (SELECT count(*) FROM stock_movements)").fetchone()
        if counts == (0, 0):
            conn.execute((ROOT / "db/demo_inventory_seed.sql").read_text(encoding="utf-8"))
        conn.execute("GRANT SELECT ON warehouses, stock_movements TO seminar_reader")
    print("Inventory schema upgraded; sales rows preserved. Backup:", backup)


def add_sale() -> None:
    with psycopg.connect(connection_string(admin=True)) as conn:
        # Fixed ID makes the presentation step repeatable, never accumulating.
        exists = conn.execute("SELECT 1 FROM orders WHERE id = 11").fetchone()
        if not exists:
            conn.execute("INSERT INTO orders (id, order_date, status) VALUES (11, '2026-09-25', 'paid')")
            conn.execute("INSERT INTO order_items (order_id, product_id, qty, unit_price) VALUES (11, 1, 20, 15)")
    print("Demo sale present: pen +20 x 15 = +300 THB. September paid revenue = 1550.00 THB")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "upgrade-inventory", "reset", "add-sale", "status", "stop"])
    args = parser.parse_args()
    if args.action == "start":
        start()
    elif args.action == "reset":
        reset()
    elif args.action == "upgrade-inventory":
        upgrade_inventory()
    elif args.action == "add-sale":
        add_sale()
    elif args.action == "status":
        with psycopg.connect(connection_string()) as conn:
            print(conn.execute("SELECT current_database(), current_user, count(*) FROM orders").fetchone())
    elif DATA.exists():
        pg_run("pg_ctl", "-D", str(DATA), "-m", "fast", "-w", "stop")
        print("Local demo cluster stopped.")


if __name__ == "__main__":
    main()
