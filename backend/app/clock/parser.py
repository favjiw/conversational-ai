"""Clock and Tema parsing utilities (FR-1).

Phase 1 scope: load from JSON files. Phase 2 adds docx parsing via Gemini.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from app.schemas import Clock, PersonaCard

logger = logging.getLogger(__name__)


def load_clock(path: str | Path) -> Clock:
    """Load and validate a clock JSON file.

    Args:
        path: Absolute or relative path to the clock JSON file.

    Returns:
        A validated ``Clock`` instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        pydantic.ValidationError: If the JSON does not match the schema.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Clock file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    clock = Clock.model_validate(data)
    logger.info("Loaded clock '%s' with %d slots", clock.show, len(clock.slots))
    return clock


def load_persona(path: str | Path) -> PersonaCard:
    """Load and validate a persona card JSON file.

    Args:
        path: Absolute or relative path to the persona JSON file.

    Returns:
        A validated ``PersonaCard`` instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        pydantic.ValidationError: If the JSON does not match the schema.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Persona file not found: {path}")

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    persona = PersonaCard.model_validate(data)
    logger.info("Loaded persona '%s' (%s)", persona.name, persona.id)
    return persona


def load_all_personas(directory: str | Path) -> dict[str, PersonaCard]:
    """Load all persona JSON files from a directory.

    Returns:
        Dict mapping persona id to PersonaCard.
    """
    directory = Path(directory)
    personas: dict[str, PersonaCard] = {}
    for path in sorted(directory.glob("*.json")):
        persona = load_persona(path)
        personas[persona.id] = persona
    return personas


def get_talk_slots(clock: Clock) -> list:
    """Return only the Talk-type slots from a clock, ordered."""
    from app.schemas import SlotType

    return [s for s in clock.slots if s.type == SlotType.TALK]
