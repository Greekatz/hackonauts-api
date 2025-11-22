"""
Database configuration and models
Supports SQLite (default) or PostgreSQL
"""
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship
from datetime import datetime
import uuid
import os


# Default to SQLite for easy setup, use PostgreSQL in production
# SQLite: sqlite+aiosqlite:///./sra.db
# PostgreSQL: postgresql+asyncpg://user:pass@localhost:5432/sra
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./sra.db"
)


class Base(DeclarativeBase):
    pass


class UserDB(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    is_active = Column(Boolean, default=True)

    api_keys = relationship("APIKeyDB", back_populates="user", cascade="all, delete-orphan")


class APIKeyDB(Base):
    __tablename__ = "api_keys"

    key = Column(String, primary_key=True, default=lambda: f"sra_{uuid.uuid4().hex}")
    name = Column(String, nullable=False)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    last_used = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True)

    user = relationship("UserDB", back_populates="api_keys")


class SessionTokenDB(Base):
    __tablename__ = "session_tokens"

    token = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    expires_at = Column(DateTime, nullable=True)


class IncidentDB(Base):
    __tablename__ = "incidents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())
    status = Column(String, default="open")
    severity = Column(String, default="medium")
    title = Column(String, default="")
    description = Column(Text, default="")
    resolution_summary = Column(Text, nullable=True)
    resolved_at = Column(DateTime, nullable=True)

    # Store JSON data as text (can use JSONB in production)
    logs_json = Column(Text, default="[]")
    metrics_json = Column(Text, default="[]")
    anomaly_json = Column(Text, nullable=True)
    rca_json = Column(Text, nullable=True)
    actions_json = Column(Text, default="[]")
    stability_json = Column(Text, default="[]")
    agent_runs = Column(String, default="0")


# Engine and session factory
engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Get database session."""
    async with async_session() as session:
        yield session
