"""Máquina de estados do agente: SQL, validação, execução, uma nova tentativa, explicação."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
import plotly.graph_objects as go

from pergunteoee.agent.charts import build_chart
from pergunteoee.agent.prompts import explain_messages, sql_messages
from pergunteoee.db import Database
from pergunteoee.llm.base import LLMClient
from pergunteoee.sql.validator import SqlValidationError, validate_sql

_MAX_ATTEMPTS = 2
_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)
_START = re.compile(r"(?is)\b(with|select)\b")


class Phase(Enum):
    GENERATE = "generate"
    VALIDATE = "validate"
    EXECUTE = "execute"
    EXPLAIN = "explain"
    DONE = "done"
    FAILED = "failed"


@dataclass
class SqlFailure:
    sql: str
    error: str


@dataclass
class AgentResult:
    question: str
    status: str
    sql: str | None
    failures: list[SqlFailure]
    frame: pd.DataFrame | None
    truncated: bool
    explanation: str | None
    figure: go.Figure | None
    error: str | None


@dataclass
class _Run:
    question: str
    explain: bool
    chart: bool
    generated: int = 0
    candidate: str = ""
    sql: str | None = None
    failures: list[SqlFailure] = field(default_factory=list)
    frame: pd.DataFrame | None = None
    truncated: bool = False
    explanation: str | None = None
    figure: go.Figure | None = None
    error: str | None = None
    status: str = "failed"

    def to_result(self) -> AgentResult:
        return AgentResult(
            question=self.question,
            status=self.status,
            sql=self.sql,
            failures=list(self.failures),
            frame=self.frame,
            truncated=self.truncated,
            explanation=self.explanation,
            figure=self.figure,
            error=self.error,
        )


def extract_sql(text: str) -> str:
    raw = text or ""
    fenced = _FENCE.search(raw)
    if fenced:
        sql = fenced.group(1)
    else:
        found = _START.search(raw)
        sql = raw[found.start() :] if found else raw
    sql = sql.strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    return sql


def answer_question(
    question: str,
    llm: LLMClient,
    database: Database,
    *,
    explain: bool = True,
    chart: bool = True,
) -> AgentResult:
    """Responde uma pergunta. Há no máximo uma nova tentativa depois de erro de SQL."""
    run = _Run(question=(question or "").strip(), explain=explain, chart=chart)
    if not run.question:
        run.error = "A pergunta está vazia."
        return run.to_result()

    phase = Phase.GENERATE
    while phase not in {Phase.DONE, Phase.FAILED}:
        if phase is Phase.GENERATE:
            phase = _generate(run, llm)
        elif phase is Phase.VALIDATE:
            phase = _validate(run)
        elif phase is Phase.EXECUTE:
            phase = _execute(run, database)
        elif phase is Phase.EXPLAIN:
            phase = _explain(run, llm)
        else:
            run.error = "Estado interno desconhecido."
            phase = Phase.FAILED
    return run.to_result()


def _generate(run: _Run, llm: LLMClient) -> Phase:
    if run.generated >= _MAX_ATTEMPTS:
        run.error = run.failures[-1].error if run.failures else "Não foi possível consultar a base."
        run.status = "failed"
        return Phase.FAILED
    history = [(item.sql, item.error) for item in run.failures]
    try:
        raw = llm.complete(sql_messages(run.question, history), temperature=0.0)
    except Exception as exc:
        run.error = f"O provedor de modelo falhou: {exc}"
        run.status = "failed"
        return Phase.FAILED
    run.generated += 1
    run.candidate = extract_sql(raw)
    return Phase.VALIDATE


def _validate(run: _Run) -> Phase:
    try:
        run.sql = validate_sql(run.candidate)
    except SqlValidationError as exc:
        run.failures.append(SqlFailure(run.candidate, str(exc)))
        run.sql = None
        return Phase.GENERATE
    return Phase.EXECUTE


def _execute(run: _Run, database: Database) -> Phase:
    try:
        result = database.query(run.sql or "")
    except Exception as exc:
        message = " ".join(str(exc).split())
        run.failures.append(SqlFailure(run.sql or "", f"Erro de execução: {message[:400]}"))
        return Phase.GENERATE
    run.frame = result.frame
    run.truncated = result.truncated
    return Phase.EXPLAIN


def _explain(run: _Run, llm: LLMClient) -> Phase:
    if run.explain and run.frame is not None and run.sql is not None:
        try:
            text = llm.complete(
                explain_messages(run.question, run.sql, run.frame, run.truncated),
                temperature=0.2,
            )
            run.explanation = text.strip()
        except Exception as exc:
            run.explanation = f"A consulta rodou, mas a explicação falhou: {exc}"
    if run.chart and run.frame is not None:
        run.figure = build_chart(run.frame)
    run.status = "answered"
    run.error = None
    return Phase.DONE
