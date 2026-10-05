"""Automated reporting for Identity Drift experiments (PRD FR-9).

Generates report.md and report.json summarizing Table 3, detailed tables,
topic models, and pronoun shift dynamics.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from experiment.config import ExperimentConfig, resolve_path
from experiment.scoring import load_all_questionnaires
from experiment.stats import (
    analyze_condition_drift,
    export_table_3_summary,
    export_table_detailed,
)
from experiment.topics import run_topic_modeling

logger = logging.getLogger(__name__)


def generate_experiment_report(
    experiment_dir: str | Path,
    config: Optional[ExperimentConfig] = None,
) -> Path:
    """Read experiment logs, compute stats, topics, and write report.md and report.json."""
    exp_path = resolve_path(experiment_dir)
    if not exp_path.exists():
        raise FileNotFoundError(f"Experiment directory not found: {exp_path}")

    conv_dir = exp_path / "conversations"
    q_dir = exp_path / "questionnaires"
    questionnaires_meta = load_all_questionnaires()

    all_conditions_summary: Dict[str, Dict[str, Any]] = {}
    detailed_per_condition: Dict[str, List[Dict[str, Any]]] = {}
    topics_per_condition: Dict[str, Dict[str, Any]] = {}

    total_conversations = 0
    total_utterances = 0

    # Process each condition
    if q_dir.exists():
        for cond_folder in q_dir.iterdir():
            if not cond_folder.is_dir():
                continue
            cond_id = cond_folder.name
            q_records: List[Dict[str, Any]] = []

            for q_file in cond_folder.glob("*.jsonl"):
                with open(q_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            q_records.append(json.loads(line))

            if q_records:
                cond_res = analyze_condition_drift(q_records, questionnaires_meta)
                all_conditions_summary[cond_id] = cond_res
                detailed_per_condition[cond_id] = cond_res["factors"]

                # Export detailed table CSV
                det_csv_path = exp_path / f"table_detailed_{cond_id}.csv"
                export_table_detailed(cond_id, cond_res["factors"], det_csv_path)

    # Process conversation utterances for topics
    if conv_dir.exists():
        for cond_folder in conv_dir.iterdir():
            if not cond_folder.is_dir():
                continue
            cond_id = cond_folder.name
            utterances: List[Dict[str, Any]] = []
            for conv_file in cond_folder.glob("*.jsonl"):
                total_conversations += 1
                with open(conv_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            u = json.loads(line)
                            utterances.append(u)
                            total_utterances += 1

            if utterances:
                topics_per_condition[cond_id] = run_topic_modeling(utterances)

    # Export Table 3 CSV and Markdown
    table3_csv = exp_path / "table3_summary.csv"
    table3_md = exp_path / "table3_summary.md"
    table3_df = export_table_3_summary(all_conditions_summary, table3_csv, table3_md)

    # Build report.md
    report_md_lines = [
        f"# Identity Drift Measurement Report: {exp_path.name}",
        "",
        "## 1. Executive Summary",
        f"- **Experiment Directory**: `{exp_path}`",
        f"- **Total Conditions**: {len(all_conditions_summary)}",
        f"- **Total Conversations**: {total_conversations}",
        f"- **Total Utterances**: {total_utterances}",
        "",
        "## 2. Table 3: Identity Consistency Across Aspects",
        "A factor is marked consistent (✓) if change across snapshots 12, 24, 36 is non-significant in both omnibus and post-hoc tests.",
        "",
        table3_df.to_markdown(index=False) if not table3_df.empty else "_No condition records found._",
        "",
        "## 3. Pronoun Dynamics (Choi et al. §5.3)",
    ]

    for cond_id, t_info in topics_per_condition.items():
        pronouns = t_info.get("pronouns", {}).get("pronouns", {})
        report_md_lines.extend([
            f"### Condition: `{cond_id}`",
            f"- **1st-Person Singular**: {pronouns.get('first_singular', {}).get('rate_per_1000_words', 0)} per 1000 words ({pronouns.get('first_singular', {}).get('count', 0)} occurrences)",
            f"- **1st-Person Plural**: {pronouns.get('first_plural', {}).get('rate_per_1000_words', 0)} per 1000 words ({pronouns.get('first_plural', {}).get('count', 0)} occurrences)",
            f"- **2nd-Person**: {pronouns.get('second_person', {}).get('rate_per_1000_words', 0)} per 1000 words ({pronouns.get('second_person', {}).get('count', 0)} occurrences)",
            "",
            "#### Top Emergent Topics:",
        ])
        for top in t_info.get("topics", [])[:5]:
            report_md_lines.append(f"- **Topic {top['topic_id']}** (size={top['count']}): {', '.join(top['keywords'])}")
        report_md_lines.append("")

    report_md_path = exp_path / "report.md"
    report_md_path.write_text("\n".join(report_md_lines), encoding="utf-8")

    # Build report.json
    report_json_path = exp_path / "report.json"
    report_data = {
        "experiment_id": exp_path.name,
        "total_conversations": total_conversations,
        "total_utterances": total_utterances,
        "table3": table3_df.to_dict(orient="records"),
        "conditions": all_conditions_summary,
        "topics": topics_per_condition,
    }
    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2, ensure_ascii=False)

    return report_md_path
