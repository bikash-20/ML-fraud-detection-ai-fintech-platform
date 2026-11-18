"""Live Database Assistant Service for Financial AI Queries.

Provides live, authorized query execution against the SQLite / PostgreSQL
database to answer questions such as:
- How much did I spend recently?
- Where did I spend my money?
- What was my latest transaction?
- Did I send or receive money?
- What money requests have I made?
- What money requests have I received?
- What are my recent split-money transactions?
- What is my current spending history?
- What is my budget / savings goal status?

All queries strictly respect the authenticated user's ID and account boundaries.
No mock data is used.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from ..models import Account, Biller, Request, SavingsGoal, Split, Transaction, TxnStatus, TxnTag, User


def _get_user_and_account(session: Session, user_id: int) -> tuple[User, Account]:
    user = session.get(User, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    account = session.query(Account).filter_by(user_id=user_id).one()
    return user, account


def get_recent_spending(session: Session, user_id: int, days: int = 30) -> Dict[str, Any]:
    """Calculate how much money the user spent recently (completed debits)."""
    user, account = _get_user_and_account(session, user_id)
    cutoff = datetime.utcnow() - timedelta(days=days)

    txns = (
        session.query(Transaction)
        .filter(
            Transaction.from_account_id == account.id,
            Transaction.status == TxnStatus.COMPLETED.value,
            Transaction.created_at >= cutoff,
        )
        .all()
    )

    total_spent = sum((t.amount_bdt for t in txns), Decimal("0.00"))
    count = len(txns)

    if count == 0:
        return {
            "total_spent_bdt": Decimal("0.00"),
            "count": 0,
            "days": days,
            "text": f"Boss, you haven't had any completed spending recorded in the last {days} days.",
        }

    return {
        "total_spent_bdt": total_spent,
        "count": count,
        "days": days,
        "text": f"Boss, you have spent a total of ৳{total_spent:,.2f} across {count} transactions in the last {days} days.",
    }


def get_user_limits_and_tier(session: Session, user_id: int) -> Dict[str, Any]:
    """Retrieve live tier, regulatory limits, and today's usage for AI assistant responses."""
    user, account = _get_user_and_account(session, user_id)
    from ..tier_config import get_effective_limits, get_effective_tier
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
    # Today's completed outbound spend
    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    spent_today = session.query(func.coalesce(func.sum(Transaction.amount_bdt), Decimal("0.00"))).filter(
        Transaction.from_account_id == account.id,
        Transaction.status == TxnStatus.COMPLETED.value,
        Transaction.created_at >= start_of_day,
    ).scalar()

    single_cap = float(limits["single_txn_limit"])
    daily_cap = float(limits["daily_limit"])
    remaining = max(0.0, daily_cap - float(spent_today))

    return {
        "user_handle": user.handle,
        "user_type": getattr(user, "user_type", "student") or "student",
        "account_tier": getattr(user, "account_tier", "personal") or getattr(user, "tier", "personal") or "personal",
        "effective_tier": eff_tier,
        "kyc_status": getattr(user, "kyc_status", "unverified") or "unverified",
        "single_limit_bdt": single_cap,
        "daily_limit_bdt": daily_cap,
        "spent_today_bdt": float(spent_today),
        "remaining_today_bdt": remaining,
        "text": f"Boss, your account is operating under {eff_tier.capitalize()} Tier limits ({getattr(user, 'user_type', 'student').capitalize()} profile, KYC {getattr(user, 'kyc_status', 'unverified')}). Your single transaction transfer cap is ৳{single_cap:,.2f} and your daily transfer cap is ৳{daily_cap:,.2f}. You have spent ৳{float(spent_today):,.2f} today, leaving ৳{remaining:,.2f} available for outbound transfers today.",
    }


def get_where_spent(session: Session, user_id: int, limit: int = 10) -> Dict[str, Any]:
    """Breakdown of where the user spent their money recently (billers, counterparties, tags)."""
    user, account = _get_user_and_account(session, user_id)

    txns = (
        session.query(Transaction)
        .filter(
            Transaction.from_account_id == account.id,
            Transaction.status == TxnStatus.COMPLETED.value,
        )
        .order_by(desc(Transaction.created_at))
        .limit(limit)
        .all()
    )

    if not txns:
        return {
            "items": [],
            "text": "Boss, there are no recorded spending transactions for your account yet.",
        }

    # Group by destination
    breakdown: Dict[str, Decimal] = {}
    for t in txns:
        dest_name = "Other"
        if t.biller_id:
            biller = session.get(Biller, t.biller_id)
            dest_name = f"Utility: {biller.name}" if biller else "Utility Bill"
        elif t.to_account_id:
            dest_user = (
                session.query(User)
                .join(Account, Account.user_id == User.id)
                .filter(Account.id == t.to_account_id)
                .one_or_none()
            )
            dest_name = f"Transfer to @{dest_user.handle}" if dest_user else "Transfer"
        elif t.kind == "savings":
            dest_name = "Savings Goal"

        breakdown[dest_name] = breakdown.get(dest_name, Decimal("0.00")) + t.amount_bdt

    details = [f"{dest} (৳{amt:,.2f})" for dest, amt in sorted(breakdown.items(), key=lambda x: x[1], reverse=True)]
    text = f"Boss, here is where your recent spending went: {', '.join(details)}."
    return {"breakdown": {k: str(v) for k, v in breakdown.items()}, "text": text}


def get_latest_transaction(session: Session, user_id: int) -> Dict[str, Any]:
    """Retrieve the most recent completed transaction for the user."""
    user, account = _get_user_and_account(session, user_id)

    latest = (
        session.query(Transaction)
        .filter(
            or_(
                Transaction.from_account_id == account.id,
                Transaction.to_account_id == account.id,
                Transaction.initiator_user_id == user.id,
            ),
            Transaction.status == TxnStatus.COMPLETED.value,
        )
        .order_by(desc(Transaction.created_at))
        .first()
    )

    if not latest:
        return {
            "transaction": None,
            "text": "Boss, you have no completed transactions in your ledger yet.",
        }

    date_str = latest.created_at.strftime("%b %d, %H:%M") if latest.created_at else "recently"
    if latest.from_account_id == account.id:
        # User spent or sent money
        if latest.biller_id:
            b = session.get(Biller, latest.biller_id)
            target = b.name if b else "Utility bill"
            desc_text = f"bill payment of ৳{latest.amount_bdt:,.2f} to {target}"
        elif latest.to_account_id:
            r_user = (
                session.query(User)
                .join(Account, Account.user_id == User.id)
                .filter(Account.id == latest.to_account_id)
                .one_or_none()
            )
            target = f"@{r_user.handle}" if r_user else "recipient"
            desc_text = f"sent ৳{latest.amount_bdt:,.2f} to {target}"
        else:
            desc_text = f"payment of ৳{latest.amount_bdt:,.2f}"
    else:
        # User received money
        s_user = None
        if latest.from_account_id:
            s_user = (
                session.query(User)
                .join(Account, Account.user_id == User.id)
                .filter(Account.id == latest.from_account_id)
                .one_or_none()
            )
        sender = f"from @{s_user.handle}" if s_user else ""
        desc_text = f"received ৳{latest.amount_bdt:,.2f} {sender}".strip()

    text = f"Boss, your latest transaction was on {date_str}: {desc_text}."
    return {
        "transaction_id": latest.id,
        "amount_bdt": latest.amount_bdt,
        "kind": latest.kind,
        "text": text,
    }


def get_sent_vs_received(session: Session, user_id: int) -> Dict[str, Any]:
    """Distinguish between sent and received money for the user."""
    user, account = _get_user_and_account(session, user_id)

    sent_txns = (
        session.query(Transaction)
        .filter(
            Transaction.from_account_id == account.id,
            Transaction.status == TxnStatus.COMPLETED.value,
        )
        .all()
    )
    sent_total = sum((t.amount_bdt for t in sent_txns), Decimal("0.00"))

    received_txns = (
        session.query(Transaction)
        .filter(
            Transaction.to_account_id == account.id,
            Transaction.status == TxnStatus.COMPLETED.value,
        )
        .all()
    )
    received_total = sum((t.amount_bdt for t in received_txns), Decimal("0.00"))

    text = (
        f"Boss, to date you have sent ৳{sent_total:,.2f} across {len(sent_txns)} transactions "
        f"and received ৳{received_total:,.2f} across {len(received_txns)} transactions."
    )
    return {
        "sent_total_bdt": sent_total,
        "sent_count": len(sent_txns),
        "received_total_bdt": received_total,
        "received_count": len(received_txns),
        "text": text,
    }


def get_money_requests_made(session: Session, user_id: int) -> Dict[str, Any]:
    """What money requests has the user made to others?"""
    user, _ = _get_user_and_account(session, user_id)

    reqs = (
        session.query(Request)
        .filter(Request.asker_user_id == user.id)
        .order_by(desc(Request.created_at))
        .limit(10)
        .all()
    )

    if not reqs:
        return {
            "requests": [],
            "text": "Boss, you haven't made any money requests to anyone yet.",
        }

    parts = []
    for r in reqs:
        payer = session.get(User, r.payer_user_id)
        payer_handle = f"@{payer.handle}" if payer else "unknown"
        parts.append(f"৳{r.amount_bdt:,.2f} from {payer_handle} ({r.status})")

    text = f"Boss, you have made {len(reqs)} money request(s): {', '.join(parts)}."
    return {"requests_count": len(reqs), "text": text}


def get_money_requests_received(session: Session, user_id: int) -> Dict[str, Any]:
    """What money requests has the user received from others?"""
    user, _ = _get_user_and_account(session, user_id)

    reqs = (
        session.query(Request)
        .filter(Request.payer_user_id == user.id)
        .order_by(desc(Request.created_at))
        .limit(10)
        .all()
    )

    if not reqs:
        return {
            "requests": [],
            "text": "Boss, you have no money requests from anyone.",
        }

    pending = [r for r in reqs if r.status == "pending"]
    parts = []
    for r in reqs:
        asker = session.get(User, r.asker_user_id)
        asker_handle = f"@{asker.handle}" if asker else "unknown"
        parts.append(f"৳{r.amount_bdt:,.2f} requested by {asker_handle} [{r.status}]")

    summary_lead = f"You have {len(pending)} pending request(s)" if pending else "All requests are resolved"
    text = f"Boss, {summary_lead}: {', '.join(parts)}."
    return {"total": len(reqs), "pending_count": len(pending), "text": text}


def get_recent_splits(session: Session, user_id: int) -> Dict[str, Any]:
    """Retrieve recent split-money transactions involving the user."""
    user, account = _get_user_and_account(session, user_id)

    # Splits initiated by user
    splits = (
        session.query(Split)
        .filter(Split.initiator_account_id == account.id)
        .order_by(desc(Split.created_at))
        .limit(5)
        .all()
    )

    # Split child transactions where user was a recipient
    child_txns = (
        session.query(Transaction)
        .filter(
            Transaction.to_account_id == account.id,
            Transaction.kind == "split_child",
            Transaction.status == TxnStatus.COMPLETED.value,
        )
        .order_by(desc(Transaction.created_at))
        .limit(5)
        .all()
    )

    if not splits and not child_txns:
        return {
            "splits": [],
            "text": "Boss, you have no recent split-money transactions recorded.",
        }

    parts = []
    for sp in splits:
        parts.append(f"Split initiated for ৳{sp.total_amount_bdt:,.2f} (৳{sp.per_amount_bdt:,.2f} each)")
    for c in child_txns:
        parts.append(f"Split share received: ৳{c.amount_bdt:,.2f}")

    text = f"Boss, your recent split-money activity: {'; '.join(parts)}."
    return {"splits_count": len(splits), "shares_received": len(child_txns), "text": text}


def get_spending_history(session: Session, user_id: int, limit: int = 5) -> Dict[str, Any]:
    """Summary of recent transactions and spending history."""
    user, account = _get_user_and_account(session, user_id)

    txns = (
        session.query(Transaction)
        .filter(
            or_(
                Transaction.from_account_id == account.id,
                Transaction.to_account_id == account.id,
            ),
            Transaction.status == TxnStatus.COMPLETED.value,
        )
        .order_by(desc(Transaction.created_at))
        .limit(limit)
        .all()
    )

    if not txns:
        return {
            "transactions": [],
            "balance_bdt": account.balance_bdt,
            "text": f"Boss, you have no transactions yet. Your current balance is ৳{account.balance_bdt:,.2f}.",
        }

    items = []
    for t in txns:
        date_str = t.created_at.strftime("%b %d") if t.created_at else ""
        if t.from_account_id == account.id:
            items.append(f"-৳{t.amount_bdt:,.2f} ({t.kind}) on {date_str}")
        else:
            items.append(f"+৳{t.amount_bdt:,.2f} ({t.kind}) on {date_str}")

    text = (
        f"Boss, your current balance is ৳{account.balance_bdt:,.2f}. "
        f"Last {len(items)} transactions: {', '.join(items)}."
    )
    return {
        "balance_bdt": account.balance_bdt,
        "items": items,
        "text": text,
    }


def get_budget_status(session: Session, user_id: int, festival: Optional[str] = None) -> Dict[str, Any]:
    """Check budget and savings goals for the user."""
    user, account = _get_user_and_account(session, user_id)

    q = session.query(SavingsGoal).filter(SavingsGoal.user_id == user.id)
    if festival:
        fest_clean = festival.strip().lower()
        q = q.filter(func.lower(SavingsGoal.festival) == fest_clean)

    goals = q.all()
    if not goals:
        if festival:
            return {
                "goals": [],
                "text": f"Boss, you don't have a budget set for '{festival}' yet. You can say 'set budget for {festival} 5000' to create one.",
            }
        return {
            "goals": [],
            "text": "Boss, you haven't set any budget or festival savings goals yet. Try 'set budget for eid 5000'.",
        }

    goal_summaries = []
    for g in goals:
        pct = (g.saved_amount_bdt / g.target_amount_bdt * 100) if g.target_amount_bdt else 0
        goal_summaries.append(
            f"{g.festival.capitalize()}: ৳{g.saved_amount_bdt:,.2f} saved of ৳{g.target_amount_bdt:,.2f} target ({pct:.1f}%)"
        )

    text = f"Boss, here is your budget status: {', '.join(goal_summaries)}."
    return {"goals_count": len(goals), "text": text}


def set_or_update_budget(session: Session, user_id: int, festival: str, target_bdt: Decimal) -> Dict[str, Any]:
    """Create or update a festival budget / savings goal."""
    user, account = _get_user_and_account(session, user_id)
    fest_clean = festival.strip().lower()

    goal = (
        session.query(SavingsGoal)
        .filter(SavingsGoal.user_id == user.id, func.lower(SavingsGoal.festival) == fest_clean)
        .one_or_none()
    )

    if goal is not None:
        goal.target_amount_bdt = target_bdt
        session.flush()
        action_verb = "updated"
    else:
        goal = SavingsGoal(
            user_id=user.id,
            festival=fest_clean,
            target_amount_bdt=target_bdt,
            saved_amount_bdt=Decimal("0.00"),
        )
        session.add(goal)
        session.flush()
        action_verb = "fixed"

    text = (
        f"Boss, I've {action_verb} your budget for '{goal.festival.capitalize()}' at "
        f"৳{target_bdt:,.2f}. Current saved: ৳{goal.saved_amount_bdt:,.2f}."
    )
    return {
        "festival": goal.festival,
        "target_amount_bdt": goal.target_amount_bdt,
        "saved_amount_bdt": goal.saved_amount_bdt,
        "text": text,
    }
