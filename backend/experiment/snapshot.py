"""Snapshot and questionnaire executor (PRD FR-3)."""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from app.llm.client import LLMClient
from experiment.config import ExperimentConfig, ConditionConfig
from experiment.scoring import (
    load_all_questionnaires,
    parse_likert_response,
    compute_factor_scores,
    resolve_path,
)

logger = logging.getLogger(__name__)

SNAPSHOT_SYSTEM_TEMPLATE = (
    "Your name is assistant.\n"
    "Considering the next conversation between user and assistant,\n"
    "answer given descriptions.\n"
    "------\n"
    "{chathistory}\n"
    "------\n"
    "{questionnaire_setup}"
)


def format_chathistory(history: List[Dict[str, Any]], agent: Literal["A", "B"]) -> str:
    """Format conversation transcript up to the current snapshot from agent's perspective."""
    lines = []
    for h in history:
        t_id = h.get("theme_id", 0)
        lines.append(f"[Theme {t_id}]")
        if agent == "A":
            lines.append(f"assistant: {h.get('agent_a', '')}")
            lines.append(f"user: {h.get('agent_b', '')}")
        else:
            lines.append(f"user: {h.get('agent_a', '')}")
            lines.append(f"assistant: {h.get('agent_b', '')}")
    return "\n".join(lines)


def format_questionnaire_setup(q_def: Dict[str, Any]) -> str:
    """Format items and instruction into setup text."""
    lines = [
        f"Questionnaire: {q_def['name']}",
        f"Instruction: {q_def['instruction']}",
        f"Scale: {q_def['scale_min']} to {q_def['scale_max']}",
        "Please provide your ratings for each item in JSON format: {\"1\": rating, \"2\": rating, ...}\n",
        "Items:",
    ]
    for item in q_def["items"]:
        lines.append(f"{item['id']}. {item['text']}")
    return "\n".join(lines)


class SnapshotEngine:
    """Executes snapshots at theme 12, 24, 36 for measured agents."""

    def __init__(
        self,
        config: ExperimentConfig,
        client_a: LLMClient,
        client_b: LLMClient,
    ):
        self.config = config
        self.client_a = client_a
        self.client_b = client_b
        self.questionnaires = load_all_questionnaires()

    async def run_snapshot_for_conversation(
        self,
        conv_id: str,
        snapshot_theme: int,
        history: List[Dict[str, Any]],
        condition: ConditionConfig,
        persona_a: Optional[Dict[str, Any]] = None,
        persona_b: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run all questionnaires for specified agents at a snapshot point."""
        log_dir = resolve_path(self.config.runtime.log_dir) / self.config.experiment_id / "questionnaires" / condition.condition_id
        log_dir.mkdir(parents=True, exist_ok=True)
        q_file = log_dir / f"{conv_id}.jsonl"

        records: List[Dict[str, Any]] = []
        repeats = self.config.questionnaire.repeats
        agents_to_measure = ["A", "B"] if "both" in self.config.questionnaire.agents_measured or set(self.config.questionnaire.agents_measured) == {"A", "B"} else self.config.questionnaire.agents_measured

        include_list = self.config.questionnaire.include
        active_q_keys = list(self.questionnaires.keys()) if "all" in include_list else [k for k in self.questionnaires if k in include_list]

        with open(q_file, "a", encoding="utf-8") as f_out:
            for agent_code in agents_to_measure:
                client = self.client_a if agent_code == "A" else self.client_b
                chathistory = format_chathistory(history, agent_code)

                for q_key in active_q_keys:
                    q_def = self.questionnaires[q_key]
                    q_setup = format_questionnaire_setup(q_def)
                    num_items = len(q_def["items"])
                    scale_min = q_def["scale_min"]
                    scale_max = q_def["scale_max"]

                    prompt = SNAPSHOT_SYSTEM_TEMPLATE.format(
                        chathistory=chathistory,
                        questionnaire_setup=q_setup,
                    )

                    for rep in range(1, repeats + 1):
                        retries = 0
                        parse_ok = False
                        raw_reply = ""
                        answers: Dict[int, float] = {}

                        while retries <= self.config.questionnaire.max_retries and not parse_ok:
                            try:
                                resp = await client.generate(
                                    prompt=prompt,
                                    temperature=self.config.questionnaire.temperature,
                                )
                                raw_reply = resp.raw or (json.dumps(resp.parsed) if resp.parsed else "")
                                answers, parse_ok = parse_likert_response(raw_reply, num_items, scale_min, scale_max)
                                if not parse_ok:
                                    retries += 1
                                    await asyncio.sleep(0.01)
                            except Exception as ex:
                                retries += 1
                                raw_reply = f"ERROR: {str(ex)}"
                                await asyncio.sleep(0.01)

                        factor_scores = compute_factor_scores(q_def, answers)

                        rec = {
                            "experiment_id": self.config.experiment_id,
                            "condition_id": condition.condition_id,
                            "conv_id": conv_id,
                            "agent": agent_code,
                            "snapshot": snapshot_theme,
                            "questionnaire": q_key,
                            "repeat": rep,
                            "raw_response": raw_reply[:500],
                            "answers": {str(k): v for k, v in answers.items()},
                            "scores": factor_scores,
                            "parse_ok": parse_ok,
                            "retries": retries,
                            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        }
                        f_out.write(json.dumps(rec, ensure_ascii=False) + "\n")
                        f_out.flush()
                        records.append(rec)

        return records

