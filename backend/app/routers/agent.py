"""Agent router — orchestrates parse -> resolve -> engine.

Safety pattern (PRD §4) lives here as the orchestration:
  text -> LLM.intent -> resolver -> engine.create_pending -> LLM.phrase
  pending -> engine.confirm (or decline) -> LLM.phrase
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from .. import engine, llm, resolver
from ..db import session_scope
from ..models import Account, Request, RequestStatus, Split, Transaction, TxnStatus, User
from ..services import assistant_db
from ..schemas import (
    AgentActRequest,
    AgentActRequestActionRequest,
    AgentActResponse,
    AgentActSendRequest,
    AgentActSplitRequest,
    AgentChatRequest,
    AgentChatResponse,
    AgentConfirmRequest,
    AgentConfirmResponse,
    ReviewCard,
)

router = APIRouter(prefix="/agent", tags=["agent"])


def _handle(session: Session, handle: str) -> User:
    u = session.query(User).filter_by(handle=handle).one_or_none()
    if u is None:
        raise HTTPException(404, f"unknown user handle: {handle}")
    return u


def _user_by_id(session: Session, user_id: int) -> User:
    u = session.get(User, user_id)
    if u is None:
        raise HTTPException(404, f"unknown user_id: {user_id}")
    return u


def _review_card_for_send(txn: Transaction, session: Session) -> ReviewCard:
    init = session.get(User, txn.initiator_user_id)
    init_acct = session.query(Account).filter_by(user_id=init.id).one()
    # The pending txn hasn't debited yet; resulting balance if confirmed.
    resulting = init_acct.balance_bdt  # unchanged while pending
    recipient = None
    phone = None
    recipient_user_id = None
    if txn.to_account_id:
        r_user = session.query(User).join(Account).filter(Account.id == txn.to_account_id).one_or_none()
        if r_user:
            recipient = r_user.handle
            phone = r_user.phone
            recipient_user_id = r_user.id

    # Attach or perform fraud assessment
    from ..models import FraudAssessment
    from ..services.fraud_engine import FraudEngine

    assessment = (
        session.query(FraudAssessment)
        .filter_by(txn_id=txn.id)
        .order_by(desc(FraudAssessment.id))
        .first()
    ) if txn.id else None

    if assessment is None and txn.id:
        res = FraudEngine.evaluate(
            session,
            initiator_user_id=init.id,
            recipient_user_id=recipient_user_id,
            amount_bdt=txn.amount_bdt,
            txn_id=txn.id,
            persist=True,
        )
        risk_level = res.risk_level
        risk_score = res.risk_score
        security_analysis = res.reasons
        requires_biometric = res.requires_biometric
    elif assessment:
        risk_level = assessment.risk_level
        risk_score = assessment.risk_score
        security_analysis = json.loads(assessment.reasons_json) if assessment.reasons_json else []
        requires_biometric = (risk_level in ("medium", "high"))
    else:
        risk_level = "low"
        risk_score = 0.0
        security_analysis = ["Normal transaction parameters verified."]
        requires_biometric = False

    return ReviewCard(
        kind="send",
        amount_bdt=txn.amount_bdt,
        recipient_label=recipient,
        recipient_phone=phone,
        note=txn.note,
        resulting_balance_bdt=resulting,  # post-debit will be lower; we phrase accurately
        initiator_handle=init.handle,
        initiator_phone=init.phone,
        risk_level=risk_level,
        risk_score=risk_score,
        security_analysis=security_analysis,
        requires_biometric=requires_biometric,
    )


def _review_card_for_request(req_row: Request, session: Session) -> ReviewCard:
    init = session.get(User, req_row.asker_user_id)
    payer = session.get(User, req_row.payer_user_id)
    current_balance = _post_debit_balance(session, init.id)
    return ReviewCard(
        kind="request",
        amount_bdt=req_row.amount_bdt,
        recipient_label=payer.handle if payer else None,
        recipient_phone=payer.phone if payer else None,
        note=req_row.note,
        resulting_balance_bdt=current_balance,
        initiator_handle=init.handle,
        initiator_phone=init.phone,
    )


def _post_debit_balance(session: Session, user_id: int) -> Decimal:
    a = session.query(Account).filter_by(user_id=user_id).one()
    return a.balance_bdt


@router.post("/act", response_model=AgentActResponse)
def agent_act(req: AgentActRequest) -> AgentActResponse:
    """Single endpoint for both voice and chat UIs."""
    with session_scope() as s:
        # Idempotency: if a transaction with this key already exists for this
        # user, return its current state.
        existing = (
            s.query(Transaction)
            .filter_by(initiator_user_id=req.user_id, idempotency_key=req.idempotency_key)
            .one_or_none()
        )
        if existing is not None:
            current_balance = _post_debit_balance(s, req.user_id)
            resulting = current_balance - existing.amount_bdt
            card = _review_card_for_send(existing, s)
            card.resulting_balance_bdt = resulting
            sub_action = "recharge" if existing.note == "Mobile Recharge" else ("cash_out" if existing.note == "Cash Out via Agent" else "send")
            text = llm.phrase(
                "review_send",
                {
                    "amount_bdt": str(existing.amount_bdt),
                    "recipient": card.recipient_label,
                    "resulting_balance_bdt": str(resulting),
                    "sub_action": sub_action,
                },
            )
            return AgentActResponse(
                text=text,
                card=card,
                pending_id=existing.id,
                action="send",
                idempotent_replay=True,
            )

        user = _user_by_id(s, req.user_id)
        handles = engine.known_handles(s)
        billers = engine.known_billers(s)

        # 1. Parse (falls back to regex internally when LLM is unreachable,
        # so we never return 503 from here).
        try:
            intent_dict = llm.parse_intent(req.text, handles, billers)
        except Exception:
            intent_dict = {"action": "unknown"}

        action = (intent_dict.get("action") or "unknown").strip().lower()

        # 2. Branch by action.
        if action == "greeting":
            return AgentActResponse(
                text=llm.chat_reply(req.text, user.handle),
                action="greeting",
            )
        if action == "thanks":
            return AgentActResponse(
                text=llm.chat_reply(req.text, user.handle),
                action="thanks",
            )
        if action == "bye":
            return AgentActResponse(
                text=llm.chat_reply(req.text, user.handle),
                action="bye",
            )
        if action in ("balance",):
            balance = _post_debit_balance(s, req.user_id)
            text = llm.phrase("balance", {"balance_bdt": str(balance)})
            return AgentActResponse(
                text=text, action="balance",
                data={"balance_bdt": str(balance), "handle": user.handle},
            )

        if action in ("history",):
            account = s.query(Account).filter_by(user_id=req.user_id).one()
            history_count = (
                s.query(Transaction)
                .filter(
                    (Transaction.from_account_id == account.id)
                    | (Transaction.to_account_id == account.id)
                )
                .count()
            )
            return AgentActResponse(
                text=llm.phrase("history_summary", {"count": history_count}),
                action="history",
                data={"redirect": "/history", "count": history_count},
            )

        # ---- Live Database Queries ----
        if action == "spending_recent":
            res = assistant_db.get_recent_spending(s, req.user_id)
            return AgentActResponse(text=res["text"], action="spending_recent", data=res)
        if action == "spending_where":
            res = assistant_db.get_where_spent(s, req.user_id)
            return AgentActResponse(text=res["text"], action="spending_where", data=res)
        if action == "latest_transaction":
            res = assistant_db.get_latest_transaction(s, req.user_id)
            return AgentActResponse(text=res["text"], action="latest_transaction", data=res)
        if action == "send_vs_receive":
            res = assistant_db.get_sent_vs_received(s, req.user_id)
            return AgentActResponse(text=res["text"], action="send_vs_receive", data=res)
        if action == "requests_made":
            res = assistant_db.get_money_requests_made(s, req.user_id)
            return AgentActResponse(text=res["text"], action="requests_made", data=res)
        if action == "requests_received":
            res = assistant_db.get_money_requests_received(s, req.user_id)
            return AgentActResponse(text=res["text"], action="requests_received", data=res)
        if action == "recent_splits":
            res = assistant_db.get_recent_splits(s, req.user_id)
            return AgentActResponse(text=res["text"], action="recent_splits", data=res)
        if action == "spending_history":
            res = assistant_db.get_spending_history(s, req.user_id)
            return AgentActResponse(text=res["text"], action="spending_history", data=res)
        if action == "budget_status":
            res = assistant_db.get_budget_status(s, req.user_id, intent_dict.get("festival"))
            return AgentActResponse(text=res["text"], action="budget_status", data=res)
        if action == "account_limits":
            res = assistant_db.get_user_limits_and_tier(s, req.user_id)
            return AgentActResponse(text=res["text"], action="account_limits", data=res)
        if action == "financial_insights":
            from ..services import financial_intelligence
            res = financial_intelligence.calculate_financial_insights(s, req.user_id)
            return AgentActResponse(text=res["text"], action="financial_insights", data=res)
        if action == "financial_literacy":
            from ..services import financial_intelligence
            res = financial_intelligence.get_financial_literacy_guide(intent_dict.get("topic"))
            return AgentActResponse(text=res["text"], action="financial_literacy", data=res)
        if action == "set_budget":
            amt = intent_dict.get("amount")
            if amt and float(amt) > 0:
                res = assistant_db.set_or_update_budget(
                    s, req.user_id, intent_dict.get("festival", "general"), Decimal(str(amt))
                )
                return AgentActResponse(text=res["text"], action="set_budget", data=res)
            return AgentActResponse(
                text=llm.phrase("missing_budget_details", {}),
                action="set_budget",
            )

        if action == "send":
            return _handle_send(s, req, intent_dict, handles, user)
        if action == "request":
            return _handle_request_action(s, req, intent_dict, handles, user)
        if action == "split":
            return _handle_split(s, req, intent_dict, handles, user)
        if action == "pay_bill":
            return _handle_pay_bill(s, req, intent_dict, billers, user)

        # Conversational / financial advisory query — ground with live database facts
        from ..services import financial_intelligence
        from ..tier_config import get_effective_limits, get_effective_tier
        insights = financial_intelligence.calculate_financial_insights(s, req.user_id)
        current_balance = _post_debit_balance(s, req.user_id)
        eff_tier = get_effective_tier(
            getattr(user, "account_tier", None) or getattr(user, "tier", "personal"),
            getattr(user, "kyc_status", "unverified"),
        )
        limits = get_effective_limits(
            eff_tier,
            getattr(user, "kyc_status", "unverified"),
            custom_single=float(user.single_txn_limit) if getattr(user, "single_txn_limit", None) else None,
            custom_daily=float(user.daily_limit) if getattr(user, "daily_limit", None) else None,
            user_type=getattr(user, "user_type", None),
        )
        user_facts = {
            "user_handle": user.handle,
            "user_type": getattr(user, "user_type", "student"),
            "account_tier": getattr(user, "account_tier", "personal"),
            "effective_tier": eff_tier,
            "kyc_status": getattr(user, "kyc_status", "unverified"),
            "single_transfer_limit_bdt": float(limits["single_txn_limit"]),
            "daily_transfer_limit_bdt": float(limits["daily_limit"]),
            "balance_bdt": float(current_balance),
            "spending_last_30_days_bdt": float(insights.get("total_spent_30d_bdt", "0").replace(",", "")),
            "spending_last_7_days_bdt": float(insights.get("total_spent_7d_bdt", "0").replace(",", "")),
            "weekly_velocity_vs_average": f"{insights.get('weekly_velocity_pct', 0)}%",
            "health_score": f"{insights.get('health_score')}/100 ({insights.get('health_rating')})",
            "category_breakdown": insights.get("category_breakdown", []),
            "recommendations": [
                f"{r.get('title')}: {r.get('description')}" for r in insights.get("recommendations", [])
            ],
        }
        reply_text = llm.chat_reply(req.text, user.handle, user_facts=user_facts)
        return AgentActResponse(
            text=reply_text,
            action="advisory",
            data=insights,
        )


def _handle_send(s, req, intent_dict, handles, user) -> AgentActResponse:
    raw_recipient = (intent_dict.get("recipient") or "").strip()
    raw_amount = intent_dict.get("amount")

    # Missing both amount and recipient
    if not raw_recipient and (raw_amount is None or float(raw_amount) <= 0):
        return AgentActResponse(
            text=llm.phrase("missing_details_send", {}),
            action="send",
        )
    # Missing recipient
    if not raw_recipient:
        return AgentActResponse(
            text=llm.phrase("missing_recipient_send", {"amount_bdt": str(raw_amount)}),
            action="send",
        )
    # Missing amount
    if raw_amount is None or float(raw_amount) <= 0:
        return AgentActResponse(
            text=llm.phrase("missing_amount_send", {"recipient": raw_recipient}),
            action="send",
        )

    try:
        recipient = resolver.resolve_recipient(raw_recipient, handles)
    except resolver.AmbiguousRecipient as e:
        return AgentActResponse(
            text=llm.phrase("ambiguous_recipient", {"candidates": e.candidates}),
            action="send",
        )
    except resolver.UnknownRecipient as e:
        return AgentActResponse(
            text=llm.phrase(
                "unknown_recipient",
                {"raw": raw_recipient, "known": handles},
            ),
            action="send",
        )
    try:
        amount = resolver.resolve_amount(raw_amount)
    except resolver.ResolutionError as e:
        raise HTTPException(422, e.message)

    try:
        txn = engine.create_pending_send(
            s,
            initiator_user_id=user.id,
            recipient_handle=recipient,
            amount=amount,
            idempotency_key=req.idempotency_key,
            note=intent_dict.get("note"),
        )
    except engine.IdempotencyReplay as r:
        # Replay: compute the correct post-debit balance for the card.
        current_balance = _post_debit_balance(s, user.id)
        resulting = current_balance - r.txn.amount_bdt
        card = _review_card_for_send(r.txn, s)
        card.resulting_balance_bdt = resulting
        sub_act = intent_dict.get("sub_action") or ("recharge" if r.txn.note == "Mobile Recharge" else ("cash_out" if r.txn.note == "Cash Out via Agent" else "send"))
        return AgentActResponse(
            text=llm.phrase(
                "review_send",
                {
                    "amount_bdt": str(r.txn.amount_bdt),
                    "recipient": card.recipient_label,
                    "resulting_balance_bdt": str(resulting),
                    "sub_action": sub_act,
                },
            ),
            card=card,
            pending_id=r.txn.id,
            action="send",
            idempotent_replay=True,
        )
    except engine.InsufficientFunds as e:
        return AgentActResponse(
            text=llm.phrase(
                "insufficient_funds",
                {"balance_bdt": str(e.balance), "amount_bdt": str(e.amount)},
            ),
            action="send",
        )
    except engine.EngineError as e:
        raise HTTPException(400, str(e))

    card = _review_card_for_send(txn, s)
    resulting = _post_debit_balance(s, user.id) - amount
    sub_action = intent_dict.get("sub_action", "send")
    text = llm.phrase(
        "review_send",
        {
            "amount_bdt": str(amount),
            "recipient": recipient,
            "resulting_balance_bdt": str(resulting),
            "sub_action": sub_action,
        },
    )
    # Patch the card with the correct post-debit balance.
    card.resulting_balance_bdt = resulting
    return AgentActResponse(text=text, card=card, pending_id=txn.id, action="send")


def _handle_request_action(s, req, intent_dict, handles, user) -> AgentActResponse:
    """User wants to ASK someone for money."""
    raw_payer = (intent_dict.get("recipient") or "").strip()
    raw_amount = intent_dict.get("amount")

    # Missing both
    if not raw_payer and (raw_amount is None or float(raw_amount) <= 0):
        return AgentActResponse(
            text=llm.phrase("missing_details_request", {}),
            action="request",
        )
    # Missing payer
    if not raw_payer:
        return AgentActResponse(
            text=llm.phrase("missing_recipient_request", {"amount_bdt": str(raw_amount)}),
            action="request",
        )
    # Missing amount
    if raw_amount is None or float(raw_amount) <= 0:
        return AgentActResponse(
            text=llm.phrase("missing_amount_request", {"recipient": raw_payer}),
            action="request",
        )

    try:
        payer_handle = resolver.resolve_recipient(raw_payer, handles)
    except resolver.AmbiguousRecipient as e:
        return AgentActResponse(
            text=llm.phrase("ambiguous_recipient", {"candidates": e.candidates}),
            action="request",
        )
    except resolver.UnknownRecipient as e:
        return AgentActResponse(
            text=llm.phrase(
                "unknown_recipient",
                {"raw": raw_payer, "known": handles},
            ),
            action="request",
        )
    try:
        amount = resolver.resolve_amount(raw_amount)
    except resolver.ResolutionError as e:
        raise HTTPException(422, e.message)
    try:
        req_row = engine.create_pending_request(
            s,
            initiator_user_id=user.id,
            payer_handle=payer_handle,
            amount=amount,
            idempotency_key=req.idempotency_key,
            note=intent_dict.get("note"),
        )
    except engine.IdempotencyReplay_for_request as replay:
        req_row = replay.req
    except engine.EngineError as e:
        raise HTTPException(400, str(e))

    card = _review_card_for_request(req_row, s)
    current_balance = _post_debit_balance(s, user.id)
    text = llm.phrase(
        "review_request",
        {
            "amount_bdt": str(amount),
            "recipient": payer_handle,
            "current_balance_bdt": str(current_balance),
        },
    )
    return AgentActResponse(
        text=text,
        card=card,
        pending_id=req_row.id,
        action="request",
    )


def _handle_split(s, req, intent_dict, handles, user) -> AgentActResponse:
    raw_recipients = intent_dict.get("split_recipients") or []
    if not raw_recipients and intent_dict.get("recipient"):
        raw_recipients = [intent_dict["recipient"]]
    raw_amount = intent_dict.get("amount")

    # Missing both
    if not raw_recipients and (raw_amount is None or float(raw_amount) <= 0):
        return AgentActResponse(
            text="Boss, who would you like to split with, and what is the total amount?",
            action="split",
        )
    # Missing recipients
    if not raw_recipients:
        return AgentActResponse(
            text=llm.phrase("missing_recipients_split", {"total_amount_bdt": str(raw_amount)}),
            action="split",
        )
    # Missing amount
    if raw_amount is None or float(raw_amount) <= 0:
        return AgentActResponse(
            text=llm.phrase("missing_amount_split", {"recipients": raw_recipients}),
            action="split",
        )

    resolved = []
    for r in raw_recipients:
        try:
            resolved.append(resolver.resolve_recipient(str(r), handles))
        except resolver.AmbiguousRecipient as e:
            return AgentActResponse(
                text=llm.phrase("ambiguous_recipient", {"candidates": e.candidates}),
                action="split",
            )
        except resolver.UnknownRecipient as e:
            return AgentActResponse(
                text=llm.phrase(
                    "unknown_recipient",
                    {"raw": str(r), "known": handles},
                ),
                action="split",
            )
    try:
        amount = resolver.resolve_amount(raw_amount)
    except resolver.ResolutionError as e:
        raise HTTPException(422, e.message)
    try:
        sp = engine.create_pending_split(
            s,
            initiator_user_id=user.id,
            recipient_handles=resolved,
            total_amount=amount,
            idempotency_key=req.idempotency_key,
            note=intent_dict.get("note"),
        )
    except engine.InsufficientFunds as e:
        return AgentActResponse(
            text=llm.phrase(
                "insufficient_funds",
                {"balance_bdt": str(e.balance), "amount_bdt": str(e.amount)},
            ),
            action="split",
        )
    except engine.EngineError as e:
        raise HTTPException(400, str(e))

    resulting = _post_debit_balance(s, user.id) - amount
    text = llm.phrase(
        "review_split",
        {
            "total_amount_bdt": str(amount),
            "recipients": resolved,
            "per_amount_bdt": str(sp.per_amount_bdt),
            "resulting_balance_bdt": str(resulting),
        },
    )
    first_child = (
        s.query(Transaction)
        .filter_by(parent_split_id=sp.id, kind="split_child")
        .order_by(Transaction.id.asc())
        .first()
    )
    if first_child is None:
        raise HTTPException(500, "split created without pending transactions")
    card = ReviewCard(
        kind="split",
        amount_bdt=amount,
        recipients=resolved,
        note=intent_dict.get("note"),
        resulting_balance_bdt=resulting,
        initiator_handle=user.handle,
        initiator_phone=user.phone,
    )
    return AgentActResponse(
        text=text,
        card=card,
        action="split",
        pending_id=first_child.id,
        data={
            "split_id": sp.id,
            "recipients": resolved,
            "per_amount_bdt": str(sp.per_amount_bdt),
            "total_amount_bdt": str(sp.total_amount_bdt),
        },
    )


def _handle_pay_bill(s, req, intent_dict, billers, user) -> AgentActResponse:
    raw_biller = (intent_dict.get("biller") or "").strip()
    try:
        biller = resolver.resolve_biller(raw_biller, billers) if raw_biller else ""
    except resolver.ResolutionError:
        biller = ""
    if not biller:
        return AgentActResponse(
            text=f"Which biller? Available: {', '.join(billers)}.",
            action="pay_bill",
        )
    try:
        amount = resolver.resolve_amount(intent_dict.get("amount"))
    except resolver.ResolutionError as e:
        raise HTTPException(422, e.message)
    try:
        txn = engine.create_pending_bill(
            s,
            initiator_user_id=user.id,
            biller_name=biller,
            amount=amount,
            idempotency_key=req.idempotency_key,
            note=intent_dict.get("note"),
        )
    except engine.IdempotencyReplay as r:
        txn = r.txn
    except engine.InsufficientFunds as e:
        return AgentActResponse(
            text=llm.phrase(
                "insufficient_funds",
                {"balance_bdt": str(e.balance), "amount_bdt": str(e.amount)},
            ),
            action="pay_bill",
        )
    except engine.EngineError as e:
        raise HTTPException(400, str(e))

    resulting = _post_debit_balance(s, user.id) - amount
    text = llm.phrase(
        "review_bill",
        {
            "biller": biller,
            "amount_bdt": str(amount),
            "resulting_balance_bdt": str(resulting),
        },
    )
    return AgentActResponse(
        text=text,
        action="pay_bill",
        pending_id=txn.id,
    )


@router.post("/chat", response_model=AgentChatResponse)
def agent_chat(req: AgentChatRequest) -> AgentChatResponse:
    """Free-form conversational endpoint. Always replies — never errors out.

    Used by the chat input bar for greetings / small talk / live DB questions.
    """
    with session_scope() as s:
        u = _user_by_id(s, req.user_id)
        fallback_intent = llm._regex_intent(
            req.text, engine.known_handles(s), engine.known_billers(s)
        )
        if fallback_intent["action"] == "balance":
            balance = _post_debit_balance(s, req.user_id)
            return AgentChatResponse(
                text=llm.phrase("balance", {"balance_bdt": str(balance)}),
                action="balance",
            )
        if fallback_intent["action"] == "history":
            account = s.query(Account).filter_by(user_id=req.user_id).one()
            count = (
                s.query(Transaction)
                .filter(
                    (Transaction.from_account_id == account.id)
                    | (Transaction.to_account_id == account.id)
                )
                .count()
            )
            return AgentChatResponse(
                text=llm.phrase("history_summary", {"count": count}),
                action="history",
            )

        # ---- Live DB Financial Queries ----
        if fallback_intent["action"] == "spending_recent":
            res = assistant_db.get_recent_spending(s, req.user_id)
            return AgentChatResponse(text=res["text"], action="spending_recent")
        if fallback_intent["action"] == "spending_where":
            res = assistant_db.get_where_spent(s, req.user_id)
            return AgentChatResponse(text=res["text"], action="spending_where")
        if fallback_intent["action"] == "latest_transaction":
            res = assistant_db.get_latest_transaction(s, req.user_id)
            return AgentChatResponse(text=res["text"], action="latest_transaction")
        if fallback_intent["action"] == "send_vs_receive":
            res = assistant_db.get_sent_vs_received(s, req.user_id)
            return AgentChatResponse(text=res["text"], action="send_vs_receive")
        if fallback_intent["action"] == "requests_made":
            res = assistant_db.get_money_requests_made(s, req.user_id)
            return AgentChatResponse(text=res["text"], action="requests_made")
        if fallback_intent["action"] == "requests_received":
            res = assistant_db.get_money_requests_received(s, req.user_id)
            return AgentChatResponse(text=res["text"], action="requests_received")
        if fallback_intent["action"] == "recent_splits":
            res = assistant_db.get_recent_splits(s, req.user_id)
            return AgentChatResponse(text=res["text"], action="recent_splits")
        if fallback_intent["action"] == "spending_history":
            res = assistant_db.get_spending_history(s, req.user_id)
            return AgentChatResponse(text=res["text"], action="spending_history")
        if fallback_intent["action"] == "budget_status":
            res = assistant_db.get_budget_status(s, req.user_id, fallback_intent.get("festival"))
            return AgentChatResponse(text=res["text"], action="budget_status")
        if fallback_intent["action"] == "financial_insights":
            from ..services import financial_intelligence
            res = financial_intelligence.calculate_financial_insights(s, req.user_id)
            return AgentChatResponse(text=res["text"], action="financial_insights")
        if fallback_intent["action"] == "financial_literacy":
            from ..services import financial_intelligence
            res = financial_intelligence.get_financial_literacy_guide(fallback_intent.get("topic"))
            return AgentChatResponse(text=res["text"], action="financial_literacy")
        if fallback_intent["action"] == "set_budget":
            amt = fallback_intent.get("amount")
            if amt and float(amt) > 0:
                res = assistant_db.set_or_update_budget(
                    s, req.user_id, fallback_intent.get("festival", "general"), Decimal(str(amt))
                )
                return AgentChatResponse(text=res["text"], action="set_budget")
            return AgentChatResponse(
                text=llm.phrase("missing_budget_details", {}),
                action="set_budget",
            )

        # Senior Architecture: Classify Casual Small Talk vs Financial Advisory Query
        norm = req.text.strip().lower()
        is_greeting = any(g in norm for g in ("hi", "hello", "hey", "salam", "assalam", "assalamu alaikum", "morning", "evening"))
        is_thanks = any(t in norm for t in ("thanks", "thank you", "thx", "shukriya"))
        is_bye = any(b in norm for b in ("bye", "goodbye", "see you", "allah hafez", "tata"))
        is_smalltalk = any(st in norm for st in ("how are you", "who are you", "what are you", "what can you do", "help me"))

        finance_signals = ("optimize", "velocity", "recommend", "advice", "saving", "spend", "budget", "target", "guidance")
        is_advice_query = any(w in norm for w in finance_signals)

        # 1. Casual Chat: Keep in LLM hands with ZERO database load or fact-dumping
        if (is_greeting or is_thanks or is_bye or is_smalltalk) and not is_advice_query:
            action = "greeting" if is_greeting else "thanks" if is_thanks else "bye" if is_bye else "smalltalk"
            text = llm.chat_reply(req.text, u.handle, user_facts=None)
            return AgentChatResponse(text=text, action=action)

        # 2. Financial Advisory / Guidance: Ground LLM with live database financial facts
        from ..services import financial_intelligence
        insights = financial_intelligence.calculate_financial_insights(s, req.user_id)
        current_balance = _post_debit_balance(s, req.user_id)
        user_facts = {
            "user_handle": u.handle,
            "balance_bdt": float(current_balance),
            "spending_last_30_days_bdt": float(insights.get("total_spent_30d_bdt", "0").replace(",", "")),
            "spending_last_7_days_bdt": float(insights.get("total_spent_7d_bdt", "0").replace(",", "")),
            "weekly_velocity_vs_average": f"{insights.get('weekly_velocity_pct', 0)}%",
            "health_score": f"{insights.get('health_score')}/100 ({insights.get('health_rating')})",
            "category_breakdown": insights.get("category_breakdown", []),
            "recommendations": [
                f"{r.get('title')}: {r.get('description')}" for r in insights.get("recommendations", [])
            ],
        }
        text = llm.chat_reply(req.text, u.handle, user_facts=user_facts)
        return AgentChatResponse(text=text, action="financial_advice" if is_advice_query else "fallback")


# ---- Explicit split (N-way) ------------------------------------------------
@router.post("/act-split", response_model=AgentActResponse)
def agent_act_split(req: AgentActSplitRequest) -> AgentActResponse:
    """LLM-free split entry point used by the N-way chip-array UI.

    Why this exists: voice/text must still flow through /agent/act (regex +
    LLM cascade), but the chip-array form knows the recipients and amount
    up-front. Sending the user through the orchestrator would force the
    LLM to *re-discover* facts it didn't need to, and would round-trip
    through Ollama at ~10s timeout per click.

    Safety boundary: still routes through `engine.create_pending_split`
    and `resolver.resolve_recipient` — the AI never owns the ledger. Only
    the user-disambiguation step is skipped.
    """
    with session_scope() as s:
        user = _user_by_id(s, req.user_id)
        handles = engine.known_handles(s)

        # De-dupe + preserve order. Reject empty.
        seen: set[str] = set()
        unique: list[str] = []
        for h in req.recipient_handles:
            h_clean = (h or "").strip()
            if not h_clean:
                continue
            if h_clean.lower() in seen:
                continue
            seen.add(h_clean.lower())
            unique.append(h_clean)
        if len(unique) < 2:
            raise HTTPException(422, "split needs at least 2 unique recipients")

        # Idempotency pre-flight: same (initiator, key) — return the
        # original pending child instead of re-running engine. The
        # orchestrator's /agent/act does this for send/bill; we mirror
        # the same behaviour for split so retries (browser double-clicks,
        # network blips) never spawn extra pending rows.
        #
        # The engine mints child keys as `{parent_key}:{user_id}`. We
        # compute the same prefix and look for any existing child.
        child_key_prefix = f"{req.idempotency_key}:"
        existing_child = (
            s.query(Transaction)
            .filter(
                Transaction.initiator_user_id == user.id,
                Transaction.kind == "split_child",
                Transaction.idempotency_key.like(f"{child_key_prefix}%"),
            )
            .order_by(Transaction.id.asc())
            .first()
        )
        if existing_child is not None:
            existing_parent_id = existing_child.parent_split_id
            siblings = (
                s.query(Transaction)
                .filter_by(parent_split_id=existing_parent_id)
                .order_by(Transaction.id.asc())
                .all()
            )
            recipient_handles_out = []
            for sib in siblings:
                if sib.to_account_id is None:
                    continue
                sib_user = (
                    s.query(User).join(Account).filter(Account.id == sib.to_account_id).one_or_none()
                )
                if sib_user is not None:
                    recipient_handles_out.append(sib_user.handle)
            existing_split = s.get(Split, existing_parent_id) if existing_parent_id else None
            per_amount_str = str(existing_split.per_amount_bdt) if existing_split else "0"
            resulting = _post_debit_balance(s, user.id) - req.amount_bdt
            card = ReviewCard(
                kind="split",
                amount_bdt=req.amount_bdt,
                recipients=recipient_handles_out,
                note=req.note,
                resulting_balance_bdt=resulting,
                initiator_handle=user.handle,
                initiator_phone=user.phone,
            )
            text = llm.phrase(
                "review_split",
                {
                    "total_amount_bdt": str(req.amount_bdt),
                    "recipients": recipient_handles_out,
                    "per_amount_bdt": per_amount_str,
                    "resulting_balance_bdt": str(resulting),
                },
            )
            return AgentActResponse(
                text=text,
                card=card,
                action="split",
                pending_id=existing_child.id,
                idempotent_replay=True,
            )

        # Resolve (fuzzy). Same safety story as the orchestrator.
        resolved: list[str] = []
        for raw in unique:
            try:
                resolved.append(resolver.resolve_recipient(raw, handles))
            except resolver.AmbiguousRecipient as e:
                return AgentActResponse(
                    text=llm.phrase("ambiguous_recipient", {"candidates": e.candidates}),
                    action="split",
                )
            except resolver.UnknownRecipient as e:
                return AgentActResponse(
                    text=llm.phrase(
                        "unknown_recipient",
                        {"raw": raw, "known": handles},
                    ),
                    action="split",
                )

        try:
            sp = engine.create_pending_split(
                s,
                initiator_user_id=user.id,
                recipient_handles=resolved,
                total_amount=req.amount_bdt,
                idempotency_key=req.idempotency_key,
                note=req.note,
            )
        except engine.InsufficientFunds as e:
            return AgentActResponse(
                text=llm.phrase(
                    "insufficient_funds",
                    {"balance_bdt": str(e.balance), "amount_bdt": str(e.amount)},
                ),
                action="split",
            )
        except engine.EngineError as e:
            raise HTTPException(400, str(e))

        resulting = _post_debit_balance(s, user.id) - req.amount_bdt
        text = llm.phrase(
            "review_split",
            {
                "total_amount_bdt": str(req.amount_bdt),
                "recipients": resolved,
                "per_amount_bdt": str(sp.per_amount_bdt),
                "resulting_balance_bdt": str(resulting),
            },
        )
        first_child = (
            s.query(Transaction)
            .filter_by(parent_split_id=sp.id, kind="split_child")
            .order_by(Transaction.id.asc())
            .first()
        )
        if first_child is None:
            raise HTTPException(500, "split created without pending transactions")
        card = ReviewCard(
            kind="split",
            amount_bdt=req.amount_bdt,
            recipients=resolved,
            note=req.note,
            resulting_balance_bdt=resulting,
            initiator_handle=user.handle,
            initiator_phone=user.phone,
        )
        return AgentActResponse(
            text=text,
            card=card,
            action="split",
            pending_id=first_child.id,
            data={
                "split_id": sp.id,
                "recipients": resolved,
                "per_amount_bdt": str(sp.per_amount_bdt),
                "total_amount_bdt": str(sp.total_amount_bdt),
            },
        )


# ---- Explicit send (Quick-send form on the dashboard) ----------------------
@router.post("/act-send", response_model=AgentActResponse)
def agent_act_send(req: AgentActSendRequest) -> AgentActResponse:
    """LLM-free send entry point used by the Quick-send form.

    Why this exists: voice/text must still flow through /agent/act (regex +
    LLM cascade), but the Quick-send form knows the recipient and amount
    up-front. Sending the user through the orchestrator would force the
    LLM to *re-discover* facts it didn't need to, and would round-trip
    through Ollama at ~10s timeout per click — which is exactly what made
    "tap Send" feel broken.

    Safety boundary: still routes through `engine.create_pending_send`
    and `resolver.resolve_recipient` — the AI never owns the ledger. Only
    the user-disambiguation step is skipped.
    """
    with session_scope() as s:
        user = _user_by_id(s, req.user_id)
        handles = engine.known_handles(s)

        # Idempotency pre-flight: same (initiator, key) → return the existing
        # pending row. Mirrors the orchestrator's behaviour so retries
        # (browser double-clicks, network blips) never spawn extra pending
        # rows. We patch the resulting_balance below because the user may
        # have changed accounts since the original click.
        existing = (
            s.query(Transaction)
            .filter_by(initiator_user_id=user.id, idempotency_key=req.idempotency_key)
            .one_or_none()
        )
        if existing is not None:
            current_balance = _post_debit_balance(s, user.id)
            resulting = current_balance - existing.amount_bdt
            card = _review_card_for_send(existing, s)
            card.resulting_balance_bdt = resulting
            text = llm.phrase(
                "review_send",
                {
                    "amount_bdt": str(existing.amount_bdt),
                    "recipient": card.recipient_label,
                    "resulting_balance_bdt": str(resulting),
                },
            )
            return AgentActResponse(
                text=text,
                card=card,
                pending_id=existing.id,
                action="send",
                idempotent_replay=True,
            )

        # Resolve (fuzzy). Same safety story as the orchestrator.
        try:
            recipient = resolver.resolve_recipient(req.recipient_handle, handles)
        except resolver.AmbiguousRecipient as e:
            return AgentActResponse(
                text=llm.phrase("ambiguous_recipient", {"candidates": e.candidates}),
                action="send",
            )
        except resolver.UnknownRecipient as e:
            return AgentActResponse(
                text=llm.phrase(
                    "unknown_recipient",
                    {"raw": req.recipient_handle, "known": handles},
                ),
                action="send",
            )

        # Schema already validated amount_bdt > 0 and has 2dp, but route
        # through resolver for symmetry with the orchestrator path.
        try:
            amount = resolver.resolve_amount(req.amount_bdt)
        except resolver.ResolutionError as e:
            raise HTTPException(422, e.message)

        try:
            txn = engine.create_pending_send(
                s,
                initiator_user_id=user.id,
                recipient_handle=recipient,
                amount=amount,
                idempotency_key=req.idempotency_key,
                note=req.note,
            )
        except engine.InsufficientFunds as e:
            return AgentActResponse(
                text=llm.phrase(
                    "insufficient_funds",
                    {"balance_bdt": str(e.balance), "amount_bdt": str(e.amount)},
                ),
                action="send",
            )
        except engine.EngineError as e:
            raise HTTPException(400, str(e))

        resulting = _post_debit_balance(s, user.id) - amount
        card = _review_card_for_send(txn, s)
        card.resulting_balance_bdt = resulting
        text = llm.phrase(
            "review_send",
            {
                "amount_bdt": str(amount),
                "recipient": recipient,
                "resulting_balance_bdt": str(resulting),
            },
        )
        return AgentActResponse(
            text=text,
            card=card,
            action="send",
            pending_id=txn.id,
        )


# ---- Explicit request (Ask-for-money modal) --------------------------------
@router.post("/act-request", response_model=AgentActResponse)
def agent_act_request(req: AgentActRequestActionRequest) -> AgentActResponse:
    """LLM-free request-money entry point used by the Ask modal.

    Creates a pending Request row that the payer's dashboard will surface
    via /users/{id}/requests. No ReviewCard is returned — the request flow
    has no review step; the asker is told the request was created.
    """
    with session_scope() as s:
        user = _user_by_id(s, req.user_id)
        handles = engine.known_handles(s)

        # Resolve the payer handle (fuzzy).
        try:
            payer_handle = resolver.resolve_recipient(req.payer_handle, handles)
        except resolver.AmbiguousRecipient as e:
            return AgentActResponse(
                text=llm.phrase("ambiguous_recipient", {"candidates": e.candidates}),
                action="request",
            )
        except resolver.UnknownRecipient as e:
            return AgentActResponse(
                text=llm.phrase(
                    "unknown_recipient",
                    {"raw": req.payer_handle, "known": handles},
                ),
                action="request",
            )

        try:
            amount = resolver.resolve_amount(req.amount_bdt)
        except resolver.ResolutionError as e:
            raise HTTPException(422, e.message)

        try:
            req_row = engine.create_pending_request(
                s,
                initiator_user_id=user.id,
                payer_handle=payer_handle,
                amount=amount,
                idempotency_key=req.idempotency_key,
                note=req.note,
            )
        except engine.IdempotencyReplay_for_request as replay:
            # Idempotent replay: return the original request.
            return AgentActResponse(
                text=llm.phrase(
                    "request_created",
                    {
                        "payer": payer_handle,
                        "amount_bdt": str(replay.req.amount_bdt),
                    },
                ),
                action="request",
                pending_id=replay.req.id,
                idempotent_replay=True,
            )
        except engine.EngineError as e:
            raise HTTPException(400, str(e))

        text = llm.phrase(
            "request_created",
            {"payer": payer_handle, "amount_bdt": str(amount)},
        )
        return AgentActResponse(
            text=text,
            action="request",
            pending_id=req_row.id,
        )


# ---- Confirm / Decline ------------------------------------------------------
@router.post("/confirm", response_model=AgentConfirmResponse)
def agent_confirm(req: AgentConfirmRequest) -> AgentConfirmResponse:
    """Execute (or cancel) a pending transaction or request."""
    with session_scope() as s:
        # Check if this pending_id refers to a Request row (from "request money")
        req_row = s.get(Request, req.pending_id)
        if req_row is not None and req_row.asker_user_id == req.user_id:
            if req.decision == "decline":
                req_row.status = RequestStatus.DECLINED.value
                s.flush()
                return AgentConfirmResponse(
                    text="Cancelled. Money request was not sent.",
                    success=False,
                )
            # Confirmed: keep it pending for the payer to see on their dashboard
            payer = s.get(User, req_row.payer_user_id)
            payer_handle = payer.handle if payer else "the user"
            current_balance = _post_debit_balance(s, req.user_id)
            return AgentConfirmResponse(
                text=llm.phrase(
                    "request_created",
                    {"payer": payer_handle, "amount_bdt": str(req_row.amount_bdt)},
                ),
                success=True,
                new_balance_bdt=current_balance,
            )

        if req.decision == "decline":
            try:
                txn = engine.decline(s, user_id=req.user_id, pending_id=req.pending_id)
            except engine.EngineError as e:
                raise HTTPException(400, str(e))
            return AgentConfirmResponse(
                text=llm.phrase("cancelled", {}),
                success=False,
            )

        # decision == "confirm"
        try:
                txn = engine.confirm_split(s, user_id=req.user_id, pending_id=req.pending_id)
        except engine.PendingExpired:
            return AgentConfirmResponse(
                text="That request expired. Try again.",
                success=False,
            )
        except engine.PendingAlreadyResolved as e:
            return AgentConfirmResponse(
                text=f"That request is already {e.args[0]}.",
                success=False,
            )
        except engine.InsufficientFunds as e:
            return AgentConfirmResponse(
                text=llm.phrase(
                    "insufficient_funds",
                    {"balance_bdt": str(e.balance), "amount_bdt": str(e.amount)},
                ),
                success=False,
            )
        except engine.UnknownPending as e:
            raise HTTPException(404, str(e))
        except engine.EngineError as e:
            raise HTTPException(400, str(e))

        new_balance = _post_debit_balance(s, req.user_id)
        # Determine phrasable facts.
        recipient = None
        biller_name = None
        if txn.to_account_id:
            r_user = (
                s.query(User).join(Account).filter(Account.id == txn.to_account_id).one()
            )
            recipient = r_user.handle
        if txn.biller_id:
            from ..models import Biller

            b = s.get(Biller, txn.biller_id)
            biller_name = b.name if b else None

        if txn.parent_split_id:
            kind = "executed_split"
            children = s.query(Transaction).filter_by(parent_split_id=txn.parent_split_id).all()
            facts = {
                "total_amount_bdt": str(sum((child.amount_bdt for child in children), Decimal("0.00"))),
                "recipients": [recipient for recipient in [
                    s.query(User).join(Account).filter(Account.id == child.to_account_id).one().handle
                    for child in children if child.to_account_id
                ]],
                "new_balance_bdt": str(new_balance),
            }
        elif txn.kind == "send":
            kind = "executed_send"
            sub_action = "recharge" if txn.note == "Mobile Recharge" else ("cash_out" if txn.note == "Cash Out via Agent" else "send")
            facts = {
                "amount_bdt": str(txn.amount_bdt),
                "recipient": recipient,
                "new_balance_bdt": str(new_balance),
                "sub_action": sub_action,
            }
        elif txn.kind == "bill":
            kind = "executed_bill"
            facts = {
                "amount_bdt": str(txn.amount_bdt),
                "biller": biller_name,
                "new_balance_bdt": str(new_balance),
            }
        else:  # split_child
            kind = "executed_send"
            facts = {
                "amount_bdt": str(txn.amount_bdt),
                "recipient": recipient,
                "new_balance_bdt": str(new_balance),
            }

        text = llm.phrase(kind, facts)
        return AgentConfirmResponse(
            text=text,
            success=True,
            new_balance_bdt=new_balance,
        )
