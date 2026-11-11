"""Compara dois resultados de consulta sem depender da ordem das linhas."""

from __future__ import annotations

import math
import numbers
from datetime import date, datetime
from decimal import Decimal

import pandas as pd

TOLERANCE = 1e-3


def frames_match(gold: pd.DataFrame, predicted: pd.DataFrame, tolerance: float = TOLERANCE) -> bool:
    """Verdadeiro quando as tabelas têm os mesmos valores, coluna a coluna.

    O nome da coluna não entra na conta. A ordem das linhas também não.
    Números usam tolerância absoluta.
    """
    if gold.shape != predicted.shape:
        return False
    pending = [_row(row) for row in predicted.itertuples(index=False)]
    for row in gold.itertuples(index=False):
        current = _row(row)
        found = None
        for index, candidate in enumerate(pending):
            if _equal(current, candidate, tolerance):
                found = index
                break
        if found is None:
            return False
        pending.pop(found)
    return True


def _row(values: tuple) -> list[tuple]:
    return [_scalar(value) for value in values]


def _scalar(value: object) -> tuple:
    if value is None:
        return ("null", None)
    if isinstance(value, float) and math.isnan(value):
        return ("null", None)
    try:
        if pd.isna(value):
            return ("null", None)
    except TypeError:
        pass
    if isinstance(value, bool):
        return ("str", str(value))
    if isinstance(value, datetime):
        return ("time", value.isoformat())
    if isinstance(value, date):
        return ("time", value.isoformat())
    if isinstance(value, Decimal | numbers.Real):
        return ("num", float(value))
    return ("str", str(value))


def _equal(left: list[tuple], right: list[tuple], tolerance: float) -> bool:
    if len(left) != len(right):
        return False
    for one, other in zip(left, right, strict=True):
        if one[0] != other[0]:
            return False
        if one[0] == "num":
            if abs(one[1] - other[1]) > tolerance:
                return False
        elif one[1] != other[1]:
            return False
    return True
