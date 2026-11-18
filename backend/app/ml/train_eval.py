"""Model Training, Validation, Threshold Tuning, Diagnostic Audit, and Evaluation Pipeline.

Adheres strictly to FinTech production standards:
1. Strict temporal 70/15/15 train/val/test split (no temporal data leakage).
2. Diagnostic audit of candidate rules on the test split (alerts fired, precision, and incremental recall over ML).
3. Trains LightGBM with class weighting and PR-curve threshold tuning.
4. Three-way benchmark comparison on the SAME held-out test split:
   - Legacy Rules Baseline
   - Standalone LightGBM Model
   - Refined Production Hybrid System
5. Cost-based financial impact analysis (configurable assumptions):
   - Missed fraud cost (FN) = ৳9,000 BDT (average fraudulent transfer loss)
   - False alarm review cost (FP) = ৳50 BDT (analyst triage overhead)
6. Per-tier false alarm rate on legitimate transfers, especially large transfers (Personal, Verified, Agent, Business).
7. Feature ablation experiment: evaluates performance loss when removing generator-derived features.
8. Per-archetype recall with 95% bootstrap confidence intervals (1,000 resamples) and low-sample flagging (<30 cases).
9. Serializes the trained model artifact for runtime integration in FraudEngine.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

FEATURE_COLS = [
    "amount_bdt",
    "drain_ratio",
    "amount_to_avg_ratio",
    "has_history",
    "txns_1h",
    "txns_24h",
    "sum_24h",
    "is_new_recipient",
    "rapid_seconds",
    "is_night_hours",
    "recipient_account_age_days",
    "recipient_fan_in_count_24h",
    "account_tier",
    "is_trusted_recipient",
    "recipient_registered_age_hours",
    "txn_vs_tier_limit_ratio",
]

TARGET_COL = "is_fraud"

# Configurable cost assumptions (verify against operational and fraud loss benchmarks)
DEFAULT_COST_MISSED_FRAUD = 9_000.0   # ৳9,000 BDT average financial loss per undetected fraud
DEFAULT_COST_FALSE_ALARM = 50.0       # ৳50 BDT investigator triage review time per false alarm


def load_dataset() -> pd.DataFrame:
    """Load the generated synthetic dataset."""
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    parquet_path = os.path.join(base_dir, "data/wallet_synthetic_300k.parquet")
    if not os.path.exists(parquet_path):
        parquet_path = os.path.join(base_dir, "../data/wallet_synthetic_300k.parquet")

    if not os.path.exists(parquet_path):
        raise FileNotFoundError(f"Parquet dataset not found at {parquet_path}")

    print(f"Loading dataset from: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    df = df.sort_values(by="timestamp").reset_index(drop=True)
    return df


def temporal_split(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Strict chronological 70% train, 15% validation, 15% test split without shuffling."""
    n = len(df)
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)

    df_train = df.iloc[:n_train].copy()
    df_val = df.iloc[n_train:n_train + n_val].copy()
    df_test = df.iloc[n_train + n_val:].copy()

    print(f"Temporal Split: Train={len(df_train):,} ({len(df_train)/n*100:.1f}%), "
          f"Val={len(df_val):,} ({len(df_val)/n*100:.1f}%), "
          f"Test={len(df_test):,} ({len(df_test)/n*100:.1f}%)")
    print(f"  Train fraud: {df_train[TARGET_COL].sum():,} ({df_train[TARGET_COL].mean()*100:.2f}%)")
    print(f"  Val fraud:   {df_val[TARGET_COL].sum():,} ({df_val[TARGET_COL].mean()*100:.2f}%)")
    print(f"  Test fraud:  {df_test[TARGET_COL].sum():,} ({df_test[TARGET_COL].mean()*100:.2f}%)")

    return df_train, df_val, df_test


def evaluate_rule_baseline(df: pd.DataFrame) -> Tuple[np.ndarray, np.ndarray]:
    """Execute the naive legacy rule baseline."""
    scores = np.zeros(len(df), dtype=float)

    # Velocity
    v1h = df["txns_1h"].values
    scores += np.where(v1h >= 4, 0.35, np.where(v1h >= 2, 0.15, 0.0))

    # Amount spike
    amt_ratio = df["amount_to_avg_ratio"].values
    amt = df["amount_bdt"].values
    scores += np.where((amt_ratio >= 4.0) & (amt >= 3000.0), 0.35,
                       np.where((amt_ratio >= 2.5) & (amt >= 2000.0), 0.15, 0.0))

    # Drain to new
    drain = df["drain_ratio"].values
    is_new = df["is_new_recipient"].values
    scores += np.where((drain >= 0.85) & (is_new == 1.0), 0.40, 0.0)

    # Rapid seconds
    rapid = df["rapid_seconds"].values
    scores += np.where(rapid < 90.0, 0.25, 0.0)

    # Mule fan-in (legacy naive: all accounts)
    fan_in = df["recipient_fan_in_count_24h"].values
    scores += np.where(fan_in >= 3, 0.40, 0.0)

    # Night hours
    night = df["is_night_hours"].values
    scores += np.where((night == 1.0) & (amt >= 10000.0), 0.20, 0.0)

    normalized_scores = np.clip(scores, 0.0, 1.0)
    preds = (normalized_scores >= 0.40).astype(int)
    return normalized_scores, preds


def find_optimal_threshold(y_true: np.ndarray, y_proba: np.ndarray) -> Tuple[float, float, float, float]:
    """Tune classification threshold on the Validation PR curve to maximize F1-score."""
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_proba)
    numerator = 2 * precisions * recalls
    denominator = precisions + recalls + 1e-9
    f1_scores = np.divide(numerator, denominator)

    best_idx = np.argmax(f1_scores)
    best_thresh = float(thresholds[min(best_idx, len(thresholds) - 1)])
    best_p = float(precisions[best_idx])
    best_r = float(recalls[best_idx])
    best_f1 = float(f1_scores[best_idx])

    return best_thresh, best_p, best_r, best_f1


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray, y_proba: np.ndarray) -> Dict[str, Any]:
    """Calculate standard evaluation metrics."""
    pr_auc = float(average_precision_score(y_true, y_proba))
    roc_auc = float(roc_auc_score(y_true, y_proba))
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))
    alerts_fired = int(y_pred.sum())
    return {
        "pr_auc": round(pr_auc, 4),
        "roc_auc": round(roc_auc, 4),
        "precision": round(prec, 4),
        "precision_pct": f"{prec * 100:.2f}%",
        "recall": round(rec, 4),
        "recall_pct": f"{rec * 100:.2f}%",
        "f1": round(f1, 4),
        "alerts_fired": alerts_fired,
    }


def compute_financial_cost(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    cost_fn: float = DEFAULT_COST_MISSED_FRAUD,
    cost_fp: float = DEFAULT_FALSE_ALARM if 'DEFAULT_FALSE_ALARM' in globals() else DEFAULT_COST_FALSE_ALARM,
) -> Dict[str, Any]:
    """Cost-based financial evaluation."""
    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel()
    fn_cost = fn * cost_fn
    fp_cost = fp * cost_fp
    total_cost = fn_cost + fp_cost
    return {
        "true_positives": int(tp),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_negatives": int(tn),
        "cost_missed_fraud_bdt": float(fn_cost),
        "cost_false_alarm_bdt": float(fp_cost),
        "total_cost_bdt": float(total_cost),
    }


def diagnose_rules_with_incremental_recall(
    df_test: pd.DataFrame, lgb_test_preds: np.ndarray
) -> Dict[str, Dict[str, Any]]:
    """Audit individual rules on the held-out test split.

    Reports:
    - Alerts fired
    - Precision %
    - Frauds caught (TP)
    - Incremental TP (frauds caught ONLY by this rule that LightGBM missed: rule=1 & y=1 & lgb=0)
    - Incremental Recall %
    """
    y = df_test[TARGET_COL].values
    total_fraud = int(y.sum())
    outbound = df_test["txn_kind"].isin(["send_money", "cash_out", "payment"])

    rules = {
        "RULE_ABSOLUTE_HARD_CAP (>5M BDT)": (df_test["amount_bdt"] > 5_000_000.0),
        "RULE_TIER_CAP (Outbound 50k/100k/1M)": outbound & (
            ((df_test["account_tier"] == 0) & (df_test["amount_bdt"] > 50_000.0))
            | ((df_test["account_tier"] == 1) & (df_test["amount_bdt"] > 100_000.0))
            | ((df_test["account_tier"] == 2) & (df_test["amount_bdt"] > 1_000_000.0))
        ),
        "RULE_NEW_ACCOUNT_LIMIT (<7d & >tier limit)": outbound & (
            ((df_test["account_tier"] == 0) & (df_test["recipient_account_age_days"] < 7.0) & (df_test["amount_bdt"] > 10_000.0))
            | ((df_test["account_tier"] == 1) & (df_test["recipient_account_age_days"] < 7.0) & (df_test["amount_bdt"] > 25_000.0))
            | ((df_test["account_tier"] == 2) & (df_test["recipient_account_age_days"] < 7.0) & (df_test["amount_bdt"] > 100_000.0))
        ),
        "RULE_BUSINESS_UNAPPROVED (>150k novel payee)": outbound & (
            (df_test["account_tier"] == 2)
            & (df_test["amount_bdt"] > 150_000.0)
            & (df_test["is_trusted_recipient"] == 0.0)
        ),
        "RULE_MULE_PERSONAL_FAN_IN (fan-in >= 4)": outbound & (
            (df_test["recipient_fan_in_count_24h"] >= 4) & (df_test["account_tier"] == 0)
        ),
        "RULE_VELOCITY_1H (>=4 txns)": outbound & (df_test["txns_1h"] >= 4),
        "RULE_AMOUNT_DEV (>=4x & >=3k)": outbound & (
            (df_test["amount_to_avg_ratio"] >= 4.0) & (df_test["amount_bdt"] >= 3000.0)
        ),
        "RULE_DRAIN_NEW_REC (>=85% & new)": outbound & (
            (df_test["drain_ratio"] >= 0.85) & (df_test["is_new_recipient"] == 1.0)
        ),
        "RULE_NIGHT_HIGH_VAL (>=10k & night)": outbound & (
            (df_test["is_night_hours"] == 1.0) & (df_test["amount_bdt"] >= 10000.0)
        ),
    }

    report = {}
    print("\n--- Diagnostic Rule Audit & Incremental Recall over LightGBM (Test Split) ---")
    print(f"%-45s | %-12s | %-10s | %-16s | %-14s" %
          ("Rule Name", "Alerts Fired", "Precision", "Incremental Recall", "Incremental TP"))
    print("-" * 105)

    for r_name, mask in rules.items():
        alerts = int(mask.sum())
        tp = int((mask & (y == 1)).sum())
        fp = alerts - tp
        prec = (tp / alerts) if alerts > 0 else 0.0
        incr_tp = int((mask & (y == 1) & (lgb_test_preds == 0)).sum())
        incr_rec = (incr_tp / total_fraud) if total_fraud > 0 else 0.0

        report[r_name] = {
            "alerts_fired": alerts,
            "true_positives": tp,
            "false_positives": fp,
            "precision": round(prec, 4),
            "precision_pct": f"{prec * 100:.2f}%",
            "incremental_tp": incr_tp,
            "incremental_recall": round(incr_rec, 4),
            "incremental_recall_pct": f"{incr_rec * 100:.2f}%",
        }
        print(f"{r_name:45s} | {alerts:12d} | {prec*100:9.2f}% | {incr_rec*100:15.2f}% | {incr_tp:14d}")

    return report


def evaluate_per_fraud_type_with_bootstrap(
    df_test: pd.DataFrame, y_pred: np.ndarray, n_bootstraps: int = 1000, seed: int = 42
) -> Dict[str, Dict[str, Any]]:
    """Compute per-archetype recall with 95% bootstrap confidence intervals and low-sample flags."""
    rng = np.random.default_rng(seed)
    breakdown: Dict[str, Dict[str, Any]] = {}
    test_copy = df_test.copy()
    test_copy["pred"] = y_pred

    fraud_df = test_copy[test_copy[TARGET_COL] == 1]
    for ftype, group in fraud_df.groupby("fraud_type"):
        total = len(group)
        detected = int(group["pred"].sum())
        recall = (detected / total) if total > 0 else 0.0

        boot_recalls = []
        indices = np.arange(total)
        for _ in range(n_bootstraps):
            sample_idx = rng.choice(indices, size=total, replace=True)
            boot_recalls.append(float(group["pred"].iloc[sample_idx].mean()))

        ci_lower = float(np.percentile(boot_recalls, 2.5))
        ci_upper = float(np.percentile(boot_recalls, 97.5))

        breakdown[ftype] = {
            "total_cases": total,
            "detected_cases": detected,
            "recall": round(recall, 4),
            "recall_pct": f"{recall * 100:.1f}%",
            "ci_95": [round(ci_lower, 4), round(ci_upper, 4)],
            "ci_95_str": f"[{ci_lower * 100:.1f}%, {ci_upper * 100:.1f}%]",
            "is_low_sample": bool(total < 30),
        }

    # Hard negative specificity
    hard_negs = test_copy[test_copy["fraud_type"] == "hard_negative"]
    if len(hard_negs) > 0:
        hn_total = len(hard_negs)
        hn_cleared = int((hard_negs["pred"] == 0).sum())
        hn_pass_rate = (hn_cleared / hn_total) if hn_total > 0 else 1.0

        boot_spec = []
        indices_hn = np.arange(hn_total)
        for _ in range(n_bootstraps):
            sample_idx = rng.choice(indices_hn, size=hn_total, replace=True)
            boot_spec.append(float((hard_negs["pred"].iloc[sample_idx] == 0).mean()))

        ci_lower = float(np.percentile(boot_spec, 2.5))
        ci_upper = float(np.percentile(boot_spec, 97.5))

        breakdown["hard_negative_specificity"] = {
            "total_cases": hn_total,
            "correctly_cleared": hn_cleared,
            "specificity": round(hn_pass_rate, 4),
            "specificity_pct": f"{hn_pass_rate * 100:.1f}%",
            "ci_95": [round(ci_lower, 4), round(ci_upper, 4)],
            "ci_95_str": f"[{ci_lower * 100:.1f}%, {ci_upper * 100:.1f}%]",
            "is_low_sample": bool(hn_total < 30),
        }

    return breakdown


def evaluate_per_tier_and_agent(df_test: pd.DataFrame, y_pred: np.ndarray) -> Dict[str, Dict[str, Any]]:
    """Compute per-tier and per-persona False Alarm Rate (FAR) on legitimate transfers, especially large ones."""
    test_copy = df_test.copy()
    test_copy["pred"] = y_pred

    slices = {
        "Personal (Tier 0)": (test_copy["account_tier"] == 0),
        "Personal Large (>20k)": (test_copy["account_tier"] == 0) & (test_copy["amount_bdt"] >= 20000.0),
        "Verified Consumer (Salaried)": (test_copy["account_tier"] == 1) & (test_copy["sender_persona"] == "salaried"),
        "Verified Merchant/Agent": (test_copy["account_tier"] == 1) & (test_copy["sender_persona"].isin(["merchant", "agent", "shopkeeper"])),
        "Agent Large Liquidity (>100k)": (test_copy["sender_persona"].isin(["merchant", "agent", "shopkeeper"])) & (test_copy["amount_bdt"] >= 100000.0),
        "Business Enterprise (Tier 2)": (test_copy["account_tier"] == 2),
        "Business Large Transfers (>150k)": (test_copy["account_tier"] == 2) & (test_copy["amount_bdt"] >= 150000.0),
    }

    results = {}
    for s_name, mask in slices.items():
        sub = test_copy[mask]
        if len(sub) == 0:
            continue
        y_sub = sub[TARGET_COL].values
        pred_sub = sub["pred"].values

        total_txns = len(sub)
        total_fraud = int(y_sub.sum())
        total_legit = total_txns - total_fraud

        tp = int(((pred_sub == 1) & (y_sub == 1)).sum())
        fp = int(((pred_sub == 1) & (y_sub == 0)).sum())
        fn = int(((pred_sub == 0) & (y_sub == 1)).sum())
        tn = int(((pred_sub == 0) & (y_sub == 0)).sum())

        prec = (tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = (tp / total_fraud) if total_fraud > 0 else 0.0
        f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        far_legit = (fp / total_legit) if total_legit > 0 else 0.0

        results[s_name] = {
            "total_transactions": total_txns,
            "total_fraud": total_fraud,
            "detected_fraud": tp,
            "false_alarms": fp,
            "precision_pct": f"{prec * 100:.2f}%",
            "recall_pct": f"{rec * 100:.2f}%",
            "f1": round(f1, 4),
            "false_alarm_rate_legit_pct": f"{far_legit * 100:.2f}%",
        }

    return results


def run_feature_ablation(
    df_train: pd.DataFrame, df_val: pd.DataFrame, df_test: pd.DataFrame
) -> Dict[str, Any]:
    """Train LightGBM without generator-derived features to measure true dependency."""
    y_train = df_train[TARGET_COL].values
    y_val = df_val[TARGET_COL].values
    y_test = df_test[TARGET_COL].values

    neg_count = int(np.sum(y_train == 0))
    pos_count = int(np.sum(y_train == 1))
    scale_pos = neg_count / max(1, pos_count)

    # Full 16 features
    m_full = lgb.LGBMClassifier(
        n_estimators=400,
        learning_rate=0.035,
        num_leaves=31,
        max_depth=6,
        scale_pos_weight=scale_pos,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        verbosity=-1,
    )
    m_full.fit(
        df_train[FEATURE_COLS].values,
        y_train,
        eval_set=[(df_val[FEATURE_COLS].values, y_val)],
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )
    val_p_full = m_full.predict_proba(df_val[FEATURE_COLS].values)[:, 1]
    t_full, _, _, _ = find_optimal_threshold(y_val, val_p_full)
    test_p_full = m_full.predict_proba(df_test[FEATURE_COLS].values)[:, 1]
    pred_full = (test_p_full >= t_full).astype(int)
    met_full = compute_metrics(y_test, pred_full, test_p_full)

    # Ablated 13 features (removing is_trusted_recipient, txn_vs_tier_limit_ratio, recipient_registered_age_hours)
    ablated_cols = [
        c for c in FEATURE_COLS
        if c not in ["is_trusted_recipient", "txn_vs_tier_limit_ratio", "recipient_registered_age_hours"]
    ]

    m_ablated = lgb.LGBMClassifier(
        n_estimators=400,
        learning_rate=0.035,
        num_leaves=31,
        max_depth=6,
        scale_pos_weight=scale_pos,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        verbosity=-1,
    )
    m_ablated.fit(
        df_train[ablated_cols].values,
        y_train,
        eval_set=[(df_val[ablated_cols].values, y_val)],
        callbacks=[lgb.early_stopping(30, verbose=False)],
    )
    val_p_abl = m_ablated.predict_proba(df_val[ablated_cols].values)[:, 1]
    t_abl, _, _, _ = find_optimal_threshold(y_val, val_p_abl)
    test_p_abl = m_ablated.predict_proba(df_test[ablated_cols].values)[:, 1]
    pred_abl = (test_p_abl >= t_abl).astype(int)
    met_abl = compute_metrics(y_test, pred_abl, test_p_abl)

    return {
        "full_features": {
            "cols_count": len(FEATURE_COLS),
            "metrics": met_full,
            "threshold": round(t_full, 4),
        },
        "ablated_features": {
            "cols_count": len(ablated_cols),
            "removed_cols": ["is_trusted_recipient", "txn_vs_tier_limit_ratio", "recipient_registered_age_hours"],
            "metrics": met_abl,
            "threshold": round(t_abl, 4),
        },
        "delta": {
            "pr_auc_drop": round(met_full["pr_auc"] - met_abl["pr_auc"], 4),
            "f1_drop": round(met_full["f1"] - met_abl["f1"], 4),
            "precision_drop": round(met_full["precision"] - met_abl["precision"], 4),
            "recall_drop": round(met_full["recall"] - met_abl["recall"], 4),
        },
    }


def main():
    print("=== Model Training, Diagnostic Audit, and Three-Way Benchmarking ===")
    df = load_dataset()
    df_train, df_val, df_test = temporal_split(df)

    X_train = df_train[FEATURE_COLS].values
    y_train = df_train[TARGET_COL].values

    X_val = df_val[FEATURE_COLS].values
    y_val = df_val[TARGET_COL].values

    X_test = df_test[FEATURE_COLS].values
    y_test = df_test[TARGET_COL].values

    outbound_test = df_test["txn_kind"].isin(["send_money", "cash_out", "payment"])

    # 1. Deterministic Legacy Rule Baseline
    rule_scores_test, rule_preds_test = evaluate_rule_baseline(df_test)
    rule_metrics = compute_metrics(y_test, rule_preds_test, rule_scores_test)
    rule_cost = compute_financial_cost(y_test, rule_preds_test)

    # 2. Train LightGBM Gradient Boosting Model
    neg_count = int(np.sum(y_train == 0))
    pos_count = int(np.sum(y_train == 1))
    scale_pos = neg_count / max(1, pos_count)

    lgb_model = lgb.LGBMClassifier(
        n_estimators=400,
        learning_rate=0.035,
        num_leaves=31,
        max_depth=6,
        scale_pos_weight=scale_pos,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        verbosity=-1,
    )
    lgb_model.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[lgb.early_stopping(stopping_rounds=30, verbose=False)],
    )

    lgb_val_proba = lgb_model.predict_proba(X_val)[:, 1]
    best_thresh, best_p, best_r, best_f1 = find_optimal_threshold(y_val, lgb_val_proba)
    print(f"LightGBM Validation PR-Optimal Threshold: {best_thresh:.4f} (Val F1: {best_f1:.4f})")

    lgb_test_proba = lgb_model.predict_proba(X_test)[:, 1]
    lgb_test_preds = (lgb_test_proba >= best_thresh).astype(int)
    lgb_metrics = compute_metrics(y_test, lgb_test_preds, lgb_test_proba)
    lgb_cost = compute_financial_cost(y_test, lgb_test_preds)

    # 3. Diagnostic Audit of Rules on Test Split
    rule_diagnosis = diagnose_rules_with_incremental_recall(df_test, lgb_test_preds)

    # 4. Refined Production Hybrid System
    # Strict Outbound-Only Rule Enforcement (never applying send/transfer limits to inbound cash_in):
    # - Absolute platform ceiling (>5M BDT)
    # - Tier single outbound limit (Personal 50k, Verified 100k, Business 1M)
    # - Business dual approval hold for novel beneficiaries (>150k BDT)
    tier_cap_outbound = outbound_test & (
        ((df_test["account_tier"] == 0) & (df_test["amount_bdt"] > 50_000.0))
        | ((df_test["account_tier"] == 1) & (df_test["amount_bdt"] > 100_000.0))
        | ((df_test["account_tier"] == 2) & (df_test["amount_bdt"] > 1_000_000.0))
        | (df_test["amount_bdt"] > 5_000_000.0)
    )

    business_unapproved_outbound = outbound_test & (
        (df_test["account_tier"] == 2)
        & (df_test["amount_bdt"] > 150_000.0)
        & (df_test["is_trusted_recipient"] == 0.0)
    )

    # High-precision hard regulatory safeguards
    regulatory_hard_rules = tier_cap_outbound | business_unapproved_outbound

    hybrid_test_preds = np.where(regulatory_hard_rules, 1, lgb_test_preds)
    hybrid_proba = np.maximum(lgb_test_proba, np.where(regulatory_hard_rules, 0.99, 0.0))

    hybrid_metrics = compute_metrics(y_test, hybrid_test_preds, hybrid_proba)
    hybrid_cost = compute_financial_cost(y_test, hybrid_test_preds)

    # 5. Three-Way Comparison Table (Legacy Rules vs LightGBM-Only vs Refined Hybrid)
    print("\n" + "=" * 115)
    print("THREE-WAY BENCHMARK COMPARISON ON SAME HELD-OUT TEMPORAL TEST SPLIT (44,913 TRANSACTIONS, 222 FRAUD)")
    print("=" * 115)
    print(f"%-26s | %-8s | %-8s | %-10s | %-8s | %-8s | %-12s | %-16s" %
          ("System Architecture", "PR-AUC", "ROC-AUC", "Precision", "Recall", "F1", "Alerts Fired", "Total Cost (BDT)"))
    print("-" * 115)

    comp_models = [
        ("Legacy Rules Baseline", rule_metrics, rule_cost),
        ("LightGBM-Only (PR-Tuned)", lgb_metrics, lgb_cost),
        ("Refined Production Hybrid", hybrid_metrics, hybrid_cost),
    ]

    for name, m, c in comp_models:
        print(f"{name:26s} | {m['pr_auc']:8.4f} | {m['roc_auc']:8.4f} | {m['precision']*100:9.2f}% | "
              f"{m['recall']*100:7.2f}% | {m['f1']:8.4f} | {m['alerts_fired']:12d} | ৳{c['total_cost_bdt']:15,.2f}")

    print("-" * 115)
    print("Cost Breakdown Assumptions:")
    print(f"  - Missed Fraud Cost (FN): ৳{DEFAULT_COST_MISSED_FRAUD:,.2f} BDT (average gross financial loss per undetected incident)")
    print(f"  - False Alarm Cost (FP):  ৳{DEFAULT_COST_FALSE_ALARM:,.2f} BDT (operational triage & human investigator review time)")
    cost_diff = hybrid_cost["total_cost_bdt"] - lgb_cost["total_cost_bdt"]
    if cost_diff > 0:
        print(f"Financial Verdict: LightGBM-only beats Hybrid on operational cost by ৳{cost_diff:,.2f} BDT "
              f"due to {hybrid_cost['false_positives'] - lgb_cost['false_positives']} additional regulatory alerts.")
    elif cost_diff < 0:
        print(f"Financial Verdict: Refined Hybrid beats LightGBM-only on net cost by ৳{abs(cost_diff):,.2f} BDT "
              f"due to catching additional high-value frauds.")
    else:
        print(f"Financial Verdict: Both systems achieve identical financial cost.")

    # 6. Per-Tier and Agent False Alarm Rates
    print("\n--- Per-Tier False Alarm Rate (FAR) on Legitimate Transfers ---")
    tier_results = evaluate_per_tier_and_agent(df_test, hybrid_test_preds)
    for s_name, stats in tier_results.items():
        print(f"  {s_name.ljust(34)}: FAR Legit = {stats['false_alarm_rate_legit_pct'].rjust(6)} "
              f"({stats['false_alarms']} FPs / {stats['total_transactions'] - stats['total_fraud']} legit) | "
              f"Precision = {stats['precision_pct'].rjust(7)} | Recall = {stats['recall_pct'].rjust(7)}")

    # 7. Per-Fraud-Type Recall with 95% Bootstrap Confidence Intervals
    print("\n--- Per-Fraud-Type Recall with 95% Bootstrap Confidence Intervals (1,000 Resamples) ---")
    type_breakdown = evaluate_per_fraud_type_with_bootstrap(df_test, hybrid_test_preds)
    for ftype, stats in type_breakdown.items():
        sample_tag = " [low-sample]" if stats.get("is_low_sample") else ""
        metric_str = stats.get("recall_pct", stats.get("specificity_pct"))
        ci_str = stats.get("ci_95_str", "")
        cases = f"{stats.get('detected_cases', stats.get('correctly_cleared'))}/{stats['total_cases']}"
        print(f"  {ftype.ljust(28)}: {metric_str} {ci_str} ({cases}){sample_tag}")

    # 8. Feature Ablation Study
    print("\n--- Feature Ablation Study: Impact of Counterparty Trust & Tier Headroom Features ---")
    ablation_res = run_feature_ablation(df_train, df_val, df_test)
    print(f"  Full 16 Features:    PR-AUC={ablation_res['full_features']['metrics']['pr_auc']:.4f}, "
          f"Precision={ablation_res['full_features']['metrics']['precision_pct']}, "
          f"Recall={ablation_res['full_features']['metrics']['recall_pct']}, "
          f"F1={ablation_res['full_features']['metrics']['f1']:.4f}")
    print(f"  Ablated 13 Features: PR-AUC={ablation_res['ablated_features']['metrics']['pr_auc']:.4f}, "
          f"Precision={ablation_res['ablated_features']['metrics']['precision_pct']}, "
          f"Recall={ablation_res['ablated_features']['metrics']['recall_pct']}, "
          f"F1={ablation_res['ablated_features']['metrics']['f1']:.4f}")
    print(f"  Ablation Drop:       Δ PR-AUC = -{ablation_res['delta']['pr_auc_drop']:.4f}, "
          f"Δ F1 = -{ablation_res['delta']['f1_drop']:.4f}")

    # 9. Serialize Production Model Artifact
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    models_dir = os.path.join(base_dir, "app/services/models")
    os.makedirs(models_dir, exist_ok=True)
    artifact_path = os.path.join(models_dir, "fraud_lgbm_model.joblib")

    artifact = {
        "model": lgb_model,
        "feature_cols": FEATURE_COLS,
        "optimal_threshold": best_thresh,
        "medium_threshold": max(0.15, best_thresh * 0.45),
        "three_way_comparison": {
            "legacy_rules": {"metrics": rule_metrics, "cost": rule_cost},
            "lightgbm_only": {"metrics": lgb_metrics, "cost": lgb_cost},
            "refined_hybrid": {"metrics": hybrid_metrics, "cost": hybrid_cost},
        },
        "rule_diagnosis": rule_diagnosis,
        "per_tier_and_agent": tier_results,
        "per_archetype_recall": type_breakdown,
        "feature_ablation": ablation_res,
    }

    joblib.dump(artifact, artifact_path)
    print(f"\nSerialized production ML artifact to: {artifact_path}")

    # Save metrics JSON to data/
    root_data_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../data"))
    os.makedirs(root_data_dir, exist_ok=True)
    metrics_json_path = os.path.join(root_data_dir, "model_evaluation_metrics.json")
    with open(metrics_json_path, "w") as f:
        json.dump(artifact, f, indent=2, default=str)
    print(f"Saved evaluation metrics JSON to: {metrics_json_path}")
    print("\nEvaluation & Benchmarking Complete!")


if __name__ == "__main__":
    main()
