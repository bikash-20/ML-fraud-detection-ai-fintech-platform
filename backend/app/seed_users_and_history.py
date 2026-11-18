"""Realistic User Types, Account Tiers, and 30-Day Ledger Seeding Script.

Applies:
- Realistic personas and tiers to existing users in wallet.db
- Proper opening/top-up cash_in ledger transactions (ledger invariance)
- 30 days of realistic, type-consistent transactions (Dhaka time, repeated recipients, business hours)
- Dynamic fraud assessments for realistic 30-day baselines
"""
from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import numpy as np

from sqlalchemy import func
from app.db import SessionLocal, init_db
from app.models import (
    Account,
    Biller,
    FraudAssessment,
    SecurityAuditLog,
    Transaction,
    TxnKind,
    TxnStatus,
    User,
)
from app.services.fraud_engine import FraudEngine
from app.tier_config import TIER_LIMITS, get_effective_tier


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def seed_realistic_users_and_history():
    init_db()
    s = SessionLocal()

    rng = random.Random(20261118)
    now = _utcnow()

    # User definitions with realistic roles and target ending balances
    # Student: 500 - 8,000
    # Salaried: 10,000 - 60,000
    # Shopkeeper: 50,000 - 250,000
    # Agent: 100,000 - 500,000
    # Business: 500,000 - 3,000,000
    USER_PROFILES = {
        "bikash": {
            "user_type": "student",
            "account_tier": "personal",
            "tier": "personal",
            "kyc_status": "verified",
            "display_name": "Bikash",
            "business_name": None,
            "target_balance": Decimal("5500.00"),
            "created_at": now - timedelta(days=60),
        },
        "rishad": {
            "user_type": "salaried",
            "account_tier": "verified",
            "tier": "verified",
            "kyc_status": "verified",
            "display_name": "Rishad",
            "business_name": None,
            "target_balance": Decimal("42000.00"),
            "created_at": now - timedelta(days=60),
        },
        "arman": {
            "user_type": "shopkeeper",
            "account_tier": "verified",
            "tier": "verified",
            "kyc_status": "verified",
            "display_name": "Arman Store",
            "business_name": "Arman Grocery & Provisions",
            "target_balance": Decimal("145000.00"),
            "created_at": now - timedelta(days=60),
        },
        "tahzib": {
            "user_type": "agent",
            "account_tier": "verified",
            "tier": "verified",
            "kyc_status": "verified",
            "display_name": "Tahzib Agent Point",
            "business_name": "Tahzib Digital MFS Point",
            "target_balance": Decimal("320000.00"),
            "created_at": now - timedelta(days=60),
        },
        "srijan": {
            "user_type": "business",
            "account_tier": "business",
            "tier": "business",
            "kyc_status": "verified",
            "display_name": "Srijan Enterprise",
            "business_name": "Srijan Electronics & Trade Ltd",
            "target_balance": Decimal("1850000.00"),
            "created_at": now - timedelta(days=60),
        },
        "mahdin": {
            "user_type": "student",
            "account_tier": "personal",
            "tier": "personal",
            "kyc_status": "unverified",
            "display_name": "Mahdin",
            "business_name": None,
            "target_balance": Decimal("2400.00"),
            "created_at": now - timedelta(days=3),  # Brand new account (<7 days old)
        },
        "rahim": {
            "user_type": "business",
            "account_tier": "personal",  # Unverified business upgrade request -> restricted to personal
            "tier": "personal",
            "kyc_status": "unverified",
            "display_name": "Rahim Traders",
            "business_name": "Rahim Agro Commodities",
            "requested_upgrade_tier": "business",
            "requested_upgrade_at": now - timedelta(days=1),
            "target_balance": Decimal("75000.00"),
            "created_at": now - timedelta(days=25),
        },
    }

    # 1. Update user records
    users_by_handle = {}
    accounts_by_user_id = {}

    for handle, prof in USER_PROFILES.items():
        u = s.query(User).filter_by(handle=handle).first()
        if not u:
            continue
        u.user_type = prof["user_type"]
        u.account_tier = prof["account_tier"]
        u.tier = prof["tier"]
        u.kyc_status = prof["kyc_status"]
        u.display_name = prof["display_name"]
        u.business_name = prof["business_name"]
        u.created_at = prof["created_at"]
        if "requested_upgrade_tier" in prof:
            u.requested_upgrade_tier = prof["requested_upgrade_tier"]
            u.requested_upgrade_at = prof["requested_upgrade_at"]
        s.flush()

        acct = s.query(Account).filter_by(user_id=u.id).first()
        if not acct:
            acct = Account(user_id=u.id, balance_bdt=Decimal("0.00"))
            s.add(acct)
            s.flush()
        users_by_handle[handle] = u
        accounts_by_user_id[u.id] = acct

    # 2. Seed 30-day realistic transactions between accounts
    # Helper to insert transaction
    txns_to_create = []

    # Student Bikash transactions (30 days: small peer sends, food/groceries at Arman Store)
    for day in range(28, 1, -2):
        ts = now - timedelta(days=day, hours=rng.randint(10, 20), minutes=rng.randint(5, 50))
        amt = Decimal(str(rng.choice([150.0, 250.0, 350.0, 500.0, 750.0, 1200.0])))
        rec = rng.choice(["arman", "rishad", "mahdin" if day < 3 else "arman"])
        txns_to_create.append({
            "initiator": "bikash",
            "from": "bikash",
            "to": rec,
            "amount": amt,
            "kind": "send",
            "status": "completed",
            "note": rng.choice(["Lunch at canteen", "Snacks & chai", "Book sharing", "Study notes", "Groceries"]),
            "created_at": ts,
        })

    # Salaried Rishad transactions (30 days: month-end bills, shopping at Arman, sending Bikash)
    for day in range(29, 1, -3):
        ts = now - timedelta(days=day, hours=rng.randint(9, 21), minutes=rng.randint(5, 55))
        amt = Decimal(str(rng.choice([1200.0, 1800.0, 2500.0, 3500.0, 4800.0])))
        rec = rng.choice(["arman", "bikash"])
        txns_to_create.append({
            "initiator": "rishad",
            "from": "rishad",
            "to": rec,
            "amount": amt,
            "kind": "send",
            "status": "completed",
            "note": rng.choice(["Monthly groceries", "Weekend dinner", "Shared utility", "Allowance"]),
            "created_at": ts,
        })

    # Shopkeeper Arman wholesale supplier payments to Srijan Enterprise
    for day in range(27, 2, -5):
        ts = now - timedelta(days=day, hours=rng.randint(11, 16), minutes=rng.randint(10, 45))
        amt = Decimal(str(rng.choice([15000.0, 22000.0, 28000.0, 35000.0])))
        txns_to_create.append({
            "initiator": "arman",
            "from": "arman",
            "to": "srijan",
            "amount": amt,
            "kind": "send",
            "status": "completed",
            "note": "Wholesale electronics & stock replenishment",
            "created_at": ts,
        })

    # Agent Tahzib servicing customer cash_ins/transfers
    for day in range(28, 1, -2):
        ts = now - timedelta(days=day, hours=rng.randint(10, 18), minutes=rng.randint(5, 50))
        amt = Decimal(str(rng.choice([8000.0, 15000.0, 25000.0, 32000.0])))
        rec = rng.choice(["rishad", "arman", "bikash"])
        txns_to_create.append({
            "initiator": "tahzib",
            "from": "tahzib",
            "to": rec,
            "amount": amt,
            "kind": "send",
            "status": "completed",
            "note": "Agent remittance payout / customer transfer",
            "created_at": ts,
        })

    # Business Srijan Enterprise commercial transactions (supplier payments & agent settlements)
    for day in range(26, 2, -4):
        ts = now - timedelta(days=day, hours=rng.randint(10, 17), minutes=rng.randint(10, 45))
        amt = Decimal(str(rng.choice([85000.0, 120000.0, 180000.0, 240000.0])))
        rec = rng.choice(["tahzib", "arman"])
        txns_to_create.append({
            "initiator": "srijan",
            "from": "srijan",
            "to": rec,
            "amount": amt,
            "kind": "send",
            "status": "completed",
            "note": "Commercial settlement / dealer distribution invoice",
            "created_at": ts,
        })

    # Brand-new user Mahdin (<3 days)
    txns_to_create.append({
        "initiator": "mahdin",
        "from": "mahdin",
        "to": "bikash",
        "amount": Decimal("350.00"),
        "kind": "send",
        "status": "completed",
        "note": "Campus tea & printout",
        "created_at": now - timedelta(days=2, hours=4),
    })
    txns_to_create.append({
        "initiator": "mahdin",
        "from": "mahdin",
        "to": "arman",
        "amount": Decimal("250.00"),
        "kind": "send",
        "status": "completed",
        "note": "Notebook & stationery",
        "created_at": now - timedelta(days=1, hours=2),
    })

    # Rahim (<25 days, business request unverified)
    txns_to_create.append({
        "initiator": "rahim",
        "from": "rahim",
        "to": "arman",
        "amount": Decimal("5000.00"),
        "kind": "send",
        "status": "completed",
        "note": "Local supplies order",
        "created_at": now - timedelta(days=10, hours=3),
    })
    txns_to_create.append({
        "initiator": "rahim",
        "from": "rahim",
        "to": "arman",
        "amount": Decimal("5000.00"),
        "kind": "send",
        "status": "completed",
        "note": "Additional provisions",
        "created_at": now - timedelta(days=5, hours=2),
    })

    # Insert seeded transactions into DB
    for t_spec in txns_to_create:
        u_init = users_by_handle[t_spec["initiator"]]
        u_from = users_by_handle[t_spec["from"]]
        u_to = users_by_handle[t_spec["to"]]
        acct_from = accounts_by_user_id[u_from.id]
        acct_to = accounts_by_user_id[u_to.id]

        idem_key = f"seed-history-{u_init.id}-{int(t_spec['created_at'].timestamp())}-{rng.randint(1000, 9999)}"
        txn = Transaction(
            idempotency_key=idem_key,
            initiator_user_id=u_init.id,
            from_account_id=acct_from.id,
            to_account_id=acct_to.id,
            amount_bdt=t_spec["amount"],
            kind=t_spec["kind"],
            status=t_spec["status"],
            note=t_spec["note"],
            created_at=t_spec["created_at"],
            completed_at=t_spec["created_at"],
        )
        s.add(txn)

    s.flush()

    # 3. Compute net historical credits/debits per account from all completed non-cash_in transactions
    # and create opening-balance cash_in transactions to achieve the exact target balance!
    # Formula:
    # Target_Balance = Opening_Cash_In + Total_Credits - Total_Debits
    # Opening_Cash_In = Target_Balance + Total_Debits - Total_Credits
    print("\n--- Ledger Balancing & Opening Top-Up Calculation ---")
    for handle, prof in USER_PROFILES.items():
        u = users_by_handle[handle]
        acct = accounts_by_user_id[u.id]
        target_bal = prof["target_balance"]

        # Calculate current sum of completed debits (outgoing sends)
        debits = s.query(func.coalesce(func.sum(Transaction.amount_bdt), Decimal("0.00"))).filter(
            Transaction.from_account_id == acct.id,
            Transaction.status == TxnStatus.COMPLETED.value,
        ).scalar()

        # Calculate current sum of completed credits (incoming sends) EXCLUDING existing cash_ins
        credits = s.query(func.coalesce(func.sum(Transaction.amount_bdt), Decimal("0.00"))).filter(
            Transaction.to_account_id == acct.id,
            Transaction.from_account_id.isnot(None),
            Transaction.status == TxnStatus.COMPLETED.value,
        ).scalar()

        # Any existing cash_ins
        existing_cash_ins = s.query(func.coalesce(func.sum(Transaction.amount_bdt), Decimal("0.00"))).filter(
            Transaction.to_account_id == acct.id,
            Transaction.from_account_id.is_(None),
            Transaction.kind == "cash_in",
            Transaction.status == TxnStatus.COMPLETED.value,
        ).scalar()

        net_flow = credits - debits + existing_cash_ins
        needed_cash_in = target_bal - net_flow

        if needed_cash_in > 0:
            cash_in_ts = prof["created_at"] + timedelta(hours=1)
            idem = f"opening-cash-in-{u.id}-{int(cash_in_ts.timestamp())}"
            cash_in_txn = Transaction(
                idempotency_key=idem,
                initiator_user_id=u.id,
                from_account_id=None,  # External banking/card funding
                to_account_id=acct.id,
                amount_bdt=needed_cash_in,
                kind="cash_in",
                status="completed",
                note=f"Verified Bank Top-up / Initial {prof['user_type'].capitalize()} Funding",
                created_at=cash_in_ts,
                completed_at=cash_in_ts,
            )
            s.add(cash_in_txn)
            s.flush()
            print(f"Created cash_in for @{handle}: ৳{needed_cash_in:,.2f}")
        elif needed_cash_in < 0:
            # If net flow exceeded target, add a balancing outward adjustment (e.g. cash_out)
            cash_out_ts = prof["created_at"] + timedelta(hours=2)
            idem = f"balancing-adjustment-{u.id}-{int(cash_out_ts.timestamp())}"
            adj_txn = Transaction(
                idempotency_key=idem,
                initiator_user_id=u.id,
                from_account_id=acct.id,
                to_account_id=None,
                amount_bdt=abs(needed_cash_in),
                kind="cash_out",
                status="completed",
                note="Bank Withdrawal / Account Rebalancing",
                created_at=cash_out_ts,
                completed_at=cash_out_ts,
            )
            s.add(adj_txn)
            s.flush()
            print(f"Created cash_out adjustment for @{handle}: ৳{abs(needed_cash_in):,.2f}")

        # Recalculate true ledger sum:
        total_in = s.query(func.coalesce(func.sum(Transaction.amount_bdt), Decimal("0.00"))).filter(
            Transaction.to_account_id == acct.id,
            Transaction.status == TxnStatus.COMPLETED.value,
        ).scalar()
        total_out = s.query(func.coalesce(func.sum(Transaction.amount_bdt), Decimal("0.00"))).filter(
            Transaction.from_account_id == acct.id,
            Transaction.status == TxnStatus.COMPLETED.value,
        ).scalar()

        true_ledger_balance = total_in - total_out
        acct.balance_bdt = true_ledger_balance
        s.flush()

        print(f"@{handle} ({prof['user_type']}, {prof['account_tier']}): In=৳{total_in:,.2f}, Out=৳{total_out:,.2f} => Balance = ৳{acct.balance_bdt:,.2f}")

    # 4. Generate Fraud Assessments on historical transactions so that 30-day baseline medians and features are grounded
    completed_sends = (
        s.query(Transaction)
        .filter(
            Transaction.kind == "send",
            Transaction.status == TxnStatus.COMPLETED.value,
            Transaction.from_account_id.isnot(None),
        )
        .order_by(Transaction.created_at.asc())
        .all()
    )

    print(f"\nEvaluating fraud assessments on {len(completed_sends)} completed transactions...")
    assessed_count = 0
    for txn in completed_sends:
        existing = s.query(FraudAssessment).filter_by(txn_id=txn.id).first()
        if existing:
            continue

        r_id = None
        if txn.to_account_id:
            r_acct = s.get(Account, txn.to_account_id)
            if r_acct:
                r_id = r_acct.user_id

        FraudEngine.evaluate(
            s,
            initiator_user_id=txn.initiator_user_id,
            recipient_user_id=r_id,
            amount_bdt=txn.amount_bdt,
            txn_id=txn.id,
            persist=True,
        )
        assessed_count += 1

    print(f"Generated {assessed_count} fresh fraud assessments.")

    # 5. Log security audit log for realistic seed
    admin = s.query(User).first()
    s.add(SecurityAuditLog(
        admin_id=admin.id if admin else 1,
        action="seed_user_types_and_tiers",
        target_type="system",
        details_json=json.dumps({"event": "Seeded 30-day type-consistent transaction history and realistic account tiers"}),
    ))

    s.commit()
    s.close()
    print("Seed and ledger balancing completed successfully!")


if __name__ == "__main__":
    seed_realistic_users_and_history()
