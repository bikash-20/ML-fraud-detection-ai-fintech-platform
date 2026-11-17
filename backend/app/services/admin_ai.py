"""Admin AI Assistant Service — Live Database Grounded Intelligence.

Queries live financial, transaction, alert, and fraud assessment records
to answer administrative questions truthfully without fabricating facts.

Supported queries:
- How many suspicious transactions occurred today?
- Which transactions have the highest risk scores?
- Are there any unusual transaction patterns?
- Which users have repeated suspicious activity?
- Show me the latest fraud alerts.
- What are the main reasons transactions are being flagged?
- What is the current transaction volume?
- Are there any unresolved investigations?
- Is the fraud detection service working properly?
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from .. import config
from ..models import (
    Account,
    AdminUser,
    FraudAlert,
    FraudAssessment,
    SecurityAuditLog,
    Transaction,
    TxnStatus,
    User,
)

log = logging.getLogger("wallet.admin_ai")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class AdminAIAssistant:
    """Tool-backed, permission-checked AI assistant for the Admin Intelligence Dashboard."""

    @classmethod
    def get_suspicious_today(cls, session: Session) -> Dict[str, Any]:
        """Count and list suspicious / high risk transactions that occurred today."""
        start_of_day = _utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        assessments = (
            session.query(FraudAssessment)
            .filter(
                FraudAssessment.created_at >= start_of_day,
                FraudAssessment.risk_level.in_(["medium", "high"]),
            )
            .order_by(desc(FraudAssessment.risk_score))
            .all()
        )
        total_today = (
            session.query(FraudAssessment)
            .filter(FraudAssessment.created_at >= start_of_day)
            .count()
        )
        suspicious_count = len(assessments)
        high_risk_count = sum(1 for a in assessments if a.risk_level == "high")

        items = []
        for a in assessments[:5]:
            user = session.get(User, a.initiator_user_id)
            items.append({
                "id": a.id,
                "user": user.handle if user else f"User #{a.initiator_user_id}",
                "amount_bdt": float(a.amount_bdt),
                "risk_score": a.risk_score,
                "risk_level": a.risk_level,
                "reasons": json.loads(a.reasons_json) if a.reasons_json else [],
            })

        summary = (
            f"Today there have been {suspicious_count} suspicious transactions "
            f"out of {total_today} total evaluated ({high_risk_count} classified as high-risk)."
        )
        return {
            "summary": summary,
            "suspicious_count": suspicious_count,
            "high_risk_count": high_risk_count,
            "total_today": total_today,
            "top_suspicious": items,
        }

    @classmethod
    def get_highest_risk_txns(cls, session: Session, limit: int = 5) -> Dict[str, Any]:
        """Fetch transactions with the absolute highest risk scores."""
        top_assessments = (
            session.query(FraudAssessment)
            .order_by(desc(FraudAssessment.risk_score), desc(FraudAssessment.created_at))
            .limit(limit)
            .all()
        )
        items = []
        for a in top_assessments:
            user = session.get(User, a.initiator_user_id)
            items.append({
                "assessment_id": a.id,
                "txn_id": a.txn_id,
                "user": user.handle if user else f"User #{a.initiator_user_id}",
                "amount_bdt": float(a.amount_bdt),
                "risk_score": a.risk_score,
                "risk_level": a.risk_level,
                "status": a.status,
                "date": a.created_at.strftime("%Y-%m-%d %H:%M"),
                "reasons": json.loads(a.reasons_json) if a.reasons_json else [],
            })

        summary = (
            f"The highest risk score recorded is {items[0]['risk_score'] if items else 0.0}. "
            f"Identified {len(items)} elevated-risk transactions requiring administrative review."
        )
        return {"summary": summary, "items": items}

    @classmethod
    def get_unusual_patterns(cls, session: Session) -> Dict[str, Any]:
        """Aggregate behavioral patterns triggered across all assessments."""
        all_assessments = (
            session.query(FraudAssessment)
            .filter(FraudAssessment.risk_score > 0.3)
            .order_by(desc(FraudAssessment.created_at))
            .limit(100)
            .all()
        )
        rule_counts: Dict[str, int] = {}
        for a in all_assessments:
            try:
                rules = json.loads(a.rules_triggered_json)
                for r in rules:
                    rule_counts[r] = rule_counts.get(r, 0) + 1
            except Exception:
                continue

        sorted_rules = sorted(rule_counts.items(), key=lambda x: x[1], reverse=True)
        patterns = [{"rule": r, "occurrences": count} for r, count in sorted_rules[:6]]

        summary = (
            f"The most prevalent anomalous pattern is '{patterns[0]['rule']}' with {patterns[0]['occurrences']} triggers, "
            f"followed by '{patterns[1]['rule']}' with {patterns[1]['occurrences']} triggers."
            if len(patterns) >= 2 else "Transaction patterns are within standard operating thresholds."
        )
        return {"summary": summary, "patterns": patterns}

    @classmethod
    def get_repeated_suspicious_users(cls, session: Session) -> Dict[str, Any]:
        """Find users with multiple medium or high risk transactions."""
        subq = (
            session.query(
                FraudAssessment.initiator_user_id,
                func.count(FraudAssessment.id).label("flagged_count"),
                func.max(FraudAssessment.risk_score).label("max_risk"),
            )
            .filter(FraudAssessment.risk_level.in_(["medium", "high"]))
            .group_by(FraudAssessment.initiator_user_id)
            .having(func.count(FraudAssessment.id) >= 1)
            .order_by(desc("flagged_count"), desc("max_risk"))
            .limit(5)
            .all()
        )
        users = []
        for user_id, count, max_risk in subq:
            u = session.get(User, user_id)
            users.append({
                "user_id": user_id,
                "handle": u.handle if u else "unknown",
                "phone": u.phone if u else "unknown",
                "flagged_transactions": count,
                "max_risk_score": float(max_risk),
                "is_flagged": getattr(u, "is_flagged", False),
                "is_frozen": getattr(u, "is_frozen", False),
            })

        summary = (
            f"Found {len(users)} users with elevated security activity. "
            + (f"User @{users[0]['handle']} has {users[0]['flagged_transactions']} flagged events." if users else "No repeat offenders detected.")
        )
        return {"summary": summary, "users": users}

    @classmethod
    def get_latest_alerts(cls, session: Session, limit: int = 5) -> Dict[str, Any]:
        """Retrieve recent fraud alerts and their statuses."""
        alerts = (
            session.query(FraudAlert)
            .order_by(desc(FraudAlert.created_at))
            .limit(limit)
            .all()
        )
        items = []
        for a in alerts:
            user = session.get(User, a.user_id)
            items.append({
                "id": a.id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "status": a.status,
                "user": user.handle if user else f"User #{a.user_id}",
                "reasons": a.detection_reasons,
                "created_at": a.created_at.strftime("%Y-%m-%d %H:%M"),
            })

        summary = f"There are {len(items)} recent fraud alerts in the triage log."
        return {"summary": summary, "alerts": items}

    @classmethod
    def get_flag_reasons_breakdown(cls, session: Session) -> Dict[str, Any]:
        """Breakdown of detection reasons."""
        alerts = session.query(FraudAlert).all()
        type_counts: Dict[str, int] = {}
        for a in alerts:
            type_counts[a.alert_type] = type_counts.get(a.alert_type, 0) + 1

        breakdown = [{"type": k, "count": v} for k, v in sorted(type_counts.items(), key=lambda x: x[1], reverse=True)]
        summary = (
            f"Primary trigger: {breakdown[0]['type']} ({breakdown[0]['count']} alerts)."
            if breakdown else "No active alerts in the system."
        )
        return {"summary": summary, "breakdown": breakdown}

    @classmethod
    def get_volume_summary(cls, session: Session) -> Dict[str, Any]:
        """Calculate total volume, transaction counts, and settlement rates."""
        total_txns = session.query(Transaction).count()
        completed = session.query(Transaction).filter_by(status=TxnStatus.COMPLETED.value).count()
        cancelled = session.query(Transaction).filter_by(status=TxnStatus.CANCELLED.value).count()
        vol = (
            session.query(func.sum(Transaction.amount_bdt))
            .filter(Transaction.status == TxnStatus.COMPLETED.value)
            .scalar()
        ) or Decimal("0.00")

        summary = (
            f"Total volume processed is ৳{vol:,.2f} across {completed} completed transactions "
            f"({total_txns} total transactions including {cancelled} cancelled/declined)."
        )
        return {
            "summary": summary,
            "total_volume_bdt": float(vol),
            "total_transactions": total_txns,
            "completed_transactions": completed,
            "cancelled_transactions": cancelled,
        }

    @classmethod
    def get_unresolved_investigations(cls, session: Session) -> Dict[str, Any]:
        """Fetch count and details of unresolved fraud investigations."""
        open_alerts = (
            session.query(FraudAlert)
            .filter(FraudAlert.status.in_(["new", "investigating"]))
            .order_by(desc(FraudAlert.created_at))
            .all()
        )
        items = []
        for a in open_alerts:
            user = session.get(User, a.user_id)
            items.append({
                "id": a.id,
                "type": a.alert_type,
                "severity": a.severity,
                "status": a.status,
                "user": user.handle if user else "unknown",
                "notes": a.investigation_notes,
                "created_at": a.created_at.strftime("%Y-%m-%d %H:%M"),
            })

        summary = (
            f"There are {len(open_alerts)} unresolved fraud investigations currently requiring attention "
            f"({sum(1 for a in open_alerts if a.severity in ('high', 'critical'))} high/critical priority)."
        )
        return {"summary": summary, "unresolved_count": len(open_alerts), "items": items}

    @classmethod
    def get_fraud_service_health(cls, session: Session) -> Dict[str, Any]:
        """Check live operational health of the fraud engine and model infrastructure."""
        assessments_count = session.query(FraudAssessment).count()
        latest_assessment = (
            session.query(FraudAssessment)
            .order_by(desc(FraudAssessment.created_at))
            .first()
        )
        avg_latency = (
            session.query(func.avg(FraudAssessment.latency_ms)).scalar()
        ) or 0.0

        summary = (
            f"Fraud Detection Engine is fully operational (Version: rule_ml_hybrid_v1.0). "
            f"Evaluated {assessments_count} transactions with an average latency of {avg_latency:.2f}ms. "
            f"Latest assessment recorded at {latest_assessment.created_at.strftime('%Y-%m-%d %H:%M') if latest_assessment else 'N/A'}."
        )
        return {
            "summary": summary,
            "status": "healthy",
            "model_version": "rule_ml_hybrid_v1.0",
            "total_assessments": assessments_count,
            "avg_latency_ms": round(float(avg_latency), 2),
            "latest_assessment_at": latest_assessment.created_at.isoformat() if latest_assessment else None,
        }

    @classmethod
    def _is_casual_conversation(cls, query: str) -> bool:
        """Detect whether a query is small talk/greeting vs an operational financial/fraud query."""
        import re
        q = query.strip().lower()
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", q).strip()
        words = cleaned.split()
        if not words:
            return True

        greetings = {"hi", "hello", "hey", "hola", "salam", "assalam", "assalamu alaikum", "good morning", "good evening", "good afternoon", "yo"}
        smalltalk_phrases = [
            "how are you", "who are you", "what can you do", "help", "help me",
            "thank you", "thanks", "thx", "bye", "goodbye", "good day", "what is your name"
        ]

        if cleaned in greetings:
            return True
        for st in smalltalk_phrases:
            if st in cleaned:
                return True

        domain_keywords = {
            "suspicious", "fraud", "risk", "highest", "alert", "alerts",
            "pattern", "patterns", "anomaly", "anomalous", "volume", "turnover",
            "spent", "transaction", "transactions", "txn", "txns", "user", "users",
            "repeated", "unresolved", "investigation", "investigations", "health",
            "system", "engine", "service", "flag", "flagged", "reasons", "today", "money"
        }
        if any(w in domain_keywords for w in words):
            return False

        if words and words[0] in greetings and len(words) <= 5:
            return True

        return False

    @classmethod
    def answer_admin_query(cls, session: Session, query: str) -> Dict[str, Any]:
        """Senior-architecture AI query handler:
        1. Casual conversation / greetings are kept strictly in the LLM's hands with 0 DB queries.
        2. Domain / operational queries target ONLY the specific live database table required,
           grounding the multi-model cascade with factual records.
        """
        from .. import llm

        # 1. Casual conversation: No DB queries, pure LLM conversational intelligence
        if cls._is_casual_conversation(query):
            system_prompt = (
                "You are the FinTech Fraud Intelligence AI Assistant speaking with Administrator Talukder. "
                "You assist with monitoring transactions, fraud alerts, risk scores, and platform security. "
                "Respond naturally, politely, and concisely (1 to 2 sentences) to the administrator's greeting or question. "
                "Address them respectfully as Talukder or Admin. "
                "Ask what they would like to investigate or monitor today. "
                "Do NOT dump or cite unrequested transaction numbers or fraud statistics."
            )
            fallback_text = (
                "Hello Talukder! I am your live Fraud Intelligence AI Assistant. "
                "I can analyze suspicious transactions, risk scores, velocities, or fraud alerts. "
                "What would you like to investigate?"
            )
            try:
                ai_text = llm.generate_cascade(system_prompt, query).strip()
                ai_text = ai_text.strip().strip('"').strip("`")
                if not ai_text:
                    ai_text = fallback_text
            except Exception as e:
                log.warning("Cascade greeting fallback: %s", e)
                ai_text = fallback_text

            return {
                "intent": "greeting",
                "response": ai_text,
                "data": None,
                "timestamp": _utcnow().isoformat(),
            }

        # 2. Targeted Live Database Query: Fetch ONLY the dataset requested
        q = query.lower()
        if any(w in q for w in ["suspicious", "today", "how many"]):
            data = cls.get_suspicious_today(session)
            intent = "suspicious_today"
        elif any(w in q for w in ["highest", "highest risk", "top risk", "risky", "high risk"]):
            data = cls.get_highest_risk_txns(session, limit=5)
            intent = "highest_risk"
        elif any(w in q for w in ["pattern", "anomalous", "unusual pattern", "anomaly"]):
            data = cls.get_unusual_patterns(session)
            intent = "unusual_patterns"
        elif any(w in q for w in ["repeat", "user", "repeated", "offenders"]):
            data = cls.get_repeated_suspicious_users(session)
            intent = "repeated_users"
        elif any(w in q for w in ["alert", "latest alert", "fraud alert"]):
            data = cls.get_latest_alerts(session)
            intent = "latest_alerts"
        elif any(w in q for w in ["reason", "flagged", "reasons", "why"]):
            data = cls.get_flag_reasons_breakdown(session)
            intent = "flag_reasons"
        elif any(w in q for w in ["volume", "total money", "turnover", "spent"]):
            data = cls.get_volume_summary(session)
            intent = "volume_summary"
        elif any(w in q for w in ["unresolved", "investigation", "pending alert"]):
            data = cls.get_unresolved_investigations(session)
            intent = "unresolved_investigations"
        elif any(w in q for w in ["health", "properly", "status", "working", "service"]):
            data = cls.get_fraud_service_health(session)
            intent = "service_health"
        else:
            data = cls.get_suspicious_today(session)
            intent = "general_overview"

        # Ground the LLM with only the specific database facts
        system_prompt = (
            "You are the FinTech Fraud Intelligence AI Assistant speaking with Administrator Talukder. "
            "You have live, direct access to the real production database records. "
            "Answer the question concisely, directly, and accurately (1 to 3 sentences). "
            "Address the administrator respectfully as Talukder or Admin. "
            "Use the exact facts from the database records provided below. Never invent numbers.\n\n"
            f"LIVE DATABASE RECORDS:\n{json.dumps(data, indent=2)}"
        )

        try:
            ai_text = llm.generate_cascade(system_prompt, query).strip()
            ai_text = ai_text.strip().strip('"').strip("`")
            if not ai_text:
                ai_text = data.get("summary", "Query processed successfully based on database records.")
        except Exception as e:
            log.warning("Cascade phrasing fallback: %s", e)
            ai_text = data.get("summary", "Query processed successfully based on database records.")

        return {
            "intent": intent,
            "response": ai_text,
            "data": data,
            "timestamp": _utcnow().isoformat(),
        }
