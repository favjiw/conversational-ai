"""Command-line interface and entry point for Identity Drift experiment (PRD FR-1, FR-6)."""
from __future__ import annotations

import argparse
import asyncio
import datetime
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.llm.client import LLMClient, MockLLMClient, GeminiLLMClient
from app.config import get_settings
from experiment.config import (
    ExperimentConfig,
    ConditionConfig,
    load_config,
    resolve_path,
)
from experiment.runner import (
    load_personas,
    ExperimentConversationRunner,
)
from experiment.snapshot import SnapshotEngine
from experiment.scoring import load_all_questionnaires
from experiment.report import generate_experiment_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("experiment")


def estimate_calls(config: ExperimentConfig) -> Dict[str, Any]:
    """Estimate total API calls and tokens for the experiment."""
    q_meta = load_all_questionnaires()
    total_q_included = len(q_meta) if "all" in config.questionnaire.include else len(config.questionnaire.include)
    n_snapshots = len(config.questionnaire.snapshots)
    agents_count = len(config.questionnaire.agents_measured)
    repeats = config.questionnaire.repeats

    total_conv_calls = 0
    total_q_calls = 0

    for cond in config.conditions:
        n_runs = cond.n_runs
        conv_calls = n_runs * 36 * 2  # 72 turns per run
        q_calls = n_runs * n_snapshots * agents_count * total_q_included * repeats
        total_conv_calls += conv_calls
        total_q_calls += q_calls

    grand_total = total_conv_calls + total_q_calls
    return {
        "conditions_count": len(config.conditions),
        "conversation_calls": total_conv_calls,
        "questionnaire_calls": total_q_calls,
        "grand_total_calls": grand_total,
        "estimated_hours_concurrency_1": round(grand_total * 2.0 / 3600, 2),
    }


def create_llm_client(model_id: str, config: ExperimentConfig, force_mock: bool = False) -> LLMClient:
    """Instantiate appropriate LLM client."""
    if force_mock or config.runtime.llm_mode == "mock":
        return MockLLMClient(default_model=model_id)

    model_def = next((m for m in config.models if m.id == model_id), None)
    if not model_def:
        return MockLLMClient(default_model=model_id)

    if model_def.provider == "mock":
        return MockLLMClient(default_model=model_def.model_name)

    api_key = os.getenv(model_def.api_key_env) or get_settings().gemini_api_key
    fail_inject = bool(config.runtime.fail_inject == "llm")
    return GeminiLLMClient(
        api_key=api_key,
        default_model=model_def.model_name,
        fail_inject=fail_inject,
    )


async def run_experiment(
    config: ExperimentConfig,
    force_mock: bool = False,
    resume: bool = False,
) -> Path:
    """Run full experiment across all conditions and write audit log + report."""
    exp_dir = resolve_path(config.runtime.log_dir) / config.experiment_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    # Save experiment config snapshot
    config_snapshot = exp_dir / "config_snapshot.json"
    with open(config_snapshot, "w", encoding="utf-8") as f:
        f.write(config.model_dump_json(indent=2))

    logger.info("Starting Experiment: %s (profile=%s)", config.experiment_id, config.profile)

    for condition in config.conditions:
        logger.info("Executing Condition: %s (%s, runs=%d)", condition.condition_id, condition.persona_type, condition.n_runs)
        client_a = create_llm_client(condition.model_id, config, force_mock)
        client_b = create_llm_client(condition.model_id, config, force_mock)

        conv_runner = ExperimentConversationRunner(config, client_a, client_b)
        snap_engine = SnapshotEngine(config, client_a, client_b)

        personas = load_personas(condition.persona_file) if condition.persona_file else []

        for r in range(1, condition.n_runs + 1):
            logger.info("Run %d/%d for condition %s", r, condition.n_runs, condition.condition_id)

            # Pair personas if RQ2
            p_a, p_b = None, None
            if personas and len(personas) >= 2:
                idx_a = ((r - 1) * 2) % len(personas)
                idx_b = ((r - 1) * 2 + 1) % len(personas)
                p_a = personas[idx_a]
                p_b = personas[idx_b]

            async def handle_snapshot(conv_id, snapshot_theme, history, **kwargs):
                logger.info("Running snapshot at theme %d for %s", snapshot_theme, conv_id)
                await snap_engine.run_snapshot_for_conversation(
                    conv_id=conv_id,
                    snapshot_theme=snapshot_theme,
                    history=history,
                    condition=condition,
                    persona_a=p_a,
                    persona_b=p_b,
                )

            await conv_runner.run_single_conversation(
                condition=condition,
                conv_idx=r,
                persona_a=p_a,
                persona_b=p_b,
                on_snapshot=handle_snapshot,
            )

    logger.info("Generating report for experiment: %s", config.experiment_id)
    report_path = generate_experiment_report(exp_dir, config)
    logger.info("Report written to %s", report_path)
    return report_path


def main():
    parser = argparse.ArgumentParser(description="Identity Drift Experiment CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_p = subparsers.add_parser("run", help="Run experiment batch")
    run_p.add_argument("--config", required=True, help="Path to config YAML")
    run_p.add_argument("--mock", action="store_true", help="Force mock LLM mode")
    run_p.add_argument("--resume", action="store_true", help="Resume from checkpoint")

    # estimate command
    est_p = subparsers.add_parser("estimate", help="Estimate API calls and tokens")
    est_p.add_argument("--config", required=True, help="Path to config YAML")

    # report command
    rep_p = subparsers.add_parser("report", help="Generate report from existing logs")
    rep_p.add_argument("--dir", required=True, help="Experiment log directory")

    args = parser.parse_args()

    if args.command == "estimate":
        cfg = load_config(args.config)
        est = estimate_calls(cfg)
        print(json.dumps(est, indent=2))

    elif args.command == "report":
        p = generate_experiment_report(args.dir)
        print(f"Report generated: {p}")

    elif args.command == "run":
        cfg = load_config(args.config)
        asyncio.run(run_experiment(cfg, force_mock=args.mock, resume=args.resume))


if __name__ == "__main__":
    main()

