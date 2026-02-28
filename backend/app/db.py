"""Database configuration and session management for FastAPI.

This module uses SQLAlchemy’s asyncio support with asyncpg to connect to
PostgreSQL.  The connection URL is assembled from environment
variables.  In production on Cloud Run with Cloud SQL, the connector
uses a Unix socket; in local development, it falls back to TCP.
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def _make_database_url() -> str:
    """Construct a database URL based on environment variables.

    The following environment variables are used:

    - CLOUDSQL_INSTANCE_CONNECTION_NAME: If set, indicates the Cloud SQL
      instance connection name (e.g. `project:region:instance`).  When
      present, the database will connect via a Unix domain socket.
    - DB_USER: Username for the database.
    - DB_PASSWORD: Password for the database.
    - DB_NAME: Name of the database.
    - DB_HOST: Hostname for local or external database (used when
      CLOUDSQL_INSTANCE_CONNECTION_NAME is not set).
    - DB_PORT: Port number (used when not connecting via socket).
    """
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "postgres")
    # Determine whether to use a Cloud SQL Unix socket
    instance_connection_name = os.getenv("CLOUDSQL_INSTANCE_CONNECTION_NAME")
    if instance_connection_name:
        return (
            f"postgresql+asyncpg://{user}:{password}@/{db_name}?host=/cloudsql/{instance_connection_name}"
        )
    # Fallback to TCP for local development
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = os.getenv("DB_PORT", "5432")
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"


# Create the async engine and sessionmaker
DATABASE_URL = _make_database_url()
engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional scope for database operations.

    This is designed to be used as a dependency with FastAPI.  It
    yields an `AsyncSession` bound to the engine and ensures that
    transactions are properly rolled back if an exception occurs.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            # The context manager takes care of closing the session
            pass