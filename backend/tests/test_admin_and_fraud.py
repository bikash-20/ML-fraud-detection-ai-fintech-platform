"""Tests for Fraud Detection Engine, Admin Authentication, and Admin Endpoints."""
from __future__ import annotations

import json
from decimal import Decimal

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
    User,
    UserSecurityPreference,
)
from app.services.admin_auth import hash_password
from app.services.fraud_engine import FraudEngine


def _bikash_id() -> int:
    with SessionLocal() as s:
        return s.query(User).filter_by(handle="bikash").one().id


def _rishad_id() -> int:
    with SessionLocal() as s:
        return s.query(User).filter_by(handle="rishad").one().id


def test_admin_auth_success_and_failure():
    """Verify admin login with phone 01926240062 and password 1234."""
    client = TestClient(app)

    # Correct credentials
    resp = client.post(
        "/admin/api/auth/login",
        json={"phone": "01926240062", "password": "1234"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "token" in data
    assert data["token"].startswith("adm_")
    assert data["admin"]["display_name"] == "talukder"
    assert data["admin"]["phone"] == "01926240062"

    token = data["token"]

    # Verify protected /admin/api/auth/me works with Bearer token
    me_resp = client.get(
        "/admin/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["display_name"] == "talukder"

    # Wrong password fails with 401
    bad_resp = client.post(
        "/admin/api/auth/login",
        json={"phone": "01926240062", "password": "wrongpassword"},
    )
    assert bad_resp.status_code == 401

    # Wrong phone fails with 401
    bad_phone = client.post(
        "/admin/api/auth/login",
        json={"phone": "01700000000", "password": "1234"},
    )
    assert bad_phone.status_code == 401


def test_unauthorized_user_blocked_from_admin_endpoints():
    """Regular users without admin token cannot access admin endpoints."""
    client = TestClient(app)

    # No token -> 401
    resp = client.get("/admin/api/overview")
    assert resp.status_code == 401

    # Bogus token -> 401
    resp2 = client.get(
        "/admin/api/overview",
        headers={"Authorization": "Bearer fake_token_xyz"},
    )
    assert resp2.status_code == 401


def test_fraud_engine_risk_tiers():
    """Test Low, Medium, and High risk fraud evaluations."""
    client = TestClient(app)
    bikash = _bikash_id()
    rishad = _rishad_id()

    with SessionLocal() as s:
        # 1. Low risk: small ordinary transfer to known contact
        res_low = FraudEngine.evaluate(
            s,
            initiator_user_id=bikash,
            recipient_user_id=rishad,
            amount_bdt=Decimal("200.00"),
            persist=False,
        )
        assert res_low.risk_level == "low"
        assert res_low.risk_score < 0.40
        assert res_low.requires_biometric is False

        # 2. High risk: massive drain of balance to a new recipient
        res_high = FraudEngine.evaluate(
            s,
            initiator_user_id=bikash,
            recipient_user_id=rishad,
            amount_bdt=Decimal("49000.00"),
            persist=True,
        )
        s.commit()
        assert res_high.risk_level in ("medium", "high")
        assert res_high.risk_score >= 0.40
        assert res_high.requires_biometric is True
        assert len(res_high.rules_triggered) > 0


def test_admin_overview_metrics():
    """Test admin overview returns live database statistics."""
    client = TestClient(app)
    login_resp = client.post(
        "/admin/api/auth/login",
        json={"phone": "01926240062", "password": "1234"},
    )
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/admin/api/overview", headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert "kpis" in data
    kpis = data["kpis"]
    assert kpis["total_users"] >= 7
    assert kpis["total_transactions"] >= 0
    assert "activity_timeline" in data["charts"]
    assert "risk_distribution" in data["charts"]


def test_admin_fraud_intelligence_and_investigation_workflow():
    """Test viewing fraud assessments and updating alert status."""
    client = TestClient(app)
    login_resp = client.post(
        "/admin/api/auth/login",
        json={"phone": "01926240062", "password": "1234"},
    )
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # List assessments
    resp = client.get("/admin/api/fraud/assessments", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body

    # List alerts
    alerts_resp = client.get("/admin/api/fraud/alerts", headers=headers)
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()["items"]
    assert len(alerts) > 0

    first_alert = alerts[0]
    # Update alert
    patch_resp = client.patch(
        f"/admin/api/fraud/alerts/{first_alert['id']}",
        json={"status": "resolved", "notes": "Investigated and verified legitimate."},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "resolved"


def test_frozen_user_account_blocks_transactions():
    """A user marked as frozen cannot initiate money transfers."""
    client = TestClient(app)
    bikash = _bikash_id()

    login_resp = client.post(
        "/admin/api/auth/login",
        json={"phone": "01926240062", "password": "1234"},
    )
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Freeze Bikash
    freeze_resp = client.post(
        f"/admin/api/users/{bikash}/freeze",
        json={"reason": "Security audit hold"},
        headers=headers,
    )
    assert freeze_resp.status_code == 200
    assert freeze_resp.json()["is_frozen"] is True

    # Attempt to send money -> should be blocked by engine
    send_resp = client.post(
        "/agent/act-send",
        json={
            "user_id": bikash,
            "recipient_handle": "rishad",
            "amount_bdt": "100.00",
            "idempotency_key": "freeze-test-key-123",
        },
    )
    assert send_resp.status_code == 400
    assert "frozen" in send_resp.text.lower()

    # Unfreeze Bikash
    unfreeze_resp = client.post(
        f"/admin/api/users/{bikash}/freeze",
        json={"reason": "Verified user cleared"},
        headers=headers,
    )
    assert unfreeze_resp.status_code == 200
    assert unfreeze_resp.json()["is_frozen"] is False


def test_user_security_preference_toggle():
    """Test user security transparency preference."""
    client = TestClient(app)
    bikash = _bikash_id()

    # Get default preference
    pref_get = client.get(f"/users/{bikash}/security-preference")
    assert pref_get.status_code == 200
    assert pref_get.json()["show_security_analysis"] is False

    # Enable preference
    pref_post = client.post(
        f"/users/{bikash}/security-preference",
        json={"show_security_analysis": True},
    )
    assert pref_post.status_code == 200
    assert pref_post.json()["show_security_analysis"] is True

    # Check updated state
    pref_get2 = client.get(f"/users/{bikash}/security-preference")
    assert pref_get2.json()["show_security_analysis"] is True


def test_admin_ai_assistant_live_database_queries():
    """Test Admin AI query answering with live database facts."""
    client = TestClient(app)
    login_resp = client.post(
        "/admin/api/auth/login",
        json={"phone": "01926240062", "password": "1234"},
    )
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    queries = [
        "How many suspicious transactions occurred today?",
        "Which transactions have the highest risk scores?",
        "Show me the latest fraud alerts.",
        "What is the current transaction volume?",
        "Is the fraud detection service working properly?",
        "check the recent activity in my system",
    ]

    for q in queries:
        resp = client.post("/admin/api/ai/query", json={"query": q}, headers=headers)
        assert resp.status_code == 200, f"Query failed: {q}"
        data = resp.json()
        assert "response" in data
        assert "data" in data
        assert len(data["response"]) > 0

    # Test casual conversation separation (0 DB overhead)
    casual_resp = client.post("/admin/api/ai/query", json={"query": "hi"}, headers=headers)
    assert casual_resp.status_code == 200
    casual_data = casual_resp.json()
    assert casual_data["intent"] == "greeting"
    assert casual_data["data"] is None

    # Test multi-turn conversational context
    history = [
        {"sender": "admin", "text": "Who is the top offender?"},
        {"sender": "ai", "text": "User bikash has 2 flagged transactions requiring review."},
    ]
    multi_resp = client.post(
        "/admin/api/ai/query",
        json={"query": "tell me more details about him", "history": history},
        headers=headers,
    )
    assert multi_resp.status_code == 200
    multi_data = multi_resp.json()
    assert multi_data["intent"] in ("follow_up", "recent_activity", "repeated_users")
    assert len(multi_data["response"]) > 0
