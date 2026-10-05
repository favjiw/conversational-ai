"""Conversation runner for Identity Drift experiment (PRD FR-2).

Generates 36 themes x 2 agents = 72 utterances per conversation,
using system prompt from paper Appendix B.2 and perspective-based role merging.
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Sequence
import yaml

from app.llm.client import LLMClient
from experiment.config import ExperimentConfig, ConditionConfig, resolve_path

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = (
    "You are now sharing your thoughts on the question with your partner.\n"
    "You only reply briefly to your thoughts only for a given question."
)


def resolve_path(p: str | Path) -> Path:
    """Resolve path whether running from repo root or backend folder."""
    path = Path(p)
    if path.exists():
        return path
    parts = path.parts
    if parts and parts[0] == "backend":
        sub = Path(*parts[1:])
        if sub.exists():
            return sub
    prefixed = Path("backend") / path
    if prefixed.exists():
        return prefixed
    return path


def load_themes(themes_path: str | Path) -> List[Dict[str, Any]]:
    """Load Aron 1997 themes from JSON file."""
    p = resolve_path(themes_path)
    if not p.exists():
        raise FileNotFoundError(f"Themes file not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def load_personas(personas_path: Optional[str | Path]) -> List[Dict[str, Any]]:
    """Load persona list from YAML file."""
    if not personas_path:
        return []
    p = resolve_path(personas_path)
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("personas", [])


def build_messages_for_agent(
    agent: Literal["A", "B"],
    theme_idx: int,
    history: List[Dict[str, Any]],
    themes: Sequence[Dict[str, Any]],
    system_prompt: str,
) -> List[Dict[str, str]]:
    """Build multi-turn messages from the perspective of agent A or B."""
    raw: List[Dict[str, str]] = []

    def q_str(idx: int) -> str:
        text = themes[idx]["text"]
        return f"Question {idx + 1} : {text}"

    if agent == "A":
        for k in range(theme_idx):
            a_ans = history[k]["agent_a"]
            b_ans = history[k]["agent_b"]
            raw.append({"role": "user", "content": q_str(k)})
            raw.append({"role": "assistant", "content": a_ans})
            raw.append({"role": "user", "content": b_ans})
        raw.append({"role": "user", "content": q_str(theme_idx)})
    else:  # agent B
        for k in range(theme_idx):
            a_ans = history[k]["agent_a"]
            b_ans = history[k]["agent_b"]
            raw.append({"role": "user", "content": q_str(k)})
            raw.append({"role": "user", "content": a_ans})
            raw.append({"role": "assistant", "content": b_ans})
        raw.append({"role": "user", "content": q_str(theme_idx)})
        a_curr = history[theme_idx]["agent_a"]
        raw.append({"role": "user", "content": a_curr})

    merged: List[Dict[str, str]] = []
    for m in raw:
        if merged and merged[-1]["role"] == "user" and m["role"] == "user":
            merged[-1]["content"] += "\n\n" + m["content"]
        else:
            merged.append(dict(m))

    return merged


def messages_to_prompt_text(messages: List[Dict[str, str]]) -> str:
    """Format message sequence into single prompt string."""
    chunks = []
    for msg in messages:
        chunks.append(f"{msg['role'].capitalize()}: {msg['content']}")
    return "\n\n".join(chunks)


class ExperimentConversationRunner:
    """Executes 36-theme Aron conversation between Agent A and Agent B."""

    def __init__(
        self,
        config: ExperimentConfig,
        client_a: LLMClient,
        client_b: LLMClient,
    ):
        self.config = config
        self.client_a = client_a
        self.client_b = client_b
        self.themes = load_themes(config.conversation.themes_file)

    async def run_single_conversation(
        self,
        condition: ConditionConfig,
        conv_idx: int,
        persona_a: Optional[Dict[str, Any]] = None,
        persona_b: Optional[Dict[str, Any]] = None,
        on_utterance: Optional[Any] = None,
        on_snapshot: Optional[Any] = None,
    ) -> List[Dict[str, Any]]:
        """Run 1 conversation (36 themes = 72 utterances) and record JSONL incrementally."""
        conv_id = f"conv_{conv_idx:02d}"
        log_dir = resolve_path(self.config.runtime.log_dir) / self.config.experiment_id / "conversations" / condition.condition_id
        log_dir.mkdir(parents=True, exist_ok=True)
        conv_file = log_dir / f"{conv_id}.jsonl"

        existing_records: List[Dict[str, Any]] = []
        if conv_file.exists():
            with open(conv_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        existing_records.append(json.loads(line))

        history: List[Dict[str, Any]] = []
        processed_turns = len(existing_records)
        completed_themes = processed_turns // 2

        for t in range(completed_themes):
            rec_a = existing_records[t * 2]
            rec_b = existing_records[t * 2 + 1]
            history.append({
                "theme_id": t + 1,
                "agent_a": rec_a["text"],
                "agent_b": rec_b["text"],
            })

        if processed_turns % 2 == 1:
            rec_a = existing_records[-1]
            history.append({
                "theme_id": completed_themes + 1,
                "agent_a": rec_a["text"],
                "agent_b": "",
            })

        sys_a = self.config.conversation.system_prompt
        sys_b = self.config.conversation.system_prompt
        if persona_a:
            sys_a = f"{persona_a.get('description', '')}\n\n{sys_a}"
        if persona_b:
            sys_b = f"{persona_b.get('description', '')}\n\n{sys_b}"

        with open(conv_file, "a", encoding="utf-8") as f_out:
            start_theme = completed_themes
            for theme_idx in range(start_theme, len(self.themes)):
                theme = self.themes[theme_idx]

                # Turn A
                if len(history) <= theme_idx or not history[theme_idx].get("agent_a"):
                    msgs_a = build_messages_for_agent("A", theme_idx, history, self.themes, sys_a)
                    prompt_a = messages_to_prompt_text(msgs_a)

                    resp_a = await self.client_a.generate(
                        prompt=prompt_a,
                        system_instruction=sys_a,
                        temperature=self.config.conversation.temperature,
                    )
                    text_a = (
                        resp_a.parsed.get("text")
                        if (isinstance(resp_a.parsed, dict) and "text" in resp_a.parsed)
                        else resp_a.raw
                    ).strip()

                    record_a = {
                        "experiment_id": self.config.experiment_id,
                        "condition_id": condition.condition_id,
                        "conv_id": conv_id,
                        "theme_idx": theme_idx,
                        "theme_id": theme["id"],
                        "agent": "A",
                        "role": "agent_1",
                        "text": text_a,
                        "model": resp_a.model,
                        "temperature": self.config.conversation.temperature,
                        "persona_id": persona_a.get("id") if persona_a else None,
                        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "latency_ms": resp_a.latency_ms,
                        "tokens_in": resp_a.input_tokens,
                        "tokens_out": resp_a.output_tokens,
                    }
                    f_out.write(json.dumps(record_a, ensure_ascii=False) + "\n")
                    f_out.flush()
                    existing_records.append(record_a)
                    if len(history) <= theme_idx:
                        history.append({"theme_id": theme["id"], "agent_a": text_a, "agent_b": ""})
                    else:
                        history[theme_idx]["agent_a"] = text_a

                    if on_utterance:
                        await on_utterance(record_a)

                # Turn B
                if not history[theme_idx].get("agent_b"):
                    msgs_b = build_messages_for_agent("B", theme_idx, history, self.themes, sys_b)
                    prompt_b = messages_to_prompt_text(msgs_b)

                    resp_b = await self.client_b.generate(
                        prompt=prompt_b,
                        system_instruction=sys_b,
                        temperature=self.config.conversation.temperature,
                    )
                    text_b = (
                        resp_b.parsed.get("text")
                        if (isinstance(resp_b.parsed, dict) and "text" in resp_b.parsed)
                        else resp_b.raw
                    ).strip()

                    record_b = {
                        "experiment_id": self.config.experiment_id,
                        "condition_id": condition.condition_id,
                        "conv_id": conv_id,
                        "theme_idx": theme_idx,
                        "theme_id": theme["id"],
                        "agent": "B",
                        "role": "agent_2",
                        "text": text_b,
                        "model": resp_b.model,
                        "temperature": self.config.conversation.temperature,
                        "persona_id": persona_b.get("id") if persona_b else None,
                        "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "latency_ms": resp_b.latency_ms,
                        "tokens_in": resp_b.input_tokens,
                        "tokens_out": resp_b.output_tokens,
                    }
                    f_out.write(json.dumps(record_b, ensure_ascii=False) + "\n")
                    f_out.flush()
                    existing_records.append(record_b)
                    history[theme_idx]["agent_b"] = text_b

                    if on_utterance:
                        await on_utterance(record_b)

                curr_theme_num = theme_idx + 1
                if curr_theme_num in self.config.questionnaire.snapshots:
                    if on_snapshot:
                        await on_snapshot(
                            conv_id=conv_id,
                            snapshot_theme=curr_theme_num,
                            history=list(history),
                            condition=condition,
                            persona_a=persona_a,
                            persona_b=persona_b,
                        )

        return existing_records

