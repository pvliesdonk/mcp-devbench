"""Performance benchmarking tests for MCP DevBench."""

import asyncio

import pytest

from mcp_devbench import server
from mcp_devbench.mcp_tools import (
    ExecInput,
    ExecPollInput,
    FileReadInput,
    FileWriteInput,
    KillInput,
    SpawnInput,
)

# Access the underlying functions (unwrapped from @mcp.tool decorator)
spawn = server.spawn.fn
kill = server.kill.fn
exec_start = server.exec_start.fn
exec_poll = server.exec_poll.fn
fs_read = server.fs_read.fn
fs_write = server.fs_write.fn


@pytest.mark.performance
@pytest.mark.asyncio
async def test_spawn_container_performance(benchmark):
    """Benchmark container spawn time."""

    async def spawn_and_kill():
        result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
        try:
            return result
        finally:
            await kill(KillInput(container_id=result.container_id, force=True))

    # Run benchmark
    result = await benchmark(spawn_and_kill)
    assert result.container_id.startswith("c_")


@pytest.mark.performance
@pytest.mark.asyncio
async def test_exec_throughput(benchmark):
    """Benchmark command execution throughput."""

    # Setup: spawn container once
    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    async def run_exec():
        # Start execution
        exec_result = await exec_start(
            ExecInput(
                container_id=container_id,
                cmd=["echo", "test"],
                timeout_s=30,
            )
        )

        # Wait for completion
        max_attempts = 20
        for _ in range(max_attempts):
            poll_result = await exec_poll(
                ExecPollInput(exec_id=exec_result.exec_id, after_seq=0)
            )
            if poll_result.complete:
                return poll_result
            await asyncio.sleep(0.1)

        return poll_result

    try:
        # Run benchmark
        result = await benchmark(run_exec)
        assert result.complete
    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.performance
@pytest.mark.asyncio
async def test_filesystem_read_performance(benchmark):
    """Benchmark filesystem read performance."""

    # Setup: spawn container and create test file
    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    # Create test file (1KB)
    test_data = b"x" * 1024
    await fs_write(
        FileWriteInput(
            container_id=container_id,
            path="/workspace/test.bin",
            content=test_data,
        )
    )

    async def read_file():
        result = await fs_read(
            FileReadInput(
                container_id=container_id,
                path="/workspace/test.bin",
            )
        )
        return result

    try:
        # Run benchmark
        result = await benchmark(read_file)
        assert len(result.content) == len(test_data)
    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.performance
@pytest.mark.asyncio
async def test_filesystem_write_performance(benchmark):
    """Benchmark filesystem write performance."""

    # Setup: spawn container
    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    # Test data (1KB)
    test_data = b"x" * 1024

    async def write_file():
        result = await fs_write(
            FileWriteInput(
                container_id=container_id,
                path="/workspace/test.bin",
                content=test_data,
            )
        )
        return result

    try:
        # Run benchmark
        result = await benchmark(write_file)
        assert result.size == len(test_data)
    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.performance
@pytest.mark.asyncio
async def test_large_file_read_performance(benchmark):
    """Benchmark reading larger files (1MB)."""

    # Setup: spawn container and create large test file
    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    # Create large test file (1MB)
    test_data = b"x" * (1024 * 1024)
    await fs_write(
        FileWriteInput(
            container_id=container_id,
            path="/workspace/large.bin",
            content=test_data,
        )
    )

    async def read_large_file():
        result = await fs_read(
            FileReadInput(
                container_id=container_id,
                path="/workspace/large.bin",
            )
        )
        return result

    try:
        # Run benchmark
        result = await benchmark(read_large_file)
        assert len(result.content) == len(test_data)
    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.performance
@pytest.mark.asyncio
async def test_concurrent_execs_performance(benchmark):
    """Benchmark concurrent command executions."""

    # Setup: spawn container
    spawn_result = await spawn(SpawnInput(image="alpine:latest", persistent=False))
    container_id = spawn_result.container_id

    async def run_concurrent_execs():
        # Start multiple executions concurrently (within semaphore limit)
        exec_tasks = []
        for i in range(3):  # Run 3 concurrent execs
            task = exec_start(
                ExecInput(
                    container_id=container_id,
                    cmd=["echo", f"concurrent_{i}"],
                    timeout_s=30,
                )
            )
            exec_tasks.append(task)

        # Wait for all to start
        results = await asyncio.gather(*exec_tasks)

        # Wait for all to complete
        poll_tasks = []
        for result in results:
            async def poll_until_complete(exec_id):
                for _ in range(20):
                    poll_result = await exec_poll(ExecPollInput(exec_id=exec_id, after_seq=0))
                    if poll_result.complete:
                        return poll_result
                    await asyncio.sleep(0.1)
                return poll_result

            poll_tasks.append(poll_until_complete(result.exec_id))

        poll_results = await asyncio.gather(*poll_tasks)
        return poll_results

    try:
        # Run benchmark
        results = await benchmark(run_concurrent_execs)
        assert all(r.complete for r in results)
    finally:
        await kill(KillInput(container_id=container_id, force=True))


@pytest.mark.performance
@pytest.mark.asyncio
async def test_spawn_with_idempotency_performance(benchmark):
    """Benchmark spawn with idempotency key lookup."""

    idempotency_key = "perf-test-idempotency"
    container_id = None

    async def spawn_with_idempotency():
        nonlocal container_id
        result = await spawn(
            SpawnInput(
                image="alpine:latest",
                persistent=False,
                idempotency_key=idempotency_key,
            )
        )
        container_id = result.container_id
        return result

    try:
        # First spawn creates container
        first_result = await spawn_with_idempotency()

        # Benchmark subsequent spawns (should be fast lookups)
        result = await benchmark(spawn_with_idempotency)
        assert result.container_id == first_result.container_id

    finally:
        if container_id:
            await kill(KillInput(container_id=container_id, force=True))
