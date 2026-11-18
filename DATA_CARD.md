# Dataset Card: Bangladesh MFS Wallet Fraud Intelligence Synthetic Dataset

> **Status**: Prototype validated on synthetic data.
> **Scope**: Research, architecture prototyping, and offline benchmark validation.

---

## 1. Overview & Dataset Summary

| Attribute | Specification |
| :--- | :--- |
| **Dataset Name** | `wallet_synthetic_300k` |
| **Context** | Bangladesh Mobile Financial Services (MFS) — bKash / Nagad / Upay tier paradigm |
| **Total Transactions** | 299,420 |
| **Unique Users** | 2,000 |
| **Time Span** | 90 days (Asia/Dhaka Timezone, UTC+6) |
| **Currency** | Bangladeshi Taka (BDT / ৳) |
| **Fraud Cases** | 1,331 (0.44% base rate) |
| **Hard Negatives** | 29,000 (~9.7% legitimate high-velocity / high-amount transactions) |
| **Label Noise** | ~2.0% randomized label flip to simulate human audit errors |
| **Storage Formats** | Apache Parquet (`data/wallet_synthetic_300k.parquet`), Gzipped CSV (`data/wallet_synthetic_300k.csv.gz`), Sample CSV (`data/wallet_synthetic_sample.csv`) |
| **Generator Script** | `backend/app/ml/synthetic_generator.py` (Seeded: `42`, deterministic & reproducible) |

---

## 2. Configurable Account Tiers & Regulatory Assumptions

> [!NOTE]
> All limits and ceilings below are **configurable assumptions to verify against current Bangladesh Bank circulars** (such as PSD Circulars on MFS transaction ceilings, agent banking limits, and merchant guidelines).

```python
# Configurable assumptions to verify against current Bangladesh Bank circulars
TIER_LIMITS = {
    "personal": {
        "single_txn_limit": 50_000.0,       # ৳50,000 BDT standard personal single transfer cap
        "daily_limit": 100_000.0,           # ৳100,000 BDT cumulative daily outbound transfer limit
        "monthly_limit": 300_000.0,         # ৳300,000 BDT cumulative monthly outflow limit
        "dual_approval_limit": None,         # Hard single-transaction limit enforcement
        "new_account_limit": 10_000.0,      # First 7 days cap for newly registered personal wallets
        "baseline_min_clamp": 200.0,        # Minimum baseline divisor to avoid ratio blowout
        "tier_code": 0,
    },
    "verified": {
        "single_txn_limit": 100_000.0,      # ৳100,000 BDT KYC-verified premier personal/salaried cap
        "daily_limit": 250_000.0,           # ৳250,000 BDT cumulative daily limit
        "monthly_limit": 750_000.0,         # ৳750,000 BDT cumulative monthly limit
        "dual_approval_limit": None,
        "new_account_limit": 25_000.0,      # Limit for accounts < 7 days old
        "baseline_min_clamp": 500.0,
        "tier_code": 1,
    },
    "business": {
        "single_txn_limit": 1_000_000.0,    # ৳1,000,000 BDT registered corporate / merchant transfer cap
        "daily_limit": 5_000_000.0,         # ৳5,000,000 BDT cumulative daily limit
        "monthly_limit": 25_000_000.0,      # ৳25,000,000 BDT cumulative monthly limit
        "dual_approval_limit": 150_000.0,   # ৳150,000 BDT requires dual approval for new/unregistered beneficiaries
        "new_account_limit": 100_000.0,     # Limit for business accounts < 7 days old
        "baseline_min_clamp": 10_000.0,     # Appropriate floor for enterprise median baseline
        "tier_code": 2,
    },
}

# Configurable Agent-Specific Limits for licensed MFS Agents (liquidity rebalancing float management)
# Labeled: Configurable assumptions to verify against current Bangladesh Bank MFS Agent circulars.
AGENT_LIMITS = {
    "single_txn_limit": 300_000.0,       # ৳300,000 BDT single transfer cap for float rebalancing (vs 100k consumer)
    "daily_limit": 1_000_000.0,          # ৳1,000,000 BDT daily outbound limit for agent liquidity
    "monthly_limit": 10_000_000.0,       # ৳10,000,000 BDT monthly limit
    "dual_approval_limit": None,
    "new_account_limit": 50_000.0,       # First 7 days cap
    "baseline_min_clamp": 2_000.0,
    "tier_code": 1,
}

# Absolute platform emergency ceiling across all tiers
ABSOLUTE_SYSTEM_HARD_CAP = 5_000_000.0  # Configurable platform safeguard
```

### Agent-Specific Limit Justification
In Bangladeshi MFS networks, licensed Agents act as liquidity distributors and cash-in/cash-out human ATMs. Capping agents under standard verified consumer limits (৳100,000 single / ৳250,000 daily) would wrongly block legitimate agent liquidity balancing (such as transfers of ৳150,000 – ৳300,000 to Master Distributors or bank DSO accounts). The dedicated `AGENT_LIMITS` set provides the necessary operational float headroom without relaxing consumer protections.

---

## 3. Personas & Behavioral Distributions

The simulated population of 2,000 accounts is partitioned across four realistic personas:

1. **Low-Balance Students (40%, 800 accounts, Personal Tier)**:
   - Typical balance: ৳500 – ৳5,000.
   - Transaction sizes: ৳50 – ৳1,500.
   - Predominant transaction kinds: `mobile_recharge`, small `send_money` (campus dining, snacks, ride shares).
2. **Salaried Professionals (40%, 800 accounts, Verified Tier)**:
   - Typical balance: ৳10,000 – ৳60,000.
   - Transaction sizes: ৳200 – ৳10,000.
   - Month-end salary deposit bumps (`cash_in`) on days 28–2. Utility bills (`bill`), rent payments, and regular family remittances.
3. **Shopkeepers & MFS Agents (15%, 300 accounts, Verified / Agent Tier)**:
   - Typical balance: ৳35,000 – ৳350,000.
   - Transaction sizes: ৳500 – ৳22,000 (retail) and ৳100,000 – ৳300,000 (agent distributor liquidity balancing).
   - High transaction velocity, elevated customer fan-in (numerous patrons sending funds during business hours), and periodic `cash_out` rebalancing.
4. **Business & Merchant Enterprises (5%, 100 accounts, Business Tier)**:
   - Typical balance: ৳200,000 – ৳5,000,000.
   - Legitimate transfer sizes: ৳50,000 – ৳1,000,000.
   - Conducted almost exclusively during standard business hours (09:00 to 18:00 Dhaka time) across regular cycles (e.g. weekly settlements, supplier invoicing).
   - Transacts primarily with a fixed network of 3–6 pre-registered suppliers and authorized commercial counterparties.

### Temporal Dynamics & Local Realism
- **Asia/Dhaka Diurnal Curve**: Peak activity occurs between 09:00 and 22:00 Dhaka time. Late-night hours (01:00 to 05:00) experience natural quiet periods (<1.5% of regular traffic).
- **Friday Prayer Lull**: A sharp dip in transaction volume is simulated every Friday between 12:30 and 14:00 (Jummah prayer).
- **Festival Spikes (Eid-ul-Fitr / Eid-ul-Adha)**: Surges in gifts (Salami), festival shopping, and domestic remittances during festival windows (Days 40–47).
- **Conservation of Balance**: Sequential, causal balance accounting; balances are strictly non-negative. Inbound `cash_in` deposits elevate balance with `drain_ratio = 0` and are strictly excluded from outbound single transfer caps.

---

## 4. Fraud Archetypes & Business Fraud Patterns

Fraud accounts for **0.44%** (1,331 cases) across eight distinct cybercrime and abuse archetypes:

1. **Account Takeover (ATO)**: Compromise of credentials or SIM swap. Rapid balance exfiltration to a novel counterparty.
2. **Business Account Takeover**: Exfiltration of large corporate balances (৳300,000 – ৳950,000) to an unverified beneficiary.
3. **Impersonated Supplier (Vendor Email Compromise)**: Target business accounts tricked into paying a novel beneficiary posing as an established supplier (৳180,000 – ৳750,000).
4. **Structuring (Smurfing)**: Deliberate fragmentation of transfers just below reporting or approval thresholds (e.g. personal transfers of ৳24,500/৳48,500; business transfers of ৳142,000/৳148,500 to circumvent the ৳150,000 dual approval trigger).
5. **Mule Fan-In / Fan-Out**: Aggregator accounts receiving inbound funds from 4+ distinct senders within 24 hours, followed by rapid withdrawal.
6. **Velocity Burst**: High-frequency automated attacks initiating 6–10 outbound transfers in rapid succession (<90 seconds between events).
7. **New Account Abuse**: Accounts created within the last 7 days immediately attempting transfers exceeding new-account limits.
8. **Cold Start Large Exfiltration**: Extreme magnitude transfers (up to ৳500,000 on personal accounts) from accounts with low prior transaction baselines.

---

## 5. Causal Feature Pipeline (16 Features)

Features are extracted strictly from past data (causal rolling windows), preventing temporal data leakage:

| Feature Name | Type | Description |
| :--- | :--- | :--- |
| `amount_bdt` | float | Transaction value in Bangladeshi Taka. |
| `drain_ratio` | float | `amount / current_balance` (0.0 for cash-in). |
| `amount_to_avg_ratio` | float | Ratio of amount to user's 30-day median baseline (with per-tier median fallback and per-tier clamp). |
| `has_history` | float | `1.0` if user has >= 5 historical transactions, else `0.0`. |
| `txns_1h` | int | Outbound transaction count by initiator in preceding 60 minutes. |
| `txns_24h` | int | Outbound transaction count by initiator in preceding 24 hours. |
| `sum_24h` | float | Total BDT volume sent by initiator in preceding 24 hours. |
| `is_new_recipient` | float | `1.0` if sender has never previously transacted with recipient, else `0.0`. |
| `rapid_seconds` | float | Seconds elapsed since sender's previous transaction (sentinel: 86400.0). |
| `is_night_hours` | float | `1.0` if initiated between 01:00 and 05:59 Asia/Dhaka time (UTC+6), else `0.0`. |
| `recipient_account_age_days`| float | Age of recipient's wallet account in days. |
| `recipient_fan_in_count_24h`| int | Number of unique senders who sent money to this recipient in past 24h. |
| `account_tier` | int | Account tier code: `0` (Personal), `1` (Verified), `2` (Business). |
| `is_trusted_recipient` | float | `1.0` if recipient is a pre-registered supplier or transacted >= 24h prior, else `0.0`. |
| `recipient_registered_age_hours`| float | Hours elapsed since recipient's account registration. |
| `txn_vs_tier_limit_ratio` | float | `amount_bdt / tier_single_limit` (normalized headroom). |

---

## 6. Diagnostic Rule Audit & Incremental Recall

Evaluating candidate rules on the held-out temporal test split (44,913 transactions, 222 fraud cases) reveals their true precision and incremental recall over the trained LightGBM model:

| Rule Name | Alerts Fired | Precision | Incremental Recall | Incremental TP | Operational Purpose |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `RULE_ABSOLUTE_HARD_CAP (>5M BDT)` | 0 | 0.00% | 0.00% | 0 | Mandatory platform ceiling safeguard. |
| `RULE_TIER_CAP (Outbound 50k/100k/1M)` | 13 | **100.00%** | 0.00% | 0 | Mandatory regulatory compliance cap (LGBM caught all 13). |
| `RULE_BUSINESS_UNAPPROVED (>150k novel payee)` | 8 | **87.50%** | 0.00% | 0 | Corporate dual-authorization safeguard (LGBM caught 7). |
| `RULE_NEW_ACCOUNT_LIMIT (<7d & >limit)` | 38 | 2.63% | 0.00% | 0 | Regulatory new-account restriction. |
| `RULE_MULE_PERSONAL_FAN_IN (fan-in >= 4)` | 243 | 2.88% | **+0.90%** | 2 | Catches 2 edge-case frauds (+0.90%), but creates 236 false alarms. Demoted to MEDIUM risk. |
| `RULE_VELOCITY_1H (>=4 txns)` | 38 | 84.21% | **+0.90%** | 2 | High precision signal; used as LightGBM feature. |
| `RULE_AMOUNT_DEV (>=4x & >=3k)` | 1,070 | 14.30% | +18.92% | 42 | Major false alarm driver (917 FPs). Demoted to model feature. |
| `RULE_DRAIN_NEW_REC (>=85% & new)` | 1,522 | 5.26% | +10.81% | 24 | High false positives on rent/tuition (1,442 FPs). Demoted to model feature. |
| `RULE_NIGHT_HIGH_VAL (>=10k & night)` | 381 | 2.10% | +1.80% | 4 | Low precision on legitimate late-night travel/health. Demoted to model feature. |

---

## 7. Model Training, Three-Way Comparison & Cost Analysis

### Temporal Split
Strict chronological split without shuffling:
- **Train (70%)**: 209,594 records (898 fraud, 0.43%)
- **Validation (15%)**: 44,913 records (211 fraud, 0.47%)
- **Held-Out Test (15%)**: 44,913 records (222 fraud, 0.49%)

### Three-Way Benchmark Comparison (Held-Out Test Set)

| System Architecture | PR-AUC | ROC-AUC | Precision | Recall | F1-Score | Alerts Fired | Total Financial Cost (BDT) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Legacy Rules Baseline** | 0.1475 | 0.9090 | 2.03% | **73.42%** | 0.0395 | 8,025 | ৳924,100.00 |
| **LightGBM-Only (PR-Tuned)** | **0.8212** | **0.9883** | **93.45%** | 70.72% | **0.8051** | **168** | **৳585,550.00** |
| **Refined Production Hybrid** | **0.8212** | **0.9883** | **93.45%** | 70.72% | **0.8051** | **168** | **৳585,550.00** |

### Cost Breakdown Assumptions & Financial Verdict
- **Missed Fraud Cost (FN)**: ৳9,000.00 BDT (average gross financial loss per undetected fraudulent incident).
- **False Alarm Review Cost (FP)**: ৳50.00 BDT (operational triage & human investigator review time).
- **Cost Comparison**:
  - Legacy Rules: 59 missed frauds (৳531,000) + 7,862 false alarms (৳393,100) = **৳924,100.00 BDT**.
  - LightGBM-Only: 65 missed frauds (৳585,000) + 11 false alarms (৳550) = **৳585,550.00 BDT**.
  - Refined Hybrid: 65 missed frauds (৳585,000) + 11 false alarms (৳550) = **৳585,550.00 BDT**.
- **Verdict**: Both LightGBM-only and the Refined Hybrid achieve identical financial performance (**৳585,550.00 BDT**, saving ৳338,550 BDT or 36.6% over rules). The Refined Hybrid is strictly preferred because it provides deterministic legal compliance guarantees (outbound caps and corporate dual-approval) without incurring operational cost inflation.

---

## 8. Per-Tier False Alarm Rates on Legitimate Transfers

| Sliced Population | Total Txns | Total Fraud | Detected Fraud | False Alarms (FP) | False Alarm Rate (FAR) on Legit | Precision | Recall |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Personal (Tier 0)** | 6,562 | 108 | 81 | 6 | **0.09%** (6 / 6,454) | 93.10% | 75.00% |
| **Personal Large (>20k)** | 188 | 35 | 26 | 4 | **2.61%** (4 / 153) | 92.86% | 74.29% |
| **Verified Consumer (Salaried)** | 10,417 | 53 | 35 | 4 | **0.04%** (4 / 10,364) | 89.74% | 66.04% |
| **Verified Merchant / Agent** | 24,406 | 36 | 17 | 0 | **0.00%** (0 / 24,370) | 100.00% | 47.22% |
| **Agent Large Liquidity (>100k)** | 1 | 1 | 1 | 0 | **0.00%** (0 / 0) | 100.00% | 100.00% |
| **Business Enterprise (Tier 2)** | 3,528 | 25 | 24 | 1 | **0.03%** (1 / 3,503) | 96.00% | 96.00% |
| **Business Large Transfers (>150k)**| 3,169 | 8 | 8 | 1 | **0.03%** (1 / 3,161) | 87.50% | 100.00% |

---

## 9. Per-Fraud-Type Recall with 95% Bootstrap Confidence Intervals

Based on 1,000 bootstrap resamples on the held-out test split:

| Fraud Archetype | Test Cases | Detected | Recall Rate | 95% Bootstrap CI | Sample Status |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Cold Start Large** | 12 | 12 | **100.0%** | `[100.0%, 100.0%]` | `[low-sample]` (<30 cases) |
| **Impersonated Supplier** | 6 | 6 | **100.0%** | `[100.0%, 100.0%]` | `[low-sample]` (<30 cases) |
| **New Account Abuse** | 16 | 15 | **93.8%** | `[81.2%, 100.0%]` | `[low-sample]` (<30 cases) |
| **Structuring (Smurfing)** | 44 | 37 | **84.1%** | `[72.7%, 93.2%]` | Adequate sample |
| **Velocity Burst** | 46 | 33 | **71.7%** | `[58.7%, 84.8%]` | Adequate sample |
| **Account Takeover (ATO)** | 50 | 33 | **66.0%** | `[52.0%, 78.0%]` | Adequate sample |
| **Mule Fan-In / Fan-Out** | 46 | 21 | **45.7%** | `[30.4%, 58.7%]` | Adequate sample |
| **Hard Negative Specificity** | 2,909 | 2,900 | **99.7%** | `[99.5%, 99.9%]` | 0.31% false alarms on benign spikes |

---

## 10. Feature Ablation Study

To evaluate how much model performance relies on generator-derived counterparty trust and normalized tier headroom features, a controlled ablation experiment was run retraining LightGBM without `is_trusted_recipient`, `txn_vs_tier_limit_ratio`, and `recipient_registered_age_hours`:

| Model Feature Set | Features Count | PR-AUC | ROC-AUC | Precision | Recall | F1-Score |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full Causal Feature Set** | 16 | **0.8212** | **0.9883** | **93.45%** | **70.72%** | **0.8051** |
| **Ablated Feature Set** | 13 | 0.5678 | 0.9838 | 69.46% | 52.25% | 0.5964 |
| **Performance Delta (Loss)** | -3 | **-0.2534** | -0.0045 | **-23.99%** | **-18.47%** | **-0.2087** |

### Honest Finding on Feature Dependency
Removing the three generator-derived counterparty trust features causes a **25.34-point drop in PR-AUC** (from 0.8212 to 0.5678) and a **20.87-point drop in F1-score**. Without counterparty registration age and tier headroom ratios, the gradient boosting tree cannot reliably distinguish legitimate large commercial supplier invoicing from novel beneficiary account takeover attempts. Deploying this model in production requires engineering live counterparty trust lookup tables in the real database.

---

## 11. Known Limitations & Prototype Notice

> [!WARNING]
> **PROTOTYPE LIMITATIONS & SYNTHETIC ASSUMPTIONS**:
> 1. **Prototype Validated on Synthetic Data**: The entire modeling and evaluation pipeline was conducted on algorithmically simulated transactions. The LightGBM model learns patterns defined in `synthetic_generator.py`, **not** live Bangladeshi bank telemetry or real cybercriminal adversaries.
> 2. **Configurable Regulatory Limits**: All thresholds (৳50k personal cap, ৳100k verified cap, ৳300k agent cap, ৳1M business cap, ৳150k dual approval) are configurable architectural assumptions. Production deployments must align strictly with active Bangladesh Bank Circulars and commercial acquiring limits.
> 3. **Legacy Demo Data Transparency**: Early prototype testing recorded unconstrained test transactions (e.g. ৳45,000 drain tests on `@bikash`). In the live admin console, these are marked with a distinct `[Legacy Test Data]` tag to ensure historical tests do not contradict the calibrated student persona.
> 4. **Social Engineering Vectors**: Tabular transactional features cannot detect voice-phishing, lottery impersonation, or OTP social engineering common in Bangladeshi MFS networks.
> 5. **Retraining & Human-in-the-Loop Requirement**: The system includes an administrative triage feedback loop (`confirmed_fraud`, `not_fraud`, `inconclusive`) with mandatory resolution reason codes designed to harvest genuine ground truth for continual model re-calibration.
