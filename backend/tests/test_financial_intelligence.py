"""Tests for Financial Intelligence, Health Scoring, Recommendations, and Literacy Assistant."""
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Account, Transaction, TxnKind, TxnStatus, TxnTag, User
from app.services.financial_intelligence import (
    calculate_financial_insights,
    get_financial_literacy_guide,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_financial_literacy_guide():
    overview = get_financial_literacy_guide()
    assert "topics" in overview
    assert len(overview["topics"]) >= 5

    fund = get_financial_literacy_guide("emergency_fund")
    assert fund["topic"] == "emergency_fund"
    assert "3 to 6 months" in fund["summary"]

    rule = get_financial_literacy_guide("50_30_20")
    assert rule["topic"] == "50_30_20"
    assert "50%" in rule["summary"]


def test_calculate_financial_insights_empty():
    with SessionLocal() as session:
        user = session.query(User).filter_by(handle="bikash").one()
        insights = calculate_financial_insights(session, user.id)

    assert insights["user_id"] == user.id
    assert 0 <= insights["health_score"] <= 100
    assert insights["health_rating"] in ("Excellent", "Good", "Moderate", "Needs Attention")
    assert "recommendations" in insights


def test_financial_intelligence_endpoint(client):
    with SessionLocal() as session:
        user_id = session.query(User).filter_by(handle="bikash").one().id

    res = client.get(f"/users/{user_id}/financial-intelligence")
    assert res.status_code == 200
    data = res.json()
    assert "health_score" in data
    assert "recommendations" in data
    assert "category_breakdown" in data

    res_lit = client.get(f"/users/{user_id}/financial-literacy?topic=emergency_fund")
    assert res_lit.status_code == 200
    lit_data = res_lit.json()
    assert lit_data["topic"] == "emergency_fund"


def test_recommendation_advice_endpoint(client):
    """Test AI Guide recommendation advice grounded in live database numbers."""
    with SessionLocal() as session:
        user_id = session.query(User).filter_by(handle="bikash").one().id

    res = client.post(
        f"/users/{user_id}/financial-intelligence/advice",
        json={
            "title": "Pace Eid Goal",
            "description": "You have saved ৳200 towards your ৳5,000 Eid target.",
            "category": "savings",
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert data["title"] == "Pace Eid Goal"
    assert "advice" in data
    assert "action_steps" in data
    assert len(data["action_steps"]) > 0
    assert "live_facts" in data
    assert data["live_facts"]["user_handle"] == "bikash"


def test_chat_budget_recommendations_intent(client):
    with SessionLocal() as session:
        user_id = session.query(User).filter_by(handle="bikash").one().id

    res = client.post("/agent/chat", json={"user_id": user_id, "text": "give me budget recommendations"})
    assert res.status_code == 200
    body = res.json()
    assert body["action"] == "financial_insights"
    assert "financial health score" in body["text"]


def test_chat_financial_literacy_intent(client):
    with SessionLocal() as session:
        user_id = session.query(User).filter_by(handle="bikash").one().id

    res = client.post("/agent/chat", json={"user_id": user_id, "text": "what is an emergency fund?"})
    assert res.status_code == 200
    body = res.json()
    assert body["action"] == "financial_literacy"
    assert "Emergency Fund" in body["text"]

