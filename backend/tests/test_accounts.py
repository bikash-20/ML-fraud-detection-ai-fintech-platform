from datetime import datetime, timezone
from decimal import Decimal
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Account, Transaction, TxnStatus, User


def test_history_returns_current_balance_for_today():
    client = TestClient(app)
    response = client.get("/users/1/history")

    assert response.status_code == 200
    body = response.json()
    assert body["timeline"][-1]["balance"] == float(body["balance_bdt"])


def test_history_excludes_cancelled_and_pending_transactions():
    """Recent history must ONLY return completed transactions.
    Unconfirmed, pending, cancelled, or interrupted transfers must be strictly excluded.
    """
    with SessionLocal() as s:
        bikash = s.query(User).filter_by(handle="bikash").one()
        arman = s.query(User).filter_by(handle="arman").one()
        bikash_acct = s.query(Account).filter_by(user_id=bikash.id).one()
        arman_acct = s.query(Account).filter_by(user_id=arman.id).one()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        # Add a pending transaction (e.g. before user taps confirmation toggle)
        pending_txn = Transaction(
            idempotency_key="pending-key-5000",
            initiator_user_id=bikash.id,
            from_account_id=bikash_acct.id,
            to_account_id=arman_acct.id,
            amount_bdt=Decimal("5000.00"),
            kind="send",
            status=TxnStatus.PENDING.value,
            completed_at=None,
            created_at=now,
        )
        # Add a cancelled transaction (e.g. network disconnect or user declined)
        cancelled_txn = Transaction(
            idempotency_key="cancelled-key-450",
            initiator_user_id=bikash.id,
            from_account_id=bikash_acct.id,
            to_account_id=arman_acct.id,
            amount_bdt=Decimal("450.00"),
            kind="split_child",
            status=TxnStatus.CANCELLED.value,
            completed_at=None,
            created_at=now,
        )
        s.add_all([pending_txn, cancelled_txn])
        s.commit()
        arman_id = arman.id

    client = TestClient(app)
    response = client.get(f"/users/{arman_id}/history")

    assert response.status_code == 200
    body = response.json()
    txns = body["txns"]

    # All returned transactions must have status == "completed" and a completed_at timestamp
    for t in txns:
        assert t["status"] == "completed", f"Non-completed txn found: {t}"
        assert t["completed_at"] is not None

    # Specifically verify that pending and cancelled transactions are never present
    txn_amounts = [t["amount_bdt"] for t in txns]
    assert "5000.00" not in txn_amounts, "Unconfirmed ৳5000 send incorrectly present in history"
    assert "450.00" not in txn_amounts, "Cancelled ৳450 split incorrectly present in history"


def test_history_savings_has_named_counterparty():
    """Savings transactions must display a proper counterparty instead of null or 'Unknown'."""
    with SessionLocal() as s:
        bikash = s.query(User).filter_by(handle="bikash").one()
        acct = s.query(Account).filter_by(user_id=bikash.id).one()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        savings_txn = Transaction(
            idempotency_key="savings-key-200",
            initiator_user_id=bikash.id,
            from_account_id=acct.id,
            to_account_id=None,
            amount_bdt=Decimal("200.00"),
            kind="savings",
            status=TxnStatus.COMPLETED.value,
            completed_at=now,
            note="Saving for Eid",
            created_at=now,
        )
        s.add(savings_txn)
        s.commit()
        user_id = bikash.id

    client = TestClient(app)
    response = client.get(f"/users/{user_id}/history")

    assert response.status_code == 200
    txns = response.json()["txns"]
    savings_txns = [t for t in txns if t["kind"] == "savings"]
    assert len(savings_txns) > 0
    assert savings_txns[0]["counterparty"] == "Festival Savings"

