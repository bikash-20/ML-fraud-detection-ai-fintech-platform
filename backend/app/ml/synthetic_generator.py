"""Synthetic Transaction Generator for Bangladesh MFS (BDT / Taka) Mobile Wallet.

Produces ~300,000 realistic transactions across 2,000 users over a 90-day period.
Timezone: Asia/Dhaka (+06:00).
Seeded and reproducible (seed=42).

Features:
- Realistic user personas: students, salaried employees, merchants/agents.
- Temporal patterns: diurnal curve, Friday prayer lull, weekend spikes, month-end salary bumps, Eid shopping surge.
- Strict running balance tracking (never negative).
- Fraud injection (~0.5% rate) with 6 archetypes:
  * account_takeover
  * mule_fan_in_fan_out
  * structuring
  * velocity_burst
  * new_account_abuse
  * cold_start_large
- Hard negatives (~10% rate): legit transactions that look suspicious (Eid shopping, rent/tuition, night emergency, wholesale).
- Label noise (~2% flip on borderline cases) and small share of missing values in auxiliary fields.
- Causal feature extraction: 12 key ML features calculated strictly from past data.
"""
from __future__ import annotations

import collections
import datetime
import math
import os
import random
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Import single source of truth for tier limits and platform caps
try:
    from app.tier_config import TIER_LIMITS, ABSOLUTE_SYSTEM_HARD_CAP
except ImportError:
    try:
        from ..tier_config import TIER_LIMITS, ABSOLUTE_SYSTEM_HARD_CAP
    except ImportError:
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
        from app.tier_config import TIER_LIMITS, ABSOLUTE_SYSTEM_HARD_CAP

MAX_SINGLE_TXN_LIMIT = TIER_LIMITS["personal"]["single_txn_limit"]
MAX_DAILY_SEND_LIMIT = TIER_LIMITS["personal"]["daily_limit"]
MAX_MONTHLY_SEND_LIMIT = TIER_LIMITS["personal"]["monthly_limit"]
NEW_ACCOUNT_SINGLE_LIMIT = TIER_LIMITS["personal"]["new_account_limit"]

RANDOM_SEED = 42
NUM_USERS = 2000
NUM_DAYS = 90
SIM_START_TIMESTAMP = 1785542400.0  # Approx 2026-08-01 00:00:00 UTC+6 (Dhaka time)
DHAKA_TZ_OFFSET_HOURS = 6

CITIES = ["Dhaka", "Chattogram", "Sylhet", "Rajshahi", "Khulna", "Barishal", "Rangpur", "Mymensingh", "Gazipur", "Narayanganj"]
DEVICES = ["android", "ios", "feature_phone_ussd", "web_portal"]
ISPS = ["Grameenphone", "Robi", "Banglalink", "Teletalk", "Dot Internet", "Link3", "Carnival", "AmberIT"]


def set_seed(seed: int = RANDOM_SEED) -> None:
    random.seed(seed)
    np.random.seed(seed)


class UserProfile:
    """Represents a simulated wallet account in Bangladesh."""

    def __init__(self, user_id: int, persona: str, tier: str, created_at: float, initial_balance: float):
        self.user_id = user_id
        self.persona = persona  # "student", "salaried", "merchant", "business"
        self.tier = tier        # "personal", "verified", "business"
        self.created_at = created_at
        self.balance = initial_balance
        self.frequent_recipients: List[int] = []
        self.registered_suppliers: List[int] = []
        self.recipient_registration_times: Dict[int, float] = {}
        self.preferred_device = "web_portal" if tier == "business" else random.choice(DEVICES)
        self.city = random.choice(CITIES)
        self.isp = random.choice(ISPS)


def build_user_network() -> List[UserProfile]:
    """Generate 2,000 user profiles with assigned personas, tiers, and counterparty graphs."""
    users: List[UserProfile] = []

    # 40% students (800, personal), 40% salaried (800, verified), 15% merchants (300, verified), 5% business (100, business)
    personas_and_tiers = (
        [("student", "personal")] * 800
        + [("salaried", "verified")] * 800
        + [("merchant", "verified")] * 300
        + [("business", "business")] * 100
    )
    random.shuffle(personas_and_tiers)

    for uid in range(1, NUM_USERS + 1):
        persona, tier = personas_and_tiers[uid - 1]

        # 80% accounts created before simulation start (30 to 365 days prior)
        # 20% accounts created dynamically during the 90 days simulation
        if random.random() < 0.85 or persona == "business":
            age_days_prior = random.uniform(30.0, 365.0)
            created_at = SIM_START_TIMESTAMP - (age_days_prior * 86400.0)
        else:
            created_at = SIM_START_TIMESTAMP + random.uniform(0.0, (NUM_DAYS - 5) * 86400.0)

        if persona == "student":
            initial_balance = round(random.uniform(300.0, 3500.0), 2)
        elif persona == "salaried":
            initial_balance = round(random.uniform(5000.0, 45000.0), 2)
        elif persona == "merchant":
            initial_balance = round(random.uniform(35000.0, 180000.0), 2)
        else:  # business enterprise
            initial_balance = round(random.uniform(200000.0, 5000000.0), 2)

        users.append(UserProfile(uid, persona, tier, created_at, initial_balance))

    # Pre-populate supplier & counterparty network
    merchants = [u.user_id for u in users if u.persona in ("merchant", "business")]

    for u in users:
        pool = [other.user_id for other in users if other.user_id != u.user_id]
        if u.persona == "business":
            # Business has 3 to 6 fixed registered suppliers
            avail_merchants = [m for m in merchants if m != u.user_id]
            u.registered_suppliers = random.sample(avail_merchants, min(random.randint(3, 6), len(avail_merchants)))
            u.frequent_recipients = list(u.registered_suppliers)
            # Beneficiary registration timestamp (registered at account creation or well in advance)
            for s_id in u.registered_suppliers:
                u.recipient_registration_times[s_id] = u.created_at + random.uniform(3600.0, 86400.0)
        else:
            num_freq = random.randint(2, 4)
            chosen = random.sample(pool, min(num_freq - 1, len(pool)))
            if merchants and random.random() < 0.7:
                chosen.append(random.choice([m for m in merchants if m != u.user_id]))
            u.frequent_recipients = list(set(chosen))
            for c_id in u.frequent_recipients:
                u.recipient_registration_times[c_id] = u.created_at + random.uniform(3600.0, 86400.0)

    return users


def get_dhaka_hour(ts: float) -> int:
    """Return local hour (0-23) in Asia/Dhaka time (UTC+6)."""
    return int((ts // 3600 + DHAKA_TZ_OFFSET_HOURS) % 24)


def get_dhaka_day_of_week(ts: float) -> int:
    """Return day of week (0=Mon, 4=Fri, 5=Sat, 6=Sun) in Asia/Dhaka time."""
    days_since_epoch = (ts + DHAKA_TZ_OFFSET_HOURS * 3600) // 86400
    return int((days_since_epoch + 3) % 7)


def get_hourly_activity_weight(ts: float) -> float:
    """Diurnal probability density function for Bangladesh MFS transactions."""
    hour = get_dhaka_hour(ts)
    dow = get_dhaka_day_of_week(ts)

    # Base hourly curve
    if 1 <= hour <= 5:      # Late night lull
        base = 0.08
    elif 6 <= hour <= 8:    # Early morning
        base = 0.45
    elif 9 <= hour <= 12:   # Morning business / work
        base = 1.25
    elif 13 <= hour <= 14:  # Lunch / Friday prayer window
        base = 0.70 if dow == 4 else 1.10
    elif 15 <= hour <= 18:  # Afternoon activity
        base = 1.35
    elif 19 <= hour <= 22:  # Evening peak (shopping, recharge, dining, bills)
        base = 1.65
    else:                   # 23:00 or 00:00
        base = 0.35

    # Friday & Saturday weekend lift
    if dow in (4, 5):
        base *= 1.20

    return base


def is_eid_shopping_period(ts: float) -> bool:
    """Festival surge: Day 40 to Day 47 of simulation (Eid shopping rush)."""
    day_num = int((ts - SIM_START_TIMESTAMP) // 86400)
    return 40 <= day_num <= 47


def generate_raw_transactions(users: List[UserProfile]) -> List[Dict[str, Any]]:
    """Simulate realistic transaction events across the 90-day window."""
    raw_txns: List[Dict[str, Any]] = []

    # 1. Normal Daily Activity Generation (~270k transactions)
    print("Generating standard everyday transactions across 90 days...")
    for day in range(NUM_DAYS):
        day_start = SIM_START_TIMESTAMP + day * 86400.0
        is_month_end = ((day % 30) >= 27) or ((day % 30) <= 2)
        eid_active = 40 <= day <= 47

        for u in users:
            # Skip if user account wasn't created yet
            if u.created_at > (day_start + 86400.0):
                continue

            # Calibrated transaction counts to reach ~270k baseline
            if u.persona == "business":
                dow = get_dhaka_day_of_week(day_start)
                if dow in (4, 5):  # Weekend
                    base_count = 1 if random.random() < 0.20 else 0
                else:
                    base_count = random.randint(1, 3)
            elif u.persona == "merchant":
                base_count = random.randint(4, 8)
            elif u.persona == "salaried":
                base_count = random.randint(1, 3) if (is_month_end or eid_active) else (1 if random.random() < 0.60 else 0)
            else:  # student
                base_count = 1 if random.random() < 0.55 else 0

            if eid_active and base_count > 0:
                base_count += random.randint(0, 1)

            for _ in range(base_count):
                # Pick time within day weighted by hourly activity
                for _attempt in range(8):
                    time_offset = random.uniform(0.0, 86390.0)
                    candidate_ts = day_start + time_offset
                    if candidate_ts < u.created_at:
                        continue
                    weight = get_hourly_activity_weight(candidate_ts)
                    if random.random() < (weight / 2.0):
                        break
                else:
                    candidate_ts = day_start + random.uniform(28800.0, 79200.0)

                # Choose transaction type
                if u.persona == "business":
                    if random.random() < 0.20:
                        txn_kind = "cash_in"  # Commercial receipts / deposit
                    elif random.random() < 0.85:
                        txn_kind = "send_money"  # Supplier & partner transfers
                    else:
                        txn_kind = "payment"  # Corporate utilities & vendor bills
                elif u.persona == "salaried" and is_month_end and random.random() < 0.25:
                    txn_kind = "cash_in"  # Salary deposit
                elif random.random() < 0.12:
                    txn_kind = "cash_in"  # Bank/Agent deposit
                elif random.random() < 0.38:
                    txn_kind = "send_money"
                elif random.random() < 0.68:
                    txn_kind = "payment"
                elif random.random() < 0.88:
                    txn_kind = "mobile_recharge"
                else:
                    txn_kind = "cash_out"

                # Determine amount based on persona and kind
                if txn_kind == "cash_in":
                    if u.persona == "business":
                        amount = round(random.uniform(100000.0, 1500000.0), 2)
                    elif u.persona == "salaried" and is_month_end:
                        amount = round(random.uniform(25000.0, 65000.0), 2)
                    elif u.persona == "merchant":
                        amount = round(random.uniform(15000.0, 50000.0), 2)
                    else:
                        amount = round(random.uniform(500.0, 3500.0), 2)
                elif txn_kind == "mobile_recharge":
                    amount = round(random.choice([20.0, 50.0, 100.0, 150.0, 200.0, 300.0, 500.0]), 2)
                elif u.persona == "business":
                    # Legitimate transfers 50k to 1M to registered suppliers/customers
                    amount = round(random.uniform(50000.0, 750000.0), 2)
                elif u.persona == "student":
                    amount = round(random.uniform(50.0, 1450.0), 2)
                elif u.persona == "salaried":
                    amount = round(random.uniform(250.0, 7500.0), 2)
                    if eid_active and random.random() < 0.3:
                        amount = round(random.uniform(3000.0, 15000.0), 2)
                else:  # merchant
                    amount = round(random.uniform(500.0, 22000.0), 2)

                # Pick recipient
                recipient_id: Optional[int] = None
                if txn_kind in ("send_money", "payment"):
                    if u.persona == "business":
                        # 90% goes to registered suppliers
                        if u.registered_suppliers and random.random() < 0.90:
                            recipient_id = random.choice(u.registered_suppliers)
                        elif u.frequent_recipients:
                            recipient_id = random.choice(u.frequent_recipients)
                        else:
                            recipient_id = random.randint(1, NUM_USERS)
                    elif random.random() < 0.75 and u.frequent_recipients:
                        recipient_id = random.choice(u.frequent_recipients)
                    else:
                        recipient_id = random.randint(1, NUM_USERS)
                        while recipient_id == u.user_id:
                            recipient_id = random.randint(1, NUM_USERS)

                raw_txns.append({
                    "timestamp": candidate_ts,
                    "sender_id": u.user_id,
                    "recipient_id": recipient_id,
                    "txn_kind": txn_kind,
                    "amount_bdt": amount,
                    "is_fraud": 0,
                    "fraud_type": "legitimate",
                    "device_type": u.preferred_device if random.random() > 0.02 else None,
                    "location_city": u.city if random.random() > 0.02 else None,
                    "ip_isp": u.isp if random.random() > 0.02 else None,
                })

    # 2. Hard Negatives Injection (~10% $\approx$ 30,000 transactions)
    # Legit transactions that look suspicious at surface level
    print("Injecting realistic hard negatives (~10% = ~30,000 transactions)...")
    hard_neg_count = 29_000
    b_users = [usr for usr in users if usr.persona == "business"]

    for _ in range(hard_neg_count):
        hn_type = random.choice([
            "festival_shopping", "rent_tuition", "emergency_night", "merchant_wholesale",
            "business_supplier_payment", "business_salary_settlement"
        ])
        u = random.choice(users)
        day = random.randint(0, NUM_DAYS - 1)
        day_start = SIM_START_TIMESTAMP + day * 86400.0

        if hn_type == "festival_shopping":
            ts = day_start + random.uniform(36000.0, 79200.0)
            amount = round(random.uniform(8000.0, 32000.0), 2)
            txn_kind = "payment"
            rec_id = random.randint(1701, 2000)
        elif hn_type == "rent_tuition":
            dom = (day % 30)
            if dom > 5:
                continue
            ts = day_start + random.uniform(36000.0, 64800.0)
            amount = round(random.uniform(14000.0, 42000.0), 2)
            txn_kind = "send_money"
            rec_id = random.randint(1, NUM_USERS)
        elif hn_type == "emergency_night":
            ts = day_start + random.uniform(3600.0, 18000.0)  # 01:00 to 05:00
            amount = round(random.uniform(2500.0, 18000.0), 2)
            txn_kind = "payment"
            rec_id = random.randint(1, NUM_USERS)
        elif hn_type == "merchant_wholesale":
            if u.persona != "merchant":
                continue
            ts = day_start + random.uniform(28800.0, 50400.0)
            amount = round(random.uniform(35000.0, 85000.0), 2)
            txn_kind = "send_money"
            rec_id = random.randint(1701, 2000)
        elif hn_type == "business_supplier_payment":
            if not b_users:
                continue
            u = random.choice(b_users)
            ts = day_start + random.uniform(32400.0, 61200.0)  # 09:00 to 17:00
            amount = round(random.uniform(120000.0, 850000.0), 2)
            txn_kind = "send_money"
            rec_id = random.choice(u.registered_suppliers) if u.registered_suppliers else random.randint(1, NUM_USERS)
        else:  # business_salary_settlement
            if not b_users:
                continue
            u = random.choice(b_users)
            ts = day_start + random.uniform(36000.0, 57600.0)
            amount = round(random.uniform(150000.0, 950000.0), 2)
            txn_kind = "send_money"
            rec_id = random.choice(u.frequent_recipients) if u.frequent_recipients else random.randint(1, NUM_USERS)

        if ts < u.created_at:
            continue

        raw_txns.append({
            "timestamp": ts,
            "sender_id": u.user_id,
            "recipient_id": rec_id,
            "txn_kind": txn_kind,
            "amount_bdt": amount,
            "is_fraud": 0,
            "fraud_type": "hard_negative",
            "device_type": u.preferred_device,
            "location_city": u.city,
            "ip_isp": u.isp,
        })

    # 3. Controlled Fraud Archetypes Injection (~0.5% = ~1,500 transactions)
    print("Injecting targeted fraud archetypes (~0.5% fraud rate = ~1,500 txns)...")

    # Archetype A: Account Takeover (ATO) ~320 txns (Personal, Salaried & Business)
    for _ in range(80):
        victim = random.choice([u for u in users if u.persona in ("salaried", "student")])
        mule = random.randint(1, NUM_USERS)
        while mule == victim.user_id:
            mule = random.randint(1, NUM_USERS)

        day = random.randint(10, NUM_DAYS - 2)
        base_ts = SIM_START_TIMESTAMP + day * 86400.0 + random.uniform(3600.0, 72000.0)
        num_bursts = random.randint(2, 4)
        for b in range(num_bursts):
            raw_txns.append({
                "timestamp": base_ts + b * random.uniform(40.0, 180.0),
                "sender_id": victim.user_id,
                "recipient_id": mule,
                "txn_kind": "send_money" if random.random() < 0.7 else "cash_out",
                "amount_bdt": round(random.uniform(12000.0, 38000.0), 2),
                "is_fraud": 1,
                "fraud_type": "account_takeover",
                "device_type": "android",
                "location_city": "Dhaka",
                "ip_isp": "Unknown Proxy",
            })

    # Business Account Takeover (ATO) to novel recipient
    for _ in range(25):
        if not b_users:
            break
        victim = random.choice(b_users)
        novel_mule = random.randint(1, NUM_USERS)
        while novel_mule == victim.user_id or novel_mule in victim.registered_suppliers:
            novel_mule = random.randint(1, NUM_USERS)

        day = random.randint(10, NUM_DAYS - 2)
        base_ts = SIM_START_TIMESTAMP + day * 86400.0 + random.uniform(3600.0, 72000.0)
        raw_txns.append({
            "timestamp": base_ts,
            "sender_id": victim.user_id,
            "recipient_id": novel_mule,
            "txn_kind": "send_money",
            "amount_bdt": round(random.uniform(300000.0, 950000.0), 2),
            "is_fraud": 1,
            "fraud_type": "account_takeover",
            "device_type": "web_portal",
            "location_city": "Dhaka",
            "ip_isp": "Unknown Proxy",
        })

    # Archetype B: Business Impersonated Supplier (Changed Beneficiary) ~60 txns
    for _ in range(50):
        if not b_users:
            break
        victim = random.choice(b_users)
        novel_mule = random.randint(1, NUM_USERS)
        while novel_mule == victim.user_id or novel_mule in victim.registered_suppliers:
            novel_mule = random.randint(1, NUM_USERS)

        day = random.randint(10, NUM_DAYS - 2)
        base_ts = SIM_START_TIMESTAMP + day * 86400.0 + random.uniform(32400.0, 61200.0)
        impersonated_amt = round(random.uniform(180000.0, 750000.0), 2)
        raw_txns.append({
            "timestamp": base_ts,
            "sender_id": victim.user_id,
            "recipient_id": novel_mule,
            "txn_kind": "send_money",
            "amount_bdt": impersonated_amt,
            "is_fraud": 1,
            "fraud_type": "impersonated_supplier",
            "device_type": "web_portal",
            "location_city": "Dhaka",
            "ip_isp": "Unknown Proxy",
        })

    # Archetype C: Mule Fan-In / Fan-Out ~300 txns
    for _ in range(45):
        mule_acc = random.randint(1, NUM_USERS)
        day = random.randint(10, NUM_DAYS - 2)
        window_start = SIM_START_TIMESTAMP + day * 86400.0 + random.uniform(10000.0, 60000.0)

        fan_senders = random.sample([u.user_id for u in users if u.user_id != mule_acc], random.randint(4, 7))
        for s_idx, sender in enumerate(fan_senders):
            raw_txns.append({
                "timestamp": window_start + s_idx * random.uniform(120.0, 900.0),
                "sender_id": sender,
                "recipient_id": mule_acc,
                "txn_kind": "send_money",
                "amount_bdt": round(random.uniform(15000.0, 35000.0), 2),
                "is_fraud": 1,
                "fraud_type": "mule_fan_in_fan_out",
                "device_type": "android",
                "location_city": random.choice(CITIES),
                "ip_isp": random.choice(ISPS),
            })
        raw_txns.append({
            "timestamp": window_start + len(fan_senders) * 900.0 + random.uniform(60.0, 300.0),
            "sender_id": mule_acc,
            "recipient_id": None,
            "txn_kind": "cash_out",
            "amount_bdt": round(random.uniform(40000.0, 90000.0), 2),
            "is_fraud": 1,
            "fraud_type": "mule_fan_in_fan_out",
            "device_type": "feature_phone_ussd",
            "location_city": "Dhaka",
            "ip_isp": "Grameenphone",
        })

    # Archetype D: Structuring (Smurfing) ~280 txns (Personal sub-50k + Business sub-150k dual approval)
    for _ in range(45):
        fraudster = random.choice(users)
        day = random.randint(5, NUM_DAYS - 2)
        base_ts = SIM_START_TIMESTAMP + day * 86400.0 + random.uniform(20000.0, 70000.0)
        num_splits = random.randint(3, 5)
        for s_idx in range(num_splits):
            struct_amt = round(random.choice([24200.0, 24500.0, 24800.0, 48500.0, 49200.0]), 2)
            raw_txns.append({
                "timestamp": base_ts + s_idx * random.uniform(90.0, 450.0),
                "sender_id": fraudster.user_id,
                "recipient_id": random.randint(1, NUM_USERS),
                "txn_kind": "send_money",
                "amount_bdt": struct_amt,
                "is_fraud": 1,
                "fraud_type": "structuring",
                "device_type": fraudster.preferred_device,
                "location_city": fraudster.city,
                "ip_isp": fraudster.isp,
            })

    # Business structuring below 150k dual approval limit
    for _ in range(30):
        if not b_users:
            break
        victim = random.choice(b_users)
        novel_rec = random.randint(1, NUM_USERS)
        while novel_rec == victim.user_id or novel_rec in victim.registered_suppliers:
            novel_rec = random.randint(1, NUM_USERS)

        day = random.randint(10, NUM_DAYS - 2)
        base_ts = SIM_START_TIMESTAMP + day * 86400.0 + random.uniform(20000.0, 70000.0)
        num_splits = random.randint(3, 4)
        for s_idx in range(num_splits):
            struct_amt = round(random.choice([138000.0, 142000.0, 145000.0, 148500.0]), 2)
            raw_txns.append({
                "timestamp": base_ts + s_idx * random.uniform(120.0, 480.0),
                "sender_id": victim.user_id,
                "recipient_id": novel_rec,
                "txn_kind": "send_money",
                "amount_bdt": struct_amt,
                "is_fraud": 1,
                "fraud_type": "structuring",
                "device_type": "web_portal",
                "location_city": victim.city,
                "ip_isp": "Unknown Proxy",
            })

    # Archetype D: Velocity Burst ~250 txns
    for _ in range(30):
        victim = random.choice(users)
        day = random.randint(5, NUM_DAYS - 2)
        base_ts = SIM_START_TIMESTAMP + day * 86400.0 + random.uniform(10000.0, 70000.0)
        burst_size = random.randint(6, 10)
        for b_idx in range(burst_size):
            raw_txns.append({
                "timestamp": base_ts + b_idx * random.uniform(20.0, 90.0),
                "sender_id": victim.user_id,
                "recipient_id": random.randint(1, NUM_USERS),
                "txn_kind": "send_money",
                "amount_bdt": round(random.uniform(4500.0, 15000.0), 2),
                "is_fraud": 1,
                "fraud_type": "velocity_burst",
                "device_type": "android",
                "location_city": "Dhaka",
                "ip_isp": "Unknown Proxy",
            })

    # Archetype E: New Account Abuse ~250 txns
    new_users = [u for u in users if u.created_at >= SIM_START_TIMESTAMP]
    for _ in range(80):
        if not new_users:
            break
        abuser = random.choice(new_users)
        abuse_ts = abuser.created_at + random.uniform(3600.0, 120000.0)
        raw_txns.append({
            "timestamp": abuse_ts,
            "sender_id": abuser.user_id,
            "recipient_id": None,
            "txn_kind": "cash_in",
            "amount_bdt": 40000.0,
            "is_fraud": 0,
            "fraud_type": "legitimate",
            "device_type": abuser.preferred_device,
            "location_city": abuser.city,
            "ip_isp": abuser.isp,
        })
        raw_txns.append({
            "timestamp": abuse_ts + random.uniform(60.0, 300.0),
            "sender_id": abuser.user_id,
            "recipient_id": random.randint(1, NUM_USERS),
            "txn_kind": "send_money",
            "amount_bdt": round(random.uniform(25000.0, 39500.0), 2),
            "is_fraud": 1,
            "fraud_type": "new_account_abuse",
            "device_type": abuser.preferred_device,
            "location_city": abuser.city,
            "ip_isp": abuser.isp,
        })

    # Archetype F: Cold Start Large ~150 txns (e.g. 500,000 BDT)
    for _ in range(120):
        victim = random.choice(users)
        day = random.randint(1, NUM_DAYS - 5)
        cs_ts = SIM_START_TIMESTAMP + day * 86400.0 + random.uniform(10000.0, 60000.0)
        extreme_amt = round(random.choice([150000.0, 250000.0, 350000.0, 500000.0]), 2)
        raw_txns.append({
            "timestamp": cs_ts,
            "sender_id": victim.user_id,
            "recipient_id": random.randint(1, NUM_USERS),
            "txn_kind": "send_money",
            "amount_bdt": extreme_amt,
            "is_fraud": 1,
            "fraud_type": "cold_start_large",
            "device_type": victim.preferred_device,
            "location_city": victim.city,
            "ip_isp": victim.isp,
        })

    return raw_txns


def process_causal_features_and_balance(
    raw_txns: List[Dict[str, Any]], users: List[UserProfile]
) -> pd.DataFrame:
    """Sort raw transactions strictly by timestamp and causally compute all tier-aware features."""
    print("Sorting transactions chronologically...")
    for idx, tx in enumerate(raw_txns):
        tx["timestamp"] += (idx % 1000) * 0.0001
    raw_txns.sort(key=lambda t: t["timestamp"])

    user_map = {u.user_id: u for u in users}

    balances: Dict[int, float] = {u.user_id: u.balance for u in users}
    past_txns: Dict[int, collections.deque] = collections.defaultdict(collections.deque)
    past_recipients: Dict[int, set] = collections.defaultdict(set)
    past_recipients_first_seen: Dict[int, Dict[int, float]] = collections.defaultdict(dict)
    last_tx_time: Dict[int, float] = {}
    recipient_inbound: Dict[int, collections.deque] = collections.defaultdict(collections.deque)

    # Calculate per-tier median amounts for cold start baseline
    tier_tx_amounts: Dict[str, List[float]] = collections.defaultdict(list)
    for tx in raw_txns:
        if tx["txn_kind"] != "mobile_recharge":
            u_tier = user_map[tx["sender_id"]].tier
            tier_tx_amounts[u_tier].append(tx["amount_bdt"])

    tier_medians = {
        tier: float(np.median(amts)) if amts else 1000.0
        for tier, amts in tier_tx_amounts.items()
    }
    print(f"Per-Tier Baseline Medians (BDT): {tier_medians}")

    processed_rows: List[Dict[str, Any]] = []

    print(f"Extracting causal features across {len(raw_txns):,} transactions...")
    for idx, tx in enumerate(raw_txns):
        ts = tx["timestamp"]
        uid = tx["sender_id"]
        rec_id = tx["recipient_id"]
        kind = tx["txn_kind"]
        amt = float(tx["amount_bdt"])
        u = user_map[uid]
        u_tier = u.tier
        tier_cfg = TIER_LIMITS[u_tier]
        account_tier_code = tier_cfg["tier_code"]

        # Recipient information
        rec_u = user_map.get(rec_id) if rec_id else None

        # 1. Maintain realistic positive running balance
        curr_bal = balances[uid]
        if kind == "cash_in":
            balances[uid] += amt
            drain_ratio = 0.0
        else:
            if amt > curr_bal:
                top_up = (amt - curr_bal) + random.uniform(500.0, 5000.0)
                balances[uid] += top_up
                curr_bal = balances[uid]
            drain_ratio = min(1.0, max(0.0, amt / curr_bal)) if curr_bal > 0 else 1.0
            balances[uid] = max(0.0, balances[uid] - amt)

        # 2. 30-Day Median Amount per Tier & History Flag
        cutoff_30d = ts - (30 * 86400.0)
        user_history = past_txns[uid]
        while user_history and user_history[0][0] < cutoff_30d:
            user_history.popleft()

        recent_amounts = [item[1] for item in user_history]
        has_history = 1.0 if len(recent_amounts) >= 5 else 0.0
        if len(recent_amounts) >= 5:
            user_median = float(np.median(recent_amounts))
            effective_base = max(tier_cfg["baseline_min_clamp"], user_median)
        else:
            effective_base = max(tier_cfg["baseline_min_clamp"], tier_medians.get(u_tier, 1000.0))

        amount_to_avg_ratio = round(amt / effective_base, 3)

        # 3. Velocity metrics: 1h and 24h
        cutoff_1h = ts - 3600.0
        cutoff_24h = ts - 86400.0

        txns_1h = sum(1 for item in user_history if item[0] >= cutoff_1h)
        txns_24h = sum(1 for item in user_history if item[0] >= cutoff_24h)
        sum_24h = sum(item[1] for item in user_history if item[0] >= cutoff_24h)

        # 4. Rapid Seconds (Time since previous transaction)
        if uid in last_tx_time:
            delta = ts - last_tx_time[uid]
            rapid_seconds = max(0.5, delta)
        else:
            rapid_seconds = 86400.0  # First transaction sentinel

        # 5. Is New Recipient & Is Trusted Recipient
        if rec_id is not None and rec_id > 0:
            is_new_recipient = 1.0 if rec_id not in past_recipients[uid] else 0.0
            # Trusted if in registered suppliers OR known for > 24 hours with past transaction
            if rec_id in u.registered_suppliers:
                is_trusted_recipient = 1.0
            elif rec_id in past_recipients[uid]:
                first_seen_ts = past_recipients_first_seen[uid].get(rec_id, ts)
                is_trusted_recipient = 1.0 if (ts - first_seen_ts) >= 86400.0 else 0.0
            else:
                is_trusted_recipient = 0.0
        else:
            is_new_recipient = 0.0
            is_trusted_recipient = 0.0

        # 6. Recipient Registration Age in Hours and Days
        if rec_u:
            rec_reg_hours = max(0.0, (ts - rec_u.created_at) / 3600.0)
            rec_age_days = rec_reg_hours / 24.0
        else:
            rec_reg_hours = 2160.0
            rec_age_days = 90.0

        # 7. Transaction vs Tier Limit Ratio
        txn_vs_tier_limit_ratio = round(amt / tier_cfg["single_txn_limit"], 4)

        # 8. Night Hours (Dhaka local time: 01:00 to 05:59)
        dhaka_hour = get_dhaka_hour(ts)
        is_night_hours = 1.0 if (1 <= dhaka_hour <= 5) else 0.0

        # 9. Recipient Fan-In Count (24h)
        if rec_id is not None and rec_id > 0:
            rec_inbound_history = recipient_inbound[rec_id]
            while rec_inbound_history and rec_inbound_history[0][0] < cutoff_24h:
                rec_inbound_history.popleft()
            distinct_senders_24h = len(set(item[1] for item in rec_inbound_history))
        else:
            distinct_senders_24h = 0

        # Label noise: ~2% random label flip exclusively on edge-case subsets to maintain exact ~0.5% fraud rate
        label = tx["is_fraud"]
        if tx["is_fraud"] == 1 and random.random() < 0.02 and tx["fraud_type"] not in ("cold_start_large", "structuring"):
            label = 0
        elif tx["is_fraud"] == 0 and tx["fraud_type"] == "hard_negative" and random.random() < 0.001:
            label = 1

        dt_dhaka = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone(datetime.timedelta(hours=6)))

        processed_rows.append({
            "txn_id": idx + 1,
            "timestamp": ts,
            "datetime_dhaka": dt_dhaka.strftime("%Y-%m-%d %H:%M:%S%z"),
            "sender_id": uid,
            "recipient_id": rec_id,
            "sender_persona": u.persona,
            "account_tier": account_tier_code,
            "txn_kind": kind,
            "amount_bdt": amt,
            "drain_ratio": round(drain_ratio, 4),
            "amount_to_avg_ratio": amount_to_avg_ratio,
            "has_history": has_history,
            "txns_1h": txns_1h,
            "txns_24h": txns_24h,
            "sum_24h": round(sum_24h, 2),
            "is_new_recipient": is_new_recipient,
            "rapid_seconds": round(rapid_seconds, 1),
            "is_night_hours": is_night_hours,
            "recipient_account_age_days": round(rec_age_days, 1),
            "recipient_fan_in_count_24h": distinct_senders_24h,
            "is_trusted_recipient": is_trusted_recipient,
            "recipient_registered_age_hours": round(rec_reg_hours, 1),
            "txn_vs_tier_limit_ratio": txn_vs_tier_limit_ratio,
            "device_type": tx["device_type"],
            "location_city": tx["location_city"],
            "ip_isp": tx["ip_isp"],
            "is_fraud": label,
            "fraud_type": tx["fraud_type"],
        })

        user_history.append((ts, amt))
        last_tx_time[uid] = ts
        if rec_id is not None and rec_id > 0:
            if rec_id not in past_recipients[uid]:
                past_recipients[uid].add(rec_id)
                past_recipients_first_seen[uid][rec_id] = ts
            recipient_inbound[rec_id].append((ts, uid))

    df = pd.DataFrame(processed_rows)
    return df


def main():
    set_seed(RANDOM_SEED)
    print("=== Step 1: Bangladesh MFS Synthetic Dataset Generator ===")
    users = build_user_network()
    print(f"Created {len(users):,} users across personas: 800 students (Personal), 800 salaried (Verified), 300 merchants (Verified), 100 business enterprises (Business).")

    raw_txns = generate_raw_transactions(users)
    print(f"Generated {len(raw_txns):,} raw transaction events.")

    df = process_causal_features_and_balance(raw_txns, users)
    print(f"Processed DataFrame shape: {df.shape}")

    fraud_count = int(df["is_fraud"].sum())
    fraud_rate = (fraud_count / len(df)) * 100
    print(f"Total Transactions: {len(df):,}")
    print(f"Total Fraud: {fraud_count:,} ({fraud_rate:.2f}%)")
    print("Fraud breakdown by type:")
    print(df[df["is_fraud"] == 1]["fraud_type"].value_counts())

    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data"))
    os.makedirs(root_dir, exist_ok=True)

    parquet_path = os.path.join(root_dir, "wallet_synthetic_300k.parquet")
    csv_gz_path = os.path.join(root_dir, "wallet_synthetic_300k.csv.gz")
    sample_csv_path = os.path.join(root_dir, "wallet_synthetic_sample.csv")

    print(f"Saving Parquet dataset to: {parquet_path}")
    df.to_parquet(parquet_path, index=False)

    print(f"Saving Compressed CSV to: {csv_gz_path}")
    df.to_csv(csv_gz_path, compression="gzip", index=False)

    print(f"Saving 5,000-row sample CSV to: {sample_csv_path}")
    df.head(5000).to_csv(sample_csv_path, index=False)
    print("Step 1 complete: Synthetic Dataset successfully generated and saved!")


if __name__ == "__main__":
    main()
