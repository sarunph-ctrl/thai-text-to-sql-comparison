"""Generate -> JSON contract -> WMS AST guard -> read-only PostgreSQL."""
from time import perf_counter

import psycopg

from app.llm.client import generate, LLMConfigurationError, LLMCallError
from app.llm.pipeline import decode_reply
from app.wms_llm.prompt import wms_prompt_bundle
from app.wms_llm.sql_guard import check_wms_sql, execute_wms_checked, WMSSQLRejected


def run_wms_llm_pipeline(question: str, conn: psycopg.Connection, *, generator=None,
                         manual_output: str | None = None) -> dict:
    start = perf_counter()
    bundle = wms_prompt_bundle(question)
    result = {
        "method": "llm", "domain": "wms-mvp",
        "mode": "manual_output" if manual_output is not None else "live_api",
        "question": question, "status": "llm_error", "message": None,
        "prompt_version": bundle["version"], "prompt_sha256": bundle["prompt_sha256"],
        "schema_sha256": bundle["schema_sha256"], "generation": None,
        "generated_sql": None, "executed_sql": None, "columns": [], "rows": [],
        "truncated": False, "validation_ms": None, "database_ms": None,
        "elapsed_ms": None,
    }
    try:
        if manual_output is not None:
            content = manual_output
        else:
            generated = (generator or generate)(bundle)
            content = generated["content"]
            result["generation"] = {key: value for key, value in generated.items() if key != "content"}
        result["model_output"] = content
        reply = decode_reply(content)
        result["reason"] = str(reply.get("reason", ""))[:1000]
        if reply["status"] == "unsupported":
            result["status"] = "unsupported"
            return result
        result["generated_sql"] = reply["sql"]
        validation_start = perf_counter()
        checked = check_wms_sql(reply["sql"])
        result["validation_ms"] = round((perf_counter() - validation_start) * 1000, 3)
        result["executed_sql"] = checked.executed_sql
        result["tables"] = checked.tables
        result["row_cap_applied"] = checked.row_cap_applied
        database_start = perf_counter()
        result.update(execute_wms_checked(conn, checked))
        result["database_ms"] = round((perf_counter() - database_start) * 1000, 3)
        result["status"] = "truncated" if result["truncated"] else "ok"
    except LLMConfigurationError as exc:
        result["status"], result["message"] = "not_configured", str(exc)
    except LLMCallError as exc:
        result["status"], result["message"] = "llm_error", str(exc)
    except WMSSQLRejected as exc:
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
