from __future__ import annotations

from datetime import date, datetime, timedelta

import duckdb
import pandas as pd
import pytest

from pergunteoee.data.oee import VIEW_SQL
from tests.oee_reference import reference_oee


def _aplicar_view(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE linhas (
            linha VARCHAR PRIMARY KEY,
            nome VARCHAR NOT NULL,
            capacidade_nominal_un_h INTEGER NOT NULL,
            observacao VARCHAR NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE producao (
            data DATE, turno INTEGER, linha VARCHAR, produto VARCHAR,
            produzido INTEGER, meta INTEGER, refugo INTEGER
        )
        """
    )
    con.execute(
        """
        CREATE TABLE paradas (
            inicio TIMESTAMP, fim TIMESTAMP, linha VARCHAR, motivo VARCHAR, categoria VARCHAR
        )
        """
    )
    con.execute(VIEW_SQL)


def _base(con, producao, paradas, capacidade=100, linha="L1", nome="Linha teste"):
    con.execute(
        "INSERT INTO linhas VALUES (?, ?, ?, ?)",
        [linha, nome, capacidade, "teste"],
    )
    con.executemany("INSERT INTO producao VALUES (?, ?, ?, ?, ?, ?, ?)", producao)
    con.executemany("INSERT INTO paradas VALUES (?, ?, ?, ?, ?)", paradas)


def test_formula_com_numeros_fechados():
    con = duckdb.connect()
    _aplicar_view(con)
    dia = date(2026, 3, 10)
    _base(
        con,
        producao=[(dia, 1, "L1", "Pão de forma tradicional", 540, 500, 30)],
        paradas=[
            (
                datetime(2026, 3, 10, 6, 0),
                datetime(2026, 3, 10, 7, 20),
                "L1",
                "Setup de turno",
                "planejada",
            ),
            (
                datetime(2026, 3, 10, 10, 0),
                datetime(2026, 3, 10, 10, 40),
                "L1",
                "Falha mecânica",
                "nao_planejada",
            ),
        ],
        capacidade=100,
    )
    row = con.execute("SELECT * FROM vw_oee").fetchone()
    cols = [item[0] for item in con.description]
    got = dict(zip(cols, row, strict=True))
    assert got["tempo_parada_planejada_min"] == 80
    assert got["tempo_parada_nao_planejada_min"] == 40
    assert got["tempo_planejado_min"] == 400
    assert got["tempo_operando_min"] == 360
    assert got["disponibilidade"] == pytest.approx(360 / 400)
    assert got["performance"] == pytest.approx(570 / (100 * 6))
    assert got["qualidade"] == pytest.approx(540 / 570)
    assert got["oee"] == pytest.approx((360 / 400) * (570 / 600) * (540 / 570))
    con.close()


def test_parada_planejada_nao_reduz_disponibilidade():
    con = duckdb.connect()
    _aplicar_view(con)
    dia = date(2026, 3, 11)
    _base(
        con,
        producao=[(dia, 2, "L1", "Pão de forma tradicional", 300, 400, 0)],
        paradas=[
            (
                datetime(2026, 3, 11, 14, 0),
                datetime(2026, 3, 11, 15, 0),
                "L1",
                "Higienização",
                "planejada",
            ),
        ],
        capacidade=100,
    )
    disp, perf = con.execute("SELECT disponibilidade, performance FROM vw_oee").fetchone()
    assert disp == pytest.approx(1.0)
    assert perf == pytest.approx(300 / (100 * (420 / 60)))
    con.close()


def test_turno_da_noite_atravessa_a_meia_noite():
    con = duckdb.connect()
    _aplicar_view(con)
    dia = date(2026, 3, 12)
    _base(
        con,
        producao=[(dia, 3, "L1", "Pão de forma tradicional", 100, 200, 0)],
        paradas=[
            (
                datetime(2026, 3, 12, 23, 0),
                datetime(2026, 3, 12, 23, 30),
                "L1",
                "Setup de turno",
                "planejada",
            ),
            (
                datetime(2026, 3, 13, 1, 0),
                datetime(2026, 3, 13, 1, 20),
                "L1",
                "Falha de sensor",
                "nao_planejada",
            ),
        ],
        capacidade=120,
    )
    row = con.execute(
        """
        SELECT data, turno, tempo_parada_planejada_min, tempo_parada_nao_planejada_min,
               disponibilidade, qualidade
        FROM vw_oee
        """
    ).fetchone()
    assert row[0] == dia
    assert row[1] == 3
    assert row[2] == 30
    assert row[3] == 20
    assert row[4] == pytest.approx(430 / 450)
    assert row[5] == pytest.approx(1.0)
    con.close()


def test_tempo_operando_zero_zera_oee_e_anula_performance():
    con = duckdb.connect()
    _aplicar_view(con)
    dia = date(2026, 3, 14)
    inicio = datetime(2026, 3, 14, 6, 0)
    _base(
        con,
        producao=[(dia, 1, "L1", "Pão de forma tradicional", 0, 0, 0)],
        paradas=[
            (inicio, inicio + timedelta(minutes=480), "L1", "Falha mecânica", "nao_planejada"),
        ],
    )
    disp, perf, qual, oee = con.execute(
        "SELECT disponibilidade, performance, qualidade, oee FROM vw_oee"
    ).fetchone()
    assert disp == pytest.approx(0.0)
    assert perf is None
    assert qual is None
    assert oee == pytest.approx(0.0)
    con.close()


def test_view_bate_com_o_oraculo(synthetic_db):
    con = duckdb.connect(str(synthetic_db), read_only=True)
    try:
        producao = con.execute("SELECT * FROM producao").df()
        paradas = con.execute("SELECT * FROM paradas").df()
        linhas = con.execute("SELECT * FROM linhas").df()
        vista = con.execute("SELECT * FROM vw_oee").df()
    finally:
        con.close()

    esperado = reference_oee(producao, paradas, linhas)
    vista["data"] = pd.to_datetime(vista["data"]).dt.date
    esperado["data"] = pd.to_datetime(esperado["data"]).dt.date
    chaves = ["data", "turno", "linha"]
    vista = vista.sort_values(chaves).reset_index(drop=True)
    esperado = esperado.sort_values(chaves).reset_index(drop=True)
    assert len(vista) == len(esperado)
    assert vista[chaves].astype(str).values.tolist() == esperado[chaves].astype(str).values.tolist()

    for coluna in (
        "tempo_parada_planejada_min",
        "tempo_parada_nao_planejada_min",
        "tempo_planejado_min",
        "tempo_operando_min",
        "produzido",
        "refugo",
        "meta",
        "disponibilidade",
        "performance",
        "qualidade",
        "oee",
    ):
        for obtido, certo in zip(vista[coluna], esperado[coluna], strict=True):
            if pd.isna(obtido) and pd.isna(certo):
                continue
            assert obtido == pytest.approx(certo, abs=1e-9), coluna


def test_componentes_da_base_sintetica_ficam_no_intervalo(synthetic_db):
    con = duckdb.connect(str(synthetic_db), read_only=True)
    try:
        nulos = con.execute("SELECT count(*) FROM vw_oee WHERE oee IS NULL").fetchone()[0]
        fora = con.execute(
            """
            SELECT count(*) FROM vw_oee
            WHERE disponibilidade < 0 OR disponibilidade > 1
               OR qualidade < 0 OR qualidade > 1
               OR performance < 0.5 OR performance > 1.05
               OR oee < 0 OR oee > 1.05
               OR tempo_operando_min < 60
               OR tempo_planejado_min > 480
            """
        ).fetchone()[0]
        sem_nao_planejada = con.execute(
            """
            SELECT count(*) FROM vw_oee
            WHERE tempo_parada_nao_planejada_min = 0 AND abs(disponibilidade - 1) > 1e-12
            """
        ).fetchone()[0]
    finally:
        con.close()
    assert nulos == 0
    assert fora == 0
    assert sem_nao_planejada == 0
