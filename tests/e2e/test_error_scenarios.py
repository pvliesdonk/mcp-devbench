"""End-to-end tests for error scenarios and edge cases."""

import pytest

from mcp_devbench import server
from mcp_devbench.mcp_tools import (
    AttachInput,
    ExecInput,
    FileReadInput,
    FileWriteInput,
    KillInput,
    SpawnInput,
)
from mcp_devbench.utils.exceptions import (
    ContainerNotFoundError,
    ImagePolicyError,
    PathSecurityError,
)

# Access the underlying functions (unwrapped from @mcp.tool decorator)
spawn = server.spawn.fn
attach = server.attach.fn
kill = server.kill.fn
exec_start = server.exec_start.fn
fs_read = server.fs_read.fn
fs_write = server.fs_write.fn


@pytest.mark.e2e
async def test_spawn_with_invalid_image():
    """Test spawning container with non-existent image."""

    # This should fail during image resolution or pull
    with pytest.raises((ImagePolicyError, Exception)):
        await spawn(SpawnInput(image="nonexistent-image:invalid-tag", persistent=False))


@pytest.mark.e2e
async def test_attach_to_nonexistent_container():
    """Test attaching to a container that doesn't exist."""

    with pytest.raises(ContainerNotFoundError):
        await attach(
            AttachInput(
                target="c_nonexistent",
                client_name="test-client",
                session_id="test-session",
            )
        )


@pytest.mark.e2e
async def test_exec_on_nonexistent_container():
    """Test executing command on non-existent container."""

    with pytest.raises(ContainerNotFoundError):
        await exec_start(
            ExecInput(
                container_id="c_nonexistent",
                cmd=["echo", "test"],
                timeout_s=10,
            )
        )


@pytest.mark.e2e
async def test_path_traversal_attack():
    """Test that path traversal attacks are prevented."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    try:
        # Attempt to read outside workspace using ..
        with pytest.raises(PathSecurityError):
            await fs_read(
                FileReadInput(
                    container_id=container_id,
                    path="/workspace/../etc/passwd",
                )
            )

        # Attempt to write outside workspace
        with pytest.raises(PathSecurityError):
            await fs_write(
                FileWriteInput(
                    container_id=container_id,
                    path="/workspace/../tmp/malicious.txt",
                    content=b"malicious",
                )
            )

    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_read_nonexistent_file():
    """Test reading a file that doesn't exist."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    try:
        with pytest.raises(FileNotFoundError):
            await fs_read(
                FileReadInput(
                    container_id=container_id,
                    path="/workspace/nonexistent.txt",
                )
            )

    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_spawn_with_duplicate_alias():
    """Test spawning containers with duplicate alias."""

    # Spawn first container with alias
    spawn_result1 = await spawn(
        SpawnInput(
            image="alpine:latest",
            persistent=False,
            alias="duplicate-alias",
        )
    )

    try:
        # Attempt to spawn second container with same alias (should fail or be prevented)
        with pytest.raises(Exception):  # Could be various exceptions based on implementation
            await spawn(
                SpawnInput(
                    image="alpine:latest",
                    persistent=False,
                    alias="duplicate-alias",
                )
            )

    finally:
        await kill(KillInput(container_id=spawn_result1.container_id, force=True))


@pytest.mark.e2e
async def test_exec_with_empty_command():
    """Test exec with empty command list."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    try:
        # Empty command should fail validation
        with pytest.raises((ValueError, Exception)):
            await exec_start(
                ExecInput(
                    container_id=container_id,
                    cmd=[],
                    timeout_s=10,
                )
            )

    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_file_write_etag_mismatch():
    """Test conditional write with mismatched etag."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    try:
        # Write initial file
        write_result1 = await fs_write(
            FileWriteInput(
                container_id=container_id,
                path="/workspace/etag-test.txt",
                content=b"version 1",
            )
        )

        # Modify file (etag changes) - not used, but needed to change etag
        await fs_write(
            FileWriteInput(
                container_id=container_id,
                path="/workspace/etag-test.txt",
                content=b"version 2",
            )
        )

        # Attempt to write with old etag (should fail)
        with pytest.raises(Exception):  # ETag mismatch error
            await fs_write(
                FileWriteInput(
                    container_id=container_id,
                    path="/workspace/etag-test.txt",
                    content=b"version 3",
                    if_match_etag=write_result1.etag,  # Old etag
                )
            )

    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_kill_already_killed_container():
    """Test killing a container that's already been killed."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    # Kill once
    await kill(KillInput(container_id=container_id, force=True))

    # Attempt to kill again - should fail gracefully
    with pytest.raises(ContainerNotFoundError):
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_absolute_path_requirement():
    """Test that relative paths are rejected."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    try:
        # Relative path should be rejected
        with pytest.raises((PathSecurityError, ValueError)):
            await fs_read(
                FileReadInput(
                    container_id=container_id,
                    path="relative/path.txt",  # Not absolute
                )
            )

    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_workspace_root_protection():
    """Test that workspace root cannot be deleted."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    try:
        # Attempt to delete workspace root - should be prevented
        from mcp_devbench.mcp_tools import FileDeleteInput
        from mcp_devbench.server import fs_delete

        with pytest.raises((PathSecurityError, PermissionError, Exception)):
            await fs_delete(
                FileDeleteInput(
                    container_id=container_id,
                    path="/workspace",
                )
            )

    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_spawn_idempotency_with_same_key():
    """Test that spawn with same idempotency key returns same container."""

    idempotency_key = "test-idempotency-key-001"

    # First spawn
    spawn_result1 = await spawn(
        SpawnInput(
            image="alpine:latest",
            persistent=False,
            idempotency_key=idempotency_key,
        )
    )

    try:
        # Second spawn with same key should return same container
        spawn_result2 = await spawn(
            SpawnInput(
                image="alpine:latest",
                persistent=False,
                idempotency_key=idempotency_key,
            )
        )

        # Should be the same container
        assert spawn_result1.container_id == spawn_result2.container_id

    finally:
        await kill(KillInput(container_id=spawn_result1.container_id, force=True))


@pytest.mark.e2e
async def test_exec_idempotency_with_same_key():
    """Test that exec with same idempotency key doesn't duplicate execution."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    try:
        idempotency_key = "exec-idempotency-001"

        # First exec
        exec_result1 = await exec_start(
            ExecInput(
                container_id=container_id,
                cmd=["echo", "idempotent"],
                timeout_s=30,
                idempotency_key=idempotency_key,
            )
        )

        # Second exec with same key should return same exec_id
        exec_result2 = await exec_start(
            ExecInput(
                container_id=container_id,
                cmd=["echo", "idempotent"],
                timeout_s=30,
                idempotency_key=idempotency_key,
            )
        )

        # Should be the same execution
        assert exec_result1.exec_id == exec_result2.exec_id

    finally:
        await kill(KillInput(container_id=container_id, force=True))
