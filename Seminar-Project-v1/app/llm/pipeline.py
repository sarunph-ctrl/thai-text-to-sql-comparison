"""Generate -> parse JSON -> validate SELECT -> execute; no rule-based fallback."""
import json
from time import perf_counter

import psycopg

from app.llm.client import generate, LLMConfigurationError, LLMCallError
from app.llm.prompt import prompt_bundle
from app.llm.sql_guard import check_sql, execute_checked, SQLRejected


def decode_reply(content: str) -> dict:
    # A single JSON code fence is tolerated; prose plus SQL is not extracted.
    text = content.strip()
    if text.startswith("```json\n") and text.endswith("```"):
        text = text[8:-3].strip()
    if len(text) > 24000:
        raise ValueError("Model output exceeds limit")
    reply = json.loads(text)
    if not isinstance(reply, dict) or reply.get("status") not in ("ok", "unsupported"):
        raise ValueError("Model must return a JSON status object")
    if reply["status"] == "ok" and not isinstance(reply.get("sql"), str):
        raise ValueError("Successful reply must contain SQL")
    if reply["status"] == "unsupported" and reply.get("sql") is not None:
        raise ValueError("Unsupported reply must not contain SQL")
    return reply


def run_llm_pipeline(question: str, conn: psycopg.Connection, *, generator=None, manual_output: str | None = None) -> dict:
    start = perf_counter()
    bundle = prompt_bundle(question)
    result = {"method": "llm", "mode": "manual_output" if manual_output is not None else "live_api",
              "question": question, "status": "llm_error", "message": None,
              "prompt_version": bundle["version"], "prompt_sha256": bundle["prompt_sha256"],
              "schema_sha256": bundle["schema_sha256"], "generation": None,
              "generated_sql": None, "executed_sql": None, "columns": [], "rows": [],
              "truncated": False, "validation_ms": None, "database_ms": None, "elapsed_ms": None}
    try:
        if manual_output is not None:
            content = manual_output
        else:
            generated = (generator or generate)(bundle)
            content = generated["content"]
            result["generation"] = {k: v for k, v in generated.items() if k != "content"}
        result["model_output"] = content
        reply = decode_reply(content)
        result["reason"] = str(reply.get("reason", ""))[:1000]
        if reply["status"] == "unsupported":
            result["status"] = "unsupported"
            return result
        result["generated_sql"] = reply["sql"]
        validate_start = perf_counter()
        checked = check_sql(reply["sql"])
        result["validation_ms"] = round((perf_counter() - validate_start) * 1000, 3)
        result["executed_sql"] = checked.executed_sql
        result["tables"] = checked.tables
        result["row_cap_applied"] = checked.row_cap_applied
        db_start = perf_counter()
        result.update(execute_checked(conn, checked))
        result["database_ms"] = round((perf_counter() - db_start) * 1000, 3)
        result["status"] = "truncated" if result["truncated"] else "ok"
    except LLMConfigurationError as exc:
        result["status"], result["message"] = "not_configured", str(exc)
    except LLMCallError as exc:
        result["status"], result["message"] = "llm_error", str(exc)
    except SQLRejected as exc:
        result["status"], result["message"] = "blocked", str(exc)
    except (ValueError, KeyError, TypeError):
        result["status"], result["message"] = "llm_error", "Model output does not match the required JSON contract"
    except psycopg.Error as exc:
        result["status"] = "sql_error"
        result["message"] = "PostgreSQL rejected the query or execution timed out"
        result["sqlstate"] = exc.sqlstate
    finally:
        result["elapsed_ms"] = round((perf_counter() - start) * 1000, 3)
    return result
