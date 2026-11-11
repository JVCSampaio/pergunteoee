from __future__ import annotations

import pytest

from pergunteoee.db import Database
from pergunteoee.sql.validator import SqlValidationError, validate_sql

VALIDAS = [
    "SELECT * FROM producao",
    "SELECT linha, AVG(oee) AS oee_medio FROM vw_oee GROUP BY linha ORDER BY linha",
    "WITH t AS (SELECT * FROM producao) SELECT linha, SUM(produzido) FROM t GROUP BY linha",
    "SELECT * FROM producao WHERE produto = 'Pão; DROP TABLE producao'",
    "SELECT * FROM producao /* ; DROP TABLE linhas */",
    "SELECT chave, valor FROM metadados ORDER BY chave",
    "SELECT * FROM main.linhas",
    """
    SELECT motivo, SUM(CAST(epoch(fim - inicio) / 60 AS INTEGER)) AS minutos
    FROM paradas
    GROUP BY motivo
    ORDER BY minutos DESC
    LIMIT 5
    """,
]


@pytest.mark.parametrize("sql", VALIDAS)
def test_aceita_select_de_leitura(sql):
    normalizado = validate_sql(sql)
    assert normalizado.lower().lstrip().startswith(("select", "with"))
    assert validate_sql(normalizado) == normalizado


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "   ",
        "SELECT * FROM producao; DROP TABLE producao",
        "SELECT * FROM producao; DELETE FROM paradas",
        "SELECT 1; SELECT 2",
        "DROP TABLE producao",
        "DELETE FROM producao",
        "UPDATE producao SET produzido = 0",
        "INSERT INTO producao VALUES (DATE '2026-01-01', 1, 'L1', 'x', 1, 1, 0)",
        "CREATE TABLE segredo (a VARCHAR)",
        "COPY producao TO 'out.csv'",
        "ATTACH 'outro.duckdb' AS extra",
        "PRAGMA database_list",
        "INSTALL httpfs",
        "LOAD httpfs",
        "SELECT * FROM segredos",
        "SELECT * FROM information_schema.tables",
        "SELECT * FROM read_csv_auto('/etc/passwd')",
        "SELECT * FROM 'segredo.csv'",
        "SELECT read_blob('/etc/passwd')",
        "SELECT getenv('OPENAI_API_KEY')",
        (
            "WITH segredos AS (SELECT 1 AS a) "
            "SELECT * FROM segredos UNION ALL SELECT * FROM producao "
            "WHERE linha = (SELECT linha FROM linhas_secretas)"
        ),
        "SELECT * FROM producao UNION ALL SELECT * FROM read_parquet('base.parquet')",
        "WITH producao AS (SELECT * FROM linhas) SELECT * FROM producao; DROP TABLE linhas",
    ],
)
def test_rejeita_escrita_multiplo_comando_e_tabela_estranha(sql):
    with pytest.raises(SqlValidationError):
        validate_sql(sql)


def test_cte_pode_reusar_o_nome_de_uma_tabela_permitida():
    sql = "WITH producao AS (SELECT linha, nome FROM linhas) SELECT * FROM producao"
    normalizado = validate_sql(sql)
    assert "linhas" in normalizado.lower()


def test_sql_normalizado_roda_na_base(synthetic_db):
    sql = validate_sql(
        """
        SELECT linha, ROUND(AVG(oee), 4) AS oee_medio
        FROM vw_oee
        GROUP BY linha
        ORDER BY linha
        """
    )
    frame = Database(synthetic_db).query(sql).frame
    assert list(frame["linha"]) == ["L1", "L2", "L3", "L4"]


def test_mensagem_cita_a_tabela_bloqueada():
    with pytest.raises(SqlValidationError, match="segredos"):
        validate_sql("SELECT * FROM segredos")
