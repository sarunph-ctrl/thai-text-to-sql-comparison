"""Independent review packet is complete, blinded, and secret resistant."""
import json
from zipfile import ZipFile

import yaml

from scripts.build_wms_review_packet import build_packet, SOURCE_FILES


def test_review_packet_contains_forms_and_excludes_system_results(tmp_path):
    output = build_packet(tmp_path / "review.zip")
    with ZipFile(output) as archive:
        names = set(archive.namelist())
        assert "START_HERE.md" in names
        assert "01_core/review_record.yaml" in names
        assert "02_questions/candidate_review_record.yaml" in names
        assert "packet_manifest.json" in names
        assert set(SOURCE_FILES).issubset(names)
        assert not any("RESULT" in name.upper() or "RAW" in name.upper() for name in names)

        form = yaml.safe_load(archive.read("02_questions/candidate_review_record.yaml"))
        assert len(form["cases"]) == 35
        assert all(case["decision"] == "pending" for case in form["cases"])
        assert all("execution" not in str(case).casefold() for case in form["cases"])

        manifest = json.loads(archive.read("packet_manifest.json"))
        assert manifest["review_status"] == "pending_independent_review"
        assert set(manifest["files"]) == names - {"packet_manifest.json"}


def test_review_packet_refuses_to_overwrite(tmp_path):
    output = build_packet(tmp_path / "review.zip")
    try:
        build_packet(output)
    except FileExistsError:
        pass
    else:
        raise AssertionError("review packet was overwritten without force")
