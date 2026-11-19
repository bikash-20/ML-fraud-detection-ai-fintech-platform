"""Accounts, history, pending requests, billers, session switching, Face ID."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, joinedload

from .. import engine
from ..db import session_scope
from ..models import Account, Biller, Request, RequestStatus, SavingsGoal, Transaction, TxnKind, TxnStatus, User, UserSecurityPreference
from ..schemas import (
    BalanceOut,
    BillerOut,
    FaceDeleteResponse,
    FaceEnrollRequest,
    FaceEnrollResponse,
    FaceStatusResponse,
    HistoryResponse,
    LoginRequest,
    PendingRequestOut,
    SavingsContribution,
    SavingsGoalCreate,
    SavingsGoalOut,
    TxnOut,
    UserOut,
    UserProfileDetailsOut,
    UserUpgradeRequest,
)
from ..tier_config import (
    ACCOUNT_TIERS,
    AGENT_LIMITS,
    DEFAULT_TYPE_TIER_MAPPING,
    TIER_BASELINE_FALLBACKS,
    TIER_LIMITS,
    USER_TYPES,
    get_effective_limits,
    get_effective_tier,
)


def _build_user_out(u: User) -> UserOut:
    eff_tier = get_effective_tier(
        getattr(u, "account_tier", None) or getattr(u, "tier", "personal"),
        getattr(u, "kyc_status", "unverified"),
    )
    limits = get_effective_limits(
        eff_tier,
        getattr(u, "kyc_status", "unverified"),
        custom_single=float(u.single_txn_limit) if getattr(u, "single_txn_limit", None) else None,
        custom_daily=float(u.daily_limit) if getattr(u, "daily_limit", None) else None,
        user_type=getattr(u, "user_type", None),
    )
    return UserOut(
        id=u.id,
        handle=u.handle,
        display_name=u.display_name,
        phone=u.phone,
        email=f"{u.handle}@wallet.com",
        user_type=getattr(u, "user_type", "student") or "student",
        account_tier=getattr(u, "account_tier", "personal") or getattr(u, "tier", "personal") or "personal",
        effective_tier=eff_tier,
        kyc_status=getattr(u, "kyc_status", "unverified") or "unverified",
        business_name=getattr(u, "business_name", None),
        masked_phone=u.masked_phone,
        created_at=u.created_at,
        daily_limit=u.daily_limit,
        single_txn_limit=u.single_txn_limit,
        effective_single_limit=float(limits["single_txn_limit"]),
        effective_daily_limit=float(limits["daily_limit"]),
        requested_upgrade_tier=getattr(u, "requested_upgrade_tier", None),
        requested_upgrade_at=getattr(u, "requested_upgrade_at", None),
    )


# ---- Face ID embedding (de)serialisation -----------------------------------
# We store the 128-dim float32 vector produced by face-api.js as a JSON-encoded
# UTF-8 byte blob inside `users.face_embedding` (LargeBinary). Storing as JSON
# (rather than raw float32 bytes) keeps the column human-readable for ops and
# matches the wire format the browser already uses (a JS Float32Array →
# plain array of numbers). Per-user footprint is ~1.5 KB.


def _pack_embedding(vec: list[float]) -> bytes:
    """Serialise a validated 128-dim float vector for storage."""
    return json.dumps(vec, separators=(",", ":")).encode("utf-8")


def _unpack_embedding(blob: bytes) -> list[float]:
    """Reverse of _pack_embedding. Defensive: returns [] on any decode error
    rather than crashing a status call (status reads must never 500)."""
    try:
        vec = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return []
    if not isinstance(vec, list):
        return []
    return [float(x) for x in vec]

router = APIRouter(tags=["accounts"])


@router.get("/tier-config")
def get_tier_config() -> dict:
    """Single source of truth for account tiers and transaction limits.

    Labeled: Configurable assumptions to verify against current Bangladesh Bank rules.
    """
    return {
        "tiers": TIER_LIMITS,
        "agent_limits": AGENT_LIMITS,
        "user_types": USER_TYPES,
        "account_tiers": ACCOUNT_TIERS,
        "default_type_tier_mapping": DEFAULT_TYPE_TIER_MAPPING,
        "regulatory_disclaimer": "Configurable assumptions to verify against current Bangladesh Bank rules",
    }


@router.get("/users", response_model=list[UserOut])
def list_users() -> list[UserOut]:
    with session_scope() as s:
        rows = s.execute(select(User).order_by(User.id)).scalars().all()
        return [_build_user_out(u) for u in rows]


@router.post("/auth/login", response_model=UserOut)
def login(body: LoginRequest) -> UserOut:
    raw = (body.email or "").strip().lower()
    if not raw:
        raise HTTPException(400, "Email or username is required")
    # If user passed e.g. bikash@wallet.com, candidate handle is bikash
    candidate_handle = raw.split("@")[0].strip()
    with session_scope() as s:
        u = s.query(User).filter(
            (User.handle == raw) |
            (User.handle == candidate_handle) |
            (User.phone == raw)
        ).first()
        if u is None:
            raise HTTPException(401, "No account found matching this email or username.")
        return _build_user_out(u)


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(user_id: int) -> UserOut:
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(404, "user not found")
        return _build_user_out(u)


@router.get("/users/handle/{handle}", response_model=UserOut)
def get_user_by_handle(handle: str) -> UserOut:
    with session_scope() as s:
        u = s.query(User).filter_by(handle=handle).one_or_none()
        if u is None:
            raise HTTPException(404, "user not found")
        return _build_user_out(u)


@router.get("/users/{user_id}/profile", response_model=UserProfileDetailsOut)
def get_user_profile(user_id: int) -> UserProfileDetailsOut:
    """Return comprehensive profile view including limits, today's spend vs limit, and frequent recipients."""
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(404, "user not found")

        acct = s.query(Account).filter_by(user_id=u.id).one_or_none()
        bal = acct.balance_bdt if acct else Decimal("0.00")

        # Today's completed outbound spend
        now = _utcnow()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        daily_spent = Decimal("0.00")
        if acct:
            spent_row = (
                s.query(func.sum(Transaction.amount_bdt))
                .filter(
                    Transaction.from_account_id == acct.id,
                    Transaction.status == TxnStatus.COMPLETED.value,
                    Transaction.created_at >= start_of_day,
                )
                .scalar()
            )
            if spent_row:
                daily_spent = Decimal(str(spent_row))

        user_out = _build_user_out(u)
        daily_limit_val = Decimal(str(user_out.effective_daily_limit or 100000.0))
        remaining = max(Decimal("0.00"), daily_limit_val - daily_spent)
        usage_pct = float(round((daily_spent / daily_limit_val) * Decimal("100.0"), 1)) if daily_limit_val > 0 else 0.0

        # Frequent recipients
        frequent = []
        if acct:
            rec_rows = (
                s.query(Transaction.to_account_id, func.count(Transaction.id).label("cnt"))
                .filter(
                    Transaction.from_account_id == acct.id,
                    Transaction.to_account_id.isnot(None),
                    Transaction.status == TxnStatus.COMPLETED.value,
                )
                .group_by(Transaction.to_account_id)
                .order_by(desc("cnt"))
                .limit(4)
                .all()
            )
            for r_acct_id, cnt in rec_rows:
                rec_acct = s.get(Account, r_acct_id)
                if rec_acct and rec_acct.user_id:
                    rec_u = s.get(User, rec_acct.user_id)
                    if rec_u:
                        frequent.append({
                            "user_id": rec_u.id,
                            "handle": rec_u.handle,
                            "display_name": rec_u.display_name,
                            "tier": rec_u.account_tier,
                            "count": cnt,
                        })

        # Calculate 30-day baseline median
        import numpy as np
        t30 = now - timedelta(days=30)
        past_amounts = []
        if acct:
            res_30d = (
                s.query(Transaction.amount_bdt)
                .filter(
                    Transaction.from_account_id == acct.id,
                    Transaction.status == TxnStatus.COMPLETED.value,
                    Transaction.created_at >= t30,
                )
                .all()
            )
            past_amounts = [float(r[0]) for r in res_30d if r[0] is not None]

        if len(past_amounts) >= 5:
            baseline_med = float(np.median(past_amounts))
        else:
            baseline_med = TIER_BASELINE_FALLBACKS.get(user_out.effective_tier, 1000.0)

        return UserProfileDetailsOut(
            user=user_out,
            current_balance_bdt=bal,
            daily_spent_today_bdt=daily_spent,
            daily_limit_bdt=daily_limit_val,
            daily_remaining_bdt=remaining,
            daily_usage_pct=usage_pct,
            frequent_recipients=frequent,
            baseline_median_30d=baseline_med,
        )


@router.post("/users/{user_id}/upgrade-request")
def request_user_upgrade(user_id: int, body: UserUpgradeRequest) -> dict:
    """Submit a request to upgrade tier (e.g. to verified or business).

    Security rule:
    User cannot activate tier directly. The request is placed in pending state.
    Business or agent tier becomes active ONLY after an admin sets kyc_status = verified.
    """
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(404, "user not found")

        u.requested_upgrade_tier = body.requested_tier
        u.requested_upgrade_at = _utcnow()
        if body.business_name:
            u.business_name = body.business_name

        s.flush()
        return {
            "success": True,
            "message": f"Upgrade request to {body.requested_tier.capitalize()} Tier submitted. Pending administrator KYC verification.",
            "requested_tier": body.requested_tier,
            "kyc_status": u.kyc_status,
            "effective_tier": u.effective_tier,
            "business_name": u.business_name,
        }


@router.get("/users/{user_id}/balance", response_model=BalanceOut)
def get_balance(user_id: int) -> BalanceOut:
    with session_scope() as s:
        snap = engine.snapshot(s, user_id)
        return BalanceOut(
            user_id=snap.user_id,
            handle=snap.handle,
            balance_bdt=snap.balance_bdt,
            as_of=_utcnow(),
        )


def _format_txn_for_user(txn: Transaction, user_id: int, session: Session) -> TxnOut:
    direction: str
    counterparty: Optional[str] = None
    counterparty_phone: Optional[str] = None
    if txn.from_account_id and txn.to_account_id:
        # Use account->user to figure out direction.
        from_user = (
            session.query(User).join(Account).filter(Account.id == txn.from_account_id).one_or_none()
        )
        to_user = (
            session.query(User).join(Account).filter(Account.id == txn.to_account_id).one_or_none()
        )
        if from_user and from_user.id == user_id:
            direction = "out"
            if to_user:
                counterparty = to_user.handle
                counterparty_phone = to_user.phone
        elif to_user and to_user.id == user_id:
            direction = "in"
            if from_user:
                counterparty = from_user.handle
                counterparty_phone = from_user.phone
        else:
            direction = "out"
    elif txn.from_account_id:
        direction = "out"
        if txn.biller_id:
            b = session.get(Biller, txn.biller_id)
            if b:
                counterparty = b.name
        elif txn.kind == "savings":
            counterparty = "Festival Savings"
        else:
            counterparty = "Savings Goal"
    else:
        direction = "in"
        counterparty = "Deposit"

    if counterparty is None:
        if txn.kind == "savings":
            counterparty = "Festival Savings"
        elif txn.kind == "bill":
            counterparty = "Utility Bill"
        else:
            counterparty = "Wallet Transfer"

    return TxnOut(
        id=txn.id,
        kind=txn.kind,
        status=txn.status,
        amount_bdt=txn.amount_bdt,
        direction=direction,
        counterparty=counterparty,
        counterparty_phone=counterparty_phone,
        note=txn.note,
        created_at=txn.created_at,
        completed_at=txn.completed_at,
    )


@router.get("/users/{user_id}/history", response_model=HistoryResponse)
def get_history(user_id: int, limit: int = 50) -> HistoryResponse:
    """Return recent txns + a 14-day balance timeline.

    Only strictly COMPLETED and confirmed transactions are returned in recent history.
    Pending, cancelled, declined, or interrupted transactions are excluded so that
    history accurately reflects real funds debited or credited after user confirmation.
    """
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(404, "user not found")
        acct = s.query(Account).filter_by(user_id=u.id).one()

        # Pull strictly completed, confirmed transactions involving this user's account
        rows = (
            s.query(Transaction)
            .filter(
                (Transaction.from_account_id == acct.id)
                | (Transaction.to_account_id == acct.id),
                Transaction.status == TxnStatus.COMPLETED.value,
                Transaction.completed_at.isnot(None),
            )
            .order_by(Transaction.completed_at.desc(), Transaction.id.desc())
            .limit(limit)
            .all()
        )
        txns = [_format_txn_for_user(t, u.id, s) for t in rows]

        # 14-day timeline: compute by walking transactions chronologically.
        # We'll start from current balance and subtract/apply deltas going back.
        timeline = _build_timeline(s, acct.id, acct.balance_bdt, days=14)

        return HistoryResponse(
            user_id=u.id,
            handle=u.handle,
            balance_bdt=acct.balance_bdt,
            txns=txns,
            timeline=timeline,
        )


def _build_timeline(
    s: Session, account_id: int, current_balance: Decimal, days: int = 14
) -> list[dict]:
    """Build a balance timeline across the last N days.

    Includes daily baseline points for days without activity, plus progressive
    points for every completed transaction so intraday sends, receives, bill
    payments, and splits immediately bend and update the chart.
    """
    now = _utcnow()
    cutoff = now - timedelta(days=days)
    txns = (
        s.query(Transaction)
        .filter(
            (Transaction.from_account_id == account_id)
            | (Transaction.to_account_id == account_id),
            Transaction.status == TxnStatus.COMPLETED.value,
            Transaction.completed_at.isnot(None),
            Transaction.completed_at >= cutoff,
        )
        .order_by(Transaction.completed_at.asc())
        .all()
    )

    # Walk backward from current_balance to calculate balance after each transaction
    # and the starting balance before the 14-day window.
    post_balances: list[tuple[Transaction, Decimal]] = []
    running = Decimal(str(current_balance))
    for t in reversed(txns):
        post_balances.append((t, running))
        if t.from_account_id == account_id and t.to_account_id == account_id:
            pass
        elif t.from_account_id == account_id:
            running += t.amount_bdt
        elif t.to_account_id == account_id:
            running -= t.amount_bdt

    post_balances.reverse()
    # Stored value wallet cannot be negative
    start_balance = max(Decimal("0.00"), running)
    today = now.date()

    # Group completed transactions by calendar date
    by_date: dict[str, list[tuple[Transaction, Decimal]]] = {}
    for t, bal in post_balances:
        d_key = t.completed_at.date().isoformat()
        by_date.setdefault(d_key, []).append((t, max(Decimal("0.00"), bal)))

    timeline: list[dict] = []
    cur_bal = start_balance

    for d_offset in range(days, -1, -1):
        day = today - timedelta(days=d_offset)
        d_str = day.isoformat()
        if d_str in by_date:
            day_txns = by_date[d_str]
            # Add opening anchor for the day so intraday fluctuations start from prior closing
            timeline.append({"date": f"{d_str} 00:00", "balance": float(round(cur_bal, 2))})
            for t, bal in day_txns:
                t_label = t.completed_at.strftime("%Y-%m-%d %H:%M")
                timeline.append({"date": t_label, "balance": float(round(bal, 2))})
                cur_bal = bal
        else:
            timeline.append({"date": d_str, "balance": float(round(cur_bal, 2))})

    # Defensive guarantee: the timeline's final element must strictly match current_balance
    if timeline:
        timeline[-1]["balance"] = float(round(current_balance, 2))
    else:
        timeline.append({"date": today.isoformat(), "balance": float(round(current_balance, 2))})

    return timeline


@router.get("/users/{user_id}/savings-goals", response_model=list[SavingsGoalOut])
def get_savings_goals(user_id: int) -> list[SavingsGoalOut]:
    with session_scope() as s:
        if s.get(User, user_id) is None:
            raise HTTPException(404, "user not found")
        return [SavingsGoalOut.model_validate(g) for g in s.query(SavingsGoal).filter_by(user_id=user_id).order_by(SavingsGoal.created_at.desc()).all()]


@router.post("/users/{user_id}/savings-goals", response_model=SavingsGoalOut)
def create_savings_goal(user_id: int, payload: SavingsGoalCreate) -> SavingsGoalOut:
    with session_scope() as s:
        if s.get(User, user_id) is None:
            raise HTTPException(404, "user not found")
        goal = SavingsGoal(user_id=user_id, festival=payload.festival.strip(), target_amount_bdt=payload.target_amount_bdt, target_date=payload.target_date)
        s.add(goal)
        try:
            s.flush()
        except Exception as exc:
            raise HTTPException(409, "a savings goal for this festival already exists") from exc
        return SavingsGoalOut.model_validate(goal)


@router.post("/users/{user_id}/savings-goals/{goal_id}/contribute", response_model=SavingsGoalOut)
def contribute_savings(user_id: int, goal_id: int, payload: SavingsContribution) -> SavingsGoalOut:
    """Move money into a festival goal atomically; no silent overdrafts."""
    with session_scope() as s:
        goal = s.get(SavingsGoal, goal_id)
        if goal is None or goal.user_id != user_id:
            raise HTTPException(404, "savings goal not found")
        account = s.query(Account).filter_by(user_id=user_id).one()
        transaction_key = f"saving:{goal_id}:{payload.idempotency_key}"
        existing = s.query(Transaction).filter_by(
            initiator_user_id=user_id, idempotency_key=transaction_key
        ).one_or_none()
        if existing is not None:
            return SavingsGoalOut.model_validate(goal)
        if account.balance_bdt < payload.amount_bdt:
            raise HTTPException(422, "insufficient balance for this saving")
        account.balance_bdt -= payload.amount_bdt
        s.add(Transaction(
            idempotency_key=transaction_key,
            initiator_user_id=user_id,
            from_account_id=account.id,
            amount_bdt=payload.amount_bdt,
            kind=TxnKind.SAVINGS.value,
            status=TxnStatus.COMPLETED.value,
            note=f"Saving for {goal.festival}",
            completed_at=_utcnow(),
        ))
        goal.saved_amount_bdt += payload.amount_bdt
        s.flush()
        return SavingsGoalOut.model_validate(goal)


@router.get("/users/{user_id}/requests", response_model=list[PendingRequestOut])
def get_pending_requests(user_id: int) -> list[PendingRequestOut]:
    """Requests where THIS user is the payer (i.e. owes someone)."""
    with session_scope() as s:
        rows = (
            s.query(Request)
            .filter_by(payer_user_id=user_id, status=RequestStatus.PENDING.value)
            .order_by(Request.created_at.desc())
            .all()
        )
        out: list[PendingRequestOut] = []
        for r in rows:
            asker = s.get(User, r.asker_user_id)
            out.append(
                PendingRequestOut(
                    id=r.id,
                    asker_handle=asker.handle if asker else "?",
                    asker_phone=asker.phone if asker else "",
                    amount_bdt=r.amount_bdt,
                    note=r.note,
                    created_at=r.created_at,
                )
            )
        return out


@router.post("/requests/{request_id}/pay")
def pay_request_endpoint(request_id: int, idempotency_key: str, user_id: int) -> dict:
    """Mark a request as paid (pays the asker).

    `user_id` must be the payer. Raises 403 if the caller is not the
    designated payer on the request, preventing any authenticated user
    from paying someone else's debt.
    """
    from .. import engine as eng

    with session_scope() as s:
        req_row = s.get(Request, request_id)
        if req_row is None:
            raise HTTPException(404, "request not found")
        if req_row.payer_user_id != user_id:
            raise HTTPException(403, "you are not the payer for this request")
        try:
            txn = eng.pay_request(
                s,
                payer_user_id=user_id,
                request_id=request_id,
                idempotency_key=idempotency_key,
            )
        except eng.InsufficientFunds as e:
            raise HTTPException(422, str(e))
        except eng.EngineError as e:
            raise HTTPException(400, str(e))
        new_balance = s.query(Account).filter_by(user_id=txn.initiator_user_id).one().balance_bdt
        return {"success": True, "new_balance_bdt": str(new_balance)}


@router.post("/requests/{request_id}/decline")
def decline_request_endpoint(request_id: int) -> dict:
    from .. import engine as eng

    with session_scope() as s:
        r = s.get(Request, request_id)
        if r is None:
            raise HTTPException(404, "request not found")
        try:
            eng.decline_request(s, user_id=r.payer_user_id, request_id=request_id)
        except eng.EngineError as e:
            raise HTTPException(400, str(e))
        return {"success": True}


@router.get("/billers", response_model=list[BillerOut])
def list_billers() -> list[BillerOut]:
    with session_scope() as s:
        rows = s.execute(select(Biller).order_by(Biller.id)).scalars().all()
        return [
            BillerOut(id=b.id, name=b.name, category=b.category, account_number=b.account_number)
            for b in rows
        ]


# ---- Face ID -----------------------------------------------------------------
# Browser-side flow:
#   1. The settings UI loads face-api.js models, opens the webcam, runs the
#      detector on a frame, and calls /face/status to learn whether this user
#      is already enrolled.
#   2. If not enrolled, the UI shows an enroll modal: capture a frame, extract
#      the 128-dim descriptor, POST it to /face. The server stores it as an
#      opaque blob. We never see the raw image.
#   3. During payment confirmation, the UI re-opens the camera, runs the
#      detector, computes cosine similarity against the stored embedding, and
#      only fires /agent/confirm if the score exceeds the threshold (default
#      0.6 — same convention as face-api.js). The server is NOT in the loop
#      for matching; it just gates the confirm call by accepting the request.
#
# Threat model: this is a *demo* biometric. It raises the cost of accidental
# shoulder-surfing and stops a casual user from confirming while a different
# person is at the screen. It is NOT a security boundary — the matching is
# fully client-side and trivially bypassable by anyone with browser DevTools.

# L2-normalised cosine similarity, computed identically client- and server-side.
# We expose it only for tests; the live confirm path runs in the browser.
FACE_MATCH_THRESHOLD = 0.6


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Standard cosine similarity. Returns 0.0 on dimension mismatch.

    Face-api.js always emits a 128-dim vector, and the request schema
    enforces that. If we ever see a different length in stored data
    (corruption, schema drift), treat it as no match rather than risk
    a coincidental shared-prefix false positive.
    """
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return 0.0
    return dot / ((na ** 0.5) * (nb ** 0.5))


@router.get("/users/{user_id}/face/status", response_model=FaceStatusResponse)
def get_face_status(user_id: int) -> FaceStatusResponse:
    """Whether this user has enrolled a face. Never 500s — the UI relies on
    this during initial bootstrap."""
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(404, "user not found")
        return FaceStatusResponse(
            user_id=u.id,
            enrolled=u.face_embedding is not None,
            enrolled_at=u.face_enrolled_at,
        )


@router.post("/users/{user_id}/face", response_model=FaceEnrollResponse)
def enroll_face(user_id: int, payload: FaceEnrollRequest) -> FaceEnrollResponse:
    """Upsert the user's face embedding.

    Re-enrollment is allowed and overwrites the previous blob + timestamp.
    The Pydantic validator already enforced dimensionality and finite values,
    so by the time we reach this body the vector is well-formed.
    """
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(404, "user not found")
        u.face_embedding = _pack_embedding(payload.embedding)
        u.face_enrolled_at = _utcnow()
        s.flush()
        return FaceEnrollResponse(
            user_id=u.id,
            enrolled=True,
            enrolled_at=u.face_enrolled_at,
        )


@router.delete("/users/{user_id}/face", response_model=FaceDeleteResponse)
def delete_face(user_id: int) -> FaceDeleteResponse:
    """Clear any prior enrollment. Idempotent: returns enrolled=false whether
    or not anything was actually present."""
    with session_scope() as s:
        u = s.get(User, user_id)
        if u is None:
            raise HTTPException(404, "user not found")
        u.face_embedding = None
        u.face_enrolled_at = None
        s.flush()
        return FaceDeleteResponse(user_id=u.id, enrolled=False)


# ---- User Security Preference (Requirement 7) -------------------------------
@router.get("/users/{user_id}/security-preference")
def get_user_security_preference(user_id: int) -> dict:
    with session_scope() as s:
        u = s.get(User, user_id)
        if not u:
            raise HTTPException(404, "User not found")
        pref = s.query(UserSecurityPreference).filter_by(user_id=user_id).one_or_none()
        show = pref.show_security_analysis if pref else False
        return {"user_id": user_id, "show_security_analysis": show}


@router.post("/users/{user_id}/security-preference")
def set_user_security_preference(user_id: int, payload: dict) -> dict:
    show = bool(payload.get("show_security_analysis", False))
    with session_scope() as s:
        u = s.get(User, user_id)
        if not u:
            raise HTTPException(404, "User not found")
        pref = s.query(UserSecurityPreference).filter_by(user_id=user_id).one_or_none()
        if not pref:
            pref = UserSecurityPreference(user_id=user_id, show_security_analysis=show)
            s.add(pref)
        else:
            pref.show_security_analysis = show
        s.flush()
        return {"user_id": user_id, "show_security_analysis": pref.show_security_analysis}

