"""Idempotent seed: 6 users, 2 billers, deterministic BD phone numbers.

Run via `python -m app.seed` or called from app.main lifespan.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from . import config
from .models import Account, AdminUser, Biller, FraudAlert, FraudAssessment, SecurityAuditLog, Transaction, User
from .services.admin_auth import hash_password
from .services.fraud_engine import FraudEngine


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Order matters for stable phone numbers.
DEMO_USERS: list[tuple[str, str]] = [
    ("bikash", "Bikash"),
    ("rishad", "Rishad"),
    ("arman", "Arman"),
    ("rahim", "Rahim"),
    ("tahzib", "Tahzib"),
    ("srijan", "Srijan"),
    ("mahdin", "Mahdin"),
]

DEMO_BILLERS: list[tuple[str, str, str]] = [
    # name, category, account_number
    ("Internet", "utility", "ISP-001"),
    ("Electricity", "utility", "PWR-002"),
    ("Shopping", "shopping", "SHOP-003"),
]


def _bd_phone(rng: random.Random) -> str:
    """Generate a +880 1XXX-XXXXXX number. 1[3-9]XX prefix, random 6 digits."""
    op = rng.choice(["13", "14", "15", "16", "17", "18", "19"])
    mid = f"{rng.randint(100, 999)}"
    last = f"{rng.randint(0, 999999):06d}"
    return f"+880 {op}{mid}-{last}"


def seed(session: Session) -> dict:
    """Insert demo data. Returns counts. Safe to call repeatedly."""
    rng = random.Random(20260922)  # fixed seed -> reproducible phone numbers

    user_count = 0
    for handle, display in DEMO_USERS:
        existing = session.query(User).filter_by(handle=handle).one_or_none()
        if existing:
            continue
        user = User(
            handle=handle,
            display_name=display,
            phone=_bd_phone(rng),
        )
        session.add(user)
        session.flush()
        # Seed balance: bikash rich, everyone else 10k.
        balance = (
            Decimal(config.SEED_BALANCE_BIKASH)
            if handle == "bikash"
            else Decimal(config.SEED_BALANCE_DEFAULT)
        )
        session.add(Account(user_id=user.id, balance_bdt=balance))
        user_count += 1

    biller_count = 0
    for name, category, acc_no in DEMO_BILLERS:
        existing = session.query(Biller).filter_by(name=name).one_or_none()
        if existing:
            continue
        session.add(Biller(name=name, category=category, account_number=acc_no))
        biller_count += 1

    # Seed Admin User (phone: 01926240062, pass: 1234, name: talukder)
    admin_phone = "01926240062"
    admin = session.query(AdminUser).filter_by(phone=admin_phone).one_or_none()
    pwd_hash, salt = hash_password("1234")
    if not admin:
        admin = AdminUser(
            phone=admin_phone,
            display_name="talukder",
            password_hash=pwd_hash,
            salt=salt,
            role="super_admin",
            is_active=True,
        )
        session.add(admin)
        session.flush()
    else:
        # Update credentials to ensure matching requirements
        admin.display_name = "talukder"
        admin.password_hash = pwd_hash
        admin.salt = salt
        admin.is_active = True
        session.flush()

    # Backfill or seed initial fraud assessments on existing transactions if empty
    existing_assessments = session.query(FraudAssessment).count()
    if existing_assessments == 0:
        txns = session.query(Transaction).limit(30).all()
        for t in txns:
            rec_id = None
            if t.to_account_id:
                rec_u = session.query(User).join(Account).filter(Account.id == t.to_account_id).first()
                if rec_u:
                    rec_id = rec_u.id
            FraudEngine.evaluate(
                session,
                initiator_user_id=t.initiator_user_id,
                recipient_user_id=rec_id,
                amount_bdt=t.amount_bdt,
                txn_id=t.id,
                persist=True,
            )

    # Ensure a few realistic sample alerts exist for triage demonstration if alerts count is low
    if session.query(FraudAlert).count() < 3:
        # 1. High risk alert: Large deviation / balance drain
        res_high = FraudEngine.evaluate(
            session,
            initiator_user_id=1,
            recipient_user_id=4,
            amount_bdt=Decimal("45000.00"),
            persist=True,
        )
        # 2. Medium risk alert: Velocity spike
        a_med = FraudAssessment(
            initiator_user_id=2,
            recipient_user_id=3,
            amount_bdt=Decimal("8500.00"),
            risk_score=0.55,
            risk_level="medium",
            status="flagged_review",
            rules_triggered_json=json.dumps(["RULE_VELOCITY_SPIKE_1H", "RULE_MODERATE_AMOUNT_DEVIATION"]),
            reasons_json=json.dumps([
                "Rapid transaction velocity: 4 transactions initiated in the past hour.",
                "Above-average amount: transaction is 3.2x higher than typical spend."
            ]),
            features_json=json.dumps({"txns_1h": 4, "amount_bdt": 8500.0, "amount_to_avg_ratio": 3.2}),
            model_version=FraudEngine.MODEL_VERSION,
            latency_ms=1.8,
        )
        session.add(a_med)
        session.flush()
        alert_med = FraudAlert(
            assessment_id=a_med.id,
            user_id=2,
            alert_type="RULE_VELOCITY_SPIKE_1H",
            severity="medium",
            status="investigating",
            detection_reasons="Rapid transaction velocity: 4 transactions in past hour.",
            investigation_notes="[System]: Assigned to fraud review queue.",
        )
        session.add(alert_med)

        # 3. Resolved alert (previously investigated)
        a_resolved = FraudAssessment(
            initiator_user_id=3,
            recipient_user_id=1,
            amount_bdt=Decimal("12000.00"),
            risk_score=0.48,
            risk_level="medium",
            status="cleared",
            rules_triggered_json=json.dumps(["RULE_UNUSUAL_HOURS_HIGH_VALUE"]),
            reasons_json=json.dumps(["High-value transfer initiated during unusual late-night hours."]),
            features_json=json.dumps({"is_night_hours": True, "amount_bdt": 12000.0}),
            model_version=FraudEngine.MODEL_VERSION,
            latency_ms=2.1,
        )
        session.add(a_resolved)
        session.flush()
        alert_resolved = FraudAlert(
            assessment_id=a_resolved.id,
            user_id=3,
            alert_type="RULE_UNUSUAL_HOURS_HIGH_VALUE",
            severity="medium",
            status="resolved",
            detection_reasons="High-value transfer during unusual hours.",
            investigation_notes=f"[{admin.display_name}]: User confirmed transfer for urgent festival shopping. Cleared safe.",
            resolved_by_admin_id=admin.id,
            resolved_at=_utcnow(),
        )
        session.add(alert_resolved)

        # Log initial audit entries
        session.add(SecurityAuditLog(
            admin_id=admin.id,
            action="system_seed",
            target_type="system",
            details_json=json.dumps({"event": "Seeded initial fraud rules and baseline assessments"}),
        ))
        session.flush()

    return {"new_users": user_count, "new_billers": biller_count, "admin": admin_phone}


if __name__ == "__main__":
    from .db import SessionLocal, init_db

    init_db()
    with SessionLocal() as s:
        result = seed(s)
        s.commit()
        print(result)
