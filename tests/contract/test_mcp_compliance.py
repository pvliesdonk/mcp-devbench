"""Contract tests validating MCP protocol compliance."""

import inspect

import pytest
from pydantic import ValidationError

from mcp_devbench import mcp_tools, server
from mcp_devbench.mcp_tools import (
    AttachInput,
    CancelInput,
    ExecInput,
    ExecPollInput,
    FileReadInput,
    FileWriteInput,
    KillInput,
    SpawnInput,
    SpawnOutput,
)

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


def test_all_tool_inputs_are_valid_pydantic_models():
    """Verify all MCP tool inputs are valid Pydantic models."""
    input_models = []

    for name, obj in inspect.getmembers(mcp_tools):
        if name.endswith("Input") and inspect.isclass(obj):
            input_models.append((name, obj))
            # Check for Pydantic model methods
            assert hasattr(obj, "model_validate"), f"{name} missing model_validate"
            assert hasattr(obj, "model_dump"), f"{name} missing model_dump"
            assert hasattr(obj, "model_json_schema"), f"{name} missing model_json_schema"

    # Ensure we found input models
    assert len(input_models) > 0, "No Input models found"


def test_all_tool_outputs_are_valid_pydantic_models():
    """Verify all MCP tool outputs are valid Pydantic models."""
    output_models = []

    for name, obj in inspect.getmembers(mcp_tools):
        if name.endswith("Output") and inspect.isclass(obj):
            output_models.append((name, obj))
            # Check for Pydantic model methods
            assert hasattr(obj, "model_validate"), f"{name} missing model_validate"
            assert hasattr(obj, "model_dump"), f"{name} missing model_dump"
            assert hasattr(obj, "model_json_schema"), f"{name} missing model_json_schema"

    # Ensure we found output models
    assert len(output_models) > 0, "No Output models found"


@pytest.mark.asyncio
async def test_spawn_tool_contract():
    """Test spawn tool adheres to MCP contract."""
    # Valid input
    valid_input = SpawnInput(image="alpine:latest", persistent=False)

    result = await spawn(valid_input)

    # Output validation
    assert isinstance(result, SpawnOutput)
    assert hasattr(result, "container_id")
    assert hasattr(result, "status")
    assert result.status in ["running", "created", "stopped", "exited"]
    assert result.container_id.startswith("c_")

    # Clean up
    await kill(KillInput(container_id=result.container_id, force=True))


def test_spawn_input_validation():
    """Test spawn input validates correctly."""
    # Valid input
    spawn_input = SpawnInput(image="python:3.11-slim", persistent=False)
    assert spawn_input.image == "python:3.11-slim"
    assert spawn_input.persistent is False

    # Invalid input - missing required field
    with pytest.raises(ValidationError):
        SpawnInput(persistent=False)  # Missing required 'image' field

    # Invalid input - wrong type
    with pytest.raises(ValidationError):
        SpawnInput(image=123, persistent=False)  # Wrong type for image


@pytest.mark.asyncio
async def test_exec_streaming_contract():
    """Test exec streaming follows MCP protocol."""
    # Spawn container
    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    try:
        # Start exec
        exec_result = await exec_start(
            ExecInput(container_id=container_id, cmd=["echo", "test"], timeout_s=30)
        )

        # Validate exec output structure
        assert hasattr(exec_result, "exec_id")
        assert exec_result.exec_id.startswith("e_")
        assert hasattr(exec_result, "status")

        # Poll should return messages with sequence numbers
        poll_result = await exec_poll(ExecPollInput(exec_id=exec_result.exec_id, after_seq=0))

        # Validate poll output structure
        assert hasattr(poll_result, "messages")
        assert hasattr(poll_result, "complete")
        assert isinstance(poll_result.messages, list)

        # Validate message structure
        for msg in poll_result.messages:
            assert hasattr(msg, "seq")
            assert isinstance(msg.seq, int)

            if msg.complete:
                # Completed messages should have exit_code and usage
                assert hasattr(msg, "exit_code")
                assert hasattr(msg, "usage")
            else:
                # Non-completed messages should have stream and data
                if msg.stream is not None:
                    assert msg.stream in ["stdout", "stderr"]
                if msg.data is not None:
                    assert isinstance(msg.data, str)

    finally:
        await kill(KillInput(container_id=container_id, force=True))


def test_file_operations_input_validation():
    """Test file operation inputs validate correctly."""
    # Valid FileReadInput
    read_input = FileReadInput(container_id="c_test", path="/workspace/file.txt")
    assert read_input.container_id == "c_test"
    assert read_input.path == "/workspace/file.txt"

    # Valid FileWriteInput
    write_input = FileWriteInput(container_id="c_test", path="/workspace/file.txt", content=b"test")
    assert write_input.content == b"test"

    # Invalid - missing required fields
    with pytest.raises(ValidationError):
        FileReadInput(path="/workspace/file.txt")  # Missing container_id

    with pytest.raises(ValidationError):
        FileWriteInput(container_id="c_test", path="/workspace/file.txt")  # Missing content


def test_model_serialization():
    """Test that models can be serialized/deserialized."""
    # Create input model
    spawn_input = SpawnInput(image="alpine:latest", persistent=False, alias="test")

    # Serialize to dict
    data = spawn_input.model_dump()
    assert isinstance(data, dict)
    assert data["image"] == "alpine:latest"
    assert data["persistent"] is False
    assert data["alias"] == "test"

    # Deserialize from dict
    restored = SpawnInput.model_validate(data)
    assert restored.image == spawn_input.image
    assert restored.persistent == spawn_input.persistent
    assert restored.alias == spawn_input.alias


def test_model_json_schema():
    """Test that models have valid JSON schemas."""
    # Get JSON schema for SpawnInput
    schema = SpawnInput.model_json_schema()

    assert isinstance(schema, dict)
    assert "properties" in schema
    assert "image" in schema["properties"]
    assert "persistent" in schema["properties"]
    assert "required" in schema
    assert "image" in schema["required"]


def test_optional_fields():
    """Test that optional fields work correctly."""
    # Spawn with minimal required fields
    spawn_input = SpawnInput(image="alpine:latest")
    assert spawn_input.persistent is False  # Default value
    assert spawn_input.alias is None  # Optional, not provided
    assert spawn_input.ttl_s is None  # Optional, not provided
    assert spawn_input.idempotency_key is None  # Optional, not provided

    # Spawn with all fields
    spawn_input_full = SpawnInput(
        image="alpine:latest",
        persistent=True,
        alias="test-alias",
        ttl_s=3600,
        idempotency_key="test-key",
    )
    assert spawn_input_full.persistent is True
    assert spawn_input_full.alias == "test-alias"
    assert spawn_input_full.ttl_s == 3600
    assert spawn_input_full.idempotency_key == "test-key"


def test_exec_input_defaults():
    """Test exec input default values."""
    # Minimal exec input
    exec_input = ExecInput(container_id="c_test", cmd=["echo", "test"])

    assert exec_input.cwd == "/workspace"  # Default
    assert exec_input.env is None  # Optional
    assert exec_input.as_root is False  # Default
    assert exec_input.timeout_s == 600  # Default
    assert exec_input.idempotency_key is None  # Optional


def test_field_descriptions_present():
    """Test that all models have field descriptions."""
    models_to_check = [
        SpawnInput,
        SpawnOutput,
        AttachInput,
        KillInput,
        ExecInput,
        FileReadInput,
        FileWriteInput,
    ]

    for model_class in models_to_check:
        schema = model_class.model_json_schema()
        properties = schema.get("properties", {})

        # Check that fields have descriptions
        for field_name, field_info in properties.items():
            assert "description" in field_info, (
                f"{model_class.__name__}.{field_name} missing description"
            )


@pytest.mark.asyncio
async def test_attach_tool_contract():
    """Test attach tool contract compliance."""
    # Spawn a container first
    spawn_result = await spawn(
        SpawnInput(image="alpine:latest", persistent=False, alias="attach-test")
    )
    container_id = spawn_result.container_id

    try:
        # Test attach
        attach_result = await attach(
            AttachInput(
                target=container_id,
                client_name="test-client",
                session_id="test-session",
            )
        )

        # Validate structure
        assert hasattr(attach_result, "container_id")
        assert hasattr(attach_result, "alias")
        assert hasattr(attach_result, "roots")
        assert isinstance(attach_result.roots, list)
        assert len(attach_result.roots) > 0

    finally:
        await kill(KillInput(container_id=container_id, force=True))


def test_kill_input_validation():
    """Test kill input validation."""
    # Valid input
    kill_input = KillInput(container_id="c_test", force=False)
    assert kill_input.container_id == "c_test"
    assert kill_input.force is False

    # Valid input with force
    kill_input_force = KillInput(container_id="c_test", force=True)
    assert kill_input_force.force is True

    # Invalid - missing container_id
    with pytest.raises(ValidationError):
        KillInput(force=True)


def test_cancel_input_validation():
    """Test cancel input validation."""
    # Valid input
    cancel_input = CancelInput(exec_id="e_test")
    assert cancel_input.exec_id == "e_test"

    # Invalid - missing exec_id
    with pytest.raises(ValidationError):
        CancelInput()
