"""Admin Authentication & Session Service.

Handles password hashing, token lifecycle, and administrative session verification.
Admin credentials specified: phone "01926240062", password "1234", name "talukder".
"""
from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_session
from ..models import AdminSession, AdminUser


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """Hash password using PBKDF2-HMAC-SHA256 with 100,000 rounds."""
    if not salt:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return dk.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify password against stored hash."""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, password_hash)


def create_admin_session(
    session: Session, admin_id: int, duration_hours: int = 24
) -> AdminSession:
    """Generate a high-entropy session token for an admin user."""
    token = "adm_" + secrets.token_urlsafe(48)
    expires_at = _utcnow() + timedelta(hours=duration_hours)
    adm_session = AdminSession(
        admin_id=admin_id,
        token=token,
        expires_at=expires_at,
        is_revoked=False,
    )
    session.add(adm_session)
    session.flush()
    return adm_session


def verify_admin_token(session: Session, token: str) -> Optional[AdminUser]:
    """Verify bearer token, checking expiry and revocation."""
    if not token:
        return None
    # Strip optional "Bearer " prefix
    if token.startswith("Bearer "):
        token = token[7:].strip()
    adm_session = (
        session.query(AdminSession)
        .filter_by(token=token, is_revoked=False)
        .one_or_none()
    )
    if not adm_session:
        return None
    if adm_session.expires_at < _utcnow():
        return None
    admin = session.get(AdminUser, adm_session.admin_id)
    if not admin or not admin.is_active:
        return None
    return admin


def revoke_admin_token(session: Session, token: str) -> bool:
    """Revoke an active admin session."""
    if token.startswith("Bearer "):
        token = token[7:].strip()
    adm_session = session.query(AdminSession).filter_by(token=token).one_or_none()
    if adm_session:
        adm_session.is_revoked = True
        session.flush()
        return True
    return False


def get_current_admin(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    session: Session = Depends(get_session),
) -> AdminUser:
    """FastAPI Dependency: Authenticate admin user or raise 401 Unauthorized."""
    raw_token = authorization or x_admin_token
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    admin = verify_admin_token(session, raw_token)
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or revoked admin token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return admin
