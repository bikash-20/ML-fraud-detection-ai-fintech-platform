"""Scenario tests covering User Types, Account Tiers, Security Rules, and Profile Views.

Validates:
1. Business ৳200k to trusted supplier passes.
2. Business ৳200k to untrusted recipient holds for dual approval.
3. Personal tier user sending ৳200k holds on tier single cap (৳50k).
4. Unverified user requesting Business tier is restricted to Personal limits.
5. Cash-in transactions never inflate 30-day spending median baseline.
6. User profile endpoint returns live limits, daily spend vs limit, and frequent recipients.
7. User upgrade request enters pending review state.
8. Admin KYC verification activates pending tier and writes audit log.
9. Admin tier change requires mandatory reason code and creates audit log.
10. Tier config endpoint provides single source of truth.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Account, AdminSession, AdminUser, FraudAssessment, SecurityAuditLog, Transaction, TxnStatus, User
from app.services.admin_auth import hash_password
from app.services.fraud_engine import FraudEngine
from app.tier_config import TIER_LIMITS, get_effective_limits, get_effective_tier


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def admin_token(client):
    """Create an active admin session and return bearer token."""
    with SessionLocal() as s:
        admin = s.query(AdminUser).filter_by(phone="01926240062").first()
        if not admin:
            pwd_hash, salt = hash_password("1234")
            admin = AdminUser(
                phone="01926240062",
                display_name="Test Super Admin",
                password_hash=pwd_hash,
                salt=salt,
                role="super_admin",
                is_active=True,
            )
            s.add(admin)
            s.flush()
        token = "test-token-tier-scenarios-123456"
        s.add(AdminSession(
            admin_id=admin.id,
            token=token,
            expires_at=_utcnow() + timedelta(days=1),
        ))
        s.commit()
    return token


def test_business_200k_trusted_passes():
    """Scenario 1: Verified Business user sending ৳200k to a trusted supplier passes."""
    with SessionLocal() as s:
        now = _utcnow()
        corp = User(
            handle=f"corp_{int(now.timestamp())}",
            display_name="Apex Global Ltd",
            phone="01711000001",
            user_type="business",
            account_tier="business",
            tier="business",
            kyc_status="verified",
            created_at=now - timedelta(days=45),
        )
        supp = User(
            handle=f"supp_{int(now.timestamp())}",
            display_name="Supplier Trade Co",
            phone="01711000002",
            user_type="business",
            account_tier="business",
            tier="business",
            kyc_status="verified",
            created_at=now - timedelta(days=45),
        )
        s.add_all([corp, supp])
        s.flush()

        corp_acct = Account(user_id=corp.id, balance_bdt=Decimal("2500000.00"))
        supp_acct = Account(user_id=supp.id, balance_bdt=Decimal("500000.00"))
        s.add_all([corp_acct, supp_acct])
        s.flush()

        # Seed prior completed transaction > 24h ago to establish trust
        prior_ts = now - timedelta(days=5)
        s.add(Transaction(
            idempotency_key=f"prior-biz-{int(now.timestamp())}",
            initiator_user_id=corp.id,
            from_account_id=corp_acct.id,
            to_account_id=supp_acct.id,
            amount_bdt=Decimal("120000.00"),
            kind="send",
            status=TxnStatus.COMPLETED.value,
            created_at=prior_ts,
            completed_at=prior_ts,
        ))
        s.flush()

        res = FraudEngine.evaluate(
            s,
            initiator_user_id=corp.id,
            recipient_user_id=supp.id,
            amount_bdt=Decimal("200000.00"),
            persist=False,
        )

        assert res.risk_level in ("low", "medium")
        assert not res.is_hard_block
        assert not res.requires_dual_approval
        assert "RULE_TIER_LIMIT_EXCEEDED" not in res.rules_triggered
        assert "RULE_BUSINESS_UNTRUSTED_RECIPIENT_DUAL_APPROVAL" not in res.rules_triggered


def test_business_200k_untrusted_requires_dual_approval():
    """Scenario 2: Business sending ৳200k to a brand-new recipient requires dual approval."""
    with SessionLocal() as s:
        now = _utcnow()
        corp = User(
            handle=f"corp2_{int(now.timestamp())}",
            display_name="Meghna Industries",
            phone="01711000003",
            user_type="business",
            account_tier="business",
            tier="business",
            kyc_status="verified",
            created_at=now - timedelta(days=45),
        )
        new_payee = User(
            handle=f"newpayee_{int(now.timestamp())}",
            display_name="Novel Supplier",
            phone="01711000004",
            user_type="business",
            account_tier="business",
            tier="business",
            kyc_status="verified",
            created_at=now - timedelta(days=2),
        )
        s.add_all([corp, new_payee])
        s.flush()

        corp_acct = Account(user_id=corp.id, balance_bdt=Decimal("2500000.00"))
        new_acct = Account(user_id=new_payee.id, balance_bdt=Decimal("10000.00"))
        s.add_all([corp_acct, new_acct])
        s.flush()

        res = FraudEngine.evaluate(
            s,
            initiator_user_id=corp.id,
            recipient_user_id=new_payee.id,
            amount_bdt=Decimal("200000.00"),
            persist=False,
        )

        assert res.requires_dual_approval is True
        assert res.is_hard_block is True
        assert "RULE_BUSINESS_UNTRUSTED_RECIPIENT_DUAL_APPROVAL" in res.rules_triggered


def test_personal_tier_200k_holds_on_tier_cap():
    """Scenario 3: Personal tier user sending ৳200,000 is blocked/held by tier limit (৳50k cap)."""
    with SessionLocal() as s:
        now = _utcnow()
        student = User(
            handle=f"stud_{int(now.timestamp())}",
            display_name="Student User",
            phone="01711000005",
            user_type="student",
            account_tier="personal",
            tier="personal",
            kyc_status="verified",
            created_at=now - timedelta(days=30),
        )
        rec = User(
            handle=f"rec_{int(now.timestamp())}",
            display_name="Friend",
            phone="01711000006",
            user_type="student",
            account_tier="personal",
            tier="personal",
            kyc_status="verified",
            created_at=now - timedelta(days=30),
        )
        s.add_all([student, rec])
        s.flush()

        stud_acct = Account(user_id=student.id, balance_bdt=Decimal("250000.00"))
        rec_acct = Account(user_id=rec.id, balance_bdt=Decimal("5000.00"))
        s.add_all([stud_acct, rec_acct])
        s.flush()

        res = FraudEngine.evaluate(
            s,
            initiator_user_id=student.id,
            recipient_user_id=rec.id,
            amount_bdt=Decimal("200000.00"),
            persist=False,
        )

        assert res.is_hard_block is True
        assert "RULE_TIER_LIMIT_EXCEEDED" in res.rules_triggered
        assert any("Personal account limit exceeded" in reason for reason in res.reasons)


def test_unverified_business_user_restricted_to_personal_tier():
    """Scenario 4: Security Rule: User requested business tier, but unverified -> bounded by personal limits."""
    with SessionLocal() as s:
        now = _utcnow()
        unverified_biz = User(
            handle=f"unver_{int(now.timestamp())}",
            display_name="Pending Agro Trader",
            phone="01711000007",
            user_type="business",
            account_tier="business",
            tier="business",
            kyc_status="unverified",  # NOT verified by admin!
            created_at=now - timedelta(days=20),
        )
        rec = User(
            handle=f"rec2_{int(now.timestamp())}",
            display_name="Vendor",
            phone="01711000008",
            user_type="shopkeeper",
            account_tier="verified",
            kyc_status="verified",
            created_at=now - timedelta(days=20),
        )
        s.add_all([unverified_biz, rec])
        s.flush()

        u_acct = Account(user_id=unverified_biz.id, balance_bdt=Decimal("300000.00"))
        rec_acct = Account(user_id=rec.id, balance_bdt=Decimal("20000.00"))
        s.add_all([u_acct, rec_acct])
        s.flush()

        # Check effective tier
        assert unverified_biz.effective_tier == "personal"

        # Transferring ৳60,000 exceeds personal tier cap (৳50,000)
        res = FraudEngine.evaluate(
            s,
            initiator_user_id=unverified_biz.id,
            recipient_user_id=rec.id,
            amount_bdt=Decimal("60000.00"),
            persist=False,
        )

        assert res.is_hard_block is True
        assert "RULE_TIER_LIMIT_EXCEEDED" in res.rules_triggered


def test_cash_in_does_not_inflate_spending_median():
    """Scenario 5: Cash-in top-up transactions do NOT count towards outbound spending median."""
    with SessionLocal() as s:
        now = _utcnow()
        u = User(
            handle=f"saver_{int(now.timestamp())}",
            display_name="Smart Saver",
            phone="01711000009",
            user_type="student",
            account_tier="personal",
            kyc_status="verified",
            created_at=now - timedelta(days=40),
        )
        s.add(u)
        s.flush()
        acct = Account(user_id=u.id, balance_bdt=Decimal("100000.00"))
        s.add(acct)
        s.flush()

        # Seed 5 small historical spends
        for amt in [100.0, 150.0, 200.0, 250.0, 300.0]:
            s.add(Transaction(
                idempotency_key=f"spend-{u.id}-{amt}-{int(now.timestamp())}",
                initiator_user_id=u.id,
                from_account_id=acct.id,
                to_account_id=None,
                amount_bdt=Decimal(str(amt)),
                kind="send",
                status=TxnStatus.COMPLETED.value,
                created_at=now - timedelta(days=10),
                completed_at=now - timedelta(days=10),
            ))

        # Seed a massive cash_in of ৳5,000,000
        s.add(Transaction(
            idempotency_key=f"cashin-{u.id}-{int(now.timestamp())}",
            initiator_user_id=u.id,
            from_account_id=None,
            to_account_id=acct.id,
            amount_bdt=Decimal("5000000.00"),
            kind="cash_in",
            status=TxnStatus.COMPLETED.value,
            created_at=now - timedelta(days=2),
            completed_at=now - timedelta(days=2),
        ))
        s.flush()

        feats = FraudEngine.extract_features(
            s,
            initiator_user_id=u.id,
            recipient_user_id=None,
            amount_bdt=Decimal("150.00"),
            current_balance=acct.balance_bdt,
        )

        # Median of [100, 150, 200, 250, 300] is 200. Clamped to 200.
        assert feats["user_median_amount_30d"] == 200.0
        assert feats["past_txns_30d"] == 5  # Exactly 5 completed sends, cash_in not counted!


def test_profile_api_endpoint(client):
    """Scenario 6: User profile endpoint returns live limits, daily spend vs limit, and frequent recipients."""
    # Test on Bikash (user_id = 1)
    res = client.get("/api/users/1/profile")
    assert res.status_code == 200
    data = res.json()
    assert "user" in data
    assert data["user"]["handle"] == "bikash"
    assert data["user"]["user_type"] == "student"
    assert data["user"]["effective_tier"] == "personal"
    assert "daily_limit_bdt" in data
    assert "daily_spent_today_bdt" in data
    assert "daily_remaining_bdt" in data
    assert "daily_usage_pct" in data
    assert "baseline_median_30d" in data
    assert isinstance(data["frequent_recipients"], list)


def test_user_upgrade_request_api(client):
    """Scenario 7: User can submit upgrade request which enters pending state."""
    res = client.post(
        "/api/users/1/upgrade-request",
        json={
            "requested_tier": "verified",
            "reason": "Submitted Smart NID for verified status",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["requested_tier"] == "verified"
    assert "Pending administrator KYC verification" in data["message"]


def test_admin_kyc_verification_activates_tier(client, admin_token):
    """Scenario 8: Admin KYC verification activates pending requested tier and records audit log."""
    # Place a pending upgrade on user 6 (Mahdin)
    with SessionLocal() as s:
        u = s.get(User, 6)
        u.requested_upgrade_tier = "verified"
        u.kyc_status = "unverified"
        s.commit()

    headers = {"Authorization": f"Bearer {admin_token}"}
    res = client.patch(
        "/admin/api/users/6/kyc",
        headers=headers,
        json={"kyc_status": "verified", "activate_requested_tier": True, "notes": "NID verified valid"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["kyc_status"] == "verified"
    assert data["account_tier"] == "verified"

    # Verify audit log entry
    with SessionLocal() as s:
        log_entry = (
            s.query(SecurityAuditLog)
            .filter_by(action="verify_user_kyc", target_id="6")
            .order_by(SecurityAuditLog.id.desc())
            .first()
        )
        assert log_entry is not None
        details = json.loads(log_entry.details_json)
        assert details["new_kyc"] == "verified"


def test_admin_tier_change_mandatory_reason_code(client, admin_token):
    """Scenario 9: Admin tier change requires mandatory reason code and creates audit log."""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Missing reason code should be rejected (422)
    res_fail = client.patch(
        "/admin/api/users/6/tier",
        headers=headers,
        json={"account_tier": "business", "reason_code": ""},
    )
    assert res_fail.status_code == 422

    # 2. Valid reason code succeeds
    res_ok = client.patch(
        "/admin/api/users/6/tier",
        headers=headers,
        json={
            "account_tier": "business",
            "reason_code": "corporate_onboarding",
            "notes": "Corporate trade documents validated",
        },
    )
    assert res_ok.status_code == 200
    assert res_ok.json()["account_tier"] == "business"

    # Check audit log
    with SessionLocal() as s:
        audit = (
            s.query(SecurityAuditLog)
            .filter_by(action="change_user_tier", target_id="6")
            .order_by(SecurityAuditLog.id.desc())
            .first()
        )
        assert audit is not None
        assert "corporate_onboarding" in audit.details_json


def test_tier_config_endpoint(client):
    """Scenario 10: Centralized single source of truth endpoint returns tier definitions."""
    res = client.get("/api/tier-config")
    assert res.status_code == 200
    data = res.json()
    assert "tiers" in data
    assert "personal" in data["tiers"]
    assert "verified" in data["tiers"]
    assert "business" in data["tiers"]
    assert data["tiers"]["personal"]["single_txn_limit"] == 50000.0
    assert data["tiers"]["verified"]["single_txn_limit"] == 100000.0
    assert data["tiers"]["business"]["single_txn_limit"] == 1000000.0
    assert "agent_limits" in data
    assert data["agent_limits"]["single_txn_limit"] == 300000.0
    assert "regulatory_disclaimer" in data


def test_agent_liquidity_rebalance_uses_agent_limits():
    """Scenario 11: Verified MFS Agent transferring ৳200,000 float is NOT blocked by consumer 100k cap."""
    with SessionLocal() as s:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        agent_u = User(
            handle=f"agent_float_{int(now.timestamp())}",
            display_name="City Point Agent",
            phone="01811999901",
            user_type="agent",
            account_tier="verified",
            kyc_status="verified",
            created_at=now - timedelta(days=60),
        )
        distributor_u = User(
            handle=f"dso_{int(now.timestamp())}",
            display_name="Master Distributor DSO",
            phone="01811999902",
            user_type="business",
            account_tier="business",
            kyc_status="verified",
            created_at=now - timedelta(days=90),
        )
        s.add_all([agent_u, distributor_u])
        s.flush()

        agent_acct = Account(user_id=agent_u.id, balance_bdt=Decimal("500000.00"))
        dso_acct = Account(user_id=distributor_u.id, balance_bdt=Decimal("2000000.00"))
        s.add_all([agent_acct, dso_acct])
        s.flush()

        # Seed prior transaction 5 days ago to establish relationship
        tx = Transaction(
            from_account_id=agent_acct.id,
            to_account_id=dso_acct.id,
            amount_bdt=Decimal("150000.00"),
            status=TxnStatus.COMPLETED.value,
            created_at=now - timedelta(days=5),
            completed_at=now - timedelta(days=5),
            kind="send",
            idempotency_key=f"agent-float-seed-{now.timestamp()}",
            initiator_user_id=agent_u.id,
        )
        s.add(tx)
        s.flush()

        # 1. Transfer of ৳200,000 (exceeds 100k consumer cap, but under 300k agent limit)
        res_ok = FraudEngine.evaluate(
            s,
            initiator_user_id=agent_u.id,
            recipient_user_id=distributor_u.id,
            amount_bdt=Decimal("200000.00"),
            persist=False,
        )
        assert "RULE_TIER_LIMIT_EXCEEDED" not in res_ok.rules_triggered
        assert res_ok.is_hard_block is False
        assert res_ok.risk_level in ("low", "medium")

        # 2. Transfer of ৳350,000 exceeds agent limit (৳300,000) and triggers hard block
        res_exceed = FraudEngine.evaluate(
            s,
            initiator_user_id=agent_u.id,
            recipient_user_id=distributor_u.id,
            amount_bdt=Decimal("350000.00"),
            persist=False,
        )
        assert "RULE_TIER_LIMIT_EXCEEDED" in res_exceed.rules_triggered
        assert res_exceed.is_hard_block is True
