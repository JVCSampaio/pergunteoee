from __future__ import annotations

import os

from pergunteoee.config import load_local_env


def test_env_local_preenche_e_nao_sobrescreve(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_MODEL", "ja-definido")
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "\n".join(
            [
                "# comentario",
                "OPENAI_MODEL=outro",
                "OPENAI_BASE_URL=http://127.0.0.1:11434/v1",
            ]
        ),
        encoding="utf-8",
    )
    load_local_env(path)
    assert os.environ["OPENAI_MODEL"] == "ja-definido"
    assert os.environ["OPENAI_BASE_URL"] == "http://127.0.0.1:11434/v1"
