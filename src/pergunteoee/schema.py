"""Descrição estável do esquema, usada no prompt e na documentação do agente."""

from __future__ import annotations

SCHEMA_TEXT = """
Tabelas DuckDB. A base inteira é sintética (metadados.origem = 'SYNTHETIC').

linhas
  linha VARCHAR  -- L1, L2, L3, L4
  nome VARCHAR
  capacidade_nominal_un_h INTEGER  -- unidades boas+refugo por hora, em ritmo nominal
  observacao VARCHAR  -- calendário da linha (turno 3, domingo)

producao  -- uma linha por data, turno, linha e produto
  data DATE
  turno INTEGER  -- 1 manhã 06:00-14:00, 2 tarde 14:00-22:00, 3 noite 22:00-06:00
  linha VARCHAR
  produto VARCHAR
  produzido INTEGER  -- unidades boas
  meta INTEGER       -- meta do turno, definida sem descontar parada não planejada
  refugo INTEGER     -- unidades descartadas

paradas
  inicio TIMESTAMP
  fim TIMESTAMP
  linha VARCHAR
  motivo VARCHAR
  categoria VARCHAR  -- 'planejada' ou 'nao_planejada'

vw_oee  -- um registro por data, turno e linha que produziu
  data, turno, linha, linha_nome, capacidade_nominal_un_h
  tempo_turno_min                  -- sempre 480
  tempo_parada_planejada_min
  tempo_parada_nao_planejada_min
  tempo_planejado_min              -- 480 menos parada planejada
  tempo_operando_min               -- tempo planejado menos parada não planejada
  produzido, refugo, meta          -- somas dos produtos daquele turno
  disponibilidade                  -- tempo_operando / tempo_planejado
  performance                      -- (produzido + refugo) /
                                   -- (capacidade_nominal_un_h * horas operando)
  qualidade                        -- produzido / (produzido + refugo)
  oee                              -- disponibilidade * performance * qualidade
                                   -- 0 quando o tempo operando é zero

As razões disponibilidade, performance, qualidade e oee estão entre 0 e pouco acima de 1
(a performance pode passar de 1 se o ritmo superar o nominal). Não estão em porcentagem.

metadados
  chave VARCHAR
  valor VARCHAR
  -- origem, semente, data_inicio, data_fim, aviso

Regras de negócio usadas na view:
  Parada planejada sai do tempo planejado e não reduz a disponibilidade.
  Parada não planejada reduz a disponibilidade.
  A parada entra no turno em que começa. O gerador não deixa uma parada cruzar o turno.
  A linha L4 (confeitaria) não tem turno 3 e não opera no domingo.
""".strip()

ALLOWED_TABLES = frozenset({"producao", "paradas", "linhas", "vw_oee", "metadados"})
