"""Admin Router — Dedicated FinTech Fraud Intelligence & Monitoring Platform.

All endpoints are strictly protected by `get_current_admin`.
Admin phone: "01926240062", password: "1234", name: "talukder".
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_
from sqlalchemy.orm import Session

from .. import config
from ..db import get_session
from ..models import (
    Account,
    AdminSession,
    AdminUser,
    Biller,
    FraudAlert,
    FraudAssessment,
    SecurityAuditLog,
    Split,
    Transaction,
    TxnStatus,
    TxnTag,
    User,
    UserSecurityPreference,
)
from ..services.admin_ai import AdminAIAssistant
from ..services.admin_auth import (
    create_admin_session,
    get_current_admin,
    hash_password,
    revoke_admin_token,
    verify_password,
)

log = logging.getLogger("wallet.admin_api")

router = APIRouter(prefix="/admin/api", tags=["admin"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---- Schemas ----------------------------------------------------------------
class AdminLoginRequest(BaseModel):
    phone: str = Field(..., description="Admin phone, e.g. 01926240062")
    password: str = Field(..., description="Admin password")


class AdminReviewAssessmentRequest(BaseModel):
    decision: str = Field(..., description="cleared | confirmed_fraud | investigating")
    notes: Optional[str] = None


class AdminUpdateAlertRequest(BaseModel):
    status: str = Field(..., description="new | investigating | resolved | false_positive")
    notes: Optional[str] = None
    assign_to_me: bool = False


class AdminUserActionRequest(BaseModel):
    reason: Optional[str] = None


class AdminAIQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)


# ---- Auth Endpoints ---------------------------------------------------------
@router.post("/auth/login")
def admin_login(req: AdminLoginRequest, session: Session = Depends(get_session)) -> dict:
    """Secure admin authentication.

    Accepts credentials: phone 01926240062, pass 1234.
    """
    admin = session.query(AdminUser).filter_by(phone=req.phone.strip()).one_or_none()
    if not admin or not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrative phone or credentials",
        )

    if not verify_password(req.password, admin.password_hash, admin.salt):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid administrative phone or credentials",
        )

    # Update last login
    admin.last_login_at = _utcnow()
    # Create high-entropy bearer session
    adm_session = create_admin_session(session, admin.id, duration_hours=48)

    # Log audit entry
    audit = SecurityAuditLog(
        admin_id=admin.id,
        action="admin_login",
        target_type="admin",
        target_id=str(admin.id),
        details_json=json.dumps({"phone": admin.phone, "display_name": admin.display_name}),
    )
    session.add(audit)
    session.commit()

    return {
        "token": adm_session.token,
        "expires_at": adm_session.expires_at.isoformat(),
        "admin": {
            "id": admin.id,
            "phone": admin.phone,
            "display_name": admin.display_name,
            "role": admin.role,
        },
    }


@router.get("/auth/me")
def admin_me(admin: AdminUser = Depends(get_current_admin)) -> dict:
    return {
        "id": admin.id,
        "phone": admin.phone,
        "display_name": admin.display_name,
        "role": admin.role,
        "last_login_at": admin.last_login_at.isoformat() if admin.last_login_at else None,
    }


@router.post("/auth/logout")
def admin_logout(
    authorization: Optional[str] = Header(None),
    x_admin_token: Optional[str] = Header(None),
    session: Session = Depends(get_session),
    admin: AdminUser = Depends(get_current_admin),
) -> dict:
    token = authorization or x_admin_token or ""
    revoke_admin_token(session, token)
    session.commit()
    return {"success": True, "message": "Admin session revoked"}


# ---- Section A: Overview Metrics & Visualizations ---------------------------
@router.get("/overview")
def get_overview(
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    """Provide real, live database metrics and time-series for the dashboard."""
    now = _utcnow()
    t30 = now - timedelta(days=30)
    t14 = now - timedelta(days=14)

    total_users = session.query(User).count()

    # Active users (sent or received completed txn in last 30d)
    active_user_ids = (
        session.query(Transaction.initiator_user_id)
        .filter(
            Transaction.status == TxnStatus.COMPLETED.value,
            Transaction.created_at >= t30,
        )
        .distinct()
        .all()
    )
    active_users = len(active_user_ids)

    total_txns = session.query(Transaction).count()
    completed_txns = (
        session.query(Transaction)
        .filter_by(status=TxnStatus.COMPLETED.value)
        .count()
    )
    failed_cancelled_txns = (
        session.query(Transaction)
        .filter(Transaction.status.in_([TxnStatus.CANCELLED.value, TxnStatus.DECLINED.value]))
        .count()
    )

    total_volume = (
        session.query(func.sum(Transaction.amount_bdt))
        .filter(Transaction.status == TxnStatus.COMPLETED.value)
        .scalar()
    ) or Decimal("0.00")

    # Fraud Assessment metrics
    total_assessments = session.query(FraudAssessment).count()
    suspicious_txns = (
        session.query(FraudAssessment)
        .filter(FraudAssessment.risk_level.in_(["medium", "high"]))
        .count()
    )
    high_risk_txns = (
        session.query(FraudAssessment)
        .filter(FraudAssessment.risk_level == "high")
        .count()
    )
    pending_investigations = (
        session.query(FraudAlert)
        .filter(FraudAlert.status.in_(["new", "investigating"]))
        .count()
    )

    # 1. Time-series: Daily transaction volume & count over last 14 days
    daily_stats = []
    for i in range(13, -1, -1):
        day_start = (now - timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        day_vol = (
            session.query(func.sum(Transaction.amount_bdt))
            .filter(
                Transaction.status == TxnStatus.COMPLETED.value,
                Transaction.created_at >= day_start,
                Transaction.created_at < day_end,
            )
            .scalar()
        ) or Decimal("0.00")

        day_count = (
            session.query(Transaction)
            .filter(
                Transaction.created_at >= day_start,
                Transaction.created_at < day_end,
            )
            .count()
        )

        day_alerts = (
            session.query(FraudAlert)
            .filter(
                FraudAlert.created_at >= day_start,
                FraudAlert.created_at < day_end,
            )
            .count()
        )

        daily_stats.append({
            "date": day_start.strftime("%b %d"),
            "volume_bdt": float(day_vol),
            "transactions": day_count,
            "alerts": day_alerts,
        })

    # 2. Risk Distribution
    low_risk = session.query(FraudAssessment).filter_by(risk_level="low").count()
    med_risk = session.query(FraudAssessment).filter_by(risk_level="medium").count()
    high_risk = session.query(FraudAssessment).filter_by(risk_level="high").count()

    risk_distribution = [
        {"name": "Low Risk", "count": low_risk, "color": "#10b981"},
        {"name": "Medium Risk", "count": med_risk, "color": "#f59e0b"},
        {"name": "High Risk", "count": high_risk, "color": "#ef4444"},
    ]

    return {
        "kpis": {
            "total_users": total_users,
            "active_users": max(active_users, 1),
            "total_transactions": total_txns,
            "completed_transactions": completed_txns,
            "failed_cancelled_transactions": failed_cancelled_txns,
            "total_volume_bdt": float(total_volume),
            "suspicious_transactions": suspicious_txns,
            "high_risk_transactions": high_risk_txns,
            "pending_investigations": pending_investigations,
        },
        "charts": {
            "activity_timeline": daily_stats,
            "risk_distribution": risk_distribution,
        },
    }


# ---- Section B: Fraud Intelligence -----------------------------------------
@router.get("/fraud/assessments")
def list_fraud_assessments(
    risk_level: Optional[str] = None,
    status: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(15, ge=1, le=100),
    search: Optional[str] = None,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    q = session.query(FraudAssessment)

    if risk_level:
        q = q.filter(FraudAssessment.risk_level == risk_level)
    if status:
        q = q.filter(FraudAssessment.status == status)

    if search:
        s_term = f"%{search}%"
        # Match user handle or txn id
        user_matches = session.query(User.id).filter(User.handle.ilike(s_term)).subquery()
        q = q.filter(
            or_(
                FraudAssessment.initiator_user_id.in_(user_matches),
                FraudAssessment.txn_id == (int(search) if search.isdigit() else -1),
            )
        )

    total = q.count()
    assessments = (
        q.order_by(desc(FraudAssessment.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for a in assessments:
        u = session.get(User, a.initiator_user_id)
        rec_u = session.get(User, a.recipient_user_id) if a.recipient_user_id else None
        items.append({
            "id": a.id,
            "txn_id": a.txn_id,
            "initiator": {"id": u.id, "handle": u.handle, "phone": u.phone} if u else None,
            "recipient": {"id": rec_u.id, "handle": rec_u.handle} if rec_u else None,
            "amount_bdt": float(a.amount_bdt),
            "risk_score": a.risk_score,
            "risk_level": a.risk_level,
            "status": a.status,
            "rules_triggered": json.loads(a.rules_triggered_json) if a.rules_triggered_json else [],
            "reasons": json.loads(a.reasons_json) if a.reasons_json else [],
            "latency_ms": a.latency_ms,
            "created_at": a.created_at.isoformat(),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/fraud/assessments/{assessment_id}")
def get_fraud_assessment(
    assessment_id: int,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    a = session.get(FraudAssessment, assessment_id)
    if not a:
        raise HTTPException(404, "Fraud assessment not found")

    u = session.get(User, a.initiator_user_id)
    rec_u = session.get(User, a.recipient_user_id) if a.recipient_user_id else None
    txn = session.get(Transaction, a.txn_id) if a.txn_id else None

    # Linked alert
    alert = session.query(FraudAlert).filter_by(assessment_id=a.id).first()

    return {
        "id": a.id,
        "txn_id": a.txn_id,
        "initiator": {
            "id": u.id,
            "handle": u.handle,
            "display_name": u.display_name,
            "phone": u.phone,
            "is_flagged": getattr(u, "is_flagged", False),
            "is_frozen": getattr(u, "is_frozen", False),
        } if u else None,
        "recipient": {
            "id": rec_u.id,
            "handle": rec_u.handle,
            "display_name": rec_u.display_name,
            "phone": rec_u.phone,
        } if rec_u else None,
        "amount_bdt": float(a.amount_bdt),
        "risk_score": a.risk_score,
        "risk_level": a.risk_level,
        "status": a.status,
        "rules_triggered": json.loads(a.rules_triggered_json) if a.rules_triggered_json else [],
        "reasons": json.loads(a.reasons_json) if a.reasons_json else [],
        "features": json.loads(a.features_json) if a.features_json else {},
        "model_version": a.model_version,
        "latency_ms": a.latency_ms,
        "created_at": a.created_at.isoformat(),
        "transaction": {
            "id": txn.id,
            "kind": txn.kind,
            "status": txn.status,
            "created_at": txn.created_at.isoformat(),
        } if txn else None,
        "linked_alert_id": alert.id if alert else None,
    }


@router.post("/fraud/assessments/{assessment_id}/review")
def review_fraud_assessment(
    assessment_id: int,
    req: AdminReviewAssessmentRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    a = session.get(FraudAssessment, assessment_id)
    if not a:
        raise HTTPException(404, "Fraud assessment not found")

    a.status = req.decision

    # If linked alert exists, update it as well
    alert = session.query(FraudAlert).filter_by(assessment_id=a.id).first()
    if alert:
        if req.decision == "cleared":
            alert.status = "resolved"
            alert.resolved_at = _utcnow()
            alert.resolved_by_admin_id = admin.id
        elif req.decision == "confirmed_fraud":
            alert.status = "investigating"
        if req.notes:
            alert.investigation_notes = (alert.investigation_notes or "") + f"\n[{admin.display_name}]: {req.notes}"

    audit = SecurityAuditLog(
        admin_id=admin.id,
        action="review_assessment",
        target_type="fraud_assessment",
        target_id=str(a.id),
        details_json=json.dumps({"decision": req.decision, "notes": req.notes}),
    )
    session.add(audit)
    session.commit()

    return {"success": True, "assessment_id": a.id, "new_status": a.status}


# ---- Section C: Transaction Monitoring -------------------------------------
@router.get("/transactions")
def list_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    risk_level: Optional[str] = None,
    search: Optional[str] = None,
    min_amount: Optional[float] = None,
    max_amount: Optional[float] = None,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    q = session.query(Transaction)

    if status:
        q = q.filter(Transaction.status == status)

    if min_amount is not None:
        q = q.filter(Transaction.amount_bdt >= Decimal(str(min_amount)))
    if max_amount is not None:
        q = q.filter(Transaction.amount_bdt <= Decimal(str(max_amount)))

    if search:
        s_term = f"%{search}%"
        user_ids = session.query(User.id).filter(
            or_(User.handle.ilike(s_term), User.phone.ilike(s_term))
        ).subquery()
        q = q.filter(
            or_(
                Transaction.initiator_user_id.in_(user_ids),
                Transaction.id == (int(search) if search.isdigit() else -1),
            )
        )

    # Filter by risk_level if requested
    if risk_level:
        matching_assessment_txns = (
            session.query(FraudAssessment.txn_id)
            .filter(FraudAssessment.risk_level == risk_level, FraudAssessment.txn_id != None)
            .subquery()
        )
        q = q.filter(Transaction.id.in_(matching_assessment_txns))

    total = q.count()
    txns = (
        q.order_by(desc(Transaction.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for t in txns:
        sender = session.get(User, t.initiator_user_id)
        recipient = None
        if t.to_account_id:
            recipient = (
                session.query(User)
                .join(Account)
                .filter(Account.id == t.to_account_id)
                .first()
            )
        elif t.biller_id:
            biller = session.get(Biller, t.biller_id)
            if biller:
                recipient = User(handle=f"biller:{biller.name}", display_name=biller.name, phone=biller.account_number)

        # Get attached fraud assessment
        assessment = (
            session.query(FraudAssessment)
            .filter_by(txn_id=t.id)
            .order_by(desc(FraudAssessment.id))
            .first()
        )

        items.append({
            "id": t.id,
            "kind": t.kind,
            "status": t.status,
            "amount_bdt": float(t.amount_bdt),
            "sender": {"id": sender.id, "handle": sender.handle, "phone": sender.phone} if sender else None,
            "recipient": {"id": recipient.id, "handle": recipient.handle, "phone": recipient.phone} if recipient else None,
            "note": t.note,
            "created_at": t.created_at.isoformat(),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "fraud_assessment": {
                "id": assessment.id,
                "risk_score": assessment.risk_score,
                "risk_level": assessment.risk_level,
                "status": assessment.status,
            } if assessment else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.get("/transactions/{txn_id}")
def get_transaction_details(
    txn_id: int,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    t = session.get(Transaction, txn_id)
    if not t:
        raise HTTPException(404, "Transaction not found")

    sender = session.get(User, t.initiator_user_id)
    recipient = None
    if t.to_account_id:
        recipient = session.query(User).join(Account).filter(Account.id == t.to_account_id).first()

    assessment = (
        session.query(FraudAssessment)
        .filter_by(txn_id=t.id)
        .order_by(desc(FraudAssessment.id))
        .first()
    )

    tags = session.query(TxnTag).filter_by(txn_id=t.id).all()

    return {
        "id": t.id,
        "idempotency_key": t.idempotency_key,
        "kind": t.kind,
        "status": t.status,
        "amount_bdt": float(t.amount_bdt),
        "note": t.note,
        "sender": {
            "id": sender.id,
            "handle": sender.handle,
            "display_name": sender.display_name,
            "phone": sender.phone,
        } if sender else None,
        "recipient": {
            "id": recipient.id,
            "handle": recipient.handle,
            "display_name": recipient.display_name,
            "phone": recipient.phone,
        } if recipient else None,
        "created_at": t.created_at.isoformat(),
        "expires_at": t.expires_at.isoformat() if t.expires_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "tags": [{"slug": tg.tag_slug, "source": tg.source} for tg in tags],
        "fraud_assessment": {
            "id": assessment.id,
            "risk_score": assessment.risk_score,
            "risk_level": assessment.risk_level,
            "status": assessment.status,
            "rules": json.loads(assessment.rules_triggered_json) if assessment.rules_triggered_json else [],
            "reasons": json.loads(assessment.reasons_json) if assessment.reasons_json else [],
        } if assessment else None,
    }


# ---- Section D: User Management ---------------------------------------------
@router.get("/users")
def list_users(
    search: Optional[str] = None,
    status_filter: Optional[str] = None,  # flagged, frozen, all
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    q = session.query(User)

    if search:
        s_term = f"%{search}%"
        q = q.filter(
            or_(User.handle.ilike(s_term), User.display_name.ilike(s_term), User.phone.ilike(s_term))
        )

    if status_filter == "flagged":
        q = q.filter(User.is_flagged == True)
    elif status_filter == "frozen":
        q = q.filter(User.is_frozen == True)

    users = q.order_by(User.id.asc()).all()

    items = []
    for u in users:
        acct = session.query(Account).filter_by(user_id=u.id).first()
        bal = float(acct.balance_bdt) if acct else 0.0

        alert_count = session.query(FraudAlert).filter_by(user_id=u.id).count()
        total_txns = session.query(Transaction).filter_by(initiator_user_id=u.id).count()

        items.append({
            "id": u.id,
            "handle": u.handle,
            "display_name": u.display_name,
            "phone": u.phone,
            "balance_bdt": bal,
            "total_transactions": total_txns,
            "fraud_alerts_count": alert_count,
            "face_enrolled": bool(u.face_embedding is not None),
            "is_flagged": getattr(u, "is_flagged", False),
            "is_frozen": getattr(u, "is_frozen", False),
            "created_at": u.created_at.isoformat(),
        })

    return {"users": items, "count": len(items)}


@router.post("/users/{user_id}/flag")
def toggle_user_flag(
    user_id: int,
    req: AdminUserActionRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    u = session.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")

    new_flag = not getattr(u, "is_flagged", False)
    u.is_flagged = new_flag

    audit = SecurityAuditLog(
        admin_id=admin.id,
        action="flag_user" if new_flag else "unflag_user",
        target_type="user",
        target_id=str(u.id),
        details_json=json.dumps({"is_flagged": new_flag, "reason": req.reason}),
    )
    session.add(audit)
    session.commit()

    return {"success": True, "user_id": u.id, "is_flagged": u.is_flagged}


@router.post("/users/{user_id}/freeze")
def toggle_user_freeze(
    user_id: int,
    req: AdminUserActionRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    u = session.get(User, user_id)
    if not u:
        raise HTTPException(404, "User not found")

    new_freeze = not getattr(u, "is_frozen", False)
    u.is_frozen = new_freeze

    audit = SecurityAuditLog(
        admin_id=admin.id,
        action="freeze_account" if new_freeze else "unfreeze_account",
        target_type="user",
        target_id=str(u.id),
        details_json=json.dumps({"is_frozen": new_freeze, "reason": req.reason}),
    )
    session.add(audit)
    session.commit()

    return {"success": True, "user_id": u.id, "is_frozen": u.is_frozen}


# ---- Section E: Fraud Alerts & Investigation -------------------------------
@router.get("/fraud/alerts")
def list_fraud_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    q = session.query(FraudAlert)
    if status:
        q = q.filter(FraudAlert.status == status)
    if severity:
        q = q.filter(FraudAlert.severity == severity)

    total = q.count()
    alerts = (
        q.order_by(desc(FraudAlert.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for a in alerts:
        u = session.get(User, a.user_id)
        txn = session.get(Transaction, a.txn_id) if a.txn_id else None
        assigned = session.get(AdminUser, a.assigned_to_admin_id) if a.assigned_to_admin_id else None

        items.append({
            "id": a.id,
            "assessment_id": a.assessment_id,
            "txn_id": a.txn_id,
            "user": {"id": u.id, "handle": u.handle, "phone": u.phone} if u else None,
            "alert_type": a.alert_type,
            "severity": a.severity,
            "status": a.status,
            "detection_reasons": a.detection_reasons,
            "investigation_notes": a.investigation_notes,
            "assigned_admin": assigned.display_name if assigned else None,
            "created_at": a.created_at.isoformat(),
            "updated_at": a.updated_at.isoformat(),
            "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
            "amount_bdt": float(txn.amount_bdt) if txn else None,
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": (total + page_size - 1) // page_size,
    }


@router.patch("/fraud/alerts/{alert_id}")
def update_fraud_alert(
    alert_id: int,
    req: AdminUpdateAlertRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    alert = session.get(FraudAlert, alert_id)
    if not alert:
        raise HTTPException(404, "Fraud alert not found")

    old_status = alert.status
    alert.status = req.status

    if req.assign_to_me:
        alert.assigned_to_admin_id = admin.id

    if req.status in ("resolved", "false_positive"):
        alert.resolved_at = _utcnow()
        alert.resolved_by_admin_id = admin.id

    if req.notes:
        existing = alert.investigation_notes or ""
        alert.investigation_notes = (existing + f"\n[{admin.display_name} - {_utcnow().strftime('%Y-%m-%d %H:%M')}]: {req.notes}").strip()

    audit = SecurityAuditLog(
        admin_id=admin.id,
        action="update_alert_status",
        target_type="fraud_alert",
        target_id=str(alert.id),
        details_json=json.dumps({"old_status": old_status, "new_status": req.status, "notes": req.notes}),
    )
    session.add(audit)
    session.commit()

    return {"success": True, "alert_id": alert.id, "status": alert.status}


@router.get("/audit-logs")
def list_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    q = session.query(SecurityAuditLog)
    total = q.count()
    logs = (
        q.order_by(desc(SecurityAuditLog.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = []
    for l in logs:
        adm = session.get(AdminUser, l.admin_id) if l.admin_id else None
        items.append({
            "id": l.id,
            "admin": adm.display_name if adm else "System",
            "action": l.action,
            "target_type": l.target_type,
            "target_id": l.target_id,
            "details": json.loads(l.details_json) if l.details_json else None,
            "created_at": l.created_at.isoformat(),
        })

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


# ---- Section F: System Monitoring -------------------------------------------
@router.get("/system/status")
def get_system_status(
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    """Live production telemetry: API, database, fraud engine, and AI infrastructure."""
    # Database stats
    total_txns = session.query(Transaction).count()
    total_users = session.query(User).count()
    total_assessments = session.query(FraudAssessment).count()
    avg_latency = session.query(func.avg(FraudAssessment.latency_ms)).scalar() or 0.0

    # Probe Ollama
    from ..main import _ollama_models, _probe_ollama, _probe_openrouter
    installed_ollama = _ollama_models()
    ollama_ok = _probe_ollama()
    openrouter_ok = _probe_openrouter()
    grok_configured = bool((config.GROK_API_KEY or "").strip())

    return {
        "service": "Wallet Platform Backend",
        "timestamp": _utcnow().isoformat(),
        "database": {
            "status": "connected",
            "dialect": "sqlite",
            "path": str(config.DB_PATH),
            "tables": {
                "users": total_users,
                "transactions": total_txns,
                "fraud_assessments": total_assessments,
            },
        },
        "fraud_detection_engine": {
            "status": "operational",
            "version": "rule_ml_hybrid_v1.0",
            "average_evaluation_latency_ms": round(float(avg_latency), 2),
            "active_rules_count": 7,
            "ml_anomaly_scorer": "active",
        },
        "ai_cascade_infrastructure": {
            "ollama_local": {
                "reachable": ollama_ok,
                "url": config.OLLAMA_URL,
                "installed_models": installed_ollama,
                "active_model": [m for m in config.LLM_CASCADE if m in installed_ollama],
            },
            "grok_xai": {
                "configured": grok_configured,
                "models": config.GROK_MODELS,
            },
            "openrouter_cloud": {
                "configured": openrouter_ok,
                "models": config.OPENROUTER_MODELS,
            },
            "deterministic_fallback": True,
        },
    }


# ---- Admin AI Assistant -----------------------------------------------------
@router.post("/ai/query")
def admin_ai_query(
    req: AdminAIQueryRequest,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict:
    """Live-database-grounded AI intelligence for administrators."""
    return AdminAIAssistant.answer_admin_query(session, req.query)
