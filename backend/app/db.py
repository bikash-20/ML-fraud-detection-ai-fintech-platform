"""SQLAlchemy engine, session factory, schema init."""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from . import config
from .models import Base


def _engine_url() -> str:
    return f"sqlite:///{config.DB_PATH}"


def make_engine() -> Engine:
    """Build a fresh engine bound to the current config.DB_PATH.

    Factored out so tests can rebuild it against a tmp file without messing
    with module-level singletons.
    """
    eng = create_engine(
        _engine_url(),
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(eng, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _):
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.close()

    return eng


# Default engine used by the running app; tests override via reset_engine().
_engine: Engine = make_engine()
_SessionLocal = sessionmaker(bind=_engine, autoflush=False, expire_on_commit=False)


def reset_engine() -> Engine:
    """Drop the cached engine and rebuild against current config. Test-only."""
    global _engine, _SessionLocal
    try:
        _engine.dispose()
    except Exception:
        pass
    _engine = make_engine()
    _SessionLocal.configure(bind=_engine)
    return _engine


def init_db() -> None:
    """Create tables if they don't exist. Idempotent."""
    Base.metadata.create_all(_engine)
    # Lightweight development migration for the existing SQLite demo DB.
    # Production deployments should run a real migration tool such as Alembic.
    if _engine.dialect.name == "sqlite":
        _migrate_requests_idempotency_key()
        _migrate_users_face_columns()
        _migrate_users_security_columns()
        _migrate_users_tier_column()
        _migrate_user_types_and_tiers()
        _migrate_fraud_alerts_resolution_columns()


def _migrate_user_types_and_tiers() -> None:
    """Add user_type, account_tier, kyc_status, business_name, and limit columns to users."""
    columns = {column["name"] for column in inspect(_engine).get_columns("users")}
    with _engine.begin() as connection:
        if "account_tier" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN account_tier VARCHAR(16) NOT NULL DEFAULT 'personal'")
            )
            # Sync existing tier data if available
            if "tier" in columns:
                connection.execute(text("UPDATE users SET account_tier = tier WHERE tier IS NOT NULL"))
        if "user_type" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN user_type VARCHAR(32) NOT NULL DEFAULT 'student'")
            )
        if "kyc_status" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN kyc_status VARCHAR(16) NOT NULL DEFAULT 'unverified'")
            )
        if "business_name" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN business_name VARCHAR(128) NULL")
            )
        if "daily_limit" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN daily_limit NUMERIC(12, 2) NULL")
            )
        if "single_txn_limit" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN single_txn_limit NUMERIC(12, 2) NULL")
            )
        if "requested_upgrade_tier" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN requested_upgrade_tier VARCHAR(16) NULL")
            )
        if "requested_upgrade_at" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN requested_upgrade_at DATETIME NULL")
            )


def _migrate_users_tier_column() -> None:
    """Add tier column to users table if missing."""
    columns = {column["name"] for column in inspect(_engine).get_columns("users")}
    with _engine.begin() as connection:
        if "tier" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN tier VARCHAR(16) NOT NULL DEFAULT 'personal'")
            )


def _migrate_fraud_alerts_resolution_columns() -> None:
    """Add resolution_reason_code and is_confirmed_fraud columns to fraud_alerts if missing."""
    insp = inspect(_engine)
    if not insp.has_table("fraud_alerts"):
        return
    columns = {column["name"] for column in insp.get_columns("fraud_alerts")}
    with _engine.begin() as connection:
        if "resolution_reason_code" not in columns:
            connection.execute(
                text("ALTER TABLE fraud_alerts ADD COLUMN resolution_reason_code VARCHAR(64) NULL")
            )
        if "is_confirmed_fraud" not in columns:
            connection.execute(
                text("ALTER TABLE fraud_alerts ADD COLUMN is_confirmed_fraud BOOLEAN NULL")
            )


def _migrate_users_security_columns() -> None:
    """Add is_flagged and is_frozen columns to users table if missing."""
    columns = {column["name"] for column in inspect(_engine).get_columns("users")}
    with _engine.begin() as connection:
        if "is_flagged" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN is_flagged BOOLEAN NOT NULL DEFAULT 0")
            )
        if "is_frozen" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN is_frozen BOOLEAN NOT NULL DEFAULT 0")
            )


def _migrate_requests_idempotency_key() -> None:
    """Backfill the requests.idempotency_key column on legacy DBs."""
    columns = {column["name"] for column in inspect(_engine).get_columns("requests")}
    if "idempotency_key" not in columns:
        with _engine.begin() as connection:
            connection.execute(
                text("ALTER TABLE requests ADD COLUMN idempotency_key VARCHAR(64) NOT NULL DEFAULT ''")
            )
    with _engine.begin() as connection:
        legacy_rows = connection.execute(
            text(
                "SELECT id FROM requests "
                "WHERE idempotency_key IS NULL OR idempotency_key = ''"
            )
        ).scalars().all()
        for request_id in legacy_rows:
            connection.execute(
                text(
                    "UPDATE requests SET idempotency_key = :key "
                    "WHERE id = :request_id"
                ),
                {"key": f"legacy-request:{request_id}", "request_id": request_id},
            )
        connection.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_request_idem "
            "ON requests (asker_user_id, idempotency_key)"
        ))


def _migrate_users_face_columns() -> None:
    """Add the Face ID columns to users on legacy DBs.

    Both columns are nullable — NULL embedding means "not enrolled".
    Idempotent: skipped if columns already exist.
    """
    columns = {column["name"] for column in inspect(_engine).get_columns("users")}
    with _engine.begin() as connection:
        if "face_embedding" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN face_embedding BLOB")
            )
        if "face_enrolled_at" not in columns:
            connection.execute(
                text("ALTER TABLE users ADD COLUMN face_enrolled_at DATETIME")
            )


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional context. Commits on success, rolls back on exception."""
    s = _SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency. Caller is responsible for commit/rollback."""
    s = _SessionLocal()
    try:
        yield s
    finally:
        s.close()


# Module-level alias for callers that want the bound session factory.
# Note: this is a reference, but since _SessionLocal.configure(bind=...) updates
# the existing sessionmaker in place, callers using SessionLocal() will pick up
# the new engine automatically.
SessionLocal = _SessionLocal
