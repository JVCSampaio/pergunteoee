"""Oráculo em Python da view vw_oee, independente do SQL."""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

SHIFT_MINUTES = 480


def attribute_shift(inicio: datetime) -> tuple[date, int]:
    if isinstance(inicio, pd.Timestamp):
        inicio = inicio.to_pydatetime()
    if inicio.hour < 6:
        return inicio.date() - timedelta(days=1), 3
    if inicio.hour < 14:
        return inicio.date(), 1
    if inicio.hour < 22:
        return inicio.date(), 2
    return inicio.date(), 3


def _minutes(inicio: datetime, fim: datetime) -> int:
    if isinstance(inicio, pd.Timestamp):
        inicio = inicio.to_pydatetime()
    if isinstance(fim, pd.Timestamp):
        fim = fim.to_pydatetime()
    return int((fim - inicio).total_seconds() // 60)


def reference_oee(
    producao: pd.DataFrame,
    paradas: pd.DataFrame,
    linhas: pd.DataFrame,
) -> pd.DataFrame:
    agrupado = producao.groupby(["data", "turno", "linha"], as_index=False)[
        ["produzido", "refugo", "meta"]
    ].sum()
    nomes = linhas.set_index("linha")

    parada_min: dict[tuple, list[int]] = {}
    for row in paradas.itertuples(index=False):
        dia, turno = attribute_shift(row.inicio)
        chave = (dia, turno, row.linha)
        planejada, nao = parada_min.get(chave, [0, 0])
        minutos = _minutes(row.inicio, row.fim)
        if row.categoria == "planejada":
            planejada += minutos
        elif row.categoria == "nao_planejada":
            nao += minutos
        else:
            raise AssertionError(row.categoria)
        parada_min[chave] = [planejada, nao]

    registros = []
    for row in agrupado.itertuples(index=False):
        dia = row.data.date() if isinstance(row.data, pd.Timestamp) else row.data
        chave = (dia, int(row.turno), row.linha)
        planejada, nao = parada_min.get(chave, [0, 0])
        planejado = SHIFT_MINUTES - planejada
        operando = planejado - nao
        produzido = float(row.produzido)
        refugo = float(row.refugo)
        meta = float(row.meta)
        capacidade = int(nomes.loc[row.linha, "capacidade_nominal_un_h"])
        total = produzido + refugo

        if planejado <= 0:
            disponibilidade = None
        else:
            disponibilidade = operando / planejado
        if operando <= 0:
            performance = None
        else:
            performance = total / (capacidade * (operando / 60.0))
        if total == 0:
            qualidade = None
        else:
            qualidade = produzido / total

        if planejado <= 0:
            oee = None
        elif operando <= 0 or total == 0:
            oee = 0.0
        else:
            oee = disponibilidade * performance * qualidade

        registros.append(
            {
                "data": dia,
                "turno": int(row.turno),
                "linha": row.linha,
                "linha_nome": nomes.loc[row.linha, "nome"],
                "capacidade_nominal_un_h": capacidade,
                "tempo_turno_min": SHIFT_MINUTES,
                "tempo_parada_planejada_min": planejada,
                "tempo_parada_nao_planejada_min": nao,
                "tempo_planejado_min": planejado,
                "tempo_operando_min": operando,
                "produzido": produzido,
                "refugo": refugo,
                "meta": meta,
                "disponibilidade": disponibilidade,
                "performance": performance,
                "qualidade": qualidade,
                "oee": oee,
            }
        )
    return pd.DataFrame(registros)
