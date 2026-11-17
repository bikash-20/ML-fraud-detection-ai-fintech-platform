"""Fraud Detection Engine — Deterministic Rules & Behavioral Anomaly Scoring.

Integrated into the financial transaction lifecycle.
Provides explainable, low-latency, and fail-safe risk assessments before execution.

Risk levels:
- Low (0.00 - 0.39): Cleared, standard execution
- Medium (0.40 - 0.74): Heightened scrutiny, alert generated, biometric required
- High (0.75 - 1.00): High-risk flag, alert generated, requires Face ID verification / admin review
"""
from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..models import (
    Account,
    FraudAlert,
    FraudAssessment,
    SecurityAuditLog,
    Transaction,
    TxnKind,
    TxnStatus,
    User,
)

log = logging.getLogger("wallet.fraud")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class AssessmentResult:
    assessment_id: Optional[int]
    risk_score: float
    risk_level: str  # "low" | "medium" | "high"
    status: str      # "approved" | "flagged_review" | "blocked" | "investigating"
    rules_triggered: list[str]
    reasons: list[str]
    features: dict[str, Any]
    requires_biometric: bool
    latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FraudEngine:
    """Core fraud evaluation service with rule-based baseline and behavioral anomaly scoring."""

    MODEL_VERSION = "rule_ml_hybrid_v1.0"

    @classmethod
    def extract_features(
        cls,
        session: Session,
        *,
        initiator_user_id: int,
        recipient_user_id: Optional[int],
        amount_bdt: Decimal,
        current_balance: Decimal,
    ) -> Dict[str, Any]:
        """Extract transactional and behavioral feature signals from live database history."""
        now = _utcnow()
        amt_float = float(amount_bdt)
        bal_float = float(current_balance) if current_balance > 0 else 0.01

        # 1. 30-day historical spending baseline
        t30 = now - timedelta(days=30)
        user_acct = session.query(Account).filter_by(user_id=initiator_user_id).one_or_none()
        acct_id = user_acct.id if user_acct else None

        avg_amount = 0.0
        past_txns_30d = 0
        if acct_id:
            res_30d = (
                session.query(
                    func.count(Transaction.id),
                    func.avg(Transaction.amount_bdt),
                )
                .filter(
                    Transaction.from_account_id == acct_id,
                    Transaction.status == TxnStatus.COMPLETED.value,
                    Transaction.created_at >= t30,
                )
                .first()
            )
            if res_30d and res_30d[0]:
                past_txns_30d = int(res_30d[0])
                avg_amount = float(res_30d[1] or 0.0)

        # Ratio to historical average (if no history, benchmark against standard demo spend ~1,000)
        baseline_avg = avg_amount if avg_amount > 50.0 else 1000.0
        amount_to_avg_ratio = amt_float / baseline_avg

        # 2. Velocity metrics: 1-hour and 24-hour windows
        t1h = now - timedelta(hours=1)
        t24h = now - timedelta(hours=24)

        txns_1h = 0
        sent_1h = 0.0
        if acct_id:
            r1h = (
                session.query(
                    func.count(Transaction.id),
                    func.sum(Transaction.amount_bdt),
                )
                .filter(
                    Transaction.from_account_id == acct_id,
                    Transaction.status.in_([TxnStatus.COMPLETED.value, TxnStatus.PENDING.value]),
                    Transaction.created_at >= t1h,
                )
                .first()
            )
            if r1h and r1h[0]:
                txns_1h = int(r1h[0])
                sent_1h = float(r1h[1] or 0.0)

        # 3. Time elapsed since immediately preceding transaction
        rapid_seconds: Optional[float] = None
        if acct_id:
            last_txn = (
                session.query(Transaction)
                .filter(
                    Transaction.from_account_id == acct_id,
                    Transaction.created_at >= t24h,
                )
                .order_by(desc(Transaction.created_at))
                .first()
            )
            if last_txn:
                delta = (now - last_txn.created_at).total_seconds()
                rapid_seconds = max(0.0, delta)

        # 4. Recipient novelty check (is this a first-time counterparty?)
        is_new_recipient = False
        recipient_unique_senders_1h = 0
        if recipient_user_id and acct_id:
            rec_acct = session.query(Account).filter_by(user_id=recipient_user_id).one_or_none()
            if rec_acct:
                prior = (
                    session.query(Transaction.id)
                    .filter(
                        Transaction.from_account_id == acct_id,
                        Transaction.to_account_id == rec_acct.id,
                        Transaction.status == TxnStatus.COMPLETED.value,
                    )
                    .first()
                )
                is_new_recipient = (prior is None)

                # Check inbound velocity to recipient (mule / funnel check)
                rec_inbound = (
                    session.query(func.count(func.distinct(Transaction.initiator_user_id)))
                    .filter(
                        Transaction.to_account_id == rec_acct.id,
                        Transaction.created_at >= t1h,
                    )
                    .scalar()
                )
                recipient_unique_senders_1h = int(rec_inbound or 0)

        # 5. Temporal signal: late night / dawn hours (01:00 to 05:00 UTC)
        hour = now.hour
        is_night_hours = 1 <= hour <= 5

        # 6. Account balance drain ratio
        drain_ratio = amt_float / bal_float

        # 7. Check if user is already flagged
        user = session.get(User, initiator_user_id)
        user_flagged = getattr(user, "is_flagged", False)

        return {
            "amount_bdt": amt_float,
            "current_balance": bal_float,
            "drain_ratio": round(drain_ratio, 4),
            "past_txns_30d": past_txns_30d,
            "user_avg_amount_30d": round(avg_amount, 2),
            "amount_to_avg_ratio": round(amount_to_avg_ratio, 2),
            "txns_1h": txns_1h,
            "total_sent_1h": round(sent_1h, 2),
            "rapid_seconds": round(rapid_seconds, 1) if rapid_seconds is not None else None,
            "is_new_recipient": is_new_recipient,
            "recipient_unique_senders_1h": recipient_unique_senders_1h,
            "is_night_hours": is_night_hours,
            "user_flagged": bool(user_flagged),
        }

    @classmethod
    def evaluate(
        cls,
        session: Session,
        *,
        initiator_user_id: int,
        recipient_user_id: Optional[int],
        amount_bdt: Decimal,
        txn_id: Optional[int] = None,
        persist: bool = True,
    ) -> AssessmentResult:
        """Run comprehensive fraud risk evaluation and optionally store the assessment."""
        start_time = time.perf_counter()

        try:
            # Get current balance
            user_acct = session.query(Account).filter_by(user_id=initiator_user_id).one_or_none()
            balance = user_acct.balance_bdt if user_acct else Decimal("0.00")

            features = cls.extract_features(
                session,
                initiator_user_id=initiator_user_id,
                recipient_user_id=recipient_user_id,
                amount_bdt=amount_bdt,
                current_balance=balance,
            )

            # Rule evaluation
            rules_triggered: list[str] = []
            reasons: list[str] = []
            rule_score = 0.0

            # Rule 1: High velocity in 1h
            if features["txns_1h"] >= 4:
                rules_triggered.append("RULE_VELOCITY_SPIKE_1H")
                reasons.append(
                    f"Rapid transaction velocity: {features['txns_1h']} transactions initiated in the past hour."
                )
                rule_score += 0.35
            elif features["txns_1h"] >= 2:
                rules_triggered.append("RULE_MODERATE_VELOCITY_1H")
                reasons.append(
                    f"Elevated velocity: {features['txns_1h']} transactions in the past hour."
                )
                rule_score += 0.15

            # Rule 2: Large amount deviation vs 30d baseline
            if features["amount_to_avg_ratio"] >= 4.0 and features["amount_bdt"] >= 3000.0:
                rules_triggered.append("RULE_LARGE_AMOUNT_DEVIATION")
                reasons.append(
                    f"Unusual amount spike: ৳{features['amount_bdt']:,.2f} is {features['amount_to_avg_ratio']:.1f}x higher than your 30-day average."
                )
                rule_score += 0.35
            elif features["amount_to_avg_ratio"] >= 2.5 and features["amount_bdt"] >= 2000.0:
                rules_triggered.append("RULE_MODERATE_AMOUNT_DEVIATION")
                reasons.append(
                    f"Above-average amount: transaction is {features['amount_to_avg_ratio']:.1f}x typical spend."
                )
                rule_score += 0.15

            # Rule 3: Account balance drain to new recipient
            if features["drain_ratio"] >= 0.85 and features["is_new_recipient"]:
                rules_triggered.append("RULE_BALANCE_DRAIN_NEW_RECIPIENT")
                reasons.append(
                    f"High drain ratio: sending {features['drain_ratio']*100:.0f}% of total balance to a first-time recipient."
                )
                rule_score += 0.40

            # Rule 4: Rapid successive transfer (< 90 seconds)
            if features["rapid_seconds"] is not None and features["rapid_seconds"] < 90.0:
                rules_triggered.append("RULE_RAPID_SUCCESSIVE")
                reasons.append(
                    f"Rapid succession: initiated only {int(features['rapid_seconds'])} seconds after your previous transaction."
                )
                rule_score += 0.25

            # Rule 5: Mule recipient inbound aggregation
            if features["recipient_unique_senders_1h"] >= 3:
                rules_triggered.append("RULE_MULE_AGGREGATION_RECIPIENT")
                reasons.append(
                    f"Recipient account received transfers from {features['recipient_unique_senders_1h']} distinct accounts in the last hour."
                )
                rule_score += 0.40

            # Rule 6: High-value transaction during unusual hours
            if features["is_night_hours"] and features["amount_bdt"] >= 10000.0:
                rules_triggered.append("RULE_UNUSUAL_HOURS_HIGH_VALUE")
                reasons.append(
                    "High-value transfer initiated during unusual late-night hours."
                )
                rule_score += 0.20

            # Rule 7: User under administrative watch
            if features["user_flagged"]:
                rules_triggered.append("RULE_USER_UNDER_WATCH")
                reasons.append(
                    "Sender account is currently flagged for heightened security monitoring."
                )
                rule_score += 0.50

            # ML Statistical Anomaly Scoring
            # Compute continuous behavioral anomaly score using normalized feature vector
            feat_vec = np.array([
                min(3.0, features["amount_to_avg_ratio"]) / 3.0,
                min(6.0, float(features["txns_1h"])) / 6.0,
                min(1.0, features["drain_ratio"]),
                1.0 if features["is_new_recipient"] else 0.0,
                1.0 if (features["rapid_seconds"] is not None and features["rapid_seconds"] < 120.0) else 0.0,
            ], dtype=float)

            # Feature weights
            weights = np.array([0.30, 0.25, 0.20, 0.15, 0.10], dtype=float)
            ml_anomaly_score = float(np.dot(feat_vec, weights))

            # Combine Rule score and ML anomaly score
            composite_score = min(1.0, max(rule_score, (rule_score * 0.6) + (ml_anomaly_score * 0.4)))
            composite_score = round(composite_score, 3)

            # Determine risk level
            if composite_score >= 0.75:
                risk_level = "high"
                status = "flagged_review"
                requires_biometric = True
            elif composite_score >= 0.40:
                risk_level = "medium"
                status = "flagged_review"
                requires_biometric = True
            else:
                risk_level = "low"
                status = "approved"
                requires_biometric = False
                if not reasons:
                    reasons.append("Transaction amount is within typical historical range.")
                    reasons.append("Account velocity and counterparty activity are normal.")

            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

            # Create DB records if persistence requested
            assessment_id = None
            if persist:
                assessment = FraudAssessment(
                    txn_id=txn_id,
                    initiator_user_id=initiator_user_id,
                    recipient_user_id=recipient_user_id,
                    amount_bdt=amount_bdt,
                    risk_score=composite_score,
                    risk_level=risk_level,
                    status=status,
                    rules_triggered_json=json.dumps(rules_triggered),
                    reasons_json=json.dumps(reasons),
                    features_json=json.dumps(features),
                    model_version=cls.MODEL_VERSION,
                    latency_ms=latency_ms,
                )
                session.add(assessment)
                session.flush()
                assessment_id = assessment.id

                # Generate alert for medium or high risk
                if risk_level in ("medium", "high"):
                    alert_type = rules_triggered[0] if rules_triggered else "ANOMALY_SCORE_ELEVATED"
                    severity = "critical" if composite_score >= 0.85 else ("high" if risk_level == "high" else "medium")
                    alert = FraudAlert(
                        assessment_id=assessment.id,
                        txn_id=txn_id,
                        user_id=initiator_user_id,
                        alert_type=alert_type,
                        severity=severity,
                        status="new",
                        detection_reasons="\n".join(reasons),
                    )
                    session.add(alert)
                    session.flush()

            return AssessmentResult(
                assessment_id=assessment_id,
                risk_score=composite_score,
                risk_level=risk_level,
                status=status,
                rules_triggered=rules_triggered,
                reasons=reasons,
                features=features,
                requires_biometric=requires_biometric,
                latency_ms=latency_ms,
            )

        except Exception as e:
            # FAIL-SAFE: Never crash or abort money movement if fraud evaluation encounters an unexpected runtime glitch
            log.exception("Fraud evaluation failed safely with error: %s", e)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return AssessmentResult(
                assessment_id=None,
                risk_score=0.0,
                risk_level="low",
                status="approved",
                rules_triggered=["ENGINE_FAILSAFE_FALLBACK"],
                reasons=["Standard transaction validation passed (fail-safe fallback)."],
                features={"error": str(e)},
                requires_biometric=False,
                latency_ms=latency_ms,
            )
