"""Build a standalone presentation HTML with real recorded results, no key/API.

The raw synthetic data is embedded only if its hash matches the recorded run.
"""
from datetime import datetime
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from presentation_data import ROOT, recorded_report, schema_payload


def safe_json(value) -> str:
    # A SQL string from a model may contain </script>. Do not end the data tag.
    return json.dumps(value, ensure_ascii=False).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def build_html(payload: dict) -> str:
    html = (ROOT / "web/index.html").read_text(encoding="utf-8")
    css = (ROOT / "web/styles.css").read_text(encoding="utf-8")
    js = (ROOT / "web/app.js").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="/assets/styles.css">', "<style>" + css + "</style>")
    html = html.replace('<script src="/assets/app.js" defer></script>',
        '<script id="offline-payload" type="application/json">' + safe_json(payload) + '</script>\n<script>' + js + '</script>')
    return html.replace("<title>Thai Query Lab · Seminar Demo</title>", "<title>Thai Query Lab · ผลบันทึกออฟไลน์</title>")


def main():
    report = recorded_report()
    captured = None
    try:
        from demo_dashboard import synthetic_data
        current = synthetic_data()
        if not any(t["truncated"] for t in current["tables"].values()):
            rows = {name: t["rows"] for name, t in current["tables"].items()}
            fingerprint = sha256(json.dumps(rows, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
            if fingerprint == report["data_snapshot_sha256"]:
                captured = current
    except HTTPException:
        pass  # Recorded results still form a useful offline backup.
    payload = {"built_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(), "report": report,
               "info": {"schema": schema_payload(), "llm": {"requested_model": report["model"], "configured": False}},
               "data": captured}
    output = ROOT / "output/presentation/offline-demo.html"
    output.parent.mkdir(exist_ok=True)
    output.write_text(build_html(payload), encoding="utf-8")
    print("Standalone offline backup:", output)
    print("Raw data snapshot matches recorded experiment:", bool(captured))


if __name__ == "__main__":
    main()
