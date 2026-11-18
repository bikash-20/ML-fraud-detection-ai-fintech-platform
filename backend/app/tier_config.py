"""Centralized Source of Truth for Account Tiers, User Types, and Limits.

Configurable assumptions to verify against current Bangladesh Bank rules.
All modules (backend services, fraud engine, ML pipeline, API endpoints, and tests)
read tier definitions and regulatory caps strictly from this file.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# Supported User Types and Account Tiers
USER_TYPES: List[str] = ["student", "salaried", "shopkeeper", "agent", "business"]
ACCOUNT_TIERS: List[str] = ["personal", "verified", "business"]
KYC_STATUSES: List[str] = ["unverified", "verified"]

# Default tier mapping for user types (when KYC verified)
DEFAULT_TYPE_TIER_MAPPING: Dict[str, str] = {
    "student": "personal",
    "salaried": "verified",
    "shopkeeper": "verified",
    "agent": "verified",
    "business": "business",
}

# Configurable limits per tier.
# Labeled: Configurable assumptions to verify against current Bangladesh Bank rules.
TIER_LIMITS: Dict[str, Dict[str, Any]] = {
    "personal": {
        "tier_name": "Personal Tier",
        "description": "Standard consumer wallet for students and personal users",
        "single_txn_limit": 50_000.0,       # ৳50,000 BDT single transfer cap
        "daily_limit": 100_000.0,           # ৳100,000 BDT cumulative daily outbound limit
        "monthly_limit": 300_000.0,         # ৳300,000 BDT cumulative monthly limit
        "dual_approval_limit": None,         # Personal accounts cannot exceed single_txn_limit
        "new_account_limit": 10_000.0,      # Limit for accounts < 7 days old
        "baseline_min_clamp": 200.0,        # Minimum baseline divisor to avoid blowout
        "tier_code": 0,
    },
    "verified": {
        "tier_name": "Verified Tier",
        "description": "KYC-verified premier personal, salaried, and merchant accounts",
        "single_txn_limit": 100_000.0,      # ৳100,000 BDT single transfer cap
        "daily_limit": 250_000.0,           # ৳250,000 BDT cumulative daily limit
        "monthly_limit": 750_000.0,         # ৳750,000 BDT cumulative monthly limit
        "dual_approval_limit": None,
        "new_account_limit": 25_000.0,
        "baseline_min_clamp": 500.0,
        "tier_code": 1,
    },
    "business": {
        "tier_name": "Business Tier",
        "description": "Registered commercial enterprise and corporate accounts",
        "single_txn_limit": 1_000_000.0,    # ৳1,000,000 BDT single transfer cap
        "daily_limit": 5_000_000.0,         # ৳5,000,000 BDT cumulative daily limit
        "monthly_limit": 25_000_000.0,      # ৳25,000,000 BDT cumulative monthly limit
        "dual_approval_limit": 150_000.0,   # ৳150,000 BDT requires dual approval for new/unregistered beneficiaries
        "new_account_limit": 100_000.0,     # Limit for business accounts < 7 days old
        "baseline_min_clamp": 10_000.0,
        "tier_code": 2,
    },
}

# Configurable Agent-Specific Limits for licensed MFS Agents (liquidity rebalancing / cash-in / cash-out float management)
# Labeled: Configurable assumptions to verify against current Bangladesh Bank MFS Agent circulars.
AGENT_LIMITS: Dict[str, Any] = {
    "tier_name": "MFS Agent Tier",
    "description": "Authorized MFS agent banking wallet for liquidity float and customer cash-in/cash-out",
    "single_txn_limit": 300_000.0,       # ৳300,000 BDT single transfer cap for float rebalancing (vs 100k consumer)
    "daily_limit": 1_000_000.0,          # ৳1,000,000 BDT daily outbound limit
    "monthly_limit": 10_000_000.0,       # ৳10,000,000 BDT monthly limit
    "dual_approval_limit": None,
    "new_account_limit": 50_000.0,       # First 7 days cap
    "baseline_min_clamp": 2_000.0,
    "tier_code": 1,                      # Part of verified commercial tier
}

# Absolute platform ceiling across all tiers (configurable platform ceiling)
ABSOLUTE_SYSTEM_HARD_CAP = 5_000_000.0

# Tier fallback baselines used by the fraud engine when < 5 historical transactions exist
TIER_BASELINE_FALLBACKS: Dict[str, float] = {
    "personal": 1_000.0,
    "verified": 4_500.0,
    "agent": 15_000.0,
    "business": 250_000.0,
}


def get_effective_tier(account_tier: str, kyc_status: str) -> str:
    """Security rule:
    Business and agent tiers become active ONLY after an admin sets kyc_status = verified.
    Until then, the user is restricted to personal tier limits!
    """
    tier = (account_tier or "personal").lower()
    kyc = (kyc_status or "unverified").lower()
    if kyc != "verified" and tier in ("verified", "business"):
        return "personal"
    if tier not in TIER_LIMITS:
        return "personal"
    return tier


def get_effective_limits(
    account_tier: str,
    kyc_status: str,
    custom_single: Optional[float] = None,
    custom_daily: Optional[float] = None,
    user_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Calculate effective limits based on account tier, KYC status, user type, and optional custom limits."""
    eff_tier = get_effective_tier(account_tier, kyc_status)
    if (user_type or "").lower() == "agent" and (kyc_status or "").lower() == "verified":
        cfg = dict(AGENT_LIMITS)
    else:
        cfg = dict(TIER_LIMITS.get(eff_tier, TIER_LIMITS["personal"]))

    if custom_single is not None and custom_single > 0:
        cfg["single_txn_limit"] = min(float(custom_single), float(cfg["single_txn_limit"]))
    if custom_daily is not None and custom_daily > 0:
        cfg["daily_limit"] = min(float(custom_daily), float(cfg["daily_limit"]))

    cfg["effective_tier"] = eff_tier
    cfg["is_tier_restricted"] = (eff_tier != (account_tier or "personal").lower())
    return cfg
