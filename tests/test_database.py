from __future__ import annotations

import duckdb
import pytest

from pergunteoee.db import Database, DatabaseError, assert_synthetic, connect_readonly


def test_recusa_base_sem_marca(tmp_path):
    path = tmp_path / "vazia.duckdb"
    con = duckdb.connect(str(path))
    con.execute("CREATE TABLE metadados (chave VARCHAR, valor VARCHAR)")
    con.execute("INSERT INTO metadados VALUES ('origem', 'real')")
    con.close()
    with pytest.raises(DatabaseError):
        assert_synthetic(path)


def test_consulta_e_somente_leitura(synthetic_db, tmp_path):
    db = Database(synthetic_db)
    antes = db.query("SELECT count(*) AS n FROM producao").frame["n"].iloc[0]
    with pytest.raises(duckdb.Error):
        db.query("DELETE FROM producao")
    csv = tmp_path / "segredo.csv"
    csv.write_text("a\n1\n", encoding="utf-8")
    with pytest.raises(duckdb.Error):
        db.query(f"SELECT * FROM read_csv_auto('{csv.as_posix()}')")
    depois = db.query("SELECT count(*) AS n FROM producao").frame["n"].iloc[0]
    assert antes == depois
    meta = db.metadata()
    assert meta["origem"] == "SYNTHETIC"


def test_attach_somente_leitura_nao_grava(synthetic_db):
    con = connect_readonly(synthetic_db)
    try:
        with pytest.raises(duckdb.Error):
            con.execute("UPDATE linhas SET nome = 'x'")
    finally:
        con.close()
