"""Gráfico escolhido pela forma do resultado, sem uma segunda chamada ao modelo."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

_DIMENSIONS = {
    "turno",
    "linha",
    "produto",
    "motivo",
    "categoria",
    "linha_nome",
    "nome",
    "semana",
    "data",
    "chave",
}
_TEMPORAL = {"data", "semana"}
_COLORS = ["#9A3412", "#1F4E5F", "#C2410C", "#3F6212", "#44403C", "#0F766E"]
_LABELS = {
    "oee_medio": "OEE médio",
    "oee": "OEE",
    "disponibilidade": "Disponibilidade",
    "performance": "Performance",
    "qualidade": "Qualidade",
    "produzido": "Produzido",
    "meta": "Meta",
    "refugo": "Refugo",
    "minutos": "Minutos",
    "linha": "Linha",
    "turno": "Turno",
    "produto": "Produto",
    "motivo": "Motivo",
    "data": "Data",
    "categoria": "Categoria",
    "atingimento": "Atingimento da meta",
    "taxa_refugo": "Taxa de refugo",
    "ocorrencias": "Ocorrências",
    "paradas": "Paradas",
    "semana": "Semana",
    "nome": "Nome",
    "valor": "Valor",
}


def build_chart(frame: pd.DataFrame) -> go.Figure | None:
    if frame is None or frame.empty or not (2 <= len(frame) <= 40):
        return None
    dimensions = [column for column in frame.columns if _is_dimension(frame[column])]
    measures = [column for column in frame.columns if _is_measure(frame[column])]
    if not measures:
        return None
    measures = measures[:4]
    varying = [column for column in dimensions if frame[column].nunique(dropna=False) > 1]
    temporal = [column for column in varying if _is_temporal(frame[column])]
    discrete = [column for column in varying if column not in temporal]
    if len(temporal) == 1 and not discrete:
        return _line(frame, temporal[0], measures)
    if len(discrete) == 1 and not temporal:
        return _bar(frame, discrete[0], measures)
    return None


def _is_dimension(series: pd.Series) -> bool:
    name = str(series.name).lower()
    if name in _DIMENSIONS:
        return True
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    return not pd.api.types.is_numeric_dtype(series)


def _is_measure(series: pd.Series) -> bool:
    name = str(series.name).lower()
    if name in _DIMENSIONS or _is_temporal(series):
        return False
    return bool(pd.api.types.is_numeric_dtype(series))


def _is_temporal(series: pd.Series) -> bool:
    if pd.api.types.is_datetime64_any_dtype(series):
        return True
    return str(series.name).lower() in _TEMPORAL


def _label(name: str) -> str:
    return _LABELS.get(str(name).lower(), str(name))


def _ratios(frame: pd.DataFrame, measures: list[str]) -> bool:
    markers = ("oee", "disponib", "performance", "qualidade", "atingimento", "taxa")
    for measure in measures:
        if not any(marker in measure.lower() for marker in markers):
            return False
        numeric = pd.to_numeric(frame[measure], errors="coerce").dropna()
        if numeric.empty or not numeric.between(-0.05, 1.5).all():
            return False
    return True


def _style(fig: go.Figure, title: str, ratios: bool) -> go.Figure:
    fig.update_layout(
        template="simple_white",
        title={"text": title, "x": 0},
        margin={"l": 16, "r": 16, "t": 56, "b": 16},
        legend_title_text="",
        font={"family": "DejaVu Sans, sans-serif", "color": "#1C1917"},
        paper_bgcolor="#FBF7F2",
        plot_bgcolor="#FBF7F2",
    )
    if ratios:
        fig.update_yaxes(tickformat=".0%")
    return fig


def _line(frame: pd.DataFrame, temporal: str, measures: list[str]) -> go.Figure:
    plot_df = frame.copy()
    plot_df[temporal] = pd.to_datetime(plot_df[temporal])
    plot_df = plot_df.sort_values(temporal)
    title = f"{_joined(measures)} por {_label(temporal).lower()}"
    fig = px.line(
        plot_df,
        x=temporal,
        y=measures,
        markers=True,
        color_discrete_sequence=_COLORS,
        labels={name: _label(name) for name in [temporal, *measures]},
    )
    fig.update_layout(xaxis_title=_label(temporal), yaxis_title=_axis_title(frame, measures))
    return _style(fig, title, _ratios(frame, measures))


def _bar(frame: pd.DataFrame, dimension: str, measures: list[str]) -> go.Figure:
    plot_df = frame.copy()
    plot_df[dimension] = plot_df[dimension].astype(str)
    title = f"{_joined(measures)} por {_label(dimension).lower()}"
    fig = px.bar(
        plot_df,
        x=dimension,
        y=measures if len(measures) > 1 else measures[0],
        barmode="group",
        color_discrete_sequence=_COLORS,
        labels={name: _label(name) for name in [dimension, *measures]},
    )
    fig.update_xaxes(
        categoryorder="array",
        categoryarray=plot_df[dimension].tolist(),
        title=_label(dimension),
    )
    fig.update_yaxes(title=_axis_title(frame, measures))
    return _style(fig, title, _ratios(frame, measures))


def _joined(measures: list[str]) -> str:
    labels = [_label(measure) for measure in measures]
    if len(labels) == 1:
        return labels[0]
    return ", ".join(labels[:-1]) + " e " + labels[-1]


def _axis_title(frame: pd.DataFrame, measures: list[str]) -> str:
    if _ratios(frame, measures):
        return "Proporção"
    if len(measures) == 1:
        return _label(measures[0])
    return ""
