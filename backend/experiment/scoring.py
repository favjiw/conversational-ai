"""Scoring engine for 14 questionnaires (40 factors) - PRD FR-4."""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def resolve_path(p: str | Path) -> Path:
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


def load_all_questionnaires(q_dir: str | Path = "backend/experiment/questionnaires") -> Dict[str, Dict[str, Any]]:
    """Load all questionnaire definition files."""
    d = resolve_path(q_dir)
    if not d.exists() or not d.is_dir():
        raise FileNotFoundError(f"Questionnaires directory not found: {d}")
    out = {}
    for f in d.glob("*.json"):
        with open(f, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            out[data["id"]] = data
    return out


def parse_likert_response(raw_text: str, num_items: int, scale_min: int, scale_max: int) -> Tuple[Dict[int, float], bool]:
    """Parse questionnaire item responses from LLM raw text.

    Supports JSON objects `{"1": 4, ...}`, item lines `1: 4`, or CSV arrays `[4, 5, 2, ...]`.
    Returns (item_scores_dict, is_parse_ok).
    """
    scores: Dict[int, float] = {}

    # 1. Try direct JSON parsing
    try:
        # Find JSON object block
        json_match = re.search(r"\{[^{}]*\}", raw_text)
        if json_match:
            data = json.loads(json_match.group(0))
            for k, v in data.items():
                try:
                    item_id = int(str(k).replace("item_", "").replace("item", "").replace("q", ""))
                    val = float(v)
                    if scale_min <= val <= scale_max:
                        scores[item_id] = val
                except (ValueError, TypeError):
                    continue
            if len(scores) >= int(num_items * 0.75):
                return scores, True
    except Exception:
        pass

    # 2. Try regex line patterns: e.g. "1. 4", "Item 1: 5", "1: 4"
    pattern = re.compile(r"(?:Item\s*|Q\s*)?(\d+)[\s.:\-=]+([0-9]+(?:\.[0-9]+)?)")
    for line in raw_text.splitlines():
        line = line.strip()
        m = pattern.search(line)
        if m:
            try:
                item_id = int(m.group(1))
                val = float(m.group(2))
                if 1 <= item_id <= num_items and scale_min <= val <= scale_max:
                    scores[item_id] = val
            except (ValueError, IndexError):
                continue

    if len(scores) >= int(num_items * 0.75):
        return scores, True

    # 3. Try bracketed list `[4, 3, 2, 5, ...]`
    bracket_match = re.search(r"\[([0-9.,\s]+)\]", raw_text)
    if bracket_match:
        vals = [v.strip() for v in bracket_match.group(1).split(",") if v.strip()]
        for idx, v in enumerate(vals, start=1):
            try:
                fval = float(v)
                if scale_min <= fval <= scale_max:
                    scores[idx] = fval
            except ValueError:
                pass
        if len(scores) >= int(num_items * 0.75):
            return scores, True

    # Return partial or failed
    return scores, len(scores) == num_items


def compute_factor_scores(
    q_def: Dict[str, Any],
    item_answers: Dict[int, float],
) -> Dict[str, float]:
    """Calculate aggregated factor scores applying reverse scoring."""
    scale_min = q_def["scale_min"]
    scale_max = q_def["scale_max"]
    aggregation = q_def.get("aggregation", "mean")
    item_map = {item["id"]: item for item in q_def["items"]}

    factor_scores: Dict[str, float] = {}

    for factor_name, item_ids in q_def["subscales"].items():
        sub_vals = []
        for i_id in item_ids:
            if i_id in item_answers:
                raw_v = item_answers[i_id]
                item_meta = item_map.get(i_id, {})
                if item_meta.get("reverse", False):
                    scored_v = (scale_min + scale_max) - raw_v
                else:
                    scored_v = raw_v
                sub_vals.append(scored_v)

        if sub_vals:
            if aggregation == "sum":
                factor_scores[factor_name] = round(sum(sub_vals), 4)
            else:
                factor_scores[factor_name] = round(sum(sub_vals) / len(sub_vals), 4)
        else:
            factor_scores[factor_name] = float("nan")

    return factor_scores
