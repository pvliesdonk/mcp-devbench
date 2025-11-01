"""End-to-end tests simulating complete MCP client workflows."""

import asyncio

import pytest

from mcp_devbench import server
from mcp_devbench.mcp_tools import (
    AttachInput,
    CancelInput,
    ExecInput,
    ExecPollInput,
    FileDeleteInput,
    FileListInput,
    FileReadInput,
    FileWriteInput,
    KillInput,
    SpawnInput,
)
from mcp_devbench.utils.exceptions import ContainerNotFoundError

# Access the underlying functions (unwrapped from @mcp.tool decorator)
spawn = server.spawn.fn
attach = server.attach.fn
kill = server.kill.fn
exec_start = server.exec_start.fn
exec_poll = server.exec_poll.fn
exec_cancel = server.exec_cancel.fn
fs_read = server.fs_read.fn
fs_write = server.fs_write.fn
fs_delete = server.fs_delete.fn
fs_list = server.fs_list.fn


@pytest.mark.e2e
async def test_complete_container_lifecycle():
    """Test full workflow: spawn -> attach -> exec -> fs -> kill."""

    # 1. Spawn container
    spawn_result = await spawn(
        SpawnInput(image="python:3.11-slim", persistent=False, alias="e2e-test-container")
    )
    container_id = spawn_result.container_id

    assert container_id.startswith("c_")
    assert spawn_result.alias == "e2e-test-container"
    assert spawn_result.status == "running"

    try:
        # 2. Attach to container
        attach_result = await attach(
            AttachInput(target=container_id, client_name="e2e-client", session_id="e2e-session-001")
        )
        assert attach_result.container_id == container_id
        assert attach_result.alias == "e2e-test-container"
        assert len(attach_result.roots) > 0
        assert any("workspace" in root for root in attach_result.roots)

        # 3. Execute command
        exec_result = await exec_start(
            ExecInput(container_id=container_id, cmd=["echo", "hello world"], timeout_s=30)
        )
        assert exec_result.exec_id.startswith("e_")
        assert exec_result.status == "running"

        # 4. Poll for output
        max_attempts = 20
        poll_result = None
        for attempt in range(max_attempts):
            poll_result = await exec_poll(ExecPollInput(exec_id=exec_result.exec_id, after_seq=0))

            if poll_result.complete:
                break

            await asyncio.sleep(0.5)

        assert poll_result is not None
        assert poll_result.complete
        # Check that we got the expected output
        output_found = False
        for msg in poll_result.messages:
            if msg.data and "hello world" in msg.data:
                output_found = True
                break
        assert output_found, "Expected 'hello world' in command output"

        # 5. Write file
        write_result = await fs_write(
            FileWriteInput(
                container_id=container_id,
                path="/workspace/test.txt",
                content=b"test content",
            )
        )
        assert write_result.path == "/workspace/test.txt"
        assert write_result.size == len(b"test content")
        assert write_result.etag is not None

        # 6. Read file back
        read_result = await fs_read(
            FileReadInput(container_id=container_id, path="/workspace/test.txt")
        )
        assert read_result.content == b"test content"
        assert read_result.size == len(b"test content")
        assert read_result.etag is not None

        # 7. List files
        list_result = await fs_list(FileListInput(container_id=container_id, path="/workspace"))
        assert list_result.path == "/workspace"
        assert any(entry.path == "/workspace/test.txt" for entry in list_result.entries)

        # 8. Delete file
        delete_result = await fs_delete(
            FileDeleteInput(container_id=container_id, path="/workspace/test.txt")
        )
        assert delete_result.status == "deleted"
        assert delete_result.path == "/workspace/test.txt"

        # 9. Verify file is deleted by attempting to list
        list_result_after = await fs_list(
            FileListInput(container_id=container_id, path="/workspace")
        )
        assert not any(entry.path == "/workspace/test.txt" for entry in list_result_after.entries)

    finally:
        # 10. Kill container
        kill_result = await kill(KillInput(container_id=container_id, force=True))
        assert kill_result.status in ["stopped", "removed"]


@pytest.mark.e2e
async def test_attach_by_alias():
    """Test attaching to container using alias instead of ID."""

    # Spawn container with alias
    spawn_result = await spawn(
        SpawnInput(image="alpine:latest", persistent=False, alias="alias-test-container")
    )
    container_id = spawn_result.container_id

    try:
        # Attach using alias
        attach_result = await attach(
            AttachInput(
                target="alias-test-container",
                client_name="alias-test-client",
                session_id="alias-session-001",
            )
        )

        # Should resolve to the correct container
        assert attach_result.container_id == container_id
        assert attach_result.alias == "alias-test-container"

    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_exec_with_environment_variables():
    """Test exec with custom environment variables."""

    spawn_result = await spawn(SpawnInput(image="python:3.11-slim", persistent=False))
    container_id = spawn_result.container_id

    try:
        # Execute with environment variable
        exec_result = await exec_start(
            ExecInput(
                container_id=container_id,
                cmd=["sh", "-c", "echo $MY_VAR"],
                env={"MY_VAR": "test_value"},
                timeout_s=30,
            )
        )

        # Poll for completion
        max_attempts = 20
        poll_result = None
        for _ in range(max_attempts):
            poll_result = await exec_poll(ExecPollInput(exec_id=exec_result.exec_id, after_seq=0))
            if poll_result.complete:
                break
            await asyncio.sleep(0.5)

        assert poll_result is not None
        assert poll_result.complete

        # Check for environment variable in output
        output_found = False
        for msg in poll_result.messages:
            if msg.data and "test_value" in msg.data:
                output_found = True
                break
        assert output_found, "Expected custom environment variable in output"

    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_exec_cancellation():
    """Test cancelling a running execution."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    try:
        # Start a long-running command
        exec_result = await exec_start(
            ExecInput(container_id=container_id, cmd=["sleep", "60"], timeout_s=90)
        )

        # Wait a bit to ensure it's running
        await asyncio.sleep(1)

        # Cancel the execution
        cancel_result = await exec_cancel(CancelInput(exec_id=exec_result.exec_id))
        assert cancel_result.status in ["cancelled", "canceled"]
        assert cancel_result.exec_id == exec_result.exec_id

        # Poll to verify it's complete
        max_attempts = 10
        poll_result = None
        for _ in range(max_attempts):
            poll_result = await exec_poll(ExecPollInput(exec_id=exec_result.exec_id, after_seq=0))
            if poll_result.complete:
                break
            await asyncio.sleep(0.5)

        assert poll_result is not None
        assert poll_result.complete

    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_file_operations_with_directories():
    """Test filesystem operations with nested directories."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    try:
        # Write file in nested directory (should auto-create parent dirs)
        write_result = await fs_write(
            FileWriteInput(
                container_id=container_id,
                path="/workspace/subdir1/subdir2/nested.txt",
                content=b"nested content",
            )
        )
        assert write_result.path == "/workspace/subdir1/subdir2/nested.txt"

        # Read nested file
        read_result = await fs_read(
            FileReadInput(container_id=container_id, path="/workspace/subdir1/subdir2/nested.txt")
        )
        assert read_result.content == b"nested content"

        # List parent directory
        list_result = await fs_list(
            FileListInput(container_id=container_id, path="/workspace/subdir1")
        )
        assert any(entry.path == "/workspace/subdir1/subdir2" for entry in list_result.entries)

        # Delete entire directory tree
        delete_result = await fs_delete(
            FileDeleteInput(container_id=container_id, path="/workspace/subdir1")
        )
        assert delete_result.status == "deleted"

    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_persistent_container():
    """Test persistent container lifecycle."""

    # Spawn persistent container
    spawn_result = await spawn(
        SpawnInput(image="alpine:latest", persistent=True, alias="persistent-test")
    )
    container_id = spawn_result.container_id

    try:
        # Write a file
        await fs_write(
            FileWriteInput(
                container_id=container_id,
                path="/workspace/persistent.txt",
                content=b"persistent data",
            )
        )

        # Note: In a real persistent scenario, we'd stop/start the server
        # For this test, just verify the file exists
        read_result = await fs_read(
            FileReadInput(container_id=container_id, path="/workspace/persistent.txt")
        )
        assert read_result.content == b"persistent data"

    finally:
        # Clean up persistent container
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.e2e
async def test_cleanup_after_killed_container():
    """Test that operations fail gracefully after container is killed."""

    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    # Kill container immediately
    await kill(KillInput(container_id=container_id, force=True))

    # Attempting operations on killed container should fail
    with pytest.raises(ContainerNotFoundError):
        await exec_start(ExecInput(container_id=container_id, cmd=["echo", "test"], timeout_s=10))


@pytest.mark.e2e
async def test_multiple_sequential_execs():
    """Test multiple sequential command executions in same container."""

    spawn_result = await spawn(SpawnInput(image="python:3.11-slim", persistent=False))
    container_id = spawn_result.container_id

    try:
        commands = [
            ["echo", "command1"],
            ["echo", "command2"],
            ["echo", "command3"],
        ]

        for i, cmd in enumerate(commands):
            exec_result = await exec_start(
                ExecInput(container_id=container_id, cmd=cmd, timeout_s=30)
            )

            # Wait for completion
            max_attempts = 20
            poll_result = None
            for _ in range(max_attempts):
                poll_result = await exec_poll(
                    ExecPollInput(exec_id=exec_result.exec_id, after_seq=0)
                )
                if poll_result.complete:
                    break
                await asyncio.sleep(0.5)

            assert poll_result is not None
            assert poll_result.complete

            # Verify expected output
            output_found = False
            expected = f"command{i + 1}"
            for msg in poll_result.messages:
                if msg.data and expected in msg.data:
                    output_found = True
                    break
            assert output_found, f"Expected '{expected}' in output"

    finally:
        await kill(KillInput(container_id=container_id, force=True))
