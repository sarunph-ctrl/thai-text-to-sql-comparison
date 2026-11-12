"""Validated, secret-resistant JSONL records for reproducible evaluation runs."""
from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Iterable
from uuid import uuid4


RECORD_VERSION = "1.0"
REQUIRED_FIELDS = {
    "experiment_id",
    "case_id",
    "split",
    "snapshot_id",
    "method",
    "repeat_index",
    "scope_label",
    "status",
    "execution_correct",
    "sql_valid",
    "sql_executed",
    "columns",
    "rows",
    "ordered",
    "method_ms",
}
OPTIONAL_FIELDS = {
    "record_version",
    "run_id",
    "recorded_at",
    "code_commit",
    "family",
    "generated_sql",
    "result_fingerprint",
    "generation_ms",
    "validation_ms",
    "database_ms",
    "input_tokens",
    "output_tokens",
    "timed_out",
    "truncated",
    "error_category",
    "message",
    "provider",
    "model",
    "prompt_version",
    "retries",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | OPTIONAL_FIELDS
FORBIDDEN_KEYS = {
    "api_key",
    "llm_api_key",
    "authorization",
    "password",
    "secret",
    "access_token",
    "refresh_token",
    "bearer",
}
SECRET_VALUE = re.compile(r"(?:Bearer\s+\S+|sk_[A-Za-z0-9]{16,})", re.IGNORECASE)


class InvalidRunRecord(ValueError):
    """Raised when a raw run is incomplete, unsafe, or not serializable."""


def _canonical_cell(value: Any) -> list[Any]:
    if value is None:
        return ["null", None]
    if isinstance(value, bool):
        return ["bool", value]
    if isinstance(value, (int, float, Decimal)):
        return ["number", str(Decimal(str(value)).normalize())]
    if isinstance(value, (date, datetime)):
        return ["date", value.isoformat()]
    return ["text", str(value)]


def result_fingerprint(*, status: str, columns: list[str], rows: list[list[Any]], ordered: bool) -> str:
    """Hash normalized output; unordered rows are sorted while duplicates remain."""
    canonical_rows = [[_canonical_cell(value) for value in row] for row in rows]
    if not ordered:
        canonical_rows = sorted(
            canonical_rows,
            key=lambda row: json.dumps(row, ensure_ascii=False, separators=(",", ":")),
        )
    payload = {
        "status": status,
        "columns": columns,
        "rows": canonical_rows,
        "ordered": ordered,
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _walk_for_secrets(value: Any, path: str = "record") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key).casefold() in FORBIDDEN_KEYS:
                raise InvalidRunRecord(f"forbidden secret field: {path}.{key}")
            _walk_for_secrets(nested, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _walk_for_secrets(nested, f"{path}[{index}]")
    elif isinstance(value, str) and SECRET_VALUE.search(value):
        raise InvalidRunRecord(f"possible secret value at {path}")


def _nonnegative_number_or_none(record: dict[str, Any], field: str) -> None:
    value = record.get(field)
    if value is not None and (
        not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0
    ):
        raise InvalidRunRecord(f"{field} must be a non-negative number or null")


def validate_run_record(record: dict[str, Any]) -> None:
    if not isinstance(record, dict):
        raise InvalidRunRecord("record must be an object")
    missing = REQUIRED_FIELDS - set(record)
    unknown = set(record) - ALLOWED_FIELDS
    if missing:
        raise InvalidRunRecord("missing fields: " + ", ".join(sorted(missing)))
    if unknown:
        raise InvalidRunRecord("unknown fields: " + ", ".join(sorted(unknown)))
    _walk_for_secrets(record)

    for field in ("experiment_id", "case_id", "snapshot_id", "status"):
        if not isinstance(record[field], str) or not record[field]:
            raise InvalidRunRecord(f"{field} must be a non-empty string")
    if record["split"] not in {"development", "heldout"}:
        raise InvalidRunRecord("split must be development or heldout")
    if record["method"] not in {"rule", "llm"}:
        raise InvalidRunRecord("method must be rule or llm")
    if record["scope_label"] not in {"in_scope", "out_of_scope"}:
        raise InvalidRunRecord("scope_label must be in_scope or out_of_scope")
    if not isinstance(record["repeat_index"], int) or isinstance(record["repeat_index"], bool) or record["repeat_index"] < 1:
        raise InvalidRunRecord("repeat_index must be a positive integer")
    for field in ("execution_correct", "sql_executed", "ordered"):
        if not isinstance(record[field], bool):
            raise InvalidRunRecord(f"{field} must be boolean")
    if record["sql_valid"] is not None and not isinstance(record["sql_valid"], bool):
        raise InvalidRunRecord("sql_valid must be boolean or null")
    if not isinstance(record["columns"], list) or not all(isinstance(column, str) for column in record["columns"]):
        raise InvalidRunRecord("columns must be a list of strings")
    if not isinstance(record["rows"], list) or not all(isinstance(row, list) for row in record["rows"]):
        raise InvalidRunRecord("rows must be a list of lists")
    if any(len(row) != len(record["columns"]) for row in record["rows"]):
        raise InvalidRunRecord("every row must match the column count")
    for field in ("method_ms", "generation_ms", "validation_ms", "database_ms"):
        _nonnegative_number_or_none(record, field)
    for field in ("input_tokens", "output_tokens", "retries"):
        value = record.get(field)
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            raise InvalidRunRecord(f"{field} must be a non-negative integer or null")
    if record["scope_label"] == "out_of_scope" and record["status"] == "unsupported" and record["sql_executed"]:
        raise InvalidRunRecord("an unsupported result cannot execute SQL")


def finalize_run_record(record: dict[str, Any]) -> dict[str, Any]:
    """Add immutable metadata and a normalized result fingerprint."""
    finalized = dict(record)
    finalized.setdefault("record_version", RECORD_VERSION)
    finalized.setdefault("run_id", str(uuid4()))
    finalized.setdefault("recorded_at", datetime.now(timezone.utc).isoformat())
    finalized["result_fingerprint"] = result_fingerprint(
        status=finalized["status"],
        columns=finalized["columns"],
        rows=finalized["rows"],
        ordered=finalized["ordered"],
    )
    validate_run_record(finalized)
    return finalized


def append_jsonl(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Validate and append one UTF-8 JSON object; raw output paths are gitignored."""
    finalized = finalize_run_record(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(finalized, ensure_ascii=False, sort_keys=True) + "\n")
    return finalized


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
            validate_run_record(record)
        except (json.JSONDecodeError, InvalidRunRecord) as exc:
            raise InvalidRunRecord(f"{path}:{line_number}: {exc}") from exc
        records.append(record)
    return records


def group_by_method(records: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {"rule": [], "llm": []}
    for record in records:
        grouped[record["method"]].append(record)
    return {method: values for method, values in grouped.items() if values}
