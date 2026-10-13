"""Naturalness metrics module (PRD v1.1 FR-11).

Measures, on any JSONL session log (and optionally a reference transcript),
the repetition/echo/laughter patterns that made Live Mode sound unnatural.

Usage:
    python -m experiment.naturalness --session logs/session_X.jsonl \
        [--reference data/reference/hits-sore.txt] [--out report.md]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Optional


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _trigrams(text: str) -> list[str]:
    toks = _tokens(text)
    if len(toks) < 3:
        return []
    return [" ".join(toks[i:i + 3]) for i in range(len(toks) - 2)]


def _opener(text: str) -> str:
    toks = _tokens(text)
    return " ".join(toks[:3]) if len(toks) >= 3 else ""


def _closer(text: str) -> str:
    toks = _tokens(text)
    return " ".join(toks[-3:]) if len(toks) >= 3 else ""


def _is_question(text: str) -> bool:
    return text.rstrip().endswith("?")


def _mentions_listener(text: str) -> bool:
    lower = text.lower()
    return any(k in lower for k in ("sobat pendengar", "kalian", "pendengar", "teman-teman", "sobat hits"))


LAUGH_PATTERNS = ["hahaha", "hehe", "hihi", "wkwk", "wkwkwk"]


def _written_laughter(text: str) -> bool:
    lower = text.lower()
    return any(p in lower for p in LAUGH_PATTERNS)


def _word_count(text: str) -> int:
    return len(_tokens(text))


def compute_metrics(turns: list[dict]) -> dict[str, Any]:
    """Compute the naturalness metrics over a list of turn dicts.

    Each turn is expected to have ``persona`` and ``text`` (or ``final_text``).
    """
    persona_texts: dict[str, list[str]] = {}
    for t in turns:
        text = t.get("final_text") or t.get("text") or ""
        persona = t.get("persona") or "unknown"
        persona_texts.setdefault(persona, []).append(text)

    # 1. Top opener share per persona
    top_opener_share: dict[str, dict[str, Any]] = {}
    for persona, texts in persona_texts.items():
        openers = [o for o in (_opener(t) for t in texts) if o]
        if openers:
            top, count = Counter(openers).most_common(1)[0]
            top_opener_share[persona] = {
                "top_opener": top,
                "count": count,
                "share": count / len(openers),
            }

    # 2. Catchphrase phrases per turn
    catchphrase_list = [
        "bener banget", "wah seru", "stay tuned", "gimana nih menurut",
        "mantap pisan", "gas pol", "asik banget", "gitu dong",
    ]
    phrase_counts = Counter()
    for t in turns:
        text = (t.get("final_text") or t.get("text") or "").lower()
        for cp in catchphrase_list:
            if cp in text:
                phrase_counts[cp] += 1

    # 3. Top trigram share
    all_texts = [t.get("final_text") or t.get("text") or "" for t in turns]
    tri_counter = Counter()
    total_trigrams = 0
    for text in all_texts:
        trigs = _trigrams(text)
        tri_counter.update(trigs)
        total_trigrams += len(trigs)
    top_trigram = ""
    top_trigram_share = 0.0
    if tri_counter:
        top_trigram, top_count = tri_counter.most_common(1)[0]
        top_trigram_share = top_count / total_trigrams if total_trigrams else 0.0

    # 4. distinct-2
    bigrams = Counter()
    for text in all_texts:
        toks = _tokens(text)
        for i in range(len(toks) - 1):
            bigrams[" ".join(toks[i:i + 2])] += 1
    distinct_2 = len(bigrams) / sum(bigrams.values()) if bigrams else 0.0

    # 5. Echo rate
    echo_count = 0
    for i in range(1, len(turns)):
        prev = turns[i - 1].get("final_text") or turns[i - 1].get("text") or ""
        cur = turns[i].get("final_text") or turns[i].get("text") or ""
        if _opener(prev) and _opener(prev) == _opener(cur):
            echo_count += 1
    echo_rate = echo_count / (len(turns) - 1) if len(turns) > 1 else 0.0

    # 6. Question/listener endings
    question_ending = sum(1 for t in all_texts if _is_question(t))
    listener_mentions = sum(1 for t in all_texts if _mentions_listener(t))
    question_or_listener = sum(
        1 for t in all_texts if (_is_question(t) or _mentions_listener(t))
    )

    # 7. Written laughter
    laughter_turns = sum(1 for t in all_texts if _written_laughter(t))

    # 8. Length variation
    lengths = [_word_count(t) for t in all_texts]
    if lengths:
        mean_len = statistics.mean(lengths)
        min_len = min(lengths)
        max_len = max(lengths)
        stdev = statistics.pstdev(lengths)
        cv = stdev / mean_len if mean_len else 0.0
    else:
        mean_len = min_len = max_len = cv = 0.0

    # 9. Regenerations
    regenerations = sum(t.get("regenerations", 0) for t in turns)
    guard_regenerations = sum(t.get("guard_regenerations", 0) for t in turns)

    return {
        "n_turns": len(turns),
        "top_opener_share": top_opener_share,
        "phrase_counts": dict(phrase_counts),
        "phrases_per_turn": (sum(phrase_counts.values()) / len(turns)) if turns else 0.0,
        "top_trigram": top_trigram,
        "top_trigram_share": top_trigram_share,
        "distinct_2": distinct_2,
        "echo_rate": echo_rate,
        "echo_count": echo_count,
        "question_ending": question_ending,
        "listener_mentions": listener_mentions,
        "question_or_listener": question_or_listener,
        "question_or_listener_share": (question_or_listener / len(turns)) if turns else 0.0,
        "written_laughter": laughter_turns,
        "written_laughter_share": (laughter_turns / len(turns)) if turns else 0.0,
        "length_mean": mean_len,
        "length_min": min_len,
        "length_max": max_len,
        "length_cv": cv,
        "regenerations": regenerations,
        "guard_regenerations": guard_regenerations,
    }


def load_turns(session_path: str) -> list[dict]:
    """Load JSONL turn records from a session log."""
    turns: list[dict] = []
    with open(session_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                turns.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return turns


def _reference_metrics(reference_path: str) -> dict[str, Any]:
    """Compute text-level metrics on a raw reference transcript."""
    text = Path(reference_path).read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    pseudo = [{"persona": "reference", "text": ln} for ln in lines]
    return compute_metrics(pseudo)


def render_markdown(
    metrics: dict[str, Any],
    ref: Optional[dict[str, Any]],
    ref_labeled: bool,
) -> str:
    lines = ["# Laporan Naturalness", ""]
    lines.append(f"- Jumlah giliran: {metrics['n_turns']}")
    lines.append("- Porsi pembuka terbanyak per persona:")
    for persona, info in metrics["top_opener_share"].items():
        lines.append(f"  - {persona}: \"{info['top_opener']}\" {info['share']:.0%}")
    lines.append(f"- Frasa catchphrase per giliran: {metrics['phrases_per_turn']:.3f}")
    lines.append(f"- Porsi trigram terbanyak: {metrics['top_trigram_share']:.4f} (\"{metrics['top_trigram']}\")")
    lines.append(f"- distinct-2: {metrics['distinct_2']:.4f}")
    lines.append(f"- Echo rate: {metrics['echo_rate']:.4f}")
    lines.append(f"- Giliran berakhir tanya / menyapa pendengar: {metrics['question_or_listener_share']:.0%}")
    lines.append(f"- Tawa tertulis: {metrics['written_laughter_share']:.0%}")
    lines.append(
        f"- Panjang giliran: mean={metrics['length_mean']:.1f}, min={metrics['length_min']}, "
        f"max={metrics['length_max']}, CV={metrics['length_cv']:.3f}"
    )
    lines.append(f"- Regenerasi: {metrics['regenerations']} (guard: {metrics['guard_regenerations']})")
    lines.append("")
    if ref is not None:
        if not ref_labeled:
            lines.append("> Peringatan: referensi tanpa label pembicara; hanya metrik tingkat teks yang dibandingkan.")
        lines.append("## Referensi on-air")
        lines.append(f"- Porsi trigram terbanyak: {ref['top_trigram_share']:.4f}")
        lines.append(f"- Echo rate: {ref['echo_rate']:.4f}")
        lines.append(f"- Tawa tertulis: {ref['written_laughter_share']:.0%}")
    return "\n".join(lines)


def _write_csv(metrics: dict[str, Any], path: Path) -> None:
    rows = [
        ("n_turns", metrics["n_turns"]),
        ("phrases_per_turn", metrics["phrases_per_turn"]),
        ("top_trigram", metrics["top_trigram"]),
        ("top_trigram_share", metrics["top_trigram_share"]),
        ("distinct_2", metrics["distinct_2"]),
        ("echo_rate", metrics["echo_rate"]),
        ("question_or_listener_share", metrics["question_or_listener_share"]),
        ("written_laughter_share", metrics["written_laughter_share"]),
        ("length_mean", metrics["length_mean"]),
        ("length_min", metrics["length_min"]),
        ("length_max", metrics["length_max"]),
        ("length_cv", metrics["length_cv"]),
        ("regenerations", metrics["regenerations"]),
        ("guard_regenerations", metrics["guard_regenerations"]),
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["metric", "value"])
        writer.writerows(rows)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Naturalness metrics (PRD v1.1 FR-11)")
    parser.add_argument("--session", required=True, help="Path to session JSONL log")
    parser.add_argument("--reference", default=None, help="Path to reference transcript (optional)")
    parser.add_argument("--out", default=None, help="Output Markdown path (optional)")
    args = parser.parse_args(argv)

    turns = load_turns(args.session)
    if not turns:
        print("No turns found in session log.", file=sys.stderr)
        return 1

    metrics = compute_metrics(turns)

    ref_metrics = None
    ref_labeled = False
    if args.reference:
        ref_metrics = _reference_metrics(args.reference)

    markdown = render_markdown(metrics, ref_metrics, ref_labeled)
    print(markdown)

    if args.out:
        Path(args.out).write_text(markdown + "\n", encoding="utf-8")
        base = Path(args.out).with_suffix("")
        Path(str(base) + ".json").write_text(
            json.dumps({"session": metrics, "reference": ref_metrics}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _write_csv(metrics, Path(str(base) + ".csv"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

