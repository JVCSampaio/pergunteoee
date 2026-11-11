"""View de OEE. A fórmula também está descrita em schema.py e no README."""

from __future__ import annotations

VIEW_SQL = """
CREATE VIEW vw_oee AS
WITH producao_turno AS (
    SELECT
        data,
        turno,
        linha,
        SUM(produzido)::DOUBLE AS produzido,
        SUM(refugo)::DOUBLE AS refugo,
        SUM(meta)::DOUBLE AS meta
    FROM producao
    GROUP BY data, turno, linha
),
paradas_turno AS (
    SELECT
        CAST(
            CASE
                WHEN hour(inicio) < 6 THEN CAST(inicio AS DATE) - INTERVAL 1 DAY
                ELSE CAST(inicio AS DATE)
            END AS DATE
        ) AS data,
        CASE
            WHEN hour(inicio) >= 6 AND hour(inicio) < 14 THEN 1
            WHEN hour(inicio) >= 14 AND hour(inicio) < 22 THEN 2
            ELSE 3
        END AS turno,
        linha,
        SUM(
            CASE
                WHEN categoria = 'planejada'
                    THEN CAST(epoch(fim - inicio) / 60 AS INTEGER)
                ELSE 0
            END
        ) AS tempo_parada_planejada_min,
        SUM(
            CASE
                WHEN categoria = 'nao_planejada'
                    THEN CAST(epoch(fim - inicio) / 60 AS INTEGER)
                ELSE 0
            END
        ) AS tempo_parada_nao_planejada_min
    FROM paradas
    GROUP BY 1, 2, 3
),
base AS (
    SELECT
        p.data,
        p.turno,
        p.linha,
        l.nome AS linha_nome,
        l.capacidade_nominal_un_h,
        480 AS tempo_turno_min,
        COALESCE(a.tempo_parada_planejada_min, 0) AS tempo_parada_planejada_min,
        COALESCE(a.tempo_parada_nao_planejada_min, 0) AS tempo_parada_nao_planejada_min,
        480 - COALESCE(a.tempo_parada_planejada_min, 0) AS tempo_planejado_min,
        480
            - COALESCE(a.tempo_parada_planejada_min, 0)
            - COALESCE(a.tempo_parada_nao_planejada_min, 0) AS tempo_operando_min,
        p.produzido,
        p.refugo,
        p.meta
    FROM producao_turno AS p
    JOIN linhas AS l ON l.linha = p.linha
    LEFT JOIN paradas_turno AS a
        ON a.data = p.data
        AND a.turno = p.turno
        AND a.linha = p.linha
)
SELECT
    data,
    turno,
    linha,
    linha_nome,
    capacidade_nominal_un_h,
    tempo_turno_min,
    tempo_parada_planejada_min,
    tempo_parada_nao_planejada_min,
    tempo_planejado_min,
    tempo_operando_min,
    produzido,
    refugo,
    meta,
    CASE
        WHEN tempo_planejado_min <= 0 THEN NULL
        ELSE tempo_operando_min::DOUBLE / tempo_planejado_min
    END AS disponibilidade,
    CASE
        WHEN tempo_operando_min <= 0 THEN NULL
        ELSE (produzido + refugo)
            / (capacidade_nominal_un_h * (tempo_operando_min / 60.0))
    END AS performance,
    CASE
        WHEN (produzido + refugo) = 0 THEN NULL
        ELSE produzido / (produzido + refugo)
    END AS qualidade,
    CASE
        WHEN tempo_planejado_min <= 0 THEN NULL
        WHEN tempo_operando_min <= 0 THEN 0
        WHEN (produzido + refugo) = 0 THEN 0
        ELSE (tempo_operando_min::DOUBLE / tempo_planejado_min)
            * (
                (produzido + refugo)
                / (capacidade_nominal_un_h * (tempo_operando_min / 60.0))
            )
            * (produzido / (produzido + refugo))
    END AS oee
FROM base
""".strip()
