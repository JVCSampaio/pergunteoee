from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from pergunteoee.db import Database
from pergunteoee.eval.compare import frames_match
from pergunteoee.eval.run import evaluate, load_questions
from pergunteoee.sql.validator import validate_sql

QUESTIONS = Path(__file__).resolve().parents[1] / "eval" / "perguntas.yaml"


def test_ha_trinta_perguntas_com_sql_valido():
    questions = load_questions(QUESTIONS)
    assert len(questions) >= 30
    ids = [item["id"] for item in questions]
    assert len(ids) == len(set(ids))
    for item in questions:
        assert item["pergunta"].strip()
        assert item["sql"].strip()
        validate_sql(item["sql"])


def test_sql_de_referencia_devolve_linhas(synthetic_db):
    database = Database(synthetic_db)
    for item in load_questions(QUESTIONS):
        frame = database.query(item["sql"]).frame
        assert len(frame) > 0, item["id"]
        assert len(frame.columns) > 0


def test_comparacao_ignora_ordem_e_tolera_numero():
    gold = pd.DataFrame({"linha": ["L2", "L1"], "oee": [0.8, 0.7]})
    same = pd.DataFrame({"a": ["L1", "L2"], "b": [0.7004, 0.8]})
    assert frames_match(gold, same)
    different = pd.DataFrame({"a": ["L1", "L2"], "b": [0.2, 0.8]})
    assert not frames_match(gold, different)
    assert frames_match(
        pd.DataFrame({"n": [None]}),
        pd.DataFrame({"n": [float("nan")]}),
    )


def test_mock_percorre_o_conjunto_sem_quebrar_a_referencia(synthetic_db):
    questions = load_questions(QUESTIONS)
    report = evaluate(Database(synthetic_db), "mock", questions)
    assert report["referencia_ok"] == len(questions)
    assert report["sql_executado"] == len(questions)
    assert "não é o desempenho de um modelo" in report["aviso"].lower() or "Nao" in report["aviso"]
    assert 0 <= report["acuracia_execucao"] <= 1
    payload = yaml.safe_load(QUESTIONS.read_text(encoding="utf-8"))
    assert payload["versao"] == 1
