from __future__ import annotations
import subprocess
import sys


def test_markdownlint_cli2_runs() -> None:
    # Run via npx to avoid global install; CI will skip npm install but
    # local dev can run this and pre-commit will use npx too.
    cmd = ["npx", "-y", "markdownlint-cli2", "**/*.md"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # Exit code 0: clean; 1: lint errors
    assert proc.returncode in (0, 1), proc.stderr
