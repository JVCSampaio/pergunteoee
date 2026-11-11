"""Configuração lida do ambiente. Nada de segredo fica no código."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DB_PATH = Path("data/pergunteoee.duckdb")
DEFAULT_SEED = 42
SHIFT_MINUTES = 480


def env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def database_path() -> Path:
    raw = env("PERGUNTEOEE_DB")
    return Path(raw) if raw else DEFAULT_DB_PATH


def llm_provider_name() -> str:
    """Usa o endpoint configurado. Sem URL e sem modelo, cai no mock offline."""
    explicit = env("LLM_PROVIDER")
    if explicit:
        return explicit.lower()
    if env("OPENAI_BASE_URL") and env("OPENAI_MODEL"):
        return "openai"
    return "mock"
