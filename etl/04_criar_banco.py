# -*- coding: utf-8 -*-
"""
etl/04_criar_banco.py

Projeto Integrador III - Fatec Cotia
Cria a estrutura do banco SQLite (database/telecom.db).

ARQUITETURA EM CAMADAS
----------------------
  Camada 1 - RAW        : espelho dos CSVs da CVM, sem transformacao
  Camada 2 - ANALITICA  : financial_data (uma linha por empresa/ano)
  Camada 3 - INDICADORES: financial_indicators (vazia ate a Sprint 3)
  Apoio                 : dim_entidade, etl_log, vw_base_analitica

Guardar a camada RAW no banco evita ter que voltar aos ZIPs da CVM
caso surja a necessidade de um novo indicador (ex.: EBITDA).

Este script e IDEMPOTENTE: pode ser executado quantas vezes quiser.
Use --reset para apagar e recriar o banco do zero.

COMO RODAR
----------
  python etl/04_criar_banco.py
  python etl/04_criar_banco.py --reset
"""

import argparse
import logging
import sqlite3
import sys

from config import BANCO, DIR_LOGS, ENTIDADES, CONTAS, RAIZ

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(DIR_LOGS / "04_criar_banco.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------
# DDL
# ---------------------------------------------------------------
DDL_DIMENSAO = """
CREATE TABLE IF NOT EXISTS dim_entidade (
    cd_cvm        TEXT PRIMARY KEY,
    grupo         TEXT NOT NULL,
    razao_social  TEXT NOT NULL,
    cnpj          TEXT NOT NULL
);
"""

# Uma tabela raw por demonstracao, com a mesma estrutura dos CSVs.
DDL_RAW = """
CREATE TABLE IF NOT EXISTS raw_{tabela} (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    cnpj_cia       TEXT,
    dt_refer       TEXT,
    versao         INTEGER,
    denom_cia      TEXT,
    cd_cvm         TEXT,
    moeda          TEXT,
    escala_moeda   TEXT,
    ordem_exerc    TEXT,
    dt_ini_exerc   TEXT,
    dt_fim_exerc   TEXT,
    cd_conta       TEXT,
    ds_conta       TEXT,
    vl_conta       REAL,
    st_conta_fixa  TEXT,
    ano_arquivo    INTEGER,
    carregado_em   TEXT DEFAULT (datetime('now','localtime'))
);
"""

DDL_RAW_INDICES = """
CREATE INDEX IF NOT EXISTS ix_raw_{tabela}_cvm_ano
    ON raw_{tabela} (cd_cvm, ano_arquivo);
CREATE INDEX IF NOT EXISTS ix_raw_{tabela}_conta
    ON raw_{tabela} (cd_conta);
"""

# Camada analitica. Valores em REAIS (escala ja aplicada).
DDL_FINANCIAL = """
CREATE TABLE IF NOT EXISTS financial_data (
    empresa                   TEXT    NOT NULL,
    ano                       INTEGER NOT NULL,
    cd_cvm                    TEXT    NOT NULL,
    razao_social              TEXT,

    receita_liquida           REAL,
    lucro_liquido             REAL,
    ativo_total               REAL,
    ativo_circulante          REAL,
    passivo_total             REAL,
    passivo_circulante        REAL,
    passivo_nao_circulante    REAL,
    patrimonio_liquido        REAL,
    fluxo_caixa_operacional   REAL,

    -- capital de terceiros = 2.01 + 2.02
    -- NAO usar passivo_total (conta 2), que inclui o PL
    capital_terceiros         REAL,

    -- validacao: ativo_total deve ser igual a passivo_total
    validacao_balanco_ok      INTEGER,

    -- observacoes de auditoria sobre dados atipicos
    -- alimentada por config.OBSERVACOES
    observacao                TEXT,

    atualizado_em             TEXT DEFAULT (datetime('now','localtime')),

    PRIMARY KEY (empresa, ano)
);
"""

# Camada de indicadores - estrutura criada agora, populada na Sprint 3.
DDL_INDICADORES = """
CREATE TABLE IF NOT EXISTS financial_indicators (
    empresa                  TEXT    NOT NULL,
    ano                      INTEGER NOT NULL,

    margem_liquida           REAL,   -- lucro / receita
    roe                      REAL,   -- lucro / patrimonio liquido
    roa                      REAL,   -- lucro / ativo total
    endividamento_geral      REAL,   -- capital terceiros / ativo total
    composicao_endividamento REAL,   -- passivo circ. / capital terceiros
    liquidez_corrente        REAL,   -- ativo circ. / passivo circ.
    cobertura_caixa          REAL,   -- fco / lucro liquido

    calculado_em             TEXT DEFAULT (datetime('now','localtime')),

    PRIMARY KEY (empresa, ano),
    FOREIGN KEY (empresa, ano) REFERENCES financial_data (empresa, ano)
);
"""

DDL_LOG = """
CREATE TABLE IF NOT EXISTS etl_log (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    executado_em TEXT DEFAULT (datetime('now','localtime')),
    etapa        TEXT,
    detalhe      TEXT,
    registros    INTEGER
);
"""

# View pronta para o Streamlit consumir na Sprint 3.
DDL_VIEW = """
CREATE VIEW IF NOT EXISTS vw_base_analitica AS
SELECT
    f.empresa,
    f.ano,
    f.cd_cvm,
    f.razao_social,
    f.receita_liquida,
    f.lucro_liquido,
    f.ativo_total,
    f.ativo_circulante,
    f.capital_terceiros,
    f.passivo_circulante,
    f.passivo_nao_circulante,
    f.patrimonio_liquido,
    f.fluxo_caixa_operacional,
    f.validacao_balanco_ok,
    f.observacao
FROM financial_data f
ORDER BY f.empresa, f.ano;
"""


# ---------------------------------------------------------------
def criar(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    log.info("Criando dim_entidade")
    cur.execute(DDL_DIMENSAO)

    for dem in ("DRE", "BPA", "BPP", "DFC_MI"):
        tabela = dem.lower()
        log.info("Criando raw_%s", tabela)
        cur.execute(DDL_RAW.format(tabela=tabela))
        cur.executescript(DDL_RAW_INDICES.format(tabela=tabela))

    log.info("Criando financial_data")
    cur.execute(DDL_FINANCIAL)

    log.info("Criando financial_indicators")
    cur.execute(DDL_INDICADORES)

    log.info("Criando etl_log")
    cur.execute(DDL_LOG)

    log.info("Criando vw_base_analitica")
    cur.execute(DDL_VIEW)

    conn.commit()


def migrar(conn: sqlite3.Connection) -> None:
    """
    Adiciona colunas novas a bancos criados por versoes anteriores
    deste script, sem perder os dados ja carregados.
    """
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(financial_data)")
    existentes = {linha[1] for linha in cur.fetchall()}

    novas = {
        "observacao": "TEXT",
    }

    for coluna, tipo in novas.items():
        if coluna not in existentes:
            cur.execute(
                f"ALTER TABLE financial_data ADD COLUMN {coluna} {tipo}"
            )
            log.info("Migracao | coluna adicionada: financial_data.%s", coluna)

    # a view precisa ser recriada se a estrutura mudou
    cur.execute("DROP VIEW IF EXISTS vw_base_analitica")
    cur.execute(DDL_VIEW)

    conn.commit()


def popular_dimensao(conn: sqlite3.Connection) -> None:
    """Carrega as entidades conhecidas da CVM."""
    cur = conn.cursor()
    linhas = [
        (cd, v["grupo"], v["razao_social"], v["cnpj"])
        for cd, v in ENTIDADES.items()
    ]
    cur.executemany(
        "INSERT OR REPLACE INTO dim_entidade "
        "(cd_cvm, grupo, razao_social, cnpj) VALUES (?,?,?,?)",
        linhas,
    )
    conn.commit()
    log.info("dim_entidade populada com %d entidades", len(linhas))


def resumir(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()

    print("\n" + "=" * 70)
    print("ESTRUTURA CRIADA")
    print("=" * 70)

    cur.execute(
        "SELECT name, type FROM sqlite_master "
        "WHERE type IN ('table','view') AND name NOT LIKE 'sqlite_%' "
        "ORDER BY type, name"
    )
    for nome, tipo in cur.fetchall():
        if tipo == "table":
            cur.execute(f"SELECT COUNT(*) FROM {nome}")
            n = cur.fetchone()[0]
            print(f"  [tabela] {nome:24s} | {n:6d} registros")
        else:
            print(f"  [view]   {nome:24s}")

    print("\n" + "-" * 70)
    print("ENTIDADES CADASTRADAS")
    print("-" * 70)
    cur.execute(
        "SELECT grupo, cd_cvm, razao_social FROM dim_entidade ORDER BY grupo, cd_cvm"
    )
    for grupo, cd, razao in cur.fetchall():
        print(f"  {grupo:10s} | {cd} | {razao}")

    print("\n" + "-" * 70)
    print("INDICADORES MAPEADOS")
    print("-" * 70)
    for ind, (dem, cod, _) in CONTAS.items():
        print(f"  {ind:26s} | {dem:7s} | conta {cod}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Cria o banco SQLite do projeto.")
    ap.add_argument(
        "--reset", action="store_true",
        help="Apaga o banco existente e recria do zero.",
    )
    args = ap.parse_args()

    log.info("=" * 70)
    log.info("CRIACAO DO BANCO DE DADOS")
    log.info("Destino: %s", BANCO)
    log.info("=" * 70)

    if args.reset and BANCO.exists():
        resposta = input(
            f"\n  ATENCAO: isto apagara {BANCO.name} e todos os dados.\n"
            "  Digite 'APAGAR' para confirmar: "
        )
        if resposta.strip() != "APAGAR":
            sys.exit("  Cancelado.")
        BANCO.unlink()
        log.warning("Banco anterior removido")

    novo = not BANCO.exists()

    with sqlite3.connect(BANCO) as conn:
        criar(conn)
        if not novo:
            migrar(conn)
        popular_dimensao(conn)
        conn.execute(
            "INSERT INTO etl_log (etapa, detalhe, registros) VALUES (?,?,?)",
            ("04_criar_banco", "estrutura criada" if novo else "estrutura verificada", 0),
        )
        conn.commit()
        resumir(conn)

    print("\n" + "=" * 70)
    print(f"Banco pronto: {BANCO.relative_to(RAIZ)}")
    print("Proximo passo: python etl/05_carga.py")
    print("=" * 70)


if __name__ == "__main__":
    main()