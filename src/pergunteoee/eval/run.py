"""Roda as perguntas de referência e mede acurácia de execução.

Com o provedor mock o número só verifica a tubulação. Não é acurácia de modelo.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from pergunteoee.agent.loop import answer_question
from pergunteoee.config import DEFAULT_SEED, database_path
from pergunteoee.db import Database, ensure_database
from pergunteoee.eval.compare import frames_match
from pergunteoee.llm import build_provider

MOCK_NOTICE = (
    "Provider mock. A acurácia abaixo mede regras fixas e a tubulação de avaliação. "
    "Não é o desempenho de um modelo de linguagem."
)


def questions_path(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    candidates = [
        Path.cwd() / "eval" / "perguntas.yaml",
        Path(__file__).resolve().parents[3] / "eval" / "perguntas.yaml",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("Não encontrei eval/perguntas.yaml. Use --perguntas.")


def load_questions(path: Path) -> list[dict]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    questions = payload["perguntas"]
    if not isinstance(questions, list) or not questions:
        raise ValueError("O arquivo de perguntas não tem a lista 'perguntas'.")
    return questions


def evaluate(database: Database, provider: str, questions: list[dict]) -> dict:
    model = build_provider(provider)
    items = []
    for question in questions:
        gold_sql = str(question["sql"]).strip().rstrip(";")
        item = {
            "id": question["id"],
            "pergunta": question["pergunta"],
            "executou": False,
            "resultado_igual": False,
            "sql_gerado": None,
            "erro": None,
            "erro_referencia": None,
        }
        try:
            gold = database.query(gold_sql).frame
        except Exception as exc:
            item["erro_referencia"] = " ".join(str(exc).split())[:400]
            items.append(item)
            continue
        result = answer_question(
            question["pergunta"],
            model,
            database,
            explain=False,
            chart=False,
        )
        item["sql_gerado"] = result.sql
        item["executou"] = result.status == "answered" and result.frame is not None
        if result.error:
            item["erro"] = result.error
        if item["executou"] and result.frame is not None:
            item["resultado_igual"] = frames_match(gold, result.frame)
        items.append(item)

    total = len(items)
    reference_ok = sum(1 for item in items if item["erro_referencia"] is None)
    executed = sum(1 for item in items if item["executou"])
    matched = sum(1 for item in items if item["resultado_igual"])
    report = {
        "provider": provider,
        "total": total,
        "referencia_ok": reference_ok,
        "sql_executado": executed,
        "resultados_iguais": matched,
        "acuracia_execucao": (matched / total) if total else None,
        "itens": items,
    }
    if provider == "mock":
        report["aviso"] = MOCK_NOTICE
    return report


def _print_report(report: dict) -> None:
    print(f"provider: {report['provider']}")
    if report.get("aviso"):
        print(report["aviso"])
    print(f"{'id':<36} {'executou':<10} {'igual'}")
    for item in report["itens"]:
        executed = "sim" if item["executou"] else "nao"
        same = "sim" if item["resultado_igual"] else "nao"
        print(f"{item['id']:<36} {executed:<10} {same}")
        if item["erro_referencia"]:
            print(f"  referencia: {item['erro_referencia']}")
        elif item["erro"]:
            print(f"  erro: {item['erro']}")
    accuracy = report["acuracia_execucao"]
    shown = "n/d" if accuracy is None else f"{accuracy:.3f}"
    print(
        f"total={report['total']} referencia_ok={report['referencia_ok']} "
        f"sql_executado={report['sql_executado']} "
        f"resultados_iguais={report['resultados_iguais']} "
        f"acuracia_execucao={shown}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Avalia acurácia de execução do PergunteOEE.")
    parser.add_argument("--provider", default="mock")
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--perguntas", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)

    path = ensure_database(args.db or database_path(), seed=args.seed)
    questions = load_questions(questions_path(args.perguntas))
    report = evaluate(Database(path), args.provider, questions)
    _print_report(report)
    if args.out:
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"relatorio: {args.out}")
    if report["referencia_ok"] != report["total"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
