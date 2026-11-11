"""Chat em português sobre a base sintética de OEE."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from pergunteoee.agent.loop import AgentResult, answer_question
from pergunteoee.config import database_path, env, llm_provider_name
from pergunteoee.db import Database, ensure_database
from pergunteoee.llm import build_provider
from pergunteoee.llm.base import LLMClient

EXAMPLES = (
    "Qual é o OEE médio de cada linha?",
    "Como ficam disponibilidade, performance e qualidade por linha?",
    "Quanto cada linha produziu em relação à meta?",
    "Quais motivos de parada somaram mais minutos?",
    "Qual produto teve mais refugo?",
    "Os dados são reais?",
)

_RATIO_MARKERS = ("oee", "disponib", "performance", "qualidade", "atingimento", "taxa")

_CSS = """
<style>
.block-container { padding-top: 1.4rem; max-width: 1080px; }
h1.brand { font-size: 2.1rem; letter-spacing: -0.03em; margin-bottom: 0.15rem; }
.pill {
    display: inline-block;
    background: #9A3412;
    color: #fff;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
    padding: 0.12rem 0.5rem;
    border-radius: 999px;
    vertical-align: middle;
}
.lede { color: #44403C; font-size: 1.05rem; margin-top: 0.2rem; }
div[data-testid="stSidebar"] { border-right: 1px solid #E7D8CC; }
</style>
"""


def main() -> None:
    st.set_page_config(page_title="PergunteOEE", layout="wide")
    st.markdown(_CSS, unsafe_allow_html=True)
    if "history" not in st.session_state:
        st.session_state.history = []

    try:
        database = _database(str(database_path()))
        model = _model(llm_provider_name(), env("OPENAI_MODEL") or "", env("OPENAI_BASE_URL") or "")
    except Exception as exc:
        st.error(str(exc))
        st.stop()

    meta = database.metadata()
    clicked = _sidebar(meta)
    _header(meta)
    typed = st.chat_input("Pergunte sobre OEE, produção ou paradas")
    for item in st.session_state.history:
        _render_item(item)
    question = clicked or typed
    if question:
        _ask(question, model, database)


@st.cache_resource
def _database(path_str: str) -> Database:
    path = ensure_database(Path(path_str))
    return Database(path)


@st.cache_resource
def _model(provider_name: str, model_name: str, base_url: str) -> LLMClient:
    del model_name, base_url
    return build_provider(provider_name)


def _header(meta: dict[str, str]) -> None:
    st.markdown(
        '<h1 class="brand">PergunteOEE <span class="pill">SYNTHETIC</span></h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="lede">Perguntas em português sobre OEE, produção e paradas de uma '
        "fábrica de panificação imaginária.</p>",
        unsafe_allow_html=True,
    )
    st.caption(
        f"Período {meta.get('data_inicio', '?')} a {meta.get('data_fim', '?')} "
        f"· semente {meta.get('semente', '?')} · {meta.get('aviso', '')}"
    )


def _sidebar(meta: dict[str, str]) -> str | None:
    clicked = None
    with st.sidebar:
        st.header("PergunteOEE")
        provider = llm_provider_name()
        if provider == "mock":
            st.info(
                "Provedor mock, sem modelo. Ele escolhe o SQL por palavras da pergunta "
                "e só descreve as células devolvidas."
            )
        else:
            st.success(f"Modelo {env('OPENAI_MODEL')} em {env('OPENAI_BASE_URL')}.")
        st.markdown(f"Origem da base: **{meta.get('origem', 'desconhecida')}**")
        st.header("Exemplos")
        for index, example in enumerate(EXAMPLES):
            if st.button(example, key=f"exemplo-{index}", width="stretch"):
                clicked = example
        with st.expander("Como o OEE é calculado"):
            st.markdown(
                "Disponibilidade é o tempo operando dividido pelo tempo planejado. "
                "Parada planejada sai do tempo planejado. Parada não planejada reduz "
                "a disponibilidade. Performance compara unidades totais com a capacidade "
                "nominal no tempo operando. Qualidade é o produzido dividido pelo total. "
                "OEE é o produto dos três."
            )
    return clicked


def _ask(question: str, model: LLMClient, database: Database) -> None:
    with st.spinner("Consultando a base sintética..."):
        result = answer_question(question, model, database)
    user = {"kind": "user", "text": question}
    assistant = {"kind": "assistant", "result": result}
    st.session_state.history.extend([user, assistant])
    _render_item(user)
    _render_item(assistant)


def _render_item(item: dict) -> None:
    if item["kind"] == "user":
        with st.chat_message("user"):
            st.markdown(item["text"])
        return
    result: AgentResult = item["result"]
    with st.chat_message("assistant"):
        if result.status != "answered":
            st.error(result.error or "Não foi possível responder.")
            _show_failures(result)
            return
        st.markdown(result.explanation or "A consulta foi executada.")
        if result.figure is not None:
            st.plotly_chart(result.figure, width="stretch")
        if result.frame is not None:
            st.dataframe(
                result.frame,
                column_config=_column_config(result.frame),
                hide_index=True,
                width="stretch",
            )
        if result.truncated:
            st.caption("A tabela foi limitada a 5000 linhas.")
        st.markdown("**SQL**")
        st.code(result.sql or "", language="sql")
        _show_failures(result)


def _show_failures(result: AgentResult) -> None:
    if not result.failures:
        return
    with st.expander("Tentativa anterior"):
        for failure in result.failures:
            st.code(failure.sql or "(vazio)", language="sql")
            st.caption(failure.error)


def _column_config(frame: pd.DataFrame) -> dict:
    config = {}
    for column in frame.columns:
        folded = str(column).lower()
        if any(marker in folded for marker in _RATIO_MARKERS):
            config[column] = st.column_config.NumberColumn(format="percent")
    return config


main()
