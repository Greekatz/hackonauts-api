"""
Database Query Helpers
Reusable database query functions to reduce code duplication.
"""
from typing import Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .database import UserDB, APIKeyDB, SessionTokenDB, SlackWorkspaceDB, IncidentDB


async def get_user_by_id(db: AsyncSession, user_id: str) -> Optional[UserDB]:
    """Get user by ID."""
    result = await db.execute(select(UserDB).where(UserDB.id == user_id))
    return result.scalar_one_or_none()


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[UserDB]:
    """Get user by email."""
    result = await db.execute(select(UserDB).where(UserDB.email == email))
    return result.scalar_one_or_none()


async def get_session_by_token(db: AsyncSession, token: str) -> Optional[SessionTokenDB]:
    """Get session by token."""
    result = await db.execute(select(SessionTokenDB).where(SessionTokenDB.token == token))
    return result.scalar_one_or_none()


async def get_api_key(db: AsyncSession, key: str) -> Optional[APIKeyDB]:
    """Get API key by key string."""
    result = await db.execute(select(APIKeyDB).where(APIKeyDB.key == key))
    return result.scalar_one_or_none()


async def get_user_api_keys(db: AsyncSession, user_id: str) -> List[APIKeyDB]:
    """Get all API keys for a user."""
    result = await db.execute(select(APIKeyDB).where(APIKeyDB.user_id == user_id))
    return list(result.scalars().all())


async def get_slack_workspace(
    db: AsyncSession,
    team_id: str,
    active_only: bool = True
) -> Optional[SlackWorkspaceDB]:
    """Get Slack workspace by team ID."""
    query = select(SlackWorkspaceDB).where(SlackWorkspaceDB.team_id == team_id)
    if active_only:
        query = query.where(SlackWorkspaceDB.is_active == True)
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def get_user_slack_workspaces(
    db: AsyncSession,
    user_id: str,
    active_only: bool = False
) -> List[SlackWorkspaceDB]:
    """Get all Slack workspaces for a user."""
    query = select(SlackWorkspaceDB).where(SlackWorkspaceDB.user_id == user_id)
    if active_only:
        query = query.where(SlackWorkspaceDB.is_active == True)
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_incident_by_id(db: AsyncSession, incident_id: str) -> Optional[IncidentDB]:
    """Get incident by ID."""
    result = await db.execute(select(IncidentDB).where(IncidentDB.id == incident_id))
    return result.scalar_one_or_none()
