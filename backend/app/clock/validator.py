"""Clock validation CLI and helper functions (FR-1).

Provides a ``validate-clock`` CLI command and programmatic validation
utilities. Ensures clock JSON conforms to the schema and passes semantic
checks (ordering, talk slots have tema, etc.).
"""

from __future__ import annotations

import argparse
import json
import sys
import logging
from pathlib import Path

from app.schemas import Clock, SlotType

logger = logging.getLogger(__name__)


class ClockValidationError(Exception):
    """Raised when a clock fails semantic validation."""


def validate_clock_semantics(clock: Clock) -> list[str]:
    """Run semantic checks beyond schema validation.

    Returns:
        A list of warning/error messages. Empty list means all good.
    """
    issues: list[str] = []

    # Check slot ordering is sequential
    orders = [s.order for s in clock.slots]
    if orders != sorted(orders):
        issues.append(f"Slot ordering is not sequential: {orders}")

    # Check for duplicate slot IDs
    ids = [s.id for s in clock.slots]
    if len(ids) != len(set(ids)):
        dupes = [sid for sid in ids if ids.count(sid) > 1]
        issues.append(f"Duplicate slot IDs: {set(dupes)}")

    # Check Talk slots have tema
    for slot in clock.slots:
        if slot.type == SlotType.TALK and slot.tema is None:
            issues.append(f"Talk slot '{slot.id}' is missing a tema")

    # Check non-Talk slots with source=static_audio have asset
    for slot in clock.slots:
        if (
            slot.type != SlotType.TALK
            and slot.source is not None
            and slot.source.value == "static_audio"
            and not slot.asset
        ):
            issues.append(
                f"Slot '{slot.id}' has source=static_audio but no asset path"
            )

    # Check non-Talk slots with source=tts have tts_text
    for slot in clock.slots:
        if (
            slot.type != SlotType.TALK
            and slot.source is not None
            and slot.source.value == "tts"
            and not slot.tts_text
        ):
            issues.append(
                f"Slot '{slot.id}' has source=tts but no tts_text"
            )

    # Check total duration is reasonable
    total_sec = sum(s.duration_sec for s in clock.slots)
    expected_sec = clock.duration_min * 60
    if abs(total_sec - expected_sec) > expected_sec * 0.3:
        issues.append(
            f"Total slot duration ({total_sec}s) differs >30% from "
            f"declared show duration ({expected_sec}s)"
        )

    return issues


def validate_clock_file(path: str | Path) -> tuple[bool, list[str]]:
    """Validate a clock JSON file against schema and semantic rules.

    Args:
        path: Path to the clock JSON file.

    Returns:
        Tuple of (is_valid, list_of_issues).
    """
    path = Path(path)
    issues: list[str] = []

    # File existence
    if not path.exists():
        return False, [f"File not found: {path}"]

    # JSON parsing
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        return False, [f"Invalid JSON: {e}"]

    # Schema validation
    try:
        clock = Clock.model_validate(data)
    except Exception as e:
        return False, [f"Schema validation failed: {e}"]

    # Semantic checks
    semantic_issues = validate_clock_semantics(clock)
    issues.extend(semantic_issues)

    is_valid = len(issues) == 0
    return is_valid, issues


def main() -> None:
    """CLI entry point: ``python -m app.clock.validator <file>``."""
    parser = argparse.ArgumentParser(
        prog="validate-clock",
        description="Validate a clock JSON file against the HITS AI Live schema.",
    )
    parser.add_argument(
        "file",
        type=str,
        help="Path to the clock JSON file to validate.",
    )
    args = parser.parse_args()

    is_valid, issues = validate_clock_file(args.file)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    if is_valid:
        print(f"[OK] Clock file is valid: {args.file}")
        sys.exit(0)
    else:
        print(f"[FAIL] Clock file has issues: {args.file}")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        sys.exit(1)


if __name__ == "__main__":
    main()
