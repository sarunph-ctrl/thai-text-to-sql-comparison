"""Run secret, manifest, packet, and regression verification without LLM calls."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parent.parent
SECRET_PATTERN = re.compile(rb"(?:Bearer\s+[A-Za-z0-9._-]{16,}|sk_[A-Za-z0-9]{16,})", re.IGNORECASE)
ALLOWED_TEST_VALUES = {b"Bearer abcdefghijklmnopqrstuvwxyz"}


def git_root() -> Path:
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                            capture_output=True, text=True, timeout=10, check=True)
    return Path(result.stdout.strip())


def tracked_files() -> list[Path]:
    repository = git_root()
    result = subprocess.run(["git", "ls-files", "-z"], cwd=repository,
                            capture_output=True, timeout=10, check=True)
    return [repository / raw.decode("utf-8") for raw in result.stdout.split(b"\0") if raw]


def secret_hits(paths: list[Path]) -> list[str]:
    hits: list[str] = []
    repository = git_root()
    for path in paths:
        if not path.is_file():
            continue
        data = path.read_bytes()
        for match in SECRET_PATTERN.finditer(data):
            if match.group(0) in ALLOWED_TEST_VALUES:
                continue
            line = data.count(b"\n", 0, match.start()) + 1
            try:
                display = path.relative_to(repository)
            except ValueError:
                display = path
            hits.append(f"{display}:{line}")
    return hits


def verify_non_test_artifacts() -> None:
    from eval.run_wms_mvp import verify_frozen_inputs
    from scripts.build_wms_review_packet import build_packet

    verify_frozen_inputs("v1")
    verify_frozen_inputs("v2")
    with TemporaryDirectory(prefix="wms-review-verify-") as directory:
        packet = build_packet(Path(directory) / "review.zip")
        if packet.stat().st_size <= 0:
            raise RuntimeError("Review packet is empty")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-tests", action="store_true",
                        help="Run only secret/manifest/review-packet checks")
    args = parser.parse_args(argv)

    hits = secret_hits(tracked_files())
    if hits:
        raise RuntimeError("Possible secret in tracked files: " + ", ".join(hits))
    print("Secret scan: passed")
    verify_non_test_artifacts()
    print("Frozen manifests and blinded review packet: passed")
    if not args.skip_tests:
        completed = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=ROOT,
        )
        if completed.returncode:
            return completed.returncode
    print("Project verification: passed (no live LLM calls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
