"""Acesso somente leitura à base. Recusa arquivo sem a marca SYNTHETIC."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

from pergunteoee.data.generate import generate_database

MAX_ROWS = 5000


class DatabaseError(RuntimeError):
    pass


@dataclass
class QueryResult:
    frame: pd.DataFrame
    truncated: bool


def assert_synthetic(path: Path) -> None:
    con = duckdb.connect(str(path), read_only=True)
    try:
        try:
            row = con.execute("SELECT valor FROM metadados WHERE chave = 'origem'").fetchone()
        except duckdb.Error as exc:
            raise DatabaseError("A base não tem a tabela metadados com origem SYNTHETIC.") from exc
    finally:
        con.close()
    if row is None or row[0] != "SYNTHETIC":
        raise DatabaseError(
            "A base não está marcada como SYNTHETIC. "
            "O PergunteOEE não consulta arquivo sem esse rótulo."
        )


def ensure_database(path: Path, seed: int = 42) -> Path:
    path = Path(path)
    if not path.exists():
        generate_database(path, seed=seed)
    assert_synthetic(path)
    return path


def connect_readonly(path: Path) -> duckdb.DuckDBPyConnection:
    """Abre o arquivo em leitura e bloqueia leitura de outros arquivos."""
    return duckdb.connect(
        str(path),
        read_only=True,
        config={"enable_external_access": "false"},
    )


class Database:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        assert_synthetic(self.path)

    def query(self, sql: str, max_rows: int = MAX_ROWS) -> QueryResult:
        con = connect_readonly(self.path)
        try:
            frame = con.execute(sql).df()
        finally:
            con.close()
        truncated = len(frame) > max_rows
        if truncated:
            frame = frame.head(max_rows).reset_index(drop=True)
        return QueryResult(frame=frame, truncated=truncated)

    def metadata(self) -> dict[str, str]:
        con = connect_readonly(self.path)
        try:
            rows = con.execute("SELECT chave, valor FROM metadados").fetchall()
        finally:
            con.close()
        return {chave: valor for chave, valor in rows}
