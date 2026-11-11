"""Contrato mínimo de um provedor de modelo."""

from __future__ import annotations

from typing import Protocol


class ProviderError(RuntimeError):
    """Falha ao falar com o modelo, sem incluir segredo."""


class LLMClient(Protocol):
    name: str

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> str:
        """Devolve o texto do modelo para a conversa informada."""
