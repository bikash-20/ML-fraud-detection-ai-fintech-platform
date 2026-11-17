"""Financial Intelligence and Financial Literacy Service.

Provides automated financial health scoring, category spend breakdown,
weekly velocity analysis, personalized budget recommendations, and
conversational financial literacy education.

All calculations are grounded in real double-entry ledger transactions
and authorized user records.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..models import Account, Biller, SavingsGoal, Transaction, TxnStatus, TxnTag, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_user_and_account(session: Session, user_id: int) -> tuple[User, Account]:
    user = session.get(User, user_id)
    if not user:
        raise ValueError(f"User {user_id} not found")
    account = session.query(Account).filter_by(user_id=user_id).one()
    return user, account


def calculate_financial_insights(session: Session, user_id: int) -> Dict[str, Any]:
    """Calculate comprehensive financial intelligence metrics for a user."""
    user, account = _get_user_and_account(session, user_id)
    now = _utcnow()
    since_30d = now - timedelta(days=30)
    since_7d = now - timedelta(days=7)

    # 1. Fetch completed debits (spending) for the last 30 days
    txns_30d = (
        session.query(Transaction)
        .filter(
            Transaction.from_account_id == account.id,
            Transaction.status == TxnStatus.COMPLETED.value,
            Transaction.created_at >= since_30d,
        )
        .all()
    )

    total_spent_30d = sum((t.amount_bdt for t in txns_30d), Decimal("0.00"))
    count_30d = len(txns_30d)

    # 7-day spending
    txns_7d = [t for t in txns_30d if t.created_at and t.created_at >= since_7d]
    total_spent_7d = sum((t.amount_bdt for t in txns_7d), Decimal("0.00"))
    count_7d = len(txns_7d)

    # Weekly velocity comparison (last 7 days vs 30-day weekly average)
    avg_weekly_spend = total_spent_30d / Decimal("4.28") if total_spent_30d > 0 else Decimal("0.00")
    if avg_weekly_spend > 0:
        velocity_pct = float(((total_spent_7d - avg_weekly_spend) / avg_weekly_spend) * Decimal("100"))
    else:
        velocity_pct = 0.0

    # 2. Spend breakdown by category using TxnTag
    txn_ids_30d = [t.id for t in txns_30d]
    category_totals: Dict[str, Decimal] = {}
    if txn_ids_30d:
        tags = (
            session.query(TxnTag.tag_slug, func.sum(Transaction.amount_bdt))
            .join(Transaction, Transaction.id == TxnTag.txn_id)
            .filter(
                TxnTag.txn_id.in_(txn_ids_30d),
                Transaction.from_account_id == account.id,
                Transaction.status == TxnStatus.COMPLETED.value,
            )
            .group_by(TxnTag.tag_slug)
            .all()
        )
        for slug, amt in tags:
            category_totals[slug] = Decimal(str(amt)) if amt is not None else Decimal("0.00")

    # If some transactions had no tag, group into 'other' or inspect biller
    tagged_sum = sum(category_totals.values(), Decimal("0.00"))
    if total_spent_30d > tagged_sum:
        category_totals["other"] = category_totals.get("other", Decimal("0.00")) + (total_spent_30d - tagged_sum)

    # Build category breakdown list with percentages
    category_breakdown = []
    for cat, amt in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
        pct = float((amt / total_spent_30d) * Decimal("100")) if total_spent_30d > 0 else 0.0
        category_breakdown.append({
            "category": cat,
            "amount_bdt": f"{amt:,.2f}",
            "percentage": round(pct, 1),
            "amount_raw": float(amt),
        })

    # 3. Savings Goals status
    goals = session.query(SavingsGoal).filter_by(user_id=user_id).all()
    total_saved = sum((g.saved_amount_bdt for g in goals), Decimal("0.00"))
    total_goal_target = sum((g.target_amount_bdt for g in goals), Decimal("0.00"))

    # 4. Compute Financial Health Score (0 - 100)
    # Factor A: Savings habit (0-35 points)
    # Ratio of saved amount vs total spending or goal completion
    savings_score = Decimal("15.0")
    if total_goal_target > 0:
        goal_ratio = min(Decimal("1.0"), total_saved / total_goal_target)
        savings_score = Decimal("15.0") + (goal_ratio * Decimal("20.0"))
    elif total_saved > 0:
        savings_score = Decimal("25.0")

    # Factor B: Spending Stability / Velocity (0-35 points)
    if velocity_pct <= -10:
        stability_score = Decimal("35.0") # Spending well under average
    elif velocity_pct <= 10:
        stability_score = Decimal("30.0") # Stable
    elif velocity_pct <= 30:
        stability_score = Decimal("20.0") # Moderately accelerated
    elif velocity_pct <= 60:
        stability_score = Decimal("12.0") # Fast spend
    else:
        stability_score = Decimal("5.0") # Burn rate warning

    # Factor C: Reserve Cushion (0-30 points)
    # Current wallet balance vs estimated monthly spend
    current_balance = account.balance_bdt
    if total_spent_30d > 0:
        cushion_months = current_balance / total_spent_30d
        if cushion_months >= Decimal("1.5"):
            cushion_score = Decimal("30.0")
        elif cushion_months >= Decimal("1.0"):
            cushion_score = Decimal("25.0")
        elif cushion_months >= Decimal("0.5"):
            cushion_score = Decimal("18.0")
        elif cushion_months >= Decimal("0.2"):
            cushion_score = Decimal("10.0")
        else:
            cushion_score = Decimal("5.0")
    else:
        cushion_score = Decimal("25.0") if current_balance > 1000 else Decimal("15.0")

    total_score = min(100, max(10, int(round(float(savings_score + stability_score + cushion_score)))))

    if total_score >= 85:
        rating = "Excellent"
        rating_color = "emerald"
    elif total_score >= 70:
        rating = "Good"
        rating_color = "teal"
    elif total_score >= 50:
        rating = "Moderate"
        rating_color = "amber"
    else:
        rating = "Needs Attention"
        rating_color = "rose"

    # 5. Generate Personalized Recommendations
    recommendations: List[Dict[str, Any]] = []

    # Recommendation: Top category spend optimization
    if category_breakdown:
        top_cat = category_breakdown[0]
        if top_cat["percentage"] >= 30 and top_cat["category"] not in ("rent", "savings"):
            rec_save = float(Decimal(str(top_cat["amount_raw"])) * Decimal("0.15"))
            recommendations.append({
                "id": "top_category_cap",
                "title": f"Optimize {top_cat['category'].capitalize()} Spending",
                "category": top_cat["category"],
                "priority": "high",
                "description": (
                    f"Your {top_cat['category']} spend reached ৳{top_cat['amount_bdt']} "
                    f"({top_cat['percentage']}% of monthly outflows). Trimming discretionary purchases by 15% "
                    f"would reserve approximately ৳{rec_save:,.2f} every month."
                ),
                "action_label": "Set Category Cap",
            })

    # Recommendation: Festival Savings Progress
    for g in goals:
        remaining = g.target_amount_bdt - g.saved_amount_bdt
        if remaining > 0:
            weekly_suggest = max(Decimal("200.00"), remaining / Decimal("4.0"))
            recommendations.append({
                "id": f"goal_{g.id}",
                "title": f"Pace {g.festival.capitalize()} Goal",
                "category": "savings",
                "priority": "medium",
                "description": (
                    f"You have saved ৳{g.saved_amount_bdt:,.2f} towards your ৳{g.target_amount_bdt:,.2f} {g.festival} target. "
                    f"Allocating ৳{weekly_suggest:,.2f} per week will ensure you hit your goal comfortably."
                ),
                "action_label": "Deposit to Goal",
            })

    # Recommendation: Spending Velocity Alert or Praise
    if velocity_pct > 25:
        recommendations.append({
            "id": "velocity_warning",
            "title": "Spending Velocity Elevated",
            "category": "budget",
            "priority": "high",
            "description": (
                f"Your 7-day spending (৳{total_spent_7d:,.2f}) is running {abs(round(velocity_pct))}% higher "
                f"than your 30-day weekly baseline (৳{avg_weekly_spend:,.2f}). Consider cooling non-essential transfers for 3-4 days."
            ),
            "action_label": "Review Spending",
        })
    elif velocity_pct < -15 and total_spent_30d > 0:
        recommendations.append({
            "id": "velocity_praise",
            "title": "Prudent Spending Pace",
            "category": "budget",
            "priority": "low",
            "description": (
                f"Great discipline! Your 7-day spend is {abs(round(velocity_pct))}% below your monthly weekly pace. "
                f"You have room to allocate extra surplus towards your emergency buffer."
            ),
            "action_label": "Add to Savings",
        })

    # Recommendation: Emergency Buffer
    target_buffer = max(Decimal("10000.00"), total_spent_30d)
    if current_balance < target_buffer:
        gap = target_buffer - current_balance
        recommendations.append({
            "id": "emergency_buffer",
            "title": "Strengthen Emergency Buffer",
            "category": "safety",
            "priority": "medium",
            "description": (
                f"A resilient wallet buffer covers at least 1 month of average spending (৳{target_buffer:,.2f}). "
                f"Your current balance is ৳{current_balance:,.2f}. Adding ৳{gap:,.2f} builds full financial peace of mind."
            ),
            "action_label": "Learn More",
        })

    # 6. Concise Conversational Summary Text for Voice/AI
    vel_text = (
        f"running {round(abs(velocity_pct))}% {'higher' if velocity_pct > 0 else 'lower'} than your average"
        if avg_weekly_spend > 0 else "steady"
    )
    voice_summary = (
        f"Boss, your financial health score is {total_score} out of 100 ({rating}). "
        f"Over the last 30 days you spent ৳{total_spent_30d:,.2f}, with weekly spending {vel_text}. "
    )
    if recommendations:
        voice_summary += f"Key recommendation: {recommendations[0]['title']} — {recommendations[0]['description']}"

    return {
        "user_id": user_id,
        "health_score": total_score,
        "health_rating": rating,
        "health_color": rating_color,
        "current_balance_bdt": f"{current_balance:,.2f}",
        "total_spent_30d_bdt": f"{total_spent_30d:,.2f}",
        "total_spent_7d_bdt": f"{total_spent_7d:,.2f}",
        "count_30d": count_30d,
        "count_7d": count_7d,
        "weekly_velocity_pct": round(velocity_pct, 1),
        "category_breakdown": category_breakdown,
        "recommendations": recommendations,
        "text": voice_summary,
    }


# Curated Plain-Language Financial Literacy Curriculum
LITERACY_TOPICS: Dict[str, Dict[str, Any]] = {
    "emergency_fund": {
        "slug": "emergency_fund",
        "title": "Emergency Fund (জরুরি তহবিল)",
        "summary": "Keep 3 to 6 months of living expenses liquid and untouched for medical, family, or employment surprises.",
        "details": (
            "An emergency fund is your first line of financial defense. In Bangladesh, unexpected medical costs, "
            "urgent family needs, or temporary income interruptions can happen. "
            "Rule of thumb: Calculate your minimum monthly expenses (rent, food, utilities, transport) and multiply by 3 to 6. "
            "Keep this fund in your primary liquid wallet or instant-access savings—never locked in high-risk investments."
        ),
        "bangla_summary": "জরুরি তহবিল হলো এমন সঞ্চয় যা অপ্রত্যাশিত চিকিৎসা বা পারিবারিক প্রয়োজনে ব্যবহার করা হয়। সাধারণত ৩ থেকে ৬ মাসের খরচের সমান টাকা আলাদা রাখা উচিত।",
        "key_takeaways": [
            "Start small: Aim for an initial ৳10,000 safety cushion.",
            "Separate from daily spending to resist impulse purchases.",
            "Replenish immediately whenever you withdraw from it.",
        ],
    },
    "50_30_20": {
        "slug": "50_30_20",
        "title": "The 50/30/20 Budgeting Rule (৫০/৩০/২০ নিয়ম)",
        "summary": "Allocate 50% to essential Needs, 30% to Wants, and 20% to Savings & Debt reduction.",
        "details": (
            "The 50/30/20 rule is an intuitive framework to manage monthly cash inflows:\n"
            "• 50% Needs: Groceries, rent, utility bills, tuition, medical prescriptions.\n"
            "• 30% Wants: Dining out with friends, streaming, gadgets, festival shopping.\n"
            "• 20% Savings: Emergency fund, festival goals (Eid/Puja), and debt payoff.\n"
            "Tracking your transaction tags in this wallet lets you see instantly if your 'Wants' are overtaking your goals."
        ),
        "bangla_summary": "৫০% মৌলিক চাহিদা (বাসা ভাড়া, খাবার, বিল), ৩০% শখ বা বিনোদন, এবং ২০% বাধ্যতামূলক সঞ্চয়ে ভাগ করে নেওয়া।",
        "key_takeaways": [
            "50% covers non-negotiable living essentials.",
            "30% gives guilt-free enjoyment without breaking finances.",
            "20% guarantees compounding long-term security.",
        ],
    },
    "fraud_prevention": {
        "slug": "fraud_prevention",
        "title": "FinTech Security & Fraud Prevention (নিরাপত্তা ও প্রতারণা প্রতিরোধ)",
        "summary": "Protect your money: Never disclose OTPs or PINs, verify recipient handles, and understand AI risk safeguards.",
        "details": (
            "FinTech scams exploit human trust rather than cryptographic math. Key security rules:\n"
            "• Zero Trust on Calls: No bank or wallet officer will EVER ask for your PIN, OTP, or face authorization.\n"
            "• Multi-Factor & Biometrics: Our platform automatically requests Face ID confirmation when an unusual transfer or high risk score is detected.\n"
            "• Handle Verification: Always confirm the recipient handle and phone before pressing confirm.\n"
            "• Velocity Limits: If you suspect unauthorized access, our security system automatically freezes high-velocity drains."
        ),
        "bangla_summary": "কখনও কারও সাথে পিন বা ওটিপি শেয়ার করবেন না। সন্দেহজনক লেনদেনের ক্ষেত্রে আমাদের এআই স্বয়ংক্রিয়ভাবে ফেস আইডি যাচাই করে সুরক্ষা দেয়।",
        "key_takeaways": [
            "Never share 4-digit PIN or SMS OTP with anyone, even support agents.",
            "High-risk transactions trigger biometric Face ID challenges automatically.",
            "Review transaction cards thoroughly before confirming.",
        ],
    },
    "double_entry": {
        "slug": "double_entry",
        "title": "Double-Entry Accounting & Ledger Integrity",
        "summary": "Every debit has an equal credit. Money never vanishes or creates out of thin air.",
        "details": (
            "This wallet is engineered on mathematical double-entry accounting principles. "
            "When you send ৳500 to a friend, your account is credited/debited with an exact corresponding journal entry. "
            "This guarantees that the total money in the ecosystem is preserved at all times, making fraudulent balance inflation mathematically impossible."
        ),
        "bangla_summary": "ডাবল এন্ট্রি লেজার নিশ্চিত করে যে এক অ্যাকাউন্ট থেকে টাকা কাটলে তা অবিকল অপর অ্যাকাউন্টে যোগ হয়। কোনো গড়মিল বা গায়েবি টাকা তৈরি হতে পারে না।",
        "key_takeaways": [
            "Atomic transaction guarantees: all transfers succeed completely or revert.",
            "Zero reconciliation errors or phantom balances.",
            "Full cryptographic auditability for peace of mind.",
        ],
    },
    "festival_savings": {
        "slug": "festival_savings",
        "title": "Festival & Goal-Based Savings (উৎসব ও লক্ষ্যভিত্তিক সঞ্চয়)",
        "summary": "Break down large upcoming holiday or event expenses into small weekly allocations.",
        "details": (
            "Festivals like Eid-ul-Fitr, Eid-ul-Adha, and Durga Puja bring clustered expenses (gifts, shopping, feasts, travel). "
            "Instead of draining your monthly salary all at once, set a Festival Savings Goal 2 to 3 months early. "
            "Saving ৳1,000 every week creates a ৳12,000 stress-free celebration fund."
        ),
        "bangla_summary": "ঈদ বা পূজার মতো উৎসবের খরচ আগে থেকেই ছোট ছোট কিস্তিতে জমিয়ে রাখলে শেষ মুহূর্তে আর্থিক চাপের মুখে পড়তে হয় না।",
        "key_takeaways": [
            "Create dedicated goals for Eid, Puja, or travel.",
            "Pace your contributions evenly week by week.",
            "Keep festival funds quarantined from everyday spending.",
        ],
    },
}


def get_financial_literacy_guide(topic: Optional[str] = None) -> Dict[str, Any]:
    """Retrieve financial literacy curriculum by topic or return index."""
    if topic:
        normalized = topic.strip().lower()
        # Direct match or alias
        if normalized in LITERACY_TOPICS:
            item = LITERACY_TOPICS[normalized]
        elif "50" in normalized or "budget" in normalized or "rule" in normalized:
            item = LITERACY_TOPICS["50_30_20"]
        elif "emergency" in normalized or "fund" in normalized or "জরুরি" in normalized:
            item = LITERACY_TOPICS["emergency_fund"]
        elif "fraud" in normalized or "scam" in normalized or "safety" in normalized or "security" in normalized or "প্রতারণা" in normalized:
            item = LITERACY_TOPICS["fraud_prevention"]
        elif "ledger" in normalized or "double" in normalized or "entry" in normalized:
            item = LITERACY_TOPICS["double_entry"]
        elif "festival" in normalized or "eid" in normalized or "puja" in normalized or "উৎসব" in normalized:
            item = LITERACY_TOPICS["festival_savings"]
        else:
            item = LITERACY_TOPICS["50_30_20"]

        return {
            "topic": item["slug"],
            "title": item["title"],
            "summary": item["summary"],
            "details": item["details"],
            "bangla_summary": item["bangla_summary"],
            "key_takeaways": item["key_takeaways"],
            "text": f"Boss, here is financial guidance on {item['title']}: {item['summary']} {item['details']}",
        }

    # Return overview list
    overview = [
        {
            "slug": v["slug"],
            "title": v["title"],
            "summary": v["summary"],
            "bangla_summary": v["bangla_summary"],
        }
        for v in LITERACY_TOPICS.values()
    ]
    summary_text = (
        "Boss, I can guide you on key financial topics: "
        "1. The 50/30/20 Budgeting Rule. "
        "2. Building a 3-month Emergency Fund. "
        "3. FinTech Security and Fraud Prevention. "
        "4. Double-Entry Ledger Integrity. "
        "5. Festival Savings Planning. Ask me about any of these!"
    )
    return {
        "topics": overview,
        "text": summary_text,
    }
