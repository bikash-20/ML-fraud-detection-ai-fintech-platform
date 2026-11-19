"""Idempotent seed: 6 users, 2 billers, deterministic BD phone numbers.

Run via `python -m app.seed` or called from app.main lifespan.
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from . import config
from .models import Account, AdminUser, Biller, FraudAlert, FraudAssessment, SecurityAuditLog, Transaction, User
from .services.admin_auth import hash_password
from .services.fraud_engine import FraudEngine


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


DEMO_USER_SPECS: list[dict] = [
    {"handle": "bikash", "display": "Bikash", "user_type": "student", "tier": "personal", "kyc": "verified", "balance": Decimal("5500.00"), "biz": None},
    {"handle": "rishad", "display": "Rishad", "user_type": "salaried", "tier": "verified", "kyc": "verified", "balance": Decimal("42000.00"), "biz": None},
    {"handle": "arman", "display": "Arman Store", "user_type": "shopkeeper", "tier": "verified", "kyc": "verified", "balance": Decimal("145000.00"), "biz": "Arman Grocery & Provisions"},
    {"handle": "tahzib", "display": "Tahzib Agent Point", "user_type": "agent", "tier": "verified", "kyc": "verified", "balance": Decimal("320000.00"), "biz": "Tahzib Digital MFS Point"},
    {"handle": "srijan", "display": "Srijan Enterprise", "user_type": "business", "tier": "business", "kyc": "verified", "balance": Decimal("1850000.00"), "biz": "Srijan Electronics & Trade Ltd"},
    {"handle": "mahdin", "display": "Mahdin", "user_type": "student", "tier": "personal", "kyc": "unverified", "balance": Decimal("2400.00"), "biz": None},
    {"handle": "rahim", "display": "Rahim Traders", "user_type": "business", "tier": "personal", "kyc": "unverified", "balance": Decimal("75000.00"), "biz": "Rahim Agro Commodities"},
]

DEMO_USERS: list[tuple[str, str]] = [
    (spec["handle"], spec["display"]) for spec in DEMO_USER_SPECS
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
    for spec in DEMO_USER_SPECS:
        handle = spec["handle"]
        display = spec["display"]
        existing = session.query(User).filter_by(handle=handle).one_or_none()
        if existing:
            # Sync user type and tier attributes if missing
            if not getattr(existing, "user_type", None) or existing.user_type == "student":
                existing.user_type = spec["user_type"]
                existing.account_tier = spec["tier"]
                existing.tier = spec["tier"]
                existing.kyc_status = spec["kyc"]
                existing.display_name = spec["display"]
                existing.business_name = spec["biz"]
            continue
        user = User(
            handle=handle,
            display_name=display,
            phone=_bd_phone(rng),
            user_type=spec["user_type"],
            account_tier=spec["tier"],
            tier=spec["tier"],
            kyc_status=spec["kyc"],
            business_name=spec["biz"],
        )
        session.add(user)
        session.flush()
        balance = spec["balance"]
        acct = Account(user_id=user.id, balance_bdt=balance)
        session.add(acct)
        session.flush()

        # Create opening cash_in ledger transaction backdated by 45 days so 14-day history is established
        opening_time = _utcnow() - timedelta(days=45)
        session.add(Transaction(
            idempotency_key=f"seed-opening-{user.id}-{int(opening_time.timestamp())}",
            initiator_user_id=user.id,
            from_account_id=None,
            to_account_id=acct.id,
            amount_bdt=balance,
            kind="cash_in",
            status="completed",
            note=f"Initial {spec['user_type'].capitalize()} Deposit",
            created_at=opening_time,
            completed_at=opening_time,
        ))
        user_count += 1

    # Backfill any existing opening seed deposits to 45 days ago so live DBs have established baseline
    session.query(Transaction).filter(
        Transaction.kind == "cash_in",
        Transaction.from_account_id.is_(None),
        (Transaction.note.like("Initial%") | Transaction.idempotency_key.like("seed-opening-%")),
    ).update(
        {
            "created_at": _utcnow() - timedelta(days=45),
            "completed_at": _utcnow() - timedelta(days=45),
        },
        synchronize_session=False,
    )
    session.flush()

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

    # Seed realistic 14-day historical transactions so Admin Volume & Activity chart is vibrant
    non_cash_in = session.query(Transaction).filter(Transaction.kind != "cash_in").count()
    if non_cash_in < 10:
        bikash_acct = session.query(Account).join(User).filter(User.handle == "bikash").first()
        rishad_acct = session.query(Account).join(User).filter(User.handle == "rishad").first()
        arman_acct = session.query(Account).join(User).filter(User.handle == "arman").first()
        tahzib_acct = session.query(Account).join(User).filter(User.handle == "tahzib").first()
        srijan_acct = session.query(Account).join(User).filter(User.handle == "srijan").first()
        mahdin_acct = session.query(Account).join(User).filter(User.handle == "mahdin").first()
        rahim_acct = session.query(Account).join(User).filter(User.handle == "rahim").first()

        if rishad_acct and arman_acct and tahzib_acct and srijan_acct:
            hist_samples = [
                (13, arman_acct, rishad_acct, Decimal("1250.00"), "send", "Campus study supplies"),
                (12, rishad_acct, arman_acct, Decimal("3200.00"), "send", "Provisions & grocery"),
                (11, tahzib_acct, arman_acct, Decimal("26000.00"), "send", "Agent customer settlement"),
                (10, arman_acct, srijan_acct, Decimal("680.00"), "send", "Hardware supplies"),
                (9, srijan_acct, arman_acct, Decimal("85000.00"), "send", "Wholesale inventory supply"),
                (8, rishad_acct, arman_acct, Decimal("2400.00"), "send", "Weekly grocery"),
                (7, arman_acct, srijan_acct, Decimal("42000.00"), "send", "Merchant stock replenishment"),
                (6, rishad_acct, tahzib_acct, Decimal("600.00"), "send", "Utility recharge"),
                (5, tahzib_acct, arman_acct, Decimal("35000.00"), "send", "Agent merchant cash-out"),
                (4, srijan_acct, tahzib_acct, Decimal("120000.00"), "send", "Commercial liquidity transfer"),
                (3, mahdin_acct if mahdin_acct else arman_acct, arman_acct, Decimal("320.00"), "send", "Stationery & printing"),
                (2, rishad_acct, srijan_acct, Decimal("12000.00"), "send", "Office equipment purchase"),
                (1, rahim_acct if rahim_acct else arman_acct, arman_acct, Decimal("2200.00"), "send", "Household provisions"),
            ]
            for day_off, from_a, to_a, amt, kind, note in hist_samples:
                tx_time = _utcnow() - timedelta(days=day_off, hours=3)
                session.add(Transaction(
                    idempotency_key=f"seed-hist-{day_off}-{int(tx_time.timestamp())}",
                    initiator_user_id=from_a.user_id,
                    from_account_id=from_a.id,
                    to_account_id=to_a.id,
                    amount_bdt=amt,
                    kind=kind,
                    status="completed",
                    note=note,
                    created_at=tx_time,
                    completed_at=tx_time,
                ))
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
