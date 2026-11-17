from fastapi.testclient import TestClient

from app.db import SessionLocal
from app.main import app
from app.models import Account, User


def test_chat_balance_uses_current_account_value():
    client = TestClient(app)
    with SessionLocal() as session:
        u = session.query(User).filter_by(handle="bikash").one()
        user_id = u.id
        acct = session.query(Account).filter_by(user_id=user_id).one()
        current_balance = str(acct.balance_bdt)

    response = client.post(
        "/agent/chat",
        json={"user_id": user_id, "text": "check my balance"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "balance"
    assert current_balance in body["text"]


def test_chat_casual_greetings_do_not_dump_stats():
    client = TestClient(app)
    with SessionLocal() as session:
        u = session.query(User).filter_by(handle="bikash").one()
        user_id = u.id

    for greeting in ["hi", "hello", "salam", "hey", "how are you"]:
        response = client.post(
            "/agent/chat",
            json={"user_id": user_id, "text": greeting},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["action"] in ("greeting", "smalltalk")
        # Ensure it does not dump unrequested balance or spending stats
        assert "30-day" not in body["text"].lower()
        assert "velocity" not in body["text"].lower()
