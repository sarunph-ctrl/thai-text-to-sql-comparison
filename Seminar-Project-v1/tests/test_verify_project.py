"""Repository verification detects secrets and validates frozen artifacts."""
from pathlib import Path

from scripts.verify_project import secret_hits, verify_non_test_artifacts


def test_secret_scan_flags_realistic_tokens_but_allows_known_fixture(tmp_path):
    clean = tmp_path / "clean.txt"
    clean.write_text("Bearer abcdefghijklmnopqrstuvwxyz", encoding="utf-8")
    leaked = tmp_path / "leaked.txt"
    leaked.write_text("sk_" + "1234567890abcdefghijklmnop", encoding="utf-8")
    assert secret_hits([clean]) == []
    hits = secret_hits([leaked])
    assert len(hits) == 1 and hits[0].endswith("leaked.txt:1")


def test_current_tracked_repository_has_no_secret_pattern():
    from scripts.verify_project import tracked_files
    assert secret_hits(tracked_files()) == []


def test_manifests_and_review_packet_build_in_verification_mode():
    verify_non_test_artifacts()
