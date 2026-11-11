from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

APP_PATH = Path(__file__).resolve().parents[1] / "src" / "pergunteoee" / "app" / "streamlit_app.py"


def test_exemplo_mostra_tabela_sql_e_grafico(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "mock")
    monkeypatch.setenv("PERGUNTEOEE_DB", str(tmp_path / "app.duckdb"))
    app = AppTest.from_file(str(APP_PATH), default_timeout=60)
    app.run()
    assert not app.exception

    button = next(item for item in app.button if "OEE médio" in item.label)
    button.click().run()
    assert not app.exception

    assert app.dataframe
    values = app.dataframe[0].value
    assert list(values["linha"]) == ["L1", "L2", "L3", "L4"]
    sql = "\n".join(block.value for block in app.code if "vw_oee" in block.value.lower())
    assert "vw_oee" in sql.lower()
    assert app.get("plotly_chart")
