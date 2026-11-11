from __future__ import annotations

import duckdb

from pergunteoee.agent.loop import answer_question
from pergunteoee.db import Database
from pergunteoee.llm.base import ProviderError
from pergunteoee.llm.mock import MockProvider
from pergunteoee.llm.openai_compatible import OpenAICompatibleProvider


class Scripted:
    name = "scripted"

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)
        self.calls: list[list[dict[str, str]]] = []

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> str:
        del temperature
        self.calls.append(messages)
        if not self._replies:
            raise AssertionError("o modelo foi chamado além das respostas previstas")
        return self._replies.pop(0)


class Recording:
    def __init__(self, database: Database) -> None:
        self.database = database
        self.sql: list[str] = []

    def query(self, sql: str, max_rows: int = 5000):
        self.sql.append(sql)
        return self.database.query(sql, max_rows=max_rows)


GOOD = "SELECT linha, SUM(produzido) AS produzido FROM producao GROUP BY linha ORDER BY linha"


def test_mock_responde_oee_por_linha(synthetic_db):
    result = answer_question(
        "Qual é o OEE médio de cada linha?",
        MockProvider(),
        Database(synthetic_db),
    )
    assert result.status == "answered"
    assert result.sql is not None and "vw_oee" in result.sql.lower()
    assert result.frame is not None
    assert list(result.frame["linha"]) == ["L1", "L2", "L3", "L4"]
    assert result.explanation is not None
    assert "sintética" in result.explanation
    assert "%" in result.explanation
    assert result.figure is not None
    assert result.failures == []


def test_mock_diz_que_a_base_e_sintetica(synthetic_db):
    result = answer_question(
        "Os dados são reais?",
        MockProvider(),
        Database(synthetic_db),
    )
    assert result.status == "answered"
    assert result.frame is not None
    origem = result.frame.set_index("chave").loc["origem", "valor"]
    assert origem == "SYNTHETIC"


def test_repete_uma_vez_quando_o_sql_e_recusado(synthetic_db):
    database = Database(synthetic_db)
    recorder = Recording(database)
    antes = database.query("SELECT count(*) AS n FROM producao").frame["n"].iloc[0]
    model = Scripted(
        [
            "DELETE FROM producao",
            f"```sql\n{GOOD}\n```",
            "A soma por linha está na tabela.",
        ]
    )
    result = answer_question("Quanto cada linha produziu?", model, recorder)
    assert result.status == "answered"
    assert len(result.failures) == 1
    assert len(model.calls) == 3
    assert recorder.sql
    assert all("delete" not in sql.lower() for sql in recorder.sql)
    depois = database.query("SELECT count(*) AS n FROM producao").frame["n"].iloc[0]
    assert antes == depois


def test_devolve_o_erro_de_execucao_para_a_segunda_tentativa(synthetic_db):
    model = Scripted(
        [
            "SELECT coluna_inexistente FROM producao",
            GOOD,
            "Pronto.",
        ]
    )
    result = answer_question("Quanto cada linha produziu?", model, Database(synthetic_db))
    assert result.status == "answered"
    second_prompt = model.calls[1][-1]["content"]
    assert "coluna_inexistente" in second_prompt
    assert "Erro de execução" in second_prompt


def test_para_depois_de_duas_falhas(synthetic_db):
    database = Database(synthetic_db)
    recorder = Recording(database)
    model = Scripted(
        [
            "SELECT * FROM producao; DROP TABLE producao",
            "DROP TABLE linhas",
        ]
    )
    result = answer_question("Qual o OEE?", model, recorder)
    assert result.status == "failed"
    assert len(result.failures) == 2
    assert len(model.calls) == 2
    assert recorder.sql == []
    _expect_write_blocked(database)
    ainda = database.query("SELECT count(*) AS n FROM linhas").frame["n"].iloc[0]
    assert ainda == 4


def test_avaliacao_pode_pular_a_explicacao(synthetic_db):
    model = Scripted([GOOD])
    result = answer_question(
        "Quanto cada linha produziu?",
        model,
        Database(synthetic_db),
        explain=False,
        chart=False,
    )
    assert result.status == "answered"
    assert result.explanation is None
    assert result.figure is None
    assert len(model.calls) == 1


def test_pergunta_vazia_nao_chama_o_modelo(synthetic_db):
    model = Scripted([])
    result = answer_question("  ", model, Database(synthetic_db))
    assert result.status == "failed"
    assert model.calls == []


def test_endpoint_compativel_usa_a_url_informada(monkeypatch):
    captured: dict[str, str] = {}

    class FakeOpenAI:
        def __init__(self, **kwargs: str) -> None:
            captured.update(kwargs)

    monkeypatch.setattr("pergunteoee.llm.openai_compatible.OpenAI", FakeOpenAI)
    OpenAICompatibleProvider(
        base_url="http://127.0.0.1:11434/v1",
        api_key="ollama",
        model="qwen",
    )
    assert captured["base_url"] == "http://127.0.0.1:11434/v1"
    assert captured["api_key"] == "ollama"


def test_erro_do_provedor_nao_expoe_a_chave():
    provider = OpenAICompatibleProvider(
        base_url="http://127.0.0.1:9/v1",
        api_key="sk-secret-123",
        model="local",
    )

    class Completions:
        @staticmethod
        def create(**kwargs: object) -> None:
            del kwargs
            raise RuntimeError("unauthorized sk-secret-123")

    class Chat:
        completions = Completions()

    class Client:
        chat = Chat()

    provider._client = Client()
    try:
        provider.complete([{"role": "user", "content": "oi"}])
    except ProviderError as exc:
        message = str(exc)
    else:
        raise AssertionError("o erro do provedor deveria subir")
    assert "sk-secret-123" not in message
    assert "***" in message


def test_from_env_exige_url_e_modelo(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    try:
        OpenAICompatibleProvider.from_env()
    except ProviderError as exc:
        assert "OPENAI_MODEL" in str(exc)
    else:
        raise AssertionError("faltou recusar ambiente incompleto")


def _expect_write_blocked(database: Database) -> None:
    try:
        database.query("DELETE FROM producao")
    except duckdb.Error:
        return
    raise AssertionError("a conexão de consulta aceitou DELETE")
