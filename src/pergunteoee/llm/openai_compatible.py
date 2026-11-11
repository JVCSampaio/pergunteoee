"""Cliente para qualquer endpoint no formato da API de chat da OpenAI.

Serve para a API oficial, para o Ollama, para o LM Studio e para o servidor do
llama.cpp. A URL e o nome do modelo vêm do ambiente.
"""

from __future__ import annotations

from openai import OpenAI

from pergunteoee.config import env
from pergunteoee.llm.base import ProviderError


class OpenAICompatibleProvider:
    name = "openai"

    def __init__(self, *, base_url: str, api_key: str, model: str, timeout: float = 120.0) -> None:
        self.model = model
        self._api_key = api_key
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)

    @classmethod
    def from_env(cls) -> OpenAICompatibleProvider:
        base_url = env("OPENAI_BASE_URL")
        model = env("OPENAI_MODEL")
        if not base_url or not model:
            raise ProviderError(
                "Defina OPENAI_BASE_URL e OPENAI_MODEL. "
                "No Ollama a URL local costuma ser http://127.0.0.1:11434/v1."
            )
        timeout = float(env("OPENAI_TIMEOUT", "120") or "120")
        return cls(
            base_url=base_url,
            api_key=env("OPENAI_API_KEY", "not-needed") or "not-needed",
            model=model,
            timeout=timeout,
        )

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
            )
        except Exception as exc:
            raise ProviderError(self._public_error(exc)) from exc
        content = response.choices[0].message.content if response.choices else ""
        return content or ""

    def _public_error(self, exc: Exception) -> str:
        text = " ".join(str(exc).split())
        secret = self._api_key
        if secret and secret not in {"", "not-needed"} and secret in text:
            text = text.replace(secret, "***")
        return text[:500]
