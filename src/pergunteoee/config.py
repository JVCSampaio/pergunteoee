"""Configuração lida do ambiente. Nada de segredo fica no código."""

from __future__ import annotations

import os
from pathlib import Path


def load_local_env(path: Path | None = None) -> None:
    """Lê um .env local. Variáveis que já existem no ambiente continuam valendo."""
    env_path = path or Path(".env")
    if not env_path.is_file():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


load_local_env()

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
