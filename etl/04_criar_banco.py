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
  Apoio                 : dim_entidade, etl_log

Guardar a camada RAW no banco evita ter que voltar aos ZIPs da CVM
caso surja a necessidade de um novo indicador (ex.: EBITDA).

Este script e IDEMPOTENTE: pode ser executado quantas vezes quiser.
Use --reset para apagar e recriar o banco do zero.

MIGRACAO (revisao Sprint 3)
---------------------------
"CREATE TABLE IF NOT EXISTS" nao altera uma tabela que ja existe. Por
isso, colunas novas (ex.: observacao, contas complementares, indicadores
da Sprint 3) nunca chegavam a um banco criado antes. Agora a funcao
migrar() compara as colunas esperadas com as existentes e executa
ALTER TABLE ... ADD COLUMN para as que faltam. As VIEWS sao sempre
recriadas, para refletir a definicao atual.

COMO RODAR
----------
  python etl/04_criar_banco.py
  python etl/04_criar_banco.py --reset
"""

import argparse
import logging
import sqlite3
import sys

from config import (
    BANCO, DIR_LOGS, ENTIDADES, CONTAS, CONTAS_POR_DESCRICAO, RAIZ,
)

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
# As colunas sao declaradas em listas para que a MIGRACAO saiba
# exatamente o que precisa existir.
COLUNAS_FINANCIAL = [
    ("receita_liquida", "REAL"),
    ("lucro_liquido", "REAL"),
    ("ativo_total", "REAL"),
    ("ativo_circulante", "REAL"),
    ("passivo_total", "REAL"),
    ("passivo_circulante", "REAL"),
    ("passivo_nao_circulante", "REAL"),
    ("patrimonio_liquido", "REAL"),
    ("fluxo_caixa_operacional", "REAL"),
    # complementares (Sprint 3) - contas fixas da CVM
    ("resultado_operacional", "REAL"),        # EBIT (3.05)
    ("resultado_financeiro", "REAL"),         # 3.06
    ("despesas_financeiras", "REAL"),         # 3.06.02
    ("caixa_equivalentes", "REAL"),           # 1.01.01
    ("aplicacoes_financeiras", "REAL"),       # 1.01.02
    ("emprestimos_cp", "REAL"),               # 2.01.04
    ("emprestimos_lp", "REAL"),               # 2.02.01
    ("fluxo_caixa_investimento", "REAL"),     # 6.02
    ("fluxo_caixa_financiamento", "REAL"),    # 6.03
    ("depreciacao_amortizacao", "REAL"),      # DFC 6.01.01.* (por descricao)
    # derivadas
    ("capital_terceiros", "REAL"),            # 2.01 + 2.02 (NAO usar conta 2)
    ("ebitda", "REAL"),                       # EBIT + D&A
    ("divida_bruta", "REAL"),                 # 2.01.04 + 2.02.01
    ("divida_liquida", "REAL"),               # divida bruta - caixa - aplicacoes
    # controle e auditoria
    ("validacao_balanco_ok", "INTEGER"),      # ativo_total == passivo_total
    ("validacao_identidade_ok", "INTEGER"),   # PC + PNC + PL == ativo_total
    ("observacao", "TEXT"),                   # dados atipicos (config.OBSERVACOES)
]

DDL_FINANCIAL = (
    "CREATE TABLE IF NOT EXISTS financial_data (\n"
    "    empresa      TEXT    NOT NULL,\n"
    "    ano          INTEGER NOT NULL,\n"
    "    cd_cvm       TEXT    NOT NULL,\n"
    "    razao_social TEXT,\n"
    + "".join(f"    {nome} {tipo},\n" for nome, tipo in COLUNAS_FINANCIAL)
    + "    atualizado_em TEXT DEFAULT (datetime('now','localtime')),\n"
    "    PRIMARY KEY (empresa, ano)\n"
    ");"
)

# Camada de indicadores - populada pelo etl/08_indicadores.py (Sprint 3).
# Percentuais gravados como FRACAO (0,125 = 12,5%).
COLUNAS_INDICADORES = [
    ("margem_liquida", "REAL"),            # lucro / receita
    ("roe", "REAL"),                       # lucro / PL medio
    ("roa", "REAL"),                       # lucro / ativo medio
    ("endividamento_geral", "REAL"),       # capital terceiros / ativo total
    ("composicao_endividamento", "REAL"),  # passivo circ. / capital terceiros
    ("liquidez_corrente", "REAL"),         # ativo circ. / passivo circ.
    ("cobertura_caixa", "REAL"),           # fco / lucro liquido
    # complementares - hipoteses da secao 7.3 (Sprint 2)
    ("margem_ebitda", "REAL"),             # ebitda / receita
    ("margem_fco", "REAL"),                # fco / receita
    ("divida_liquida_ebitda", "REAL"),     # divida liquida / ebitda
    ("peso_resultado_financeiro", "REAL"), # -resultado financeiro / EBIT
    ("depreciacao_receita", "REAL"),       # D&A / receita
    ("observacao", "TEXT"),
]

DDL_INDICADORES = (
    "CREATE TABLE IF NOT EXISTS financial_indicators (\n"
    "    empresa  TEXT    NOT NULL,\n"
    "    ano      INTEGER NOT NULL,\n"
    + "".join(f"    {nome} {tipo},\n" for nome, tipo in COLUNAS_INDICADORES)
    + "    calculado_em TEXT DEFAULT (datetime('now','localtime')),\n"
    "    PRIMARY KEY (empresa, ano),\n"
    "    FOREIGN KEY (empresa, ano) REFERENCES financial_data (empresa, ano)\n"
    ");"
)

# Alertas de interpretacao dos indicadores (uma linha por ocorrencia)
DDL_ALERTAS = """
CREATE TABLE IF NOT EXISTS alertas_indicadores (
    empresa    TEXT    NOT NULL,
    ano        INTEGER NOT NULL,
    indicador  TEXT    NOT NULL,
    tipo       TEXT    NOT NULL,   -- nao_calculado | distorcido | atipico | contexto
    motivo     TEXT    NOT NULL
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

# Views prontas para o Streamlit (dashboard/). Recriadas a cada execucao.
DDL_VIEWS = {
    "vw_base_analitica": (
        "CREATE VIEW vw_base_analitica AS\n"
        "SELECT f.empresa, f.ano, f.cd_cvm, f.razao_social,\n"
        + ",\n".join(
            f"       f.{nome}" for nome, _ in COLUNAS_FINANCIAL
        )
        + "\nFROM financial_data f\nORDER BY f.empresa, f.ano;"
    ),
    "vw_indicadores": (
        "CREATE VIEW vw_indicadores AS\n"
        "SELECT i.empresa, i.ano,\n"
        + ",\n".join(
            f"       i.{nome}" for nome, _ in COLUNAS_INDICADORES
        )
        + "\nFROM financial_indicators i\nORDER BY i.empresa, i.ano;"
    ),
}


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

    log.info("Criando alertas_indicadores")
    cur.execute(DDL_ALERTAS)

    log.info("Criando etl_log")
    cur.execute(DDL_LOG)

    migrar(conn)

    for nome, ddl in DDL_VIEWS.items():
        log.info("Recriando %s", nome)
        cur.execute(f"DROP VIEW IF EXISTS {nome}")
        cur.execute(ddl)

    conn.commit()


def migrar(conn: sqlite3.Connection) -> None:
    """Acrescenta colunas que faltam em bancos criados por versoes antigas."""
    esperado = {
        "financial_data": COLUNAS_FINANCIAL,
        "financial_indicators": COLUNAS_INDICADORES,
    }
    for tabela, colunas in esperado.items():
        existentes = {
            linha[1] for linha in conn.execute(f"PRAGMA table_info({tabela})")
        }
        for nome, tipo in colunas:
            if nome not in existentes:
                conn.execute(f"ALTER TABLE {tabela} ADD COLUMN {nome} {tipo}")
                log.warning("  Migracao: coluna %s.%s adicionada", tabela, nome)


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
    for ind, (dem, prefixo, trecho) in CONTAS_POR_DESCRICAO.items():
        print(f"  {ind:26s} | {dem:7s} | {prefixo}* contendo '{trecho}'")


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

    conn = sqlite3.connect(BANCO)
    try:
        criar(conn)
        popular_dimensao(conn)
        conn.execute(
            "INSERT INTO etl_log (etapa, detalhe, registros) VALUES (?,?,?)",
            ("04_criar_banco", "estrutura criada" if novo else "estrutura verificada", 0),
        )
        conn.commit()
        resumir(conn)
    finally:
        conn.close()

    print("\n" + "=" * 70)
    print(f"Banco pronto: {BANCO.relative_to(RAIZ)}")
    print("Proximo passo: python etl/05_carga.py")
    print("=" * 70)


if __name__ == "__main__":
    main()