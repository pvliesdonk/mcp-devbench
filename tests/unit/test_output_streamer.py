"""Unit tests for OutputStreamer."""

import pytest

from mcp_devbench.managers.output_streamer import OutputStreamer


@pytest.mark.asyncio
async def test_init_exec():
    """Test initializing streaming for a new exec."""
    streamer = OutputStreamer()

    await streamer.init_exec("e_test123")

    stats = await streamer.get_stats("e_test123")
    assert stats["exec_id"] == "e_test123"
    assert stats["buffered_bytes"] == 0
    assert stats["chunk_count"] == 0
    assert stats["current_seq"] == 0
    assert stats["is_complete"] is False


@pytest.mark.asyncio
async def test_add_output():
    """Test adding output chunks."""
    streamer = OutputStreamer()

    await streamer.init_exec("e_test123")

    # Add stdout
    seq1 = await streamer.add_output("e_test123", "stdout", b"Hello\n")
    assert seq1 == 0

    # Add stderr
    seq2 = await streamer.add_output("e_test123", "stderr", b"Error\n")
    assert seq2 == 1

    # Check stats
    stats = await streamer.get_stats("e_test123")
    assert stats["chunk_count"] == 2
    assert stats["buffered_bytes"] == 12  # 6 + 6


@pytest.mark.asyncio
async def test_poll_output():
    """Test polling for output chunks."""
    streamer = OutputStreamer()

    await streamer.init_exec("e_test123")
    await streamer.add_output("e_test123", "stdout", b"Line 1\n")
    await streamer.add_output("e_test123", "stdout", b"Line 2\n")
    await streamer.add_output("e_test123", "stderr", b"Error\n")

    # Poll all chunks
    chunks, is_complete = await streamer.poll("e_test123")
    assert len(chunks) == 3
    assert chunks[0]["seq"] == 0
    assert chunks[0]["stream"] == "stdout"
    assert chunks[0]["data"] == "Line 1\n"
    assert is_complete is False

    # Poll after sequence 0
    chunks, is_complete = await streamer.poll("e_test123", after_seq=0)
    assert len(chunks) == 2
    assert chunks[0]["seq"] == 1
    assert chunks[1]["seq"] == 2


@pytest.mark.asyncio
async def test_complete():
    """Test marking execution as complete."""
    streamer = OutputStreamer()

    await streamer.init_exec("e_test123")
    await streamer.add_output("e_test123", "stdout", b"Output\n")

    # Complete with exit code
    seq = await streamer.complete("e_test123", 0, {"wall_ms": 100})
    assert seq == 1  # Second chunk (after stdout)

    # Check completion
    chunks, is_complete = await streamer.poll("e_test123")
    assert len(chunks) == 2
    assert is_complete is True

    # Last chunk should be completion
    completion = chunks[-1]
    assert completion["seq"] == 1
    assert completion["exit_code"] == 0
    assert completion["usage"]["wall_ms"] == 100
    assert completion["complete"] is True


@pytest.mark.asyncio
async def test_buffer_size_limit():
    """Test that buffer size is limited."""
    # Small buffer size for testing
    streamer = OutputStreamer(max_buffer_size=100)

    await streamer.init_exec("e_test123")

    # Add data within limit
    seq1 = await streamer.add_output("e_test123", "stdout", b"x" * 50)
    assert seq1 == 0

    # Add more data within limit
    seq2 = await streamer.add_output("e_test123", "stdout", b"y" * 49)
    assert seq2 == 1

    # Try to add data that exceeds limit
    seq3 = await streamer.add_output("e_test123", "stdout", b"z" * 10)
    assert seq3 is None  # Should be dropped

    stats = await streamer.get_stats("e_test123")
    assert stats["buffered_bytes"] == 99  # Only first two chunks


@pytest.mark.asyncio
async def test_chunk_limit():
    """Test that chunk count is limited."""
    # Small chunk limit for testing
    streamer = OutputStreamer(max_chunks=3)

    await streamer.init_exec("e_test123")

    # Add chunks up to limit
    await streamer.add_output("e_test123", "stdout", b"1")
    await streamer.add_output("e_test123", "stdout", b"2")
    await streamer.add_output("e_test123", "stdout", b"3")

    stats = await streamer.get_stats("e_test123")
    assert stats["chunk_count"] == 3

    # Add another chunk (should evict oldest)
    await streamer.add_output("e_test123", "stdout", b"4")

    stats = await streamer.get_stats("e_test123")
    assert stats["chunk_count"] == 3  # Still 3

    # Poll should not have first chunk anymore
    chunks, _ = await streamer.poll("e_test123")
    assert len(chunks) == 3
    assert chunks[0]["seq"] == 1  # Starts at seq 1 (0 was evicted)


@pytest.mark.asyncio
async def test_cleanup():
    """Test cleaning up buffers for an exec."""
    streamer = OutputStreamer()

    await streamer.init_exec("e_test123")
    await streamer.add_output("e_test123", "stdout", b"Output\n")
    await streamer.complete("e_test123", 0, {"wall_ms": 100})

    # Verify data exists
    stats = await streamer.get_stats("e_test123")
    assert stats["chunk_count"] > 0

    # Cleanup
    await streamer.cleanup("e_test123")

    # Verify data is gone
    chunks, is_complete = await streamer.poll("e_test123")
    assert len(chunks) == 0
    assert is_complete is False


@pytest.mark.asyncio
async def test_cleanup_old():
    """Test cleaning up old completed execs."""
    streamer = OutputStreamer()

    # Create exec that will be old
    await streamer.init_exec("e_old")
    await streamer.add_output("e_old", "stdout", b"Old\n")
    await streamer.complete("e_old", 0, {"wall_ms": 100})

    # Create recent exec
    await streamer.init_exec("e_new")
    await streamer.add_output("e_new", "stdout", b"New\n")
    await streamer.complete("e_new", 0, {"wall_ms": 100})

    # Clean up (with very long max_age so nothing is cleaned)
    count = await streamer.cleanup_old(max_age_seconds=3600)
    assert count == 0

    # Both should still exist
    chunks1, _ = await streamer.poll("e_old")
    chunks2, _ = await streamer.poll("e_new")
    assert len(chunks1) > 0
    assert len(chunks2) > 0


@pytest.mark.asyncio
async def test_multiple_execs():
    """Test handling multiple execs simultaneously."""
    streamer = OutputStreamer()

    # Init multiple execs
    await streamer.init_exec("e_1")
    await streamer.init_exec("e_2")
    await streamer.init_exec("e_3")

    # Add output to each
    await streamer.add_output("e_1", "stdout", b"Output 1\n")
    await streamer.add_output("e_2", "stdout", b"Output 2\n")
    await streamer.add_output("e_3", "stdout", b"Output 3\n")

    # Poll each independently
    chunks1, _ = await streamer.poll("e_1")
    chunks2, _ = await streamer.poll("e_2")
    chunks3, _ = await streamer.poll("e_3")

    assert len(chunks1) == 1
    assert len(chunks2) == 1
    assert len(chunks3) == 1

    assert chunks1[0]["data"] == "Output 1\n"
    assert chunks2[0]["data"] == "Output 2\n"
    assert chunks3[0]["data"] == "Output 3\n"


@pytest.mark.asyncio
async def test_poll_nonexistent_exec():
    """Test polling for a nonexistent exec."""
    streamer = OutputStreamer()

    chunks, is_complete = await streamer.poll("e_nonexistent")
    assert len(chunks) == 0
    assert is_complete is False
