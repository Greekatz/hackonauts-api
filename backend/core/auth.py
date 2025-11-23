"""
Authentication Utilities
Secure password hashing and token management.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt

from .config import config


def hash_password(password: str) -> str:
    """
    Hash password using bcrypt with configurable rounds.

    Args:
        password: Plain text password

    Returns:
        Bcrypt hash string
    """
    salt = bcrypt.gensalt(rounds=config.BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        password: Plain text password to verify
        hashed: Bcrypt hash to check against

    Returns:
        True if password matches
    """
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False


def generate_token() -> str:
    """Generate a cryptographically secure session token."""
    return secrets.token_urlsafe(32)


def get_token_expiry() -> datetime:
    """Get the expiry datetime for a new session token (naive UTC)."""
    return datetime.utcnow() + timedelta(hours=config.SESSION_TOKEN_EXPIRE_HOURS)


def is_token_expired(expires_at: Optional[datetime]) -> bool:
    """
    Check if a token has expired.

    Args:
        expires_at: Token expiry datetime (naive UTC)

    Returns:
        True if token is expired or expires_at is None
    """
    if expires_at is None:
        return False  # No expiry set means token doesn't expire

    # Use naive UTC datetime for comparison
    now = datetime.utcnow()

    # If expires_at has timezone info, make it naive
    if expires_at.tzinfo is not None:
        expires_at = expires_at.replace(tzinfo=None)

    return now > expires_at


def utc_now() -> datetime:
    """Get current UTC datetime (naive, for database compatibility)."""
    return datetime.utcnow()
