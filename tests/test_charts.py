from __future__ import annotations

import pandas as pd

from pergunteoee.agent.charts import build_chart


def test_barras_para_oee_por_linha():
    frame = pd.DataFrame({"linha": ["L1", "L2", "L3", "L4"], "oee_medio": [0.71, 0.74, 0.69, 0.8]})
    figure = build_chart(frame)
    assert figure is not None
    assert figure.data[0].type == "bar"
    assert figure.layout.yaxis.tickformat == ".0%"


def test_linha_para_serie_diaria():
    frame = pd.DataFrame(
        {
            "data": ["2026-03-01", "2026-03-02", "2026-03-03"],
            "produzido": [1000, 1100, 900],
            "meta": [1200, 1200, 1200],
        }
    )
    figure = build_chart(frame)
    assert figure is not None
    assert figure.data[0].type == "scatter"
    assert len(figure.data) == 2


def test_sem_grafico_quando_falta_serie():
    assert build_chart(pd.DataFrame({"registros": [10]})) is None
    assert build_chart(pd.DataFrame({"linha": [], "oee_medio": []})) is None
