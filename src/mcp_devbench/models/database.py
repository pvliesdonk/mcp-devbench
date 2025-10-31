"""Database session management for MCP DevBench."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from mcp_devbench.config import get_settings
from mcp_devbench.models.base import Base
from mcp_devbench.utils import get_logger

logger = get_logger(__name__)


class DatabaseManager:
    """Manages database connections and sessions."""

    def __init__(self) -> None:
        """Initialize database manager."""
        self._engine: AsyncEngine | None = None
        self._session_maker: async_sessionmaker[AsyncSession] | None = None
        self.settings = get_settings()

    def get_engine(self) -> AsyncEngine:
        """
        Get or create async database engine.
        
        Returns:
            AsyncEngine instance
        """
        if self._engine is None:
            # Convert sqlite path to async sqlite URL
            db_path = self.settings.state_db
            if not db_path.startswith("sqlite"):
                db_url = f"sqlite+aiosqlite:///{db_path}"
            else:
                db_url = db_path.replace("sqlite://", "sqlite+aiosqlite://")

            self._engine = create_async_engine(
                db_url,
                echo=False,  # Set to True for SQL logging
                future=True,
            )
            logger.info("Database engine created", extra={"db_url": db_url})

        return self._engine

    def get_session_maker(self) -> async_sessionmaker[AsyncSession]:
        """
        Get or create session maker.
        
        Returns:
            async_sessionmaker instance
        """
        if self._session_maker is None:
            engine = self.get_engine()
            self._session_maker = async_sessionmaker(
                engine,
                class_=AsyncSession,
                expire_on_commit=False,
            )
            logger.info("Session maker created")

        return self._session_maker

    async def create_tables(self) -> None:
        """Create all database tables."""
        engine = self.get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created")

    async def close(self) -> None:
        """Close database engine."""
        if self._engine:
            await self._engine.dispose()
            self._engine = None
            self._session_maker = None
            logger.info("Database engine closed")

    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get an async database session.
        
        Yields:
            AsyncSession instance
        """
        session_maker = self.get_session_maker()
        async with session_maker() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise


# Global instance
_db_manager: DatabaseManager | None = None


def get_db_manager() -> DatabaseManager:
    """
    Get global database manager instance.
    
    Returns:
        DatabaseManager instance
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
    return _db_manager


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Get an async database session (dependency injection helper).
    
    Yields:
        AsyncSession instance
    """
    db_manager = get_db_manager()
    async with db_manager.get_session() as session:
        yield session


async def init_db() -> None:
    """Initialize database (create tables)."""
    db_manager = get_db_manager()
    await db_manager.create_tables()


async def close_db() -> None:
    """Close database connection."""
    global _db_manager
    if _db_manager:
        await _db_manager.close()
        _db_manager = None
