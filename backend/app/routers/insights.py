"""Read-only insights + tag-management endpoints.

The categorizer worker (background) writes `TxnTag` rows after every
confirmed transaction. These endpoints read those rows for the dashboard
and let users override or remove a tag.

All endpoints are scoped by `user_id` — only the user's own txns and
tags are readable / writable. Override semantics: a user-set tag
(source='user') is preserved when the categorizer re-runs because the
UNIQUE(txn_id, tag_slug) constraint blocks duplicate rows for the same
slug, not for the same (txn, slug) source pair. To "promote" an auto-tag
to user-set, the user endpoint upserts the row with source='user'.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import Account, TxnStatus, TxnTag, Transaction, User
from ..services.categorizer import is_known_tag, known_tags


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


router = APIRouter(tags=["insights"])


# ---- Helpers ----------------------------------------------------------------
def _user_owns_txn(session: Session, user_id: int, txn_id: int) -> bool:
    """A user 'owns' a txn if either side of the transfer is their account."""
    account = session.query(Account).filter_by(user_id=user_id).one_or_none()
    if account is None:
        return False
    txn = session.get(Transaction, txn_id)
    if txn is None:
        return False
    return txn.from_account_id == account.id or txn.to_account_id == account.id


def _load_tags_for_txn(session: Session, txn_ids: list[int]) -> dict[int, list[dict]]:
    """Bulk-load tags for a set of txn ids. Returns txn_id -> [{tag, source}]."""
    if not txn_ids:
        return {}
    rows = (
        session.query(TxnTag)
        .filter(TxnTag.txn_id.in_(txn_ids))
        .order_by(TxnTag.created_at.asc())
        .all()
    )
    out: dict[int, list[dict]] = {tid: [] for tid in txn_ids}
    for r in rows:
        out[r.txn_id].append({"tag": r.tag_slug, "source": r.source})
    return out


# ---- Tag override endpoints -------------------------------------------------
@router.post("/users/{user_id}/transactions/{txn_id}/tags")
def set_txn_tag(user_id: int, txn_id: int, payload: dict) -> dict:
    """User-set a tag on a transaction. Idempotent.

    Body: {"tag_slug": "food"}
    Returns 404 if the user doesn't own the txn.
    Returns 422 if the slug isn't in the known-tag set.
    """
    slug = (payload.get("tag_slug") or "").strip().lower()
    if not is_known_tag(slug):
        raise HTTPException(422, f"unknown tag slug: {slug!r}. Known: {known_tags()}")
    with session_scope() as s:
        if not _user_owns_txn(s, user_id, txn_id):
            raise HTTPException(404, "transaction not found")
        # Upsert: if a row exists, prefer source='user'. Else insert.
        existing = (
            s.query(TxnTag)
            .filter_by(txn_id=txn_id, tag_slug=slug)
            .one_or_none()
        )
        if existing is not None:
            existing.source = "user"
            existing.by_user_id = user_id
        else:
            s.add(TxnTag(txn_id=txn_id, tag_slug=slug, source="user", by_user_id=user_id))
            try:
                s.flush()
            except Exception as exc:
                raise HTTPException(409, f"could not set tag: {exc}")
        return {"txn_id": txn_id, "tag_slug": slug, "source": "user"}


@router.delete("/users/{user_id}/transactions/{txn_id}/tags/{tag_slug}")
def delete_txn_tag(user_id: int, txn_id: int, tag_slug: str) -> dict:
    """User removes a tag (typically an auto-tag they disagree with)."""
    slug = tag_slug.strip().lower()
    with session_scope() as s:
        if not _user_owns_txn(s, user_id, txn_id):
            raise HTTPException(404, "transaction not found")
        row = s.query(TxnTag).filter_by(txn_id=txn_id, tag_slug=slug).one_or_none()
        if row is None:
            raise HTTPException(404, "tag not found")
        s.delete(row)
        return {"txn_id": txn_id, "tag_slug": slug, "removed": True}


# ---- Insights: by-category --------------------------------------------------
@router.get("/users/{user_id}/insights/by-category")
def insights_by_category(user_id: int, days: int = 30) -> dict:
    """Aggregate the user's debits by category for the last `days`.

    A "debit" for this user = a transaction where `from_account_id` is
    their account (spends, splits, bills). Income (request payouts)
    counts toward total inflow under the 'transfer' tag in a separate
    endpoint — we keep this endpoint focused on spending.

    Single SQL with one JOIN + one GROUP BY + window function for
    top-recipient per category.
    """
    days = max(1, min(days, 365))
    since = _utcnow() - timedelta(days=days)
    with session_scope() as s:
        account = s.query(Account).filter_by(user_id=user_id).one_or_none()
        if account is None:
            raise HTTPException(404, "user not found")

        # Per-category totals and counts.
        total_expr = func.coalesce(func.sum(Transaction.amount_bdt), 0)
        count_expr = func.count(Transaction.id)
        rows = (
            s.query(
                TxnTag.tag_slug.label("category"),
                total_expr.label("total"),
                count_expr.label("count"),
            )
            .join(Transaction, Transaction.id == TxnTag.txn_id)
            .filter(
                Transaction.from_account_id == account.id,
                Transaction.status == TxnStatus.COMPLETED.value,
                Transaction.completed_at >= since,
            )
            .group_by(TxnTag.tag_slug)
            .order_by(total_expr.desc())
            .all()
        )
        out = [
            {
                "category": r.category,
                "total_bdt": str(r.total),
                "count": int(r.count),
            }
            for r in rows
        ]
        # Top counterparty per category, in a second small query. Keeps
        # the GROUP BY above simple at the cost of one extra round-trip.
        top_per_cat: dict[str, str] = {}
        if out:
            cat_rows = (
                s.query(
                    TxnTag.tag_slug.label("category"),
                    User.handle.label("counterparty"),
                    func.sum(Transaction.amount_bdt).label("sum_amt"),
                )
                .join(Transaction, Transaction.id == TxnTag.txn_id)
                .join(Account, Account.id == Transaction.to_account_id)
                .join(User, User.id == Account.user_id)
                .filter(
                    Transaction.from_account_id == account.id,
                    Transaction.status == TxnStatus.COMPLETED.value,
                    Transaction.completed_at >= since,
                )
                .group_by(TxnTag.tag_slug, User.handle)
                .all()
            )
            for cat, handle, sum_amt in cat_rows:
                cur = top_per_cat.get(cat)
                if cur is None or Decimal(str(sum_amt)) > Decimal(str(cur[1])):
                    top_per_cat[cat] = (handle, sum_amt)
        for row in out:
            top = top_per_cat.get(row["category"])
            row["top_recipient"] = top[0] if top else None

        # Grand total for the same window — useful for relative bars.
        grand = (
            s.query(func.coalesce(func.sum(Transaction.amount_bdt), 0))
            .filter(
                Transaction.from_account_id == account.id,
                Transaction.status == TxnStatus.COMPLETED.value,
                Transaction.completed_at >= since,
            )
            .scalar()
        )
        return {
            "user_id": user_id,
            "days": days,
            "since": since.isoformat(),
            "grand_total_bdt": str(grand),
            "categories": out,
        }


# ---- Insights: tags on a single txn (used by HistoryList) ------------------
@router.get("/users/{user_id}/transactions/{txn_id}/tags")
def get_txn_tags(user_id: int, txn_id: int) -> dict:
    with session_scope() as s:
        if not _user_owns_txn(s, user_id, txn_id):
            raise HTTPException(404, "transaction not found")
        tags = _load_tags_for_txn(s, [txn_id])[txn_id]
        return {"txn_id": txn_id, "tags": tags}


# ---- Insights: bulk tags for the user's recent txns ------------------------
@router.get("/users/{user_id}/insights/tags-for-history")
def tags_for_history(user_id: int, limit: int = 50) -> dict:
    """Returns a `{txn_id: [{tag, source}, ...]}` map for the most recent
    `limit` txns involving this user. Frontend uses this to render
    category badges on the history list without an N+1 query."""
    limit = max(1, min(limit, 200))
    with session_scope() as s:
        account = s.query(Account).filter_by(user_id=user_id).one_or_none()
        if account is None:
            raise HTTPException(404, "user not found")
        recent = (
            s.query(Transaction.id)
            .filter(
                (Transaction.from_account_id == account.id)
                | (Transaction.to_account_id == account.id),
                Transaction.status == TxnStatus.COMPLETED.value,
                Transaction.completed_at.isnot(None),
            )
            .order_by(Transaction.completed_at.desc(), Transaction.id.desc())
            .limit(limit)
            .all()
        )
        ids = [r[0] for r in recent]
        tags = _load_tags_for_txn(s, ids)
        return {"txn_ids": ids, "tags": tags}


# ---- New Intelligence Layer: Financial Intelligence & Literacy Endpoints ----
@router.get("/users/{user_id}/financial-intelligence")
def get_user_financial_intelligence(user_id: int) -> dict:
    """Returns real-time financial health score, 30-day category breakdown,
    velocity metrics, and personalized budget recommendations.
    """
    from ..services.financial_intelligence import calculate_financial_insights
    with session_scope() as s:
        try:
            return calculate_financial_insights(s, user_id)
        except ValueError as e:
            raise HTTPException(404, str(e))


@router.get("/users/{user_id}/financial-literacy")
def get_user_financial_literacy(user_id: int, topic: str | None = None) -> dict:
    """Returns curated financial literacy guides and best practices."""
    from ..services.financial_intelligence import get_financial_literacy_guide
    return get_financial_literacy_guide(topic)


class RecommendationAdviceRequest(BaseModel):
    title: str
    description: Optional[str] = None
    category: Optional[str] = None


@router.post("/users/{user_id}/financial-intelligence/advice")
def get_recommendation_advice(user_id: int, req: RecommendationAdviceRequest) -> dict:
    """Live-database grounded AI advice for a specific budget recommendation.

    Synthesizes concrete steps, taka allocations, and velocity adjustments
    using the user's real database records via the multi-model cascade.
    """
    import json
    from .. import llm
    from ..services.financial_intelligence import calculate_financial_insights

    with session_scope() as s:
        user = s.get(User, user_id)
        if user is None:
            raise HTTPException(404, "user not found")
        acct = s.query(Account).filter_by(user_id=user_id).one()
        insights = calculate_financial_insights(s, user_id)

        live_facts = {
            "user_handle": user.handle,
            "balance_bdt": float(acct.balance_bdt),
            "spending_last_30_days_bdt": insights.get("total_spent_30d_bdt"),
            "spending_last_7_days_bdt": insights.get("total_spent_7d_bdt"),
            "weekly_velocity_pct": insights.get("weekly_velocity_pct"),
            "budget_health_score": insights.get("health_score"),
            "category_breakdown": insights.get("category_breakdown", []),
            "target_recommendation": {
                "title": req.title,
                "description": req.description,
                "category": req.category,
            },
        }

        system_prompt = (
            "You are Wallet AI Financial Guide — an expert personal finance advisor for Bangladesh. "
            "Address the user as 'Boss'. "
            "The user asked for practical guidance on this budget recommendation: "
            f"'{req.title}' ({req.description}).\n\n"
            f"LIVE USER DATABASE FINANCIALS:\n{json.dumps(live_facts, indent=2)}\n\n"
            "Provide clear, encouraging, actionable financial guidance in 2 to 3 sentences. "
            "Include concrete taka amounts based on their live numbers and suggest exactly how to execute this recommendation. "
            "Never invent unrelated numbers."
        )

        try:
            advice_text = llm.generate_cascade(system_prompt, f"How can I implement {req.title}?").strip()
            advice_text = advice_text.strip().strip('"').strip("`")
            if not advice_text:
                advice_text = req.description or "Pacing your expenses weekly helps maintain budget stability."
        except Exception as e:
            advice_text = req.description or "Pacing your expenses weekly helps maintain budget stability."

        # Concrete actionable steps
        cat = (req.category or "").lower()
        title_lower = req.title.lower()
        desc_lower = (req.description or "").lower()

        if "other" in title_lower or "discretionary" in desc_lower:
            steps = [
                "Review recent miscellaneous sends and dining expenses.",
                "Cap weekly non-essential transfers to keep ৳500+ in reserve.",
                "Use festival savings pockets to lock away surplus balance."
            ]
        elif "goal" in title_lower or "savings" in cat or "eid" in title_lower:
            steps = [
                "Set an automated weekly transfer of ৳500–৳1,000 to your savings pocket.",
                "Review active festival targets before making large transfers.",
                "Keep savings separate from your main daily transaction balance."
            ]
        elif "velocity" in title_lower or "budget" in cat:
            steps = [
                "Pause high-value non-urgent transfers for the next 48–72 hours.",
                "Pace out peer-to-peer sends to bring weekly velocity back to baseline.",
                "Check your balance before sending money to stay above emergency minimums."
            ]
        else:
            steps = [
                "Track upcoming recurring expenses in your calendar.",
                "Allocate small regular deposits towards your targets.",
                "Monitor spending velocity on your intelligence dashboard."
            ]

        return {
            "title": req.title,
            "advice": advice_text,
            "action_steps": steps,
            "live_facts": live_facts,
        }

