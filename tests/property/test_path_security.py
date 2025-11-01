"""Property-based tests for path security validation."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mcp_devbench.managers.filesystem_manager import FilesystemManager
from mcp_devbench.utils.exceptions import PathSecurityError


@pytest.mark.property
@given(st.text())
def test_path_validation_never_escapes_workspace(path: str):
    """Property: validate_path should never allow escape from /workspace."""
    manager = FilesystemManager()

    try:
        validated = manager._validate_path(path)
        # If validation passes, path must start with /workspace
        assert validated.startswith("/workspace"), (
            f"Path {validated} does not start with /workspace"
        )
    except (PathSecurityError, ValueError):
        # Expected for malicious or invalid paths
        pass


@pytest.mark.property
@given(st.lists(st.text(min_size=1, max_size=50), min_size=1, max_size=10))
def test_path_components_cannot_escape(components: list[str]):
    """Property: Joining path components should never escape workspace."""
    manager = FilesystemManager()

    # Build path from components
    path = "/workspace/" + "/".join(components)

    try:
        validated = manager._validate_path(path)
        # Must still be within workspace
        assert validated.startswith("/workspace")
        # Should not contain .. after normalization
        assert ".." not in validated
    except (PathSecurityError, ValueError):
        # Expected for invalid components
        pass


@pytest.mark.property
@given(st.integers(min_value=0, max_value=100))
def test_path_with_multiple_dots(dot_count: int):
    """Property: Multiple .. in path should be handled safely."""
    manager = FilesystemManager()

    # Create path with multiple ..
    dots = "../" * dot_count
    path = f"/workspace/{dots}test.txt"

    try:
        validated = manager._validate_path(path)
        # Should either reject or keep within workspace
        assert validated.startswith("/workspace")
    except (PathSecurityError, ValueError):
        # Expected when trying to escape
        pass


@pytest.mark.property
@given(
    st.text(
        alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters=("\x00",)),
        min_size=0,
        max_size=200,
    )
)
def test_path_with_special_characters(path_suffix: str):
    """Property: Special characters in paths should be handled safely."""
    manager = FilesystemManager()

    path = f"/workspace/{path_suffix}"

    try:
        validated = manager._validate_path(path)
        # Should be normalized and within workspace
        assert validated.startswith("/workspace")
        # Should not have null bytes (if validation passes)
        assert "\x00" not in validated
    except (PathSecurityError, ValueError):
        # Expected for invalid paths
        pass


@pytest.mark.property
@given(st.text(min_size=1, max_size=100))
def test_normalized_paths_are_idempotent(filename: str):
    """Property: Normalizing a path twice should give same result."""
    manager = FilesystemManager()

    path = f"/workspace/{filename}"

    try:
        validated1 = manager._validate_path(path)
        # Validate the already validated path
        validated2 = manager._validate_path(validated1)
        # Should be identical
        assert validated1 == validated2
    except (PathSecurityError, ValueError):
        # Expected for invalid paths
        pass


@pytest.mark.property
@given(st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5))
def test_absolute_paths_required(components: list[str]):
    """Property: Relative paths should be rejected or normalized to workspace."""
    manager = FilesystemManager()

    # Create relative path (no leading /)
    relative_path = "/".join(components)

    # If it doesn't start with /, it's relative and should be rejected or normalized
    if not relative_path.startswith("/"):
        try:
            validated = manager._validate_path(relative_path)
            # If accepted, should be normalized to workspace
            assert validated.startswith("/workspace")
        except (PathSecurityError, ValueError):
            # Expected for invalid relative paths
            pass


@pytest.mark.property
@given(st.integers(min_value=0, max_value=20))
def test_workspace_prefix_required(slash_count: int):
    """Property: Paths must be within /workspace or be normalized to it."""
    manager = FilesystemManager()

    # Create path with slashes but not in workspace
    slashes = "/" * slash_count
    path = f"{slashes}etc/passwd"

    try:
        validated = manager._validate_path(path)
        # If validation passes, should be within workspace
        assert validated.startswith("/workspace")
    except (PathSecurityError, ValueError):
        # Expected for paths outside workspace
        pass
