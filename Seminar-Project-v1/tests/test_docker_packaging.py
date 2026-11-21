from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def compose_config() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.yml").read_text(encoding="utf-8"))


def test_compose_uses_private_database_and_readonly_app_role():
    config = compose_config()
    postgres = config["services"]["postgres_db"]
    app = config["services"]["app"]

    assert "ports" not in postgres
    assert any("postgres-init.sh:/docker-entrypoint-initdb.d/" in item for item in postgres["volumes"])
    assert not any("./db:/docker-entrypoint-initdb.d" in item for item in postgres["volumes"])
    assert "seminar_reader" in app["environment"]["DATABASE_URL"]
    assert "seminar_admin" not in app["environment"]["DATABASE_URL"]
    assert app["depends_on"]["postgres_db"]["condition"] == "service_healthy"


def test_image_runs_dashboard_as_non_root_from_locked_dependencies():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "COPY requirements-lock.txt" in dockerfile
    assert "USER appuser" in dockerfile
    assert "PYTHAINLP_DATA=/home/appuser/pythainlp-data" in dockerfile
    assert "chown -R appuser:appuser /home/appuser" in dockerfile
    assert '"demo_dashboard:app"' in dockerfile
    assert "COPY .env" not in dockerfile


def test_init_script_loads_only_selected_demo_schema_and_grants_select():
    script = (ROOT / "docker" / "postgres-init.sh").read_text(encoding="utf-8")
    expected_files = {
        "demo_schema.sql",
        "demo_seed.sql",
        "demo_inventory_seed.sql",
        "wms_mvp_schema.sql",
        "wms_mvp_seed.sql",
    }

    referenced = {
        path.name
        for path in (ROOT / "db").glob("*.sql")
        if f"/project-db/{path.name}" in script
    }
    assert referenced == expected_files
    assert "default_transaction_read_only = on" in script
    assert "GRANT SELECT ON" in script
    assert script.startswith("#!/bin/sh\n")
    assert "\r\n" not in script


def test_docker_context_excludes_local_secrets_and_runtime_state():
    patterns = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".env.*" in patterns
    assert ".local" in patterns
    assert "output/wms_mvp/raw" in patterns
