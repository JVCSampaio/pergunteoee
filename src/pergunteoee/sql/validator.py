"""Aceita um único SELECT e devolve o SQL normalizado que será executado.

A execução usa o texto reescrito pelo parser, não a string original. Assim um
trecho que o parser não entendeu não chega ao DuckDB.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp
from sqlglot.errors import ParseError, SqlglotError
from sqlglot.optimizer.scope import traverse_scope

from pergunteoee.schema import ALLOWED_TABLES

_BLOCKED_FUNCTIONS = frozenset(
    {
        "read_blob",
        "read_csv",
        "read_csv_auto",
        "read_json",
        "read_json_auto",
        "read_ndjson",
        "read_ndjson_auto",
        "read_parquet",
        "read_text",
        "read_xlsx",
        "glob",
        "getenv",
        "sqlite_scan",
        "postgres_scan",
        "mysql_scan",
        "iceberg_scan",
        "delta_scan",
        "parquet_scan",
        "csv_scan",
    }
)
_ALLOWED_DB = frozenset({"", "main"})


class SqlValidationError(ValueError):
    """A consulta não pode ser executada."""


def validate_sql(sql: str) -> str:
    text = (sql or "").strip()
    if not text:
        raise SqlValidationError("A consulta está vazia.")
    try:
        parsed = sqlglot.parse(text, read="duckdb")
    except ParseError as exc:
        detail = " ".join(str(exc).split())
        raise SqlValidationError(f"SQL inválido: {detail[:300]}") from exc

    statements = [statement for statement in parsed if statement is not None]
    if len(statements) != 1:
        raise SqlValidationError("É permitido um único comando SELECT.")

    statement = statements[0]
    if not isinstance(statement, exp.Query):
        nome = type(statement).__name__
        raise SqlValidationError(f"Comando {nome} não é uma consulta de leitura.")

    _reject_functions(statement)
    _reject_unknown_tables(statement)
    return statement.sql(dialect="duckdb")


def _function_name(node: exp.Expression) -> str | None:
    if isinstance(node, exp.Anonymous):
        return node.name.lower()
    if isinstance(node, exp.Func):
        try:
            return node.sql_name().lower() or None
        except SqlglotError:
            return None
    return None


def _reject_functions(statement: exp.Expression) -> None:
    for node in statement.walk():
        name = _function_name(node)
        if not name:
            continue
        if name in _BLOCKED_FUNCTIONS or name.startswith("read_"):
            raise SqlValidationError(f"Função não permitida: {name}.")


def _reject_unknown_tables(statement: exp.Expression) -> None:
    try:
        scopes = list(traverse_scope(statement))
    except SqlglotError as exc:
        raise SqlValidationError("Não foi possível identificar as tabelas da consulta.") from exc

    for scope in scopes:
        for source in scope.sources.values():
            if not isinstance(source, exp.Table):
                continue
            name = (source.name or "").lower()
            database = (source.db or "").lower()
            catalog = (source.catalog or "").lower()
            if catalog or database not in _ALLOWED_DB:
                shown = source.sql(dialect="duckdb")
                raise SqlValidationError(f"Esquema não permitido: {shown}.")
            if name not in ALLOWED_TABLES:
                raise SqlValidationError(f"Tabela não permitida: {name or 'vazia'}.")
