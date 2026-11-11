"""Prompts em português. O marcador inicial identifica o pedido para o mock."""

from __future__ import annotations

import math
from datetime import date, datetime

import pandas as pd

from pergunteoee.schema import SCHEMA_TEXT

SQL_SYSTEM = f"""Você escreve uma única consulta DuckDB para responder
a uma pergunta sobre produção.

Regras:
- Devolva somente um bloco sql com um SELECT. Pode usar WITH.
- Não use mais de um comando. Não use ponto e vírgula no meio.
- Não use INSERT, UPDATE, DELETE, CREATE, DROP, COPY, ATTACH,
  PRAGMA, INSTALL nem leitura de arquivo.
- Tabelas permitidas: producao, paradas, linhas, vw_oee, metadados.
- disponibilidade, performance, qualidade e oee já estão em vw_oee,
  em proporção (0,81 significa 81%).
- Turno 1 é manhã, 2 é tarde, 3 é noite.
- categoria em paradas é 'planejada' ou 'nao_planejada'.
- Se a pergunta não couber nessas tabelas, leia metadados.

Esquema:
{SCHEMA_TEXT}
"""

EXPLAIN_SYSTEM = """Você explica o resultado de uma consulta sobre produção industrial.
Regras:
- Escreva em português do Brasil, em prosa curta.
- Use somente números que aparecem na tabela recebida.
- Não invente causa, tendência, comparação com outra fábrica nem meta corporativa.
- Se a tabela estiver vazia, diga isso.
- Os dados são sintéticos. Não diga que eles descrevem uma fábrica real.
- Se OEE, disponibilidade, performance ou qualidade estiver entre 0 e 1,
  cite o valor também em porcentagem.
- No máximo um parágrafo e uma lista curta se houver várias linhas.
"""


def sql_messages(question: str, failures: list[tuple[str, str]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [
        {"role": "system", "content": SQL_SYSTEM},
        {"role": "user", "content": f"Pergunta:\n{question}"},
    ]
    for sql, error in failures:
        messages.append({"role": "assistant", "content": f"```sql\n{sql}\n```"})
        messages.append(
            {
                "role": "user",
                "content": (
                    "Essa consulta foi rejeitada ou falhou na execução.\n"
                    f"Erro:\n{error}\n"
                    "Escreva uma nova consulta com um único SELECT."
                ),
            }
        )
    return messages


def explain_messages(
    question: str,
    sql: str,
    frame: pd.DataFrame,
    truncated: bool,
) -> list[dict[str, str]]:
    notice = ""
    if truncated:
        notice = "Aviso: a tabela foi cortada no limite de linhas do aplicativo.\n\n"
    return [
        {"role": "system", "content": EXPLAIN_SYSTEM},
        {
            "role": "user",
            "content": (f"Pergunta:\n{question}\n\nSQL:\n{sql}\n\n{notice}{_preview(frame)}"),
        },
    ]


def _preview(frame: pd.DataFrame, limit: int = 20) -> str:
    view = frame.head(limit)
    columns = " | ".join(str(column) for column in view.columns)
    lines = []
    for row in view.itertuples(index=False):
        cells = [_cell(value) for value in row]
        lines.append(" | ".join(cells))
    body = "\n".join(lines)
    return f"Colunas: {columns}\nLinhas:\n{body}"


def _cell(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="minutes")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return str(value)
