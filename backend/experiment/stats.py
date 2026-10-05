"""Statistical analysis of Identity Drift questionnaires (PRD FR-5).

Implements:
1. Shapiro-Wilk test for normality per factor across runs.
2. RM-ANOVA (normal) or Friedman test (non-normal) across snapshots (12, 24, 36).
3. Post-hoc: Paired t-tests or Wilcoxon signed-rank with Bonferroni correction.
4. Drift consistency criteria: consistent (✓) if omnibus AND post-hoc p >= alpha.
5. Export Table 3 (aspect summary) and Table 10-15 (detailed subscale statistics).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import scipy.stats as ss

logger = logging.getLogger(__name__)


def compute_rm_anova(df: pd.DataFrame, subject_col: str, within_col: str, value_col: str) -> Tuple[float, float]:
    """Compute 1-way repeated-measures ANOVA (F-stat, p-value)."""
    try:
        import pingouin as pg
        res = pg.rm_anova(data=df, dv=value_col, within=within_col, subject=subject_col)
        f_val = float(res["F"].iloc[0])
        p_val = float(res["p-unc"].iloc[0])
        return round(f_val, 4), round(p_val, 5)
    except Exception:
        # Fallback to exact one-way RM-ANOVA calculation
        piv = df.pivot(index=subject_col, columns=within_col, values=value_col)
        piv = piv.dropna()
        n, k = piv.shape
        if n < 2 or k < 2:
            return 0.0, 1.0

        grand_mean = piv.values.mean()
        ss_total = np.sum((piv.values - grand_mean) ** 2)
        ss_subj = k * np.sum((piv.mean(axis=1) - grand_mean) ** 2)
        ss_time = n * np.sum((piv.mean(axis=0) - grand_mean) ** 2)
        ss_err = max(ss_total - ss_subj - ss_time, 1e-12)

        df_time = k - 1
        df_err = (n - 1) * (k - 1)
        if df_err <= 0:
            return 0.0, 1.0

        ms_time = ss_time / df_time
        ms_err = ss_err / df_err
        f_val = ms_time / ms_err if ms_err > 0 else 0.0
        p_val = 1.0 - ss.f.cdf(f_val, df_time, df_err)
        return round(float(f_val), 4), round(float(p_val), 5)


def check_normality(values: np.ndarray) -> bool:
    """Test normality with Shapiro-Wilk at alpha=0.05. Return True if normal."""
    if len(values) < 3:
        return True
    # If all values are identical
    if np.all(values == values[0]):
        return True
    try:
        stat, p = ss.shapiro(values)
        return bool(p >= 0.05)
    except Exception:
        return True


def compute_factor_drift(
    records: List[Dict[str, Any]],
    factor_name: str,
    aspect_name: str,
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Compute drift statistics for a single factor across snapshots (12, 24, 36)."""
    data_points = []
    for r in records:
        if factor_name in r.get("scores", {}):
            val = r["scores"][factor_name]
            if val is not None and not np.isnan(val):
                data_points.append({
                    "conv_id": r["conv_id"],
                    "snapshot": r["snapshot"],
                    "score": float(val),
                })

    if not data_points:
        return {}

    df = pd.DataFrame(data_points)
    agg = df.groupby(["conv_id", "snapshot"])["score"].mean().reset_index()

    piv = agg.pivot(index="conv_id", columns="snapshot", values="score").dropna()
    snapshots = sorted([c for c in piv.columns if c in (12, 24, 36)])
    if len(snapshots) < 2 or len(piv) < 2:
        return {
            "factor": factor_name,
            "aspect": aspect_name,
            "test_type": "insufficient_data",
            "omnibus_stat": 0.0,
            "omnibus_p": 1.0,
            "is_normal": True,
            "consistent": True,
            "means": {str(s): float(piv[s].mean()) for s in snapshots} if len(snapshots) > 0 else {},
            "posthoc": {},
        }

    s12 = piv[12].values if 12 in piv.columns else np.array([])
    s24 = piv[24].values if 24 in piv.columns else np.array([])
    s36 = piv[36].values if 36 in piv.columns else np.array([])

    all_vals = np.concatenate([s for s in (s12, s24, s36) if len(s) > 0])
    is_normal = check_normality(all_vals)

    posthoc = {}
    consistent = True

    if is_normal and len(snapshots) == 3:
        test_type = "RM-ANOVA"
        f_stat, omnibus_p = compute_rm_anova(agg, subject_col="conv_id", within_col="snapshot", value_col="score")
        if omnibus_p < alpha:
            consistent = False

        pairs = [(12, 24, s12, s24), (24, 36, s24, s36), (12, 36, s12, s36)]
        for s_a, s_b, arr_a, arr_b in pairs:
            if len(arr_a) > 1 and len(arr_b) > 1:
                try:
                    t_res = ss.ttest_rel(arr_a, arr_b)
                    p_adj = min(1.0, float(t_res.pvalue) * 3)
                    posthoc[f"{s_a}_{s_b}"] = {"p": round(float(t_res.pvalue), 4), "p_adj": round(p_adj, 4)}
                    if p_adj < alpha:
                        consistent = False
                except Exception:
                    posthoc[f"{s_a}_{s_b}"] = {"p": 1.0, "p_adj": 1.0}
    else:
        test_type = "Friedman"
        try:
            if len(snapshots) == 3:
                f_res = ss.friedmanchisquare(s12, s24, s36)
                f_stat = round(float(f_res.statistic), 4)
                omnibus_p = round(float(f_res.pvalue), 5)
            else:
                f_stat, omnibus_p = 0.0, 1.0
        except Exception:
            f_stat, omnibus_p = 0.0, 1.0

        if omnibus_p < alpha:
            consistent = False

        pairs = [(12, 24, s12, s24), (24, 36, s24, s36), (12, 36, s12, s36)]
        for s_a, s_b, arr_a, arr_b in pairs:
            if len(arr_a) > 1 and len(arr_b) > 1:
                if np.all(arr_a == arr_b):
                    posthoc[f"{s_a}_{s_b}"] = {"p": 1.0, "p_adj": 1.0}
                else:
                    try:
                        w_res = ss.wilcoxon(arr_a, arr_b)
                        p_adj = min(1.0, float(w_res.pvalue) * 3)
                        posthoc[f"{s_a}_{s_b}"] = {"p": round(float(w_res.pvalue), 4), "p_adj": round(p_adj, 4)}
                        if p_adj < alpha:
                            consistent = False
                    except Exception:
                        posthoc[f"{s_a}_{s_b}"] = {"p": 1.0, "p_adj": 1.0}

    return {
        "factor": factor_name,
        "aspect": aspect_name,
        "test_type": test_type,
        "omnibus_stat": f_stat,
        "omnibus_p": omnibus_p,
        "is_normal": is_normal,
        "consistent": consistent,
        "means": {
            "12": round(float(s12.mean()), 3) if len(s12) > 0 else 0.0,
            "24": round(float(s24.mean()), 3) if len(s24) > 0 else 0.0,
            "36": round(float(s36.mean()), 3) if len(s36) > 0 else 0.0,
        },
        "posthoc": posthoc,
    }


def analyze_condition_drift(
    records: List[Dict[str, Any]],
    questionnaires_meta: Dict[str, Dict[str, Any]],
    alpha: float = 0.05,
) -> Dict[str, Any]:
    """Run omnibus + post-hoc tests on all factors across all 4 aspects."""
    aspect_counts = {"personality": 0, "interpersonal": 0, "motivation": 0, "emotion": 0}
    aspect_consistent = {"personality": 0, "interpersonal": 0, "motivation": 0, "emotion": 0}
    factor_results = []

    # Map each factor to questionnaire and aspect
    for q_id, q_def in questionnaires_meta.items():
        aspect = q_def["aspect"]
        for factor in q_def["subscales"].keys():
            res = compute_factor_drift(records, factor, aspect, alpha=alpha)
            if res:
                factor_results.append(res)
                aspect_counts[aspect] += 1
                if res["consistent"]:
                    aspect_consistent[aspect] += 1

    return {
        "factors": factor_results,
        "summary": {
            "personality": f"{aspect_consistent['personality']}/{aspect_counts['personality']}",
            "interpersonal": f"{aspect_consistent['interpersonal']}/{aspect_counts['interpersonal']}",
            "motivation": f"{aspect_consistent['motivation']}/{aspect_counts['motivation']}",
            "emotion": f"{aspect_consistent['emotion']}/{aspect_counts['emotion']}",
            "total": f"{sum(aspect_consistent.values())}/{sum(aspect_counts.values())}",
        },
    }


def export_table_3_summary(
    all_conditions_summary: Dict[str, Dict[str, Any]],
    output_csv_path: str | Path,
    output_md_path: Optional[str | Path] = None,
) -> pd.DataFrame:
    """Export Table 3 format (condition vs 4 aspects + total consistent count)."""
    rows = []
    for cond_id, data in all_conditions_summary.items():
        summ = data.get("summary", {})
        rows.append({
            "Condition": cond_id,
            "Personality (12)": summ.get("personality", "0/12"),
            "Interpersonal (17)": summ.get("interpersonal", "0/17"),
            "Motivation (5)": summ.get("motivation", "0/5"),
            "Emotion (6)": summ.get("emotion", "0/6"),
            "Total (40)": summ.get("total", "0/40"),
        })

    df = pd.DataFrame(rows)
    out_csv = Path(output_csv_path)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)

    if output_md_path:
        out_md = Path(output_md_path)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(df.to_markdown(index=False), encoding="utf-8")

    return df


def export_table_detailed(
    condition_id: str,
    factor_results: List[Dict[str, Any]],
    output_csv_path: str | Path,
) -> pd.DataFrame:
    """Export detailed subscale statistics (like Tables 10-15 in paper)."""
    rows = []
    for f in factor_results:
        means = f.get("means", {})
        posthoc = f.get("posthoc", {})
        rows.append({
            "Factor": f["factor"],
            "Aspect": f["aspect"],
            "Test": f["test_type"],
            "Omnibus_Stat": f["omnibus_stat"],
            "Omnibus_p": f["omnibus_p"],
            "Consistent": "✓" if f["consistent"] else "✗",
            "Mean_12": means.get("12", 0.0),
            "Mean_24": means.get("24", 0.0),
            "Mean_36": means.get("36", 0.0),
            "p_12_24": posthoc.get("12_24", {}).get("p_adj", 1.0),
            "p_24_36": posthoc.get("24_36", {}).get("p_adj", 1.0),
            "p_12_36": posthoc.get("12_36", {}).get("p_adj", 1.0),
        })
    df = pd.DataFrame(rows)
    out_p = Path(output_csv_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_p, index=False)
    return df

