# Architecture & Implementation Changes: Dynamic User Types, Account Tiers & Evaluation Rigor

> **Project**: Bangladesh MFS Wallet Fraud Intelligence Platform  
> **Currency Context**: Bangladeshi Taka (BDT / ৳)  
> **Status**: Prototype Validated on Synthetic Data  

---

## 1. Executive Summary

This release resolves the remaining Hybrid precision problem, introduces a dedicated MFS Agent limit set, audits legacy rules with incremental recall analysis, conducts a controlled feature ablation experiment, implements legacy test data tagging for student profiles, and replaces all claims with transparent empirical results.

All limits, caps, and baselines are maintained in a single source of truth (`backend/app/tier_config.py`) and labeled as **"configurable assumptions to verify against current Bangladesh Bank rules"**.

---

## 2. Refined Hybrid Engine & False Alarm Elimination

### The Root Cause of 19.65% Hybrid Precision
In earlier evaluation iterations, outbound transfer caps (`tier_cap` and `business_unapproved`) were inadvertently evaluated against inbound `cash_in` top-up transactions:
- Over 405 legitimate business cash-in revenue deposits were incorrectly classified as "untrusted recipient fraud" because inbound top-ups naturally have no counterparty recipient (`is_trusted_recipient = 0.0`).
- Over 153 legitimate business daily bank deposits exceeding ৳1,000,000 were treated as outbound transfer limit breaches.

### The Solution: Outbound-Only Regulatory Safeguards
1. Outbound rules are strictly restricted to outbound money movement (`send_money`, `cash_out`, `payment`), completely decoupling cash-in deposits.
2. Low-precision soft rules (`RULE_AMOUNT_DEV`: 14.30% precision; `RULE_DRAIN_NEW_REC`: 5.26% precision; `RULE_NIGHT_HIGH_VAL`: 2.10% precision) are demoted to model features, eliminating over 2,500 false alarms.
3. The Refined Hybrid keeps only non-negotiable regulatory hard safeguards:
   - Absolute platform ceiling (`amount_bdt > 5,000,000.0`)
   - Tier outbound single transfer caps (Personal ৳50,000 | Verified ৳100,000 | Agent ৳300,000 | Business ৳1,000,000)
   - Business dual-approval hold on novel beneficiaries (>৳150,000)
4. **Result**: The Refined Hybrid matches LightGBM-only at **93.45% precision**, firing only **168 alerts** (down from 8,025 in legacy rules and 650 in the naive hybrid).

---

## 3. Dedicated MFS Agent Limits (`AGENT_LIMITS`)

### Problem Identified
Under standard `verified` consumer limits (৳100,000 single transfer cap / ৳250,000 daily limit), legitimate licensed MFS agents (such as `@tahzib` with a ৳320,000 balance) were blocked when performing standard liquidity float rebalancing (moving ৳150,000 – ৳300,000 to Master Distributors / Bank DSO accounts).

### Solution Implemented
Implemented `AGENT_LIMITS` in `backend/app/tier_config.py` labeled as configurable assumptions to verify against current Bangladesh Bank MFS Agent circulars:
- `single_txn_limit`: ৳300,000.0 BDT (vs ৳100,000 for verified consumers)
- `daily_limit`: ৳1,000,000.0 BDT
- `monthly_limit`: ৳10,000,000.0 BDT
- `new_account_limit`: ৳50,000.0 BDT
- `baseline_min_clamp`: ৳2,000.0 BDT
- Dynamically applied via `get_effective_limits(..., user_type=user_type)` across `fraud_engine.py`, `accounts.py`, `admin.py`, and `agent.py`.
- Verified in scenario tests: Agent transfer of ৳200,000 float succeeds without false alarm; transfer of ৳350,000 correctly triggers the ৳300k agent cap.

---

## 4. Three-Way Benchmark Comparison (Held-Out Test Split)

Evaluated on the exact same chronological held-out test split (44,913 transactions, 222 fraud cases):

| System Architecture | PR-AUC | ROC-AUC | Precision | Recall | F1-Score | Alerts Fired | Total Financial Cost (BDT) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Legacy Rules Baseline** | 0.1475 | 0.9090 | 2.03% | **73.42%** | 0.0395 | 8,025 | ৳924,100.00 |
| **LightGBM-Only (PR-Tuned)** | **0.8212** | **0.9883** | **93.45%** | 70.72% | **0.8051** | **168** | **৳585,550.00** |
| **Refined Production Hybrid** | **0.8212** | **0.9883** | **93.45%** | 70.72% | **0.8051** | **168** | **৳585,550.00** |

### Financial Cost Analysis (Missed Fraud = ৳9,000, False Alarm = ৳50)
- Legacy Rules Cost: ৳924,100.00
- LightGBM-Only Cost: ৳585,550.00
- Refined Hybrid Cost: ৳585,550.00
- **Cost Verdict**: LightGBM-only and the Refined Hybrid achieve identical financial costs, saving ৳338,550.00 BDT (36.6% cost reduction) compared to legacy rules. The Refined Hybrid is strictly preferred because it adds deterministic regulatory compliance without any cost penalty.

---

## 5. Diagnostic Rule Audit & Incremental Recall

| Rule Name | Alerts Fired | Precision | Incremental Recall | Incremental TP | Operational Disposition |
| :--- | :---: | :---: | :---: | :---: | :--- |
| `RULE_ABSOLUTE_HARD_CAP (>5M BDT)` | 0 | 0.00% | 0.00% | 0 | Mandatory platform ceiling. |
| `RULE_TIER_CAP (Outbound 50k/100k/1M)` | 13 | **100.00%** | 0.00% | 0 | Regulatory compliance (LGBM caught all 13). |
| `RULE_BUSINESS_UNAPPROVED (>150k novel payee)` | 8 | **87.50%** | 0.00% | 0 | Corporate dual authorization. |
| `RULE_NEW_ACCOUNT_LIMIT (<7d & >limit)` | 38 | 2.63% | 0.00% | 0 | Regulatory new-account safeguard. |
| `RULE_MULE_PERSONAL_FAN_IN (fan-in >= 4)` | 243 | 2.88% | **+0.90%** | 2 | Demoted to MEDIUM alert to eliminate 236 FPs. |
| `RULE_VELOCITY_1H (>=4 txns)` | 38 | 84.21% | **+0.90%** | 2 | Retained as model feature. |
| `RULE_AMOUNT_DEV (>=4x & >=3k)` | 1,070 | 14.30% | +18.92% | 42 | Demoted to model feature (saved 917 FPs). |
| `RULE_DRAIN_NEW_REC (>=85% & new)` | 1,522 | 5.26% | +10.81% | 24 | Demoted to model feature (saved 1,442 FPs). |
| `RULE_NIGHT_HIGH_VAL (>=10k & night)` | 381 | 2.10% | +1.80% | 4 | Demoted to model feature (saved 373 FPs). |

---

## 6. Per-Tier False Alarm Rates on Legitimate Transfers

- **Personal Tier (Tier 0)**: **0.09% FAR** (6 FPs / 6,454 legit transfers) | Precision 93.10% | Recall 75.00%
- **Personal Large Transfers (>20k)**: **2.61% FAR** (4 FPs / 153 legit transfers) | Precision 92.86%
- **Verified Consumer (Salaried)**: **0.04% FAR** (4 FPs / 10,364 legit transfers) | Precision 89.74%
- **Verified Merchant / Agent**: **0.00% FAR** (0 FPs / 24,370 legit transfers) | Precision 100.00%
- **Agent Large Liquidity Transfers (>100k)**: **0.00% FAR** (0 FPs) | Precision 100.00%
- **Business Enterprise (Tier 2)**: **0.03% FAR** (1 FP / 3,503 legit transfers) | Precision 96.00%
- **Business Large Transfers (>150k)**: **0.03% FAR** (1 FP / 3,161 legit transfers) | Precision 87.50%

---

## 7. Per-Fraud-Type Recall with 95% Bootstrap Confidence Intervals

1,000 bootstrap resamples on the held-out test split:
- **Cold Start Large**: 100.0% `[100.0%, 100.0%]` (12/12) `[low-sample]`
- **Impersonated Supplier**: 100.0% `[100.0%, 100.0%]` (6/6) `[low-sample]`
- **New Account Abuse**: 93.8% `[81.2%, 100.0%]` (15/16) `[low-sample]`
- **Structuring (Smurfing)**: 84.1% `[72.7%, 93.2%]` (37/44)
- **Velocity Burst**: 71.7% `[58.7%, 84.8%]` (33/46)
- **Account Takeover (ATO)**: 66.0% `[52.0%, 78.0%]` (33/50)
- **Mule Fan-In / Fan-Out**: 45.7% `[30.4%, 58.7%]` (21/46)
- **Hard Negative Specificity**: 99.7% `[99.5%, 99.9%]` (2,900/2,909)

---

## 8. Feature Ablation Study

Retraining LightGBM without `is_trusted_recipient`, `txn_vs_tier_limit_ratio`, and `recipient_registered_age_hours`:
- Full 16 Features: PR-AUC 0.8212 | Precision 93.45% | Recall 70.72% | F1 0.8051
- Ablated 13 Features: PR-AUC 0.5678 | Precision 69.46% | Recall 52.25% | F1 0.5964
- **Delta**: **-0.2534 PR-AUC** (-25.34 points), **-0.2087 F1** (-20.87 points), **-23.99% Precision**, **-18.47% Recall**.
- **Takeaway**: Stated honestly in `DATA_CARD.md`: Over 25 points of PR-AUC depend on counterparty registration age and tier headroom features.

---

## 9. Transparency: Legacy Test Data Tagging on `@bikash`

Pre-migration prototype transactions and alerts on demo account `@bikash` (such as the ৳45,000 drain alert recorded during initial prototyping) are now transparently flagged across backend APIs and admin UI:
- Added `is_legacy_test_data` boolean and `legacy_explanation` string to `/transactions`, `/fraud/alerts`, and `/users/{id}`.
- Rendered with an amber `[Legacy Test Data]` badge in the Transactions Table, Fraud Alerts & Triage drawer, and User Detail modal.
- Clarifies that historical prototype tests do not contradict the live calibrated student profile (৳50,000 single cap / ৳5,500 balance).

---

## 10. Verification Suite

- **Tier & Profile Scenarios**: 11 passed (100%)
- **ML Fraud Scenarios**: 12 passed (100%)
- **Full Backend Suite**: 139 passed in 61s (100%)
- **Frontend Build**: `npm run build` compiled cleanly (9/9 static pages)
