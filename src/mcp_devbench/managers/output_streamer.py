"""Output streaming for command executions with bounded ring buffers."""

import asyncio
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Deque, Dict, List, Optional

from mcp_devbench.utils import get_logger

logger = get_logger(__name__)


@dataclass
class OutputChunk:
    """A chunk of output from a command execution."""

    seq: int
    stream: str  # "stdout" or "stderr"
    data: bytes
    ts: datetime

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "seq": self.seq,
            "stream": self.stream,
            "data": self.data.decode("utf-8", errors="replace"),
            "ts": self.ts.isoformat(),
        }


@dataclass
class CompletionChunk:
    """Final chunk indicating completion of execution."""

    seq: int
    exit_code: int
    usage: Dict
    ts: datetime

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "seq": self.seq,
            "exit_code": self.exit_code,
            "usage": self.usage,
            "ts": self.ts.isoformat(),
            "complete": True,
        }


class OutputStreamer:
    """
    Manages streaming output for command executions.

    Uses bounded ring buffers to prevent memory exhaustion and supports
    cursor-based polling for ordered delivery.
    """

    # Default maximum buffer size per exec (64MB)
    DEFAULT_MAX_BUFFER_SIZE = 64 * 1024 * 1024

    # Maximum number of chunks to keep in buffer
    DEFAULT_MAX_CHUNKS = 10000

    def __init__(
        self,
        max_buffer_size: int = DEFAULT_MAX_BUFFER_SIZE,
        max_chunks: int = DEFAULT_MAX_CHUNKS,
    ):
        """
        Initialize output streamer.

        Args:
            max_buffer_size: Maximum total bytes to buffer per exec
            max_chunks: Maximum number of chunks to keep in buffer
        """
        self.max_buffer_size = max_buffer_size
        self.max_chunks = max_chunks

        # Buffers per exec ID: deque of (OutputChunk | CompletionChunk)
        self._buffers: Dict[str, Deque] = {}

        # Current sequence number per exec ID
        self._sequences: Dict[str, int] = {}

        # Total buffered bytes per exec ID
        self._buffered_bytes: Dict[str, int] = {}

        # Lock for thread-safe operations
        self._locks: Dict[str, asyncio.Lock] = {}

        # Completion flags
        self._completed: Dict[str, bool] = {}

    def _get_lock(self, exec_id: str) -> asyncio.Lock:
        """Get or create lock for exec ID."""
        if exec_id not in self._locks:
            self._locks[exec_id] = asyncio.Lock()
        return self._locks[exec_id]

    async def init_exec(self, exec_id: str) -> None:
        """
        Initialize streaming for a new exec.

        Args:
            exec_id: Exec ID
        """
        lock = self._get_lock(exec_id)
        async with lock:
            if exec_id not in self._buffers:
                self._buffers[exec_id] = deque()
                self._sequences[exec_id] = 0
                self._buffered_bytes[exec_id] = 0
                self._completed[exec_id] = False

                logger.debug("Initialized output streaming", extra={"exec_id": exec_id})

    async def add_output(self, exec_id: str, stream: str, data: bytes) -> Optional[int]:
        """
        Add output chunk to the stream.

        Args:
            exec_id: Exec ID
            stream: Stream type ("stdout" or "stderr")
            data: Output data

        Returns:
            Sequence number of added chunk, or None if buffer is full
        """
        if not data:
            return None

        lock = self._get_lock(exec_id)
        async with lock:
            # Check if we have space in buffer
            if self._buffered_bytes.get(exec_id, 0) + len(data) > self.max_buffer_size:
                logger.warning(
                    "Output buffer full, dropping data",
                    extra={
                        "exec_id": exec_id,
                        "buffered_bytes": self._buffered_bytes[exec_id],
                        "data_size": len(data),
                    },
                )
                return None

            # Check chunk limit
            if len(self._buffers.get(exec_id, [])) >= self.max_chunks:
                # Remove oldest chunk
                oldest = self._buffers[exec_id].popleft()
                if isinstance(oldest, OutputChunk):
                    self._buffered_bytes[exec_id] -= len(oldest.data)

            # Create chunk
            seq = self._sequences[exec_id]
            self._sequences[exec_id] += 1

            chunk = OutputChunk(
                seq=seq,
                stream=stream,
                data=data,
                ts=datetime.now(timezone.utc),
            )

            # Add to buffer
            self._buffers[exec_id].append(chunk)
            self._buffered_bytes[exec_id] += len(data)

            return seq

    async def complete(self, exec_id: str, exit_code: int, usage: Dict) -> int:
        """
        Mark execution as complete and add completion chunk.

        Args:
            exec_id: Exec ID
            exit_code: Exit code from command
            usage: Resource usage information

        Returns:
            Sequence number of completion chunk
        """
        lock = self._get_lock(exec_id)
        async with lock:
            seq = self._sequences.get(exec_id, 0)
            self._sequences[exec_id] = seq + 1

            chunk = CompletionChunk(
                seq=seq,
                exit_code=exit_code,
                usage=usage,
                ts=datetime.now(timezone.utc),
            )

            if exec_id in self._buffers:
                self._buffers[exec_id].append(chunk)
            else:
                self._buffers[exec_id] = deque([chunk])

            self._completed[exec_id] = True

            logger.info(
                "Exec completed",
                extra={
                    "exec_id": exec_id,
                    "exit_code": exit_code,
                    "seq": seq,
                },
            )

            return seq

    async def poll(self, exec_id: str, after_seq: Optional[int] = None) -> tuple[List[Dict], bool]:
        """
        Poll for output chunks after a given sequence number.

        Args:
            exec_id: Exec ID
            after_seq: Return chunks after this sequence (None for all)

        Returns:
            Tuple of (chunks, is_complete)
        """
        lock = self._get_lock(exec_id)
        async with lock:
            if exec_id not in self._buffers:
                return [], False

            # Filter chunks by sequence
            chunks = []
            for chunk in self._buffers[exec_id]:
                if after_seq is None or chunk.seq > after_seq:
                    chunks.append(chunk.to_dict())

            is_complete = self._completed.get(exec_id, False)

            return chunks, is_complete

    async def get_stats(self, exec_id: str) -> Dict:
        """
        Get streaming statistics for an exec.

        Args:
            exec_id: Exec ID

        Returns:
            Statistics dictionary
        """
        lock = self._get_lock(exec_id)
        async with lock:
            return {
                "exec_id": exec_id,
                "buffered_bytes": self._buffered_bytes.get(exec_id, 0),
                "chunk_count": len(self._buffers.get(exec_id, [])),
                "current_seq": self._sequences.get(exec_id, 0),
                "is_complete": self._completed.get(exec_id, False),
            }

    async def cleanup(self, exec_id: str) -> None:
        """
        Clean up buffers for a completed exec.

        Args:
            exec_id: Exec ID
        """
        lock = self._get_lock(exec_id)
        async with lock:
            if exec_id in self._buffers:
                del self._buffers[exec_id]
            if exec_id in self._sequences:
                del self._sequences[exec_id]
            if exec_id in self._buffered_bytes:
                del self._buffered_bytes[exec_id]
            if exec_id in self._completed:
                del self._completed[exec_id]
            if exec_id in self._locks:
                del self._locks[exec_id]

            logger.debug("Cleaned up output buffers", extra={"exec_id": exec_id})

    async def cleanup_old(self, max_age_seconds: int = 3600) -> int:
        """
        Clean up buffers for old completed execs.

        Args:
            max_age_seconds: Maximum age in seconds

        Returns:
            Number of execs cleaned up
        """
        # Get list of exec IDs to clean (to avoid modifying dict during iteration)
        exec_ids_to_clean = []

        for exec_id in list(self._buffers.keys()):
            lock = self._get_lock(exec_id)
            async with lock:
                # Check if complete and has old chunks
                if self._completed.get(exec_id, False) and self._buffers.get(exec_id):
                    buffer = self._buffers[exec_id]
                    if buffer:
                        # Check age of last chunk
                        last_chunk = buffer[-1]
                        age = (datetime.now(timezone.utc) - last_chunk.ts).total_seconds()
                        if age > max_age_seconds:
                            exec_ids_to_clean.append(exec_id)

        # Clean up identified execs
        for exec_id in exec_ids_to_clean:
            await self.cleanup(exec_id)

        if exec_ids_to_clean:
            logger.info(
                "Cleaned up old output buffers",
                extra={"count": len(exec_ids_to_clean)},
            )

        return len(exec_ids_to_clean)


# Global output streamer instance
_output_streamer: Optional[OutputStreamer] = None


def get_output_streamer() -> OutputStreamer:
    """Get or create the global output streamer instance."""
    global _output_streamer
    if _output_streamer is None:
        _output_streamer = OutputStreamer()
    return _output_streamer
