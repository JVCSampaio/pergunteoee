from __future__ import annotations

from datetime import date, datetime, timedelta

import duckdb

from pergunteoee.data.generate import (
    DATA_FIM,
    LINHAS,
    MOTIVOS_NAO_PLANEJADOS,
    MOTIVOS_PLANEJADOS,
    N_DAYS,
    data_inicio,
    generate_database,
    generate_rows,
    shift_start,
)


def _con(path):
    return duckdb.connect(str(path), read_only=True)


def test_periodo_e_marca_sintetica(synthetic_db):
    con = _con(synthetic_db)
    try:
        meta = dict(con.execute("SELECT chave, valor FROM metadados").fetchall())
        assert meta["origem"] == "SYNTHETIC"
        assert meta["semente"] == "42"
        assert meta["data_inicio"] == data_inicio().isoformat()
        assert meta["data_fim"] == DATA_FIM.isoformat()
        assert "SYNTHETIC" in meta["aviso"]
        inicio, fim = con.execute("SELECT min(data), max(data) FROM producao").fetchone()
        assert inicio == data_inicio()
        assert fim == DATA_FIM
        assert (fim - inicio).days + 1 == N_DAYS
    finally:
        con.close()


def test_calendario_das_linhas(synthetic_db):
    con = _con(synthetic_db)
    try:
        for linha in LINHAS:
            turnos = {
                row[0]
                for row in con.execute(
                    "SELECT DISTINCT turno FROM producao WHERE linha = ?",
                    [linha.linha],
                ).fetchall()
            }
            assert turnos == set(linha.turnos)
            if not linha.opera_domingo:
                domingos = con.execute(
                    """
                    SELECT count(*) FROM producao
                    WHERE linha = ? AND dayofweek(data) = 0
                    """,
                    [linha.linha],
                ).fetchone()[0]
                assert domingos == 0
            else:
                grupos = con.execute(
                    """
                    SELECT count(DISTINCT (data, turno))
                    FROM producao WHERE linha = ?
                    """,
                    [linha.linha],
                ).fetchone()[0]
                assert grupos == N_DAYS * len(linha.turnos)
    finally:
        con.close()


def test_integridade_de_producao_e_paradas(synthetic_db):
    con = _con(synthetic_db)
    try:
        negativos = con.execute(
            """
            SELECT count(*) FROM producao
            WHERE produzido < 0 OR refugo < 0 OR meta < 0
            """
        ).fetchone()[0]
        assert negativos == 0
        produtos = {linha.linha: set(linha.produtos) for linha in LINHAS}
        for linha, produto in con.execute(
            "SELECT DISTINCT linha, produto FROM producao"
        ).fetchall():
            assert produto in produtos[linha]
        categorias = {
            row[0] for row in con.execute("SELECT DISTINCT categoria FROM paradas").fetchall()
        }
        assert categorias <= {"planejada", "nao_planejada"}
        motivos = {row[0] for row in con.execute("SELECT DISTINCT motivo FROM paradas").fetchall()}
        assert motivos <= set(MOTIVOS_PLANEJADOS) | {item[0] for item in MOTIVOS_NAO_PLANEJADOS}
        invertidas = con.execute("SELECT count(*) FROM paradas WHERE fim <= inicio").fetchone()[0]
        assert invertidas == 0
        acima_e_abaixo = con.execute(
            """
            SELECT
                count(*) FILTER (WHERE produzido >= meta),
                count(*) FILTER (WHERE produzido < meta)
            FROM (
                SELECT data, turno, linha, sum(produzido) AS produzido, sum(meta) AS meta
                FROM producao
                GROUP BY 1, 2, 3
            )
            """
        ).fetchone()
        assert acima_e_abaixo[0] > 0
        assert acima_e_abaixo[1] > 0
    finally:
        con.close()


def test_paradas_nao_se_sobrepoem_e_cabem_no_turno(synthetic_db):
    con = _con(synthetic_db)
    try:
        linhas = [row[0] for row in con.execute("SELECT DISTINCT linha FROM paradas").fetchall()]
        for linha in linhas:
            eventos = con.execute(
                """
                SELECT inicio, fim FROM paradas
                WHERE linha = ? ORDER BY inicio
                """,
                [linha],
            ).fetchall()
            anterior = None
            for inicio, fim in eventos:
                if anterior is not None:
                    assert inicio >= anterior, (linha, inicio, anterior)
                anterior = fim
                turno = _turno_do_instante(inicio)
                janela_ini = shift_start(turno[0], turno[1])
                janela_fim = janela_ini + timedelta(minutes=480)
                assert janela_ini <= inicio < fim <= janela_fim
    finally:
        con.close()


def test_mesma_semente_repete_e_outra_semente_muda(tmp_path):
    primeira = generate_rows(7)
    segunda = generate_rows(7)
    terceira = generate_rows(8)
    assert primeira == segunda
    assert primeira != terceira
    caminho_a = generate_database(tmp_path / "a.duckdb", seed=7)
    caminho_b = generate_database(tmp_path / "b.duckdb", seed=7)
    con_a = _con(caminho_a)
    con_b = _con(caminho_b)
    try:
        total_a = con_a.execute("SELECT sum(produzido) FROM producao").fetchone()[0]
        total_b = con_b.execute("SELECT sum(produzido) FROM producao").fetchone()[0]
        assert total_a == total_b
    finally:
        con_a.close()
        con_b.close()


def _turno_do_instante(inicio: datetime) -> tuple[date, int]:
    if inicio.hour < 6:
        return inicio.date() - timedelta(days=1), 3
    if inicio.hour < 14:
        return inicio.date(), 1
    if inicio.hour < 22:
        return inicio.date(), 2
    return inicio.date(), 3
