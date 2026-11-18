"""Scenario Tests for the Upgraded Hybrid ML Fraud Intelligence System.

Scenarios verified:
1. First-time ৳500,000 BDT transfer (cold-start large / absolute ceiling) -> blocked/held.
2. Structuring into sub-limit transfers (rapid ৳24,500 transfers) -> flagged.
3. Mule fan-in/fan-out (high distinct sender aggregation) -> flagged.
4. New account limit abuse (< 7 days old exceeding ৳10,000) -> held.
5. Night high-value transfer (৳25,000 during late hours) -> elevated risk.
6. Legitimate festival spike (hard negative) -> approved or low risk.
7. Alert deduplication: calling evaluation twice in short succession does not spam duplicate alerts.
8. Median/MAD baseline: prevents 164x blowout on users with small transaction history.
9. Admin triage status: closing alert with "confirmed_fraud" stores ground truth label & mandatory reason code.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import (
    Account,
    AdminUser,
    FraudAlert,
    FraudAssessment,
    SecurityAuditLog,
    Transaction,
    TxnStatus,
    User,
)
from app.services.fraud_engine import (
    ABSOLUTE_SYSTEM_HARD_CAP,
    MAX_SINGLE_TXN_LIMIT,
    NEW_ACCOUNT_SINGLE_LIMIT,
    FraudEngine,
)


def _get_user_ids():
    with SessionLocal() as s:
        bikash = s.query(User).filter_by(handle="bikash").one()
        rishad = s.query(User).filter_by(handle="rishad").one()
        arman = s.query(User).filter_by(handle="arman").one()
        return bikash.id, rishad.id, arman.id


def test_scenario_cold_start_large_500k():
    """Scenario 1: First-time 500,000 BDT transfer must be held by hard platform limit."""
    bikash_id, rishad_id, _ = _get_user_ids()
    with SessionLocal() as s:
        res = FraudEngine.evaluate(
            s,
            initiator_user_id=bikash_id,
            recipient_user_id=rishad_id,
            amount_bdt=Decimal("500000.00"),
            persist=False,
        )
        assert res.risk_level == "high"
        assert res.status == "flagged_review"
        assert res.requires_biometric is True
        assert any(
            r in res.rules_triggered
            for r in ["RULE_ABSOLUTE_HARD_CAP_EXCEEDED", "RULE_TIER_LIMIT_EXCEEDED", "RULE_SINGLE_TXN_LIMIT_EXCEEDED"]
        )
        assert "exceeds" in " ".join(res.reasons).lower()


def test_scenario_structuring_sub_limit_transfers():
    """Scenario 2: Rapid successive transfers just below reporting limits must be flagged."""
    bikash_id, rishad_id, _ = _get_user_ids()
    with SessionLocal() as s:
        bikash_acct = s.query(Account).filter_by(user_id=bikash_id).one()
        bikash_u = s.get(User, bikash_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        bikash_u.created_at = now - timedelta(days=30)
        s.flush()

        # Seed 3 rapid recent transactions in the past 15 minutes
        for i in range(3):
            t = Transaction(
                from_account_id=bikash_acct.id,
                to_account_id=None,
                amount_bdt=Decimal("24500.00"),
                status=TxnStatus.COMPLETED.value,
                created_at=now - timedelta(minutes=10 - i * 3),
                completed_at=now - timedelta(minutes=10 - i * 3),
                kind="send",
                idempotency_key=f"struct-test-{now.timestamp()}-{i}",
                initiator_user_id=bikash_id,
            )
            s.add(t)
        s.flush()

        res = FraudEngine.evaluate(
            s,
            initiator_user_id=bikash_id,
            recipient_user_id=rishad_id,
            amount_bdt=Decimal("24800.00"),
            persist=False,
        )
        assert res.risk_level in ("medium", "high")
        assert res.features["txns_1h"] >= 3
        assert res.requires_biometric is True


def test_scenario_mule_fan_in_aggregation():
    """Scenario 3: Recipient with multiple distinct senders within 24h must be flagged as mule."""
    bikash_id, rishad_id, arman_id = _get_user_ids()
    with SessionLocal() as s:
        bikash_u = s.get(User, bikash_id)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        bikash_u.created_at = now - timedelta(days=30)
        s.flush()

        rishad_acct = s.query(Account).filter_by(user_id=rishad_id).one()

        # Seed 4 distinct senders inbound to Rishad's account
        for sender_id in [1, 2, 3, 4]:
            t = Transaction(
                from_account_id=None,
                to_account_id=rishad_acct.id,
                amount_bdt=Decimal("15000.00"),
                status=TxnStatus.COMPLETED.value,
                created_at=now - timedelta(hours=2),
                completed_at=now - timedelta(hours=2),
                kind="send",
                idempotency_key=f"mule-test-{now.timestamp()}-{sender_id}",
                initiator_user_id=sender_id,
            )
            s.add(t)
        s.flush()

        res = FraudEngine.evaluate(
            s,
            initiator_user_id=bikash_id,
            recipient_user_id=rishad_id,
            amount_bdt=Decimal("18000.00"),
            persist=False,
        )
        assert res.features["recipient_fan_in_count_24h"] >= 3
        assert "RULE_MULE_AGGREGATION_RECIPIENT" in res.rules_triggered
        assert res.risk_level in ("medium", "high")


def test_scenario_new_account_restriction():
    """Scenario 4: Account under 7 days old attempting above-limit transfer must trigger hold."""
    with SessionLocal() as s:
        # Create brand-new user with created_at = 1 day ago
        new_u = User(
            handle=f"newuser_{int(datetime.now().timestamp())}",
            phone=f"017{int(datetime.now().timestamp()) % 100000000:08d}",
            display_name="New Customer",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1),
        )
        s.add(new_u)
        s.flush()

        acct = Account(user_id=new_u.id, balance_bdt=Decimal("50000.00"))
        s.add(acct)
        s.flush()

        res = FraudEngine.evaluate(
            s,
            initiator_user_id=new_u.id,
            recipient_user_id=1,
            amount_bdt=Decimal("25000.00"),
            persist=False,
        )
        assert res.risk_level == "high"
        assert "RULE_NEW_ACCOUNT_LIMIT_EXCEEDED" in res.rules_triggered


def test_scenario_night_high_value(monkeypatch):
    """Scenario 5: High-value transfer during deep night hours (Dhaka 03:30 AM)."""
    bikash_id, rishad_id, _ = _get_user_ids()
    # Mock UTC time so that Dhaka time (UTC+6) is 03:30 AM (i.e. UTC 21:30)
    mock_utc_night = datetime(2026, 11, 18, 21, 30, 0)
    monkeypatch.setattr("app.services.fraud_engine._utcnow", lambda: mock_utc_night)

    with SessionLocal() as s:
        res = FraudEngine.evaluate(
            s,
            initiator_user_id=bikash_id,
            recipient_user_id=rishad_id,
            amount_bdt=Decimal("30000.00"),
            persist=False,
        )
        assert res.features["is_night_hours"] == 1.0
        assert res.risk_level in ("medium", "high")


def test_scenario_legit_festival_spike(monkeypatch):
    """Scenario 6: Legitimate festival gift (e.g. ৳1,500 to a known recipient during daytime)."""
    bikash_id, rishad_id, _ = _get_user_ids()
    # Daytime: 14:00 Dhaka time -> 08:00 UTC
    mock_utc_day = datetime(2026, 11, 18, 8, 0, 0)
    monkeypatch.setattr("app.services.fraud_engine._utcnow", lambda: mock_utc_day)

    with SessionLocal() as s:
        bikash_acct = s.query(Account).filter_by(user_id=bikash_id).one()
        rishad_acct = s.query(Account).filter_by(user_id=rishad_id).one()
        for i in range(10):
            t = Transaction(
                from_account_id=bikash_acct.id,
                to_account_id=rishad_acct.id,
                amount_bdt=Decimal("1200.00"),
                status=TxnStatus.COMPLETED.value,
                created_at=mock_utc_day - timedelta(days=20 - i),
                completed_at=mock_utc_day - timedelta(days=20 - i),
                kind="send",
                idempotency_key=f"festival-seed-{mock_utc_day.timestamp()}-{i}",
                initiator_user_id=bikash_id,
            )
            s.add(t)
        s.flush()

        res = FraudEngine.evaluate(
            s,
            initiator_user_id=bikash_id,
            recipient_user_id=rishad_id,
            amount_bdt=Decimal("1500.00"),
            persist=False,
        )
        assert res.features["is_new_recipient"] == 0.0
        assert res.risk_level == "low"
        assert res.status == "approved"
        assert res.requires_biometric is False


def test_scenario_median_mad_prevents_164x_blowout():
    """Scenario 7: User with small past history uses robust median/MAD baseline without 164x inflation."""
    bikash_id, rishad_id, _ = _get_user_ids()
    with SessionLocal() as s:
        bikash_acct = s.query(Account).filter_by(user_id=bikash_id).one()
        # Seed 6 small mobile recharges of ৳20 each
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for i in range(6):
            t = Transaction(
                from_account_id=bikash_acct.id,
                to_account_id=None,
                amount_bdt=Decimal("20.00"),
                status=TxnStatus.COMPLETED.value,
                created_at=now - timedelta(days=5, hours=i),
                completed_at=now - timedelta(days=5, hours=i),
                kind="mobile_recharge",
                idempotency_key=f"recharge-test-{now.timestamp()}-{i}",
                initiator_user_id=bikash_id,
            )
            s.add(t)
        s.flush()

        feats = FraudEngine.extract_features(
            s,
            initiator_user_id=bikash_id,
            recipient_user_id=rishad_id,
            amount_bdt=Decimal("1640.00"),
            current_balance=Decimal("10000.00"),
        )
        # Old naive formula: 1640 / 10 = 164.0x
        # New robust formula: baseline is protected by max(200.0, median)
        assert feats["amount_to_avg_ratio"] < 10.0, f"Expected ratio < 10x, got {feats['amount_to_avg_ratio']}"


def test_scenario_alert_deduplication():
    """Scenario 6: Consecutive evaluations in short succession do not spam duplicate alerts."""
    bikash_id, rishad_id, _ = _get_user_ids()
    with SessionLocal() as s:
        # Clear existing alerts for clean test
        initial_count = s.query(FraudAlert).filter_by(user_id=bikash_id).count()

        # Run high risk evaluation 1
        res1 = FraudEngine.evaluate(
            s,
            initiator_user_id=bikash_id,
            recipient_user_id=rishad_id,
            amount_bdt=Decimal("500000.00"),
            persist=True,
        )
        s.commit()
        after_first = s.query(FraudAlert).filter_by(user_id=bikash_id).count()
        assert after_first == initial_count + 1

        # Run identical evaluation 2 immediately
        res2 = FraudEngine.evaluate(
            s,
            initiator_user_id=bikash_id,
            recipient_user_id=rishad_id,
            amount_bdt=Decimal("500000.00"),
            persist=True,
        )
        s.commit()
        after_second = s.query(FraudAlert).filter_by(user_id=bikash_id).count()
        # Must be deduplicated!
        assert after_second == after_first, "Duplicate alert was improperly created!"


def test_scenario_admin_triage_confirmed_fraud_ground_truth():
    """Scenario 7: Updating triage alert to confirmed_fraud sets ground truth label and reason code."""
    client = TestClient(app)
    login_resp = client.post(
        "/admin/api/auth/login",
        json={"phone": "01926240062", "password": "1234"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch latest alert
    alerts_resp = client.get("/admin/api/fraud/alerts", headers=headers)
    assert alerts_resp.status_code == 200
    items = alerts_resp.json()["items"]
    assert len(items) > 0
    alert_id = items[0]["id"]

    # Close alert as confirmed_fraud with reason code
    update_resp = client.patch(
        f"/admin/api/fraud/alerts/{alert_id}",
        json={
            "status": "confirmed_fraud",
            "reason_code": "stolen_credentials",
            "notes": "Verified unauthorized SIM swap with telecom operator.",
        },
        headers=headers,
    )
    assert update_resp.status_code == 200
    data = update_resp.json()
    assert data["status"] == "confirmed_fraud"
    assert data["reason_code"] == "stolen_credentials"
    assert data["is_confirmed_fraud"] is True

    # Verify audit log recorded
    with SessionLocal() as s:
        alert = s.get(FraudAlert, alert_id)
        assert alert.status == "confirmed_fraud"
        assert alert.is_confirmed_fraud is True
        assert alert.resolution_reason_code == "stolen_credentials"
        assert "SIM swap" in alert.investigation_notes


def test_scenario_business_large_transfer_to_trusted_supplier():
    """Scenario 8: Business transfer of ৳200,000 to a trusted, pre-registered supplier should pass."""
    with SessionLocal() as s:
        # Create a business entity user
        ts = int(datetime.now().timestamp())
        corp = User(
            handle=f"corp_bd_{ts}",
            phone=f"018{ts % 100000000:08d}",
            display_name="Apex Logistics Ltd",
            user_type="business",
            tier="business",
            account_tier="business",
            kyc_status="verified",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=60),
        )
        s.add(corp)
        s.flush()
        corp_acct = Account(user_id=corp.id, balance_bdt=Decimal("2500000.00"))
        s.add(corp_acct)

        # Create trusted supplier
        supplier = User(
            handle=f"supplier_{ts}",
            phone=f"019{ts % 100000000:08d}",
            display_name="Dhaka Steel & Mills",
            user_type="business",
            tier="verified",
            account_tier="verified",
            kyc_status="verified",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=90),
        )
        s.add(supplier)
        s.flush()
        sup_acct = Account(user_id=supplier.id, balance_bdt=Decimal("500000.00"))
        s.add(sup_acct)
        s.flush()

        # Seed past transaction from corp to supplier 10 days ago (established relationship)
        past_tx = Transaction(
            from_account_id=corp_acct.id,
            to_account_id=sup_acct.id,
            amount_bdt=Decimal("350000.00"),
            status=TxnStatus.COMPLETED.value,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10),
            completed_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10),
            kind="send",
            idempotency_key=f"corp-past-{ts}",
            initiator_user_id=corp.id,
        )
        s.add(past_tx)
        s.flush()

        res = FraudEngine.evaluate(
            s,
            initiator_user_id=corp.id,
            recipient_user_id=supplier.id,
            amount_bdt=Decimal("200000.00"),
            persist=False,
        )
        assert res.account_tier == "business"
        assert res.features["is_trusted_recipient"] == 1.0
        assert res.requires_dual_approval is False
        assert res.risk_level == "low"
        assert res.status == "approved"


def test_scenario_business_large_transfer_to_untrusted_recipient_requires_dual_approval():
    """Scenario 9: Business transfer of ৳200,000 to an untrusted / new recipient requires step-up dual approval."""
    with SessionLocal() as s:
        ts = int(datetime.now().timestamp())
        corp = User(
            handle=f"corp_flow_{ts}",
            phone=f"018{ts % 100000000:08d}",
            display_name="Bengal Commerce Ltd",
            user_type="business",
            tier="business",
            account_tier="business",
            kyc_status="verified",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=60),
        )
        s.add(corp)
        s.flush()
        corp_acct = Account(user_id=corp.id, balance_bdt=Decimal("1500000.00"))
        s.add(corp_acct)

        # Brand new unknown recipient
        new_rec = User(
            handle=f"unknown_payee_{ts}",
            phone=f"013{ts % 100000000:08d}",
            display_name="Unknown Payee",
            tier="personal",
            created_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=2),
        )
        s.add(new_rec)
        s.flush()
        rec_acct = Account(user_id=new_rec.id, balance_bdt=Decimal("100.00"))
        s.add(rec_acct)
        s.flush()

        res = FraudEngine.evaluate(
            s,
            initiator_user_id=corp.id,
            recipient_user_id=new_rec.id,
            amount_bdt=Decimal("200000.00"),
            persist=False,
        )
        assert res.account_tier == "business"
        assert res.features["is_trusted_recipient"] == 0.0
        assert res.requires_dual_approval is True
        assert res.status == "flagged_review"
        assert "RULE_BUSINESS_UNTRUSTED_RECIPIENT_DUAL_APPROVAL" in res.rules_triggered


def test_scenario_personal_tier_user_sending_200k_hard_block():
    """Scenario 10: Personal-tier user attempting to send ৳200,000 must be held/blocked by tier limit."""
    bikash_id, rishad_id, _ = _get_user_ids()
    with SessionLocal() as s:
        res = FraudEngine.evaluate(
            s,
            initiator_user_id=bikash_id,
            recipient_user_id=rishad_id,
            amount_bdt=Decimal("200000.00"),
            persist=False,
        )
        assert res.account_tier == "personal"
        assert res.risk_level == "high"
        assert res.status == "flagged_review"
        assert "RULE_TIER_LIMIT_EXCEEDED" in res.rules_triggered
        assert "exceeds" in " ".join(res.reasons).lower()

