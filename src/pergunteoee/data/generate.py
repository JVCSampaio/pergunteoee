"""Gera uma fábrica de panificação sintética, reproduzível por semente.

O arquivo DuckDB recebe a marca origem = SYNTHETIC. Não há dado de fábrica real.
"""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import duckdb

from pergunteoee.config import DEFAULT_DB_PATH, DEFAULT_SEED, SHIFT_MINUTES
from pergunteoee.data.oee import VIEW_SQL

DATA_FIM = date(2026, 3, 31)
N_DAYS = 90
MIN_OPERATING = 60

MOTIVOS_PLANEJADOS = (
    "Higienização",
    "Troca de produto",
    "Manutenção preventiva",
    "Setup de turno",
)
MOTIVOS_NAO_PLANEJADOS = (
    ("Falha mecânica", 20, 90),
    ("Falha elétrica", 15, 60),
    ("Falta de matéria-prima", 10, 40),
    ("Atolamento na embalagem", 5, 25),
    ("Ajuste de qualidade", 8, 30),
    ("Falha de sensor", 10, 35),
)


@dataclass(frozen=True)
class Linha:
    linha: str
    nome: str
    capacidade_nominal_un_h: int
    produtos: tuple[str, str]
    turnos: tuple[int, ...]
    opera_domingo: bool
    observacao: str


LINHAS: tuple[Linha, ...] = (
    Linha(
        "L1",
        "Forno de pão de forma",
        1200,
        ("Pão de forma tradicional", "Pão de forma integral"),
        (1, 2, 3),
        True,
        "Opera nos três turnos, inclusive domingo.",
    ),
    Linha(
        "L2",
        "Forno de pão de hambúrguer",
        2400,
        ("Pão de hambúrguer", "Pão de hot dog"),
        (1, 2, 3),
        True,
        "Opera nos três turnos, inclusive domingo.",
    ),
    Linha(
        "L3",
        "Linha de bisnaguinha",
        1800,
        ("Bisnaguinha", "Pão sovado"),
        (1, 2, 3),
        True,
        "Opera nos três turnos, inclusive domingo.",
    ),
    Linha(
        "L4",
        "Confeitaria",
        600,
        ("Bolo inglês", "Bolo de cenoura"),
        (1, 2),
        False,
        "Não opera no turno 3 nem aos domingos.",
    ),
)


def data_inicio() -> date:
    return DATA_FIM - timedelta(days=N_DAYS - 1)


def shift_start(day: date, turno: int) -> datetime:
    hour = {1: 6, 2: 14, 3: 22}[turno]
    return datetime(day.year, day.month, day.day, hour, 0)


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


class _Agenda:
    """Minutos ocupados dentro do turno, no intervalo [0, 480)."""

    def __init__(self) -> None:
        self.intervalos: list[tuple[int, int, str, str]] = []

    def livre(self, inicio: int, fim: int) -> bool:
        if inicio < 0 or fim > SHIFT_MINUTES or fim <= inicio:
            return False
        return all(
            fim <= atual_ini or inicio >= atual_fim
            for atual_ini, atual_fim, _, _ in self.intervalos
        )

    def alocar(self, inicio: int, duracao: int, motivo: str, categoria: str) -> bool:
        fim = inicio + duracao
        if not self.livre(inicio, fim):
            return False
        self.intervalos.append((inicio, fim, motivo, categoria))
        return True

    def encaixar(
        self,
        rng: random.Random,
        duracao: int,
        motivo: str,
        categoria: str,
        preferido: int | None = None,
    ) -> bool:
        if preferido is not None and self.alocar(preferido, duracao, motivo, categoria):
            return True
        candidatos = [
            minuto
            for minuto in range(0, SHIFT_MINUTES - duracao + 1, 5)
            if self.livre(minuto, minuto + duracao)
        ]
        if not candidatos:
            return False
        return self.alocar(rng.choice(candidatos), duracao, motivo, categoria)

    def minutos(self, categoria: str) -> int:
        return sum(fim - inicio for inicio, fim, _, cat in self.intervalos if cat == categoria)


def _operates(linha: Linha, day: date, turno: int) -> bool:
    if turno not in linha.turnos:
        return False
    if day.weekday() == 6 and not linha.opera_domingo:
        return False
    return True


def _planejar_paradas(rng: random.Random, linha: Linha, day: date, turno: int) -> _Agenda:
    agenda = _Agenda()
    if rng.random() < 0.8:
        agenda.encaixar(rng, rng.randint(8, 15), "Setup de turno", "planejada", preferido=0)
    if rng.random() < 0.45:
        duracao = rng.randint(15, 30)
        agenda.encaixar(
            rng, duracao, "Higienização", "planejada", preferido=SHIFT_MINUTES - duracao
        )
    if day.weekday() == 0 and turno == 1:
        agenda.encaixar(
            rng, rng.randint(40, 80), "Manutenção preventiva", "planejada", preferido=180
        )
    return agenda


def _escolher_produtos(rng: random.Random, linha: Linha, agenda: _Agenda) -> list[str]:
    if rng.random() < 0.18 and agenda.encaixar(
        rng, rng.randint(25, 45), "Troca de produto", "planejada", preferido=220
    ):
        return [linha.produtos[0], linha.produtos[1]]
    if rng.random() < 0.75:
        return [linha.produtos[0]]
    return [linha.produtos[1]]


def _paradas_nao_planejadas(rng: random.Random, agenda: _Agenda) -> None:
    sorteio = rng.random()
    quantidade = 0 if sorteio < 0.55 else 1 if sorteio < 0.9 else 2
    for _ in range(quantidade):
        usado = agenda.minutos("planejada") + agenda.minutos("nao_planejada")
        folga = SHIFT_MINUTES - MIN_OPERATING - usado
        if folga < 5:
            return
        motivo, baixo, alto = rng.choice(MOTIVOS_NAO_PLANEJADOS)
        duracao = min(rng.randint(baixo, alto), folga)
        agenda.encaixar(rng, duracao, motivo, "nao_planejada")


def _repartir(total: float, pesos: list[float]) -> list[int]:
    bruto = [total * peso for peso in pesos]
    inteiros = [int(round(valor)) for valor in bruto]
    diferenca = int(round(total)) - sum(inteiros)
    inteiros[-1] += diferenca
    if inteiros[-1] < 0:
        inteiros[0] += inteiros[-1]
        inteiros[-1] = 0
    return inteiros


def generate_rows(seed: int) -> tuple[list[tuple], list[tuple], list[tuple]]:
    rng = random.Random(seed)
    inicio = data_inicio()
    producao: list[tuple] = []
    paradas: list[tuple] = []

    for offset in range(N_DAYS):
        day = inicio + timedelta(days=offset)
        for linha in LINHAS:
            for turno in (1, 2, 3):
                if not _operates(linha, day, turno):
                    continue
                agenda = _planejar_paradas(rng, linha, day, turno)
                produtos = _escolher_produtos(rng, linha, agenda)
                _paradas_nao_planejadas(rng, agenda)

                planejado_min = agenda.minutos("planejada")
                nao_planejado_min = agenda.minutos("nao_planejada")
                operando = SHIFT_MINUTES - planejado_min - nao_planejado_min
                if operando < MIN_OPERATING:
                    raise RuntimeError(
                        f"Turno sem tempo mínimo de operação: {linha.linha} {day} turno {turno}"
                    )

                if len(produtos) == 1:
                    fatias = [operando]
                else:
                    primeira = int(operando * rng.uniform(0.35, 0.65))
                    fatias = [primeira, operando - primeira]

                desempenho = _clip(rng.gauss(0.91, 0.03), 0.80, 1.01)
                qualidade = _clip(rng.gauss(0.994, 0.002), 0.98, 0.999)
                if any(motivo == "Ajuste de qualidade" for _, _, motivo, _ in agenda.intervalos):
                    qualidade = _clip(qualidade - rng.uniform(0.008, 0.02), 0.96, 0.995)

                unidades = linha.capacidade_nominal_un_h * (operando / 60) * desempenho
                pesos = [fatia / operando for fatia in fatias]
                totais = _repartir(unidades, pesos)
                refugos = _repartir(unidades * (1 - qualidade), pesos)
                metas = _repartir(
                    linha.capacidade_nominal_un_h * ((SHIFT_MINUTES - planejado_min) / 60) * 0.90,
                    pesos,
                )

                for produto, total, refugo, meta in zip(
                    produtos, totais, refugos, metas, strict=True
                ):
                    refugo = min(max(refugo, 0), total)
                    produzido = total - refugo
                    producao.append(
                        (day, turno, linha.linha, produto, produzido, max(meta, 0), refugo)
                    )

                comeco = shift_start(day, turno)
                for minuto_ini, minuto_fim, motivo, categoria in agenda.intervalos:
                    paradas.append(
                        (
                            comeco + timedelta(minutes=minuto_ini),
                            comeco + timedelta(minutes=minuto_fim),
                            linha.linha,
                            motivo,
                            categoria,
                        )
                    )

    linhas_rows = [
        (linha.linha, linha.nome, linha.capacidade_nominal_un_h, linha.observacao)
        for linha in LINHAS
    ]
    return producao, paradas, linhas_rows


def _create_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE linhas (
            linha VARCHAR PRIMARY KEY,
            nome VARCHAR NOT NULL,
            capacidade_nominal_un_h INTEGER NOT NULL CHECK (capacidade_nominal_un_h > 0),
            observacao VARCHAR NOT NULL
        )
        """
    )
    con.execute(
        """
        CREATE TABLE producao (
            data DATE NOT NULL,
            turno INTEGER NOT NULL CHECK (turno IN (1, 2, 3)),
            linha VARCHAR NOT NULL,
            produto VARCHAR NOT NULL,
            produzido INTEGER NOT NULL CHECK (produzido >= 0),
            meta INTEGER NOT NULL CHECK (meta >= 0),
            refugo INTEGER NOT NULL CHECK (refugo >= 0)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE paradas (
            inicio TIMESTAMP NOT NULL,
            fim TIMESTAMP NOT NULL,
            linha VARCHAR NOT NULL,
            motivo VARCHAR NOT NULL,
            categoria VARCHAR NOT NULL CHECK (categoria IN ('planejada', 'nao_planejada')),
            CHECK (fim > inicio)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE metadados (
            chave VARCHAR PRIMARY KEY,
            valor VARCHAR NOT NULL
        )
        """
    )
    con.execute(VIEW_SQL)


def generate_database(path: Path, seed: int = DEFAULT_SEED, force: bool = False) -> Path:
    path = Path(path)
    if path.exists() and not force:
        raise FileExistsError(f"{path} já existe. Use --force para gerar de novo.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.unlink()

    producao, paradas, linhas_rows = generate_rows(seed)
    con = duckdb.connect(str(path))
    try:
        _create_schema(con)
        con.executemany("INSERT INTO linhas VALUES (?, ?, ?, ?)", linhas_rows)
        con.executemany(
            "INSERT INTO producao VALUES (?, ?, ?, ?, ?, ?, ?)",
            producao,
        )
        con.executemany("INSERT INTO paradas VALUES (?, ?, ?, ?, ?)", paradas)
        aviso = (
            "SYNTHETIC. Sorteio reproduzível de uma fábrica de panificação imaginária. "
            "Não descreve a operação real de nenhuma empresa."
        )
        con.executemany(
            "INSERT INTO metadados VALUES (?, ?)",
            [
                ("origem", "SYNTHETIC"),
                ("semente", str(seed)),
                ("data_inicio", data_inicio().isoformat()),
                ("data_fim", DATA_FIM.isoformat()),
                ("dias", str(N_DAYS)),
                ("aviso", aviso),
            ],
        )
    finally:
        con.close()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera a base DuckDB sintética do PergunteOEE.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--out", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    path = generate_database(args.out, seed=args.seed, force=args.force)
    con = duckdb.connect(str(path), read_only=True)
    try:
        n_prod = con.execute("SELECT count(*) FROM producao").fetchone()[0]
        n_par = con.execute("SELECT count(*) FROM paradas").fetchone()[0]
        n_oee = con.execute("SELECT count(*) FROM vw_oee").fetchone()[0]
    finally:
        con.close()
    print("SYNTHETIC")
    print(f"arquivo: {path}")
    print(f"semente: {args.seed}")
    print(f"periodo: {data_inicio().isoformat()} a {DATA_FIM.isoformat()}")
    print(f"producao: {n_prod} linhas")
    print(f"paradas: {n_par} eventos")
    print(f"vw_oee: {n_oee} turnos")


if __name__ == "__main__":
    main()
