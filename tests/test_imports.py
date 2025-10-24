from __future__ import annotations


def test_package_importable() -> None:
    # Minimal sanity: the src/ package must be importable under uv's venv
    import mcp_devbench  # noqa: F401


def test_pytest_runs() -> None:
    assert True
