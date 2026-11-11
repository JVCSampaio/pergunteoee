"""Provedor determinístico. Não é um modelo e não mede acurácia de LLM."""

from __future__ import annotations

_RATIO_MARKERS = (
    "oee",
    "disponib",
    "performance",
    "qualidade",
    "atingimento",
    "taxa",
)


class MockProvider:
    name = "mock"

    def complete(self, messages: list[dict[str, str]], *, temperature: float = 0.0) -> str:
        del temperature
        system = messages[0]["content"] if messages else ""
        if system.startswith("Você escreve uma única consulta DuckDB"):
            return _sql_for(_question_from(messages))
        if system.startswith("Você explica o resultado"):
            return _explain(messages[-1]["content"])
        raise RuntimeError("O mock não reconhece este pedido.")


def _question_from(messages: list[dict[str, str]]) -> str:
    for message in messages:
        content = message.get("content", "")
        if message.get("role") == "user" and content.startswith("Pergunta:"):
            return content.removeprefix("Pergunta:").strip()
    return messages[-1]["content"] if messages else ""


def _fold(text: str) -> str:
    table = str.maketrans("áàãâäéêëíóôõöúüç", "aaaaaeeeioooouuc")
    return text.lower().translate(table)


def _sql_for(question: str) -> str:
    folded = _fold(question)
    if any(token in folded for token in ("sintet", "dados reais", "sao reais", "origem")):
        return "SELECT chave, valor FROM metadados ORDER BY chave"
    if "capacidade" in folded:
        return "SELECT linha, nome, capacidade_nominal_un_h FROM linhas ORDER BY linha"
    if "motivo" in folded:
        clauses = []
        if "nao planejada" in folded:
            clauses.append("categoria = 'nao_planejada'")
        if "linha l3" in folded or "linha 3" in folded or " l3" in folded:
            clauses.append("linha = 'L3'")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return (
            "SELECT motivo, "
            "SUM(CAST(epoch(fim - inicio) / 60 AS INTEGER)) AS minutos "
            f"FROM paradas {where} "
            "GROUP BY motivo ORDER BY minutos DESC, motivo LIMIT 10"
        )
    if "parada" in folded:
        where = ""
        if "nao planejada" in folded:
            where = "WHERE categoria = 'nao_planejada'"
        elif "planejada" in folded:
            where = "WHERE categoria = 'planejada'"
        return (
            "SELECT linha, "
            "SUM(CAST(epoch(fim - inicio) / 60 AS INTEGER)) AS minutos "
            f"FROM paradas {where} GROUP BY linha ORDER BY linha"
        )
    if "produto" in folded and "qualidade" in folded:
        return (
            "SELECT produto, "
            "ROUND(SUM(produzido) * 1.0 / SUM(produzido + refugo), 4) AS qualidade "
            "FROM producao GROUP BY produto ORDER BY produto"
        )
    if "produto" in folded and "refugo" in folded:
        return (
            "SELECT produto, SUM(refugo) AS refugo "
            "FROM producao GROUP BY produto ORDER BY refugo DESC, produto"
        )
    if "produto" in folded:
        return (
            "SELECT produto, SUM(produzido) AS produzido "
            "FROM producao GROUP BY produto ORDER BY produzido DESC, produto"
        )
    if "meta" in folded and ("l1" in folded or "linha 1" in folded) and "data" in folded:
        return (
            "SELECT data, SUM(produzido) AS produzido, SUM(meta) AS meta "
            "FROM producao WHERE linha = 'L1' GROUP BY data ORDER BY data"
        )
    if "meta" in folded:
        return (
            "SELECT linha, SUM(produzido) AS produzido, SUM(meta) AS meta "
            "FROM producao GROUP BY linha ORDER BY linha"
        )
    if "turno" in folded:
        return (
            "SELECT turno, ROUND(AVG(oee), 4) AS oee_medio "
            "FROM vw_oee GROUP BY turno ORDER BY turno"
        )
    if any(token in folded for token in ("disponibilidade", "performance", "qualidade")):
        return (
            "SELECT linha, "
            "ROUND(AVG(disponibilidade), 4) AS disponibilidade, "
            "ROUND(AVG(performance), 4) AS performance, "
            "ROUND(AVG(qualidade), 4) AS qualidade "
            "FROM vw_oee GROUP BY linha ORDER BY linha"
        )
    return "SELECT linha, ROUND(AVG(oee), 4) AS oee_medio FROM vw_oee GROUP BY linha ORDER BY linha"


def _explain(user: str) -> str:
    if "Linhas:" not in user:
        return "A consulta não devolveu uma tabela para explicar."
    header, _, body = user.partition("Linhas:\n")
    columns = []
    for line in header.splitlines():
        if line.startswith("Colunas:"):
            columns = [part.strip() for part in line.removeprefix("Colunas:").split("|")]
    rows = [line for line in body.splitlines() if line.strip()]
    if not rows:
        return "A consulta não retornou linhas para essa pergunta."
    described = [_describe_row(columns, row) for row in rows[:6]]
    text = "Sem modelo de linguagem: o texto só repete a tabela da base sintética. " + " ".join(
        described
    )
    if len(rows) > 6:
        text += f" A tabela tem mais {len(rows) - 6} linhas."
    return text


def _describe_row(columns: list[str], row: str) -> str:
    cells = [cell.strip() for cell in row.split("|")]
    pairs = []
    for index, cell in enumerate(cells):
        name = columns[index] if index < len(columns) and columns[index] else f"coluna {index + 1}"
        pairs.append(f"{name} {_format_cell(name, cell)}")
    return ", ".join(pairs) + "."


def _format_cell(column: str, value: str) -> str:
    try:
        number = float(value)
    except ValueError:
        return value
    folded = _fold(column)
    if any(marker in folded for marker in _RATIO_MARKERS) and 0 <= number <= 1.5:
        return f"{number * 100:.1f}%".replace(".", ",")
    if number.is_integer():
        return str(int(number))
    return f"{number:.2f}".replace(".", ",")
