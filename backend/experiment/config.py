"""Configuration models and loader for Experiment Mode (PRD FR-1)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field
import yaml


class ModelDefinition(BaseModel):
    id: str
    provider: Literal["google", "openai", "groq", "mock"] = "google"
    model_name: str = "gemini-3.5-flash-lite"
    size_group: str = "undisclosed"
    family: str = "gemini"
    base_url: Optional[str] = None
    api_key_env: str = "GEMINI_API_KEY"


class ConditionConfig(BaseModel):
    condition_id: str
    research_question: Literal["RQ1", "RQ2", "custom"] = "RQ1"
    persona_type: Literal["none", "low", "high", "custom"] = "none"
    model_id: str
    persona_file: Optional[str] = None
    n_runs: int = 3


class ConversationConfig(BaseModel):
    temperature: float = 0.7
    max_tokens: int = 256
    themes_file: str = "backend/experiment/data/themes_aron1997.json"
    system_prompt: str = (
        "You are now sharing your thoughts on the question with your partner.\n"
        "You only reply briefly to your thoughts only for a given question."
    )


class QuestionnaireConfig(BaseModel):
    temperature: float = 0.0
    repeats: int = 3
    snapshots: List[int] = Field(default_factory=lambda: [12, 24, 36])
    agents_measured: List[str] = Field(default_factory=lambda: ["A", "B"])
    include: List[str] = Field(default_factory=lambda: ["all"])
    max_retries: int = 3


class RuntimeConfig(BaseModel):
    concurrency: int = 1
    max_retries: int = 5
    log_dir: str = "backend/logs/experiments"
    llm_mode: Literal["live", "mock"] = "live"
    fail_inject: Optional[str] = None
    seed: int = 42


class ExperimentConfig(BaseModel):
    experiment_id: str = "exp_pilot"
    profile: Literal["pilot", "full"] = "pilot"
    alpha: float = 0.05
    models: List[ModelDefinition] = Field(default_factory=list)
    conditions: List[ConditionConfig] = Field(default_factory=list)
    conversation: ConversationConfig = Field(default_factory=ConversationConfig)
    questionnaire: QuestionnaireConfig = Field(default_factory=QuestionnaireConfig)
    runtime: RuntimeConfig = Field(default_factory=RuntimeConfig)


def resolve_path(p: str | Path) -> Path:
    """Resolve path whether running from repo root or backend folder."""
    path = Path(p)
    if path.is_absolute():
        return path

    cwd = Path.cwd().resolve()
    parts = path.parts

    # If current working directory is 'backend' and path begins with 'backend'
    if cwd.name == "backend" and parts and parts[0] == "backend":
        sub = Path(*parts[1:])
        return (cwd / sub).resolve()

    # If current working directory is repo root and sub exists in backend
    if (cwd / "backend").is_dir():
        if parts and parts[0] != "backend" and (cwd / "backend" / path).exists():
            return (cwd / "backend" / path).resolve()

    return (cwd / path).resolve()


def load_config(path: str | Path) -> ExperimentConfig:
    """Load and parse experiment YAML config."""
    p = resolve_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {p}")
    with open(p, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    # Override from ENV if set
    if os.getenv("EXPERIMENT_PROFILE"):
        data["profile"] = os.getenv("EXPERIMENT_PROFILE")
    if os.getenv("EXPERIMENT_OUT_DIR"):
        data.setdefault("runtime", {})["log_dir"] = os.getenv("EXPERIMENT_OUT_DIR")
    if os.getenv("QUESTIONNAIRE_REPEATS"):
        data.setdefault("questionnaire", {})["repeats"] = int(os.getenv("QUESTIONNAIRE_REPEATS"))
    if os.getenv("LLM_MODE"):
        data.setdefault("runtime", {})["llm_mode"] = os.getenv("LLM_MODE")
    if os.getenv("FAIL_INJECT"):
        data.setdefault("runtime", {})["fail_inject"] = os.getenv("FAIL_INJECT")

    return ExperimentConfig.model_validate(data)
