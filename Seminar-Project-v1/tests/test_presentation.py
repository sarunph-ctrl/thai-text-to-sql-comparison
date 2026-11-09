import json

from presentation_data import recorded_report, schema_payload
from scripts.build_offline_demo import build_html, safe_json


def test_recorded_report_keeps_source_and_reference_distinction():
    r = recorded_report()
    assert r["recorded"] is True and r["evaluated_at"]
    assert len(r["cases"]) == r["summary"]["rule"]["total"]
    assert "configuration" not in r  # No raw environment settings exported.
    assert r["cases"][0]["expected_rows"]
    assert all("execution_correct" in c["llm"] for c in r["cases"])


def test_offline_data_cannot_break_out_of_json_script_tag():
    payload = {"question": '</script><script>alert("not executed")</script>'}
    encoded = safe_json(payload)
    assert "</script>" not in encoded
    assert json.loads(encoded) == payload


def test_backup_is_self_contained_and_identifies_recorded_data():
    payload = {"report": recorded_report(), "info": {"schema": schema_payload()}, "data": None}
    html = build_html(payload)
    assert 'id="offline-payload"' in html
    assert 'src="/assets/' not in html and 'href="/assets/' not in html
    assert "LLM_API_KEY=" not in html
    assert "ผลบันทึก" in html
