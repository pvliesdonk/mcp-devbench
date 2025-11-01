"""Property-based tests for idempotency features."""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck

from mcp_devbench import server
from mcp_devbench.mcp_tools import SpawnInput, ExecInput, KillInput

# Access the underlying functions (unwrapped from @mcp.tool decorator)
spawn = server.spawn.fn
exec_start = server.exec_start.fn
kill = server.kill.fn


@pytest.mark.property
@pytest.mark.asyncio
@given(st.text(min_size=1, max_size=100))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=10)
async def test_spawn_idempotency_is_reliable(idempotency_key: str):
    """Property: Multiple spawns with same key should return same container."""
    container_id = None

    try:
        results = []

        # Spawn same container 3 times with same idempotency key
        for _ in range(3):
            result = await spawn(
                SpawnInput(
                    image="alpine:latest",
                    persistent=False,
                    idempotency_key=idempotency_key,
                )
            )
            results.append(result.container_id)

        # All results should be the same container
        assert len(set(results)) == 1, f"Expected same container, got: {results}"
        container_id = results[0]

    finally:
        # Clean up
        if container_id:
            try:
                await kill(KillInput(container_id=container_id, force=True))
            except Exception:
                pass  # Ignore cleanup errors


@pytest.mark.property
@pytest.mark.asyncio
@given(st.text(min_size=1, max_size=100))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=5)
async def test_different_idempotency_keys_create_different_containers(idempotency_key: str):
    """Property: Different idempotency keys should create different containers."""
    container_ids = []

    try:
        # Create two containers with different keys
        key1 = f"{idempotency_key}_1"
        key2 = f"{idempotency_key}_2"

        result1 = await spawn(
            SpawnInput(
                image="alpine:latest",
                persistent=False,
                idempotency_key=key1,
            )
        )
        container_ids.append(result1.container_id)

        result2 = await spawn(
            SpawnInput(
                image="alpine:latest",
                persistent=False,
                idempotency_key=key2,
            )
        )
        container_ids.append(result2.container_id)

        # Should be different containers
        assert result1.container_id != result2.container_id

    finally:
        # Clean up
        for container_id in container_ids:
            try:
                await kill(KillInput(container_id=container_id, force=True))
            except Exception:
                pass


@pytest.mark.property
@pytest.mark.asyncio
@given(st.text(min_size=1, max_size=100))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], max_examples=5)
async def test_exec_idempotency_prevents_duplicate_execution(idempotency_key: str):
    """Property: Exec with same idempotency key returns same exec_id."""
    container_id = None

    try:
        # Spawn container
        spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
        container_id = spawn_result.container_id

        exec_ids = []

        # Execute same command twice with same idempotency key
        for _ in range(2):
            result = await exec_start(
                ExecInput(
                    container_id=container_id,
                    cmd=["echo", "test"],
                    timeout_s=30,
                    idempotency_key=idempotency_key,
                )
            )
            exec_ids.append(result.exec_id)

        # Should return same exec_id
        assert len(set(exec_ids)) == 1, f"Expected same exec_id, got: {exec_ids}"

    finally:
        # Clean up
        if container_id:
            try:
                await kill(KillInput(container_id=container_id, force=True))
            except Exception:
                pass


@pytest.mark.property
def test_idempotency_keys_allow_various_characters():
    """Property: Idempotency keys should accept various valid characters."""

    @given(
        st.text(
            alphabet=st.characters(
                whitelist_categories=("Lu", "Ll", "Nd"), min_codepoint=48, max_codepoint=122
            ),
            min_size=1,
            max_size=50,
        )
    )
    def check_key(key: str):
        # Should be able to create SpawnInput with various keys
        spawn_input = SpawnInput(
            image="alpine:latest",
            persistent=False,
            idempotency_key=key,
        )
        assert spawn_input.idempotency_key == key

    check_key()


@pytest.mark.property
def test_idempotency_key_optional():
    """Property: Idempotency key should be optional for spawn."""

    @given(st.booleans())
    def check_optional(use_key: bool):
        if use_key:
            spawn_input = SpawnInput(
                image="alpine:latest",
                persistent=False,
                idempotency_key="some-key",
            )
            assert spawn_input.idempotency_key == "some-key"
        else:
            spawn_input = SpawnInput(
                image="alpine:latest",
                persistent=False,
            )
            assert spawn_input.idempotency_key is None

    check_optional()
