"""Escolhe o provedor de modelo a partir do ambiente ou de um nome explícito."""

from __future__ import annotations

from pergunteoee.config import llm_provider_name
from pergunteoee.llm.base import LLMClient, ProviderError
from pergunteoee.llm.mock import MockProvider
from pergunteoee.llm.openai_compatible import OpenAICompatibleProvider


def build_provider(name: str | None = None) -> LLMClient:
    chosen = (name or llm_provider_name()).strip().lower()
    if chosen == "mock":
        return MockProvider()
    if chosen in {"openai", "openai_compatible"}:
        return OpenAICompatibleProvider.from_env()
    raise ProviderError("LLM_PROVIDER deve ser mock ou openai. openai aceita endpoint compatível.")


__all__ = ["LLMClient", "ProviderError", "build_provider"]
