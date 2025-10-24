from __future__ import annotations
import mcp_devbench  # noqa: F401


def test_package_importable() -> None:
    # Minimal sanity: the src/ package must be importable under uv's venv
    assert mcp_devbench is not None


def test_pytest_runs() -> None:
    assert True
