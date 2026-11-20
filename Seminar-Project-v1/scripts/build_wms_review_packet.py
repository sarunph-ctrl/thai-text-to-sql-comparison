"""Build a deterministic, blinded WMS independent-review ZIP.

The packet contains source artifacts and reviewer forms only. It intentionally
excludes system outputs, accuracy reports, raw runs, prompts, and API settings.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import yaml


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from eval.run_wms_mvp import verify_frozen_inputs


VERSION = "1.0-draft"
DEFAULT_OUTPUT = ROOT / "output/wms-review/WMS-MVP-Independent-Review-1.0-draft.zip"
SECRET_PATTERN = re.compile(r"(?:Bearer\s+\S+|sk_[A-Za-z0-9]{16,})", re.IGNORECASE)
SOURCE_FILES = {
    "01_core/INDEPENDENT_REVIEW_GUIDE.md": "eval/wms_mvp/INDEPENDENT_REVIEW_GUIDE.md",
    "01_core/review_record.yaml": "eval/wms_mvp/review_record.yaml",
    "01_core/SCOPE_WMS_MVP.md": "SCOPE_WMS_MVP.md",
    "01_core/WMS_DATA_DICTIONARY.md": "WMS_DATA_DICTIONARY.md",
    "01_core/WMS_BUSINESS_RULES.md": "WMS_BUSINESS_RULES.md",
    "01_core/wms_mvp_schema.sql": "db/wms_mvp_schema.sql",
    "01_core/wms_mvp_seed.sql": "db/wms_mvp_seed.sql",
    "01_core/ground_truth.yaml": "eval/wms_mvp/ground_truth.yaml",
    "01_core/manifest.json": "eval/wms_mvp/manifest.json",
    "02_questions/dev.candidate.yaml": "eval/wms_mvp/dev.candidate.yaml",
    "02_questions/dev_candidate_manifest.json": "eval/wms_mvp/dev_candidate_manifest.json",
    "03_robustness/wms_mvp_seed_v2.sql": "db/wms_mvp_seed_v2.sql",
    "03_robustness/snapshot_v2_expected.yaml": "eval/wms_mvp/snapshot_v2_expected.yaml",
    "03_robustness/snapshot_v2_manifest.json": "eval/wms_mvp/snapshot_v2_manifest.json",
}


START_HERE = """# เริ่มตรวจ WMS MVP ที่นี่

Packet version: 1.0-draft

## กติกาก่อนเริ่ม

- ผู้ตรวจต้องไม่ได้เป็นผู้ปรับ Rule-based หรือ LLM prompt ชุดนี้
- กรุณาตรวจโดยยังไม่ดู Accuracy, SQL ที่ระบบสร้าง หรือผลรายข้อของระบบ
- Automated tests ไม่สามารถยืนยันความถูกต้องของความหมายธุรกิจแทนผู้ตรวจได้
- หากไม่แน่ใจ ให้ตอบ `unknown` หรือ `changes_required` ไม่ต้องเดา

## ลำดับการตรวจ

1. เปิด `01_core/INDEPENDENT_REVIEW_GUIDE.md`
2. อ่าน Scope, Data Dictionary, Business rules, Schema และ Synthetic seed
3. ตรวจ `ground_truth.yaml` ทีละ `wms_ref_01`–`wms_ref_05`
4. กรอก `01_core/review_record.yaml`
5. หลังตรวจ Core แล้ว อ่าน `02_questions/dev.candidate.yaml`
6. กรอก `02_questions/candidate_review_record.yaml` ครบ 35 ข้อ
7. ตรวจ Snapshot v2 ใน `03_robustness/` ว่ายังใช้กฎเดิมและเปลี่ยนคำตอบจริง
8. ส่งไฟล์ review record ที่กรอกแล้วกลับให้ผู้พัฒนา

## สิ่งที่ไม่มีใน Packet โดยตั้งใจ

- ผล Accuracy หรือ latency
- SQL/คำตอบจาก Rule-based หรือ LLM
- Token usage และผล Provider calls
- Held-out questions
- API key หรือข้อมูลจริง

`packet_manifest.json` เก็บ SHA-256 ของทุกไฟล์ใน Packet เพื่อตรวจว่าไฟล์ไม่เปลี่ยนระหว่างส่งต่อ
"""


def candidate_review_template() -> bytes:
    dataset = yaml.safe_load((ROOT / "eval/wms_mvp/dev.candidate.yaml").read_text(encoding="utf-8"))
    form = {
        "review_version": "1.0-template",
        "dataset_version": dataset["dataset_version"],
        "dataset_status": dataset["status"],
        "reviewer": {
            "name": None,
            "role": None,
            "review_date": None,
            "independent_from_rule_and_prompt_tuning": None,
            "reviewed_before_seeing_system_outputs": None,
        },
        "instructions": {
            "allowed_decisions": ["approve", "change", "remove", "unknown"],
            "boolean_fields": "Use true/false/null. null means not yet reviewed or unknown.",
        },
        "cases": [
            {
                "id": case["id"],
                "question": case["question"],
                "scope_label_correct": None,
                "family_and_reference_correct": None,
                "natural_for_intended_user": None,
                "meaning_is_unambiguous": None,
                "not_too_similar_to_another_case": None,
                "decision": "pending",
                "comments": None,
            }
            for case in dataset["cases"]
        ],
        "overall": {
            "decision": "pending",
            "required_changes": [],
            "approved_dataset_version": None,
            "reviewer_signoff": None,
        },
    }
    return yaml.safe_dump(form, allow_unicode=True, sort_keys=False, width=120).encode("utf-8")


def zip_info(name: str) -> ZipInfo:
    info = ZipInfo(name, date_time=(2026, 11, 20, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o100644 << 16
    return info


def packet_entries() -> dict[str, bytes]:
    verify_frozen_inputs("v2")
    entries = {"START_HERE.md": START_HERE.encode("utf-8")}
    for archive_name, relative in SOURCE_FILES.items():
        entries[archive_name] = (ROOT / relative).read_bytes()
    entries["02_questions/candidate_review_record.yaml"] = candidate_review_template()
    for name, content in entries.items():
        if SECRET_PATTERN.search(content.decode("utf-8", errors="replace")):
            raise RuntimeError(f"Possible secret in review packet entry: {name}")
    manifest = {
        "packet_version": VERSION,
        "review_status": "pending_independent_review",
        "algorithm": "sha256",
        "files": {name: sha256(content).hexdigest() for name, content in sorted(entries.items())},
        "exclusions": ["system outputs", "accuracy", "generated SQL", "token usage", "held-out questions", "API settings"],
    }
    entries["packet_manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    return entries


def build_packet(output: Path, *, force: bool = False) -> Path:
    if output.exists() and not force:
        raise FileExistsError(f"Output already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    entries = packet_entries()
    with ZipFile(output, "w") as archive:
        for name, content in sorted(entries.items()):
            archive.writestr(zip_info(name), content)
    return output


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    output = build_packet(args.output, force=args.force)
    print(f"Review packet: {output}")
    print(f"SHA-256: {sha256(output.read_bytes()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
