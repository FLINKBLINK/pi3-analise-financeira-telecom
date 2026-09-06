# -*- coding: utf-8 -*-
"""
etl/05_carga.py

Projeto Integrador III - Fatec Cotia
Carrega os CSVs da CVM no SQLite e monta a base analitica.

FLUXO
-----
  CSV CVM  ->  raw_dre / raw_bpa / raw_bpp / raw_dfc_mi   (camada 1)
           ->  financial_data                            (camada 2)

REGRAS APLICADAS
----------------
  1. Apenas ORDEM_EXERC = ULTIMO (evita duplicar o ano anterior)
  2. Apenas a maior VERSAO (a CVM permite reapresentacao)
  3. Escala monetaria aplicada (MIL -> x1000), valores em REAIS
  4. Serie encadeada da Brisanet conforme config.ENCADEAMENTO
  5. capital_terceiros = passivo_circulante + passivo_nao_circulante
  6. Validacao do balanco: ativo_total deve bater com passivo_total

Este script e IDEMPOTENTE: reexecutar substitui os dados, nao duplica.

COMO RODAR
----------
  python etl/05_carga.py
  python etl/05_carga.py --somente-raw
"""

import argparse
import logging
import sqlite3

import pandas as pd

from config import (
    BANCO, DIR_LOGS, DIR_EXPORTS, RAIZ,
    ANOS, DEMONSTRACOES, ENTIDADES, ENCADEAMENTO,
    CONTAS, ORDEM_INDICADORES, CSV_KWARGS, ORDEM_EXERCICIO, ESCALA,
    COLUNAS_UTEIS, normalizar_cvm, caminho_arquivo, entidade_do_ano,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(DIR_LOGS / "05_carga.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

TOLERANCIA_BALANCO = 0.01  # 1% de diferenca aceita entre ativo e passivo


# ===============================================================
# CAMADA 1 - RAW
# ===============================================================
def ler_csv(demonstracao: str, ano: int) -> pd.DataFrame:
    """Le um CSV da CVM e devolve apenas as entidades do projeto."""
    arq = caminho_arquivo(demonstracao, ano)

    if not arq.exists():
        log.warning("  %d | arquivo ausente: %s", ano, arq.name)
        return pd.DataFrame()

    df = pd.read_csv(arq, **CSV_KWARGS)

    cols = [c for c in COLUNAS_UTEIS if c in df.columns]
    df = df[cols].copy()

    df["CD_CVM"] = normalizar_cvm(df["CD_CVM"])
    df = df[df["CD_CVM"].isin(ENTIDADES)].copy()

    if df.empty:
        log.warning("  %d | nenhuma entidade do projeto encontrada", ano)
        return df

    # valor numerico com escala aplicada
    valor = pd.to_numeric(
        df["VL_CONTA"].astype(str).str.strip().str.replace(",", ".", regex=False),
        errors="coerce",
    )
    fator = df["ESCALA_MOEDA"].str.upper().str.strip().map(ESCALA).fillna(1)
    df["VL_CONTA"] = valor * fator

    df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce").fillna(0).astype(int)
    df["ano_arquivo"] = ano

    grupos = sorted({ENTIDADES[c]["grupo"] for c in df["CD_CVM"].unique()})
    log.info("  %d | %5d linhas | %s", ano, len(df), ", ".join(grupos))

    return df


def carregar_raw(conn: sqlite3.Connection) -> None:
    log.info("=" * 70)
    log.info("CAMADA 1 | CARGA DOS DADOS BRUTOS")
    log.info("=" * 70)

    renomear = {
        "CNPJ_CIA": "cnpj_cia", "DT_REFER": "dt_refer", "VERSAO": "versao",
        "DENOM_CIA": "denom_cia", "CD_CVM": "cd_cvm", "MOEDA": "moeda",
        "ESCALA_MOEDA": "escala_moeda", "ORDEM_EXERC": "ordem_exerc",
        "DT_INI_EXERC": "dt_ini_exerc", "DT_FIM_EXERC": "dt_fim_exerc",
        "CD_CONTA": "cd_conta", "DS_CONTA": "ds_conta",
        "VL_CONTA": "vl_conta", "ST_CONTA_FIXA": "st_conta_fixa",
    }

    for dem in DEMONSTRACOES:
        tabela = f"raw_{dem.lower()}"
        log.info("\n[%s] -> %s", dem, tabela)

        partes = [ler_csv(dem, ano) for ano in ANOS]
        partes = [p for p in partes if not p.empty]

        if not partes:
            log.error("  Nenhum dado para %s", dem)
            continue

        df = pd.concat(partes, ignore_index=True)
        df = df.rename(columns=renomear)

        # idempotencia: limpa antes de inserir
        conn.execute(f"DELETE FROM {tabela}")

        colunas_bd = [c for c in renomear.values() if c in df.columns]
        colunas_bd.append("ano_arquivo")
        df[colunas_bd].to_sql(tabela, conn, if_exists="append", index=False)

        conn.execute(
            "INSERT INTO etl_log (etapa, detalhe, registros) VALUES (?,?,?)",
            ("05_carga_raw", tabela, len(df)),
        )
        log.info("  Total inserido: %d linhas", len(df))

    conn.commit()


# ===============================================================
# CAMADA 2 - BASE ANALITICA
# ===============================================================
def extrair_indicadores(conn: sqlite3.Connection) -> pd.DataFrame:
    """Le as tabelas raw e extrai os indicadores mapeados."""
    log.info("\n" + "=" * 70)
    log.info("CAMADA 2 | EXTRACAO DOS INDICADORES")
    log.info("=" * 70)

    registros = []

    for indicador, (dem, codigo, obrigatorio) in CONTAS.items():
        tabela = f"raw_{dem.lower()}"

        df = pd.read_sql(
            f"""
            SELECT cd_cvm, denom_cia, ano_arquivo, versao,
                   dt_fim_exerc, dt_refer, vl_conta
            FROM {tabela}
            WHERE TRIM(cd_conta) = ?
              AND UPPER(TRIM(ordem_exerc)) = ?
            """,
            conn,
            params=(codigo, ORDEM_EXERCICIO),
        )

        if df.empty:
            nivel = log.error if obrigatorio else log.warning
            nivel("  [!] %s | conta %s nao retornou dados", indicador, codigo)
            continue

        # ano de referencia
        df["ano"] = pd.to_datetime(
            df["dt_fim_exerc"], errors="coerce"
        ).dt.year
        df["ano"] = df["ano"].fillna(
            pd.to_datetime(df["dt_refer"], errors="coerce").dt.year
        )
        df = df[df["ano"].notna()].copy()
        df["ano"] = df["ano"].astype(int)

        # reapresentacoes: fica a maior versao
        antes = len(df)
        df = (
            df.sort_values("versao")
              .drop_duplicates(subset=["cd_cvm", "ano"], keep="last")
        )
        removidas = antes - len(df)

        df["indicador"] = indicador
        registros.append(df[["cd_cvm", "ano", "indicador", "vl_conta"]])

        log.info(
            "  %-24s | conta %-6s | %3d registros%s",
            indicador, codigo, len(df),
            f" ({removidas} reapresentacoes removidas)" if removidas else "",
        )

    if not registros:
        raise SystemExit("Nenhum indicador extraido. Verifique a camada raw.")

    return pd.concat(registros, ignore_index=True)


def aplicar_encadeamento(df: pd.DataFrame) -> pd.DataFrame:
    """
    Resolve qual entidade representa cada grupo em cada ano.

    A Brisanet possui duas entidades na CVM (holding e operacional),
    com sobreposicao em 2023. A regra de config.ENCADEAMENTO define
    qual usar em cada exercicio.
    """
    log.info("\n" + "-" * 70)
    log.info("APLICANDO SERIE ENCADEADA")
    log.info("-" * 70)

    df = df.copy()
    df["grupo"] = df["cd_cvm"].map(lambda c: ENTIDADES[c]["grupo"])

    # marca as linhas que devem ser mantidas
    df["cd_cvm_esperado"] = df.apply(
        lambda r: entidade_do_ano(r["grupo"], r["ano"]), axis=1
    )
    manter = df["cd_cvm"] == df["cd_cvm_esperado"]

    descartadas = df[~manter]
    if not descartadas.empty:
        resumo = (
            descartadas.groupby(["grupo", "ano", "cd_cvm"])
                       .size().reset_index(name="linhas")
        )
        for _, r in resumo.iterrows():
            razao = ENTIDADES[r["cd_cvm"]]["razao_social"]
            log.info(
                "  Descartado | %s %d | %s (%s) | %d linhas",
                r["grupo"], r["ano"], r["cd_cvm"], razao, r["linhas"],
            )

    df = df[manter].copy()

    for grupo, regra in ENCADEAMENTO.items():
        anos_grupo = sorted(df[df["grupo"] == grupo]["ano"].unique())
        entidades_usadas = sorted(df[df["grupo"] == grupo]["cd_cvm"].unique())
        log.info(
            "  %-10s | anos %s | entidades %s",
            grupo, anos_grupo, entidades_usadas,
        )

    return df


def montar_base(df: pd.DataFrame) -> pd.DataFrame:
    """Pivota para formato largo e calcula colunas derivadas."""
    log.info("\n" + "-" * 70)
    log.info("MONTANDO BASE ANALITICA")
    log.info("-" * 70)

    base = df.pivot_table(
        index=["grupo", "ano", "cd_cvm"],
        columns="indicador",
        values="vl_conta",
        aggfunc="first",
    ).reset_index()
    base.columns.name = None

    base = base.rename(columns={"grupo": "empresa"})
    base["razao_social"] = base["cd_cvm"].map(
        lambda c: ENTIDADES[c]["razao_social"]
    )

    for col in ORDEM_INDICADORES:
        if col not in base.columns:
            base[col] = pd.NA
            log.warning("  Indicador ausente: %s", col)

    # ---- capital de terceiros ----
    # NAO usar passivo_total (conta 2), que ja inclui o PL.
    base["capital_terceiros"] = (
        base["passivo_circulante"].fillna(0)
        + base["passivo_nao_circulante"].fillna(0)
    )

    # fallback: ativo_total - patrimonio_liquido
    sem_capital = base["capital_terceiros"] == 0
    if sem_capital.any():
        base.loc[sem_capital, "capital_terceiros"] = (
            base.loc[sem_capital, "ativo_total"]
            - base.loc[sem_capital, "patrimonio_liquido"]
        )
        log.warning(
            "  %d linhas usaram fallback (ativo - PL) para capital_terceiros",
            int(sem_capital.sum()),
        )

    # ---- validacao do balanco ----
    diff = (base["ativo_total"] - base["passivo_total"]).abs()
    denom = base["ativo_total"].abs().replace(0, pd.NA)
    base["validacao_balanco_ok"] = (
        (diff / denom) < TOLERANCIA_BALANCO
    ).astype("Int64")

    colunas = (
        ["empresa", "ano", "cd_cvm", "razao_social"]
        + ORDEM_INDICADORES
        + ["capital_terceiros", "validacao_balanco_ok"]
    )
    base = base[colunas].sort_values(["empresa", "ano"]).reset_index(drop=True)

    log.info("  Base montada: %d linhas", len(base))
    return base


def auditar(base: pd.DataFrame) -> None:
    log.info("\n" + "=" * 70)
    log.info("AUDITORIA")
    log.info("=" * 70)

    esperado = {(g, a) for g in ENCADEAMENTO for a in ANOS}
    obtido = set(zip(base["empresa"], base["ano"]))
    faltando = sorted(esperado - obtido)

    if faltando:
        log.warning("  Combinacoes empresa/ano ausentes: %s", faltando)
    else:
        log.info("  [ok] Todas as %d combinacoes empresa/ano presentes", len(esperado))

    # nulos
    log.info("\n  Completude por indicador:")
    for col in ORDEM_INDICADORES + ["capital_terceiros"]:
        nulos = base[col].isna().sum()
        marca = "[ok]" if nulos == 0 else "[!] "
        log.info("    %s %-26s | %d nulos de %d", marca, col, nulos, len(base))

    # validacao do balanco
    invalidos = base[base["validacao_balanco_ok"] != 1]
    if invalidos.empty:
        log.info("\n  [ok] Balanco valida em todas as linhas (ativo == passivo)")
    else:
        log.warning("\n  [!] Balanco NAO fecha em %d linhas:", len(invalidos))
        for _, r in invalidos.iterrows():
            log.warning(
                "      %s %d | ativo %.0f | passivo %.0f",
                r["empresa"], r["ano"], r["ativo_total"] or 0, r["passivo_total"] or 0,
            )

    # sanidade: capital de terceiros deve ser menor que o ativo
    ruim = base[base["capital_terceiros"] > base["ativo_total"]]
    if not ruim.empty:
        log.warning(
            "  [!] capital_terceiros > ativo_total em %d linhas - investigar",
            len(ruim),
        )


def gravar(conn: sqlite3.Connection, base: pd.DataFrame) -> None:
    conn.execute("DELETE FROM financial_data")

    cols = [
        "empresa", "ano", "cd_cvm", "razao_social",
        *ORDEM_INDICADORES,
        "capital_terceiros", "validacao_balanco_ok",
    ]
    base[cols].to_sql("financial_data", conn, if_exists="append", index=False)

    conn.execute(
        "INSERT INTO etl_log (etapa, detalhe, registros) VALUES (?,?,?)",
        ("05_carga_analitica", "financial_data", len(base)),
    )
    conn.commit()
    log.info("\n  financial_data gravada: %d linhas", len(base))

    destino = DIR_EXPORTS / "financial_data.csv"
    base.to_csv(destino, index=False, sep=";", encoding="utf-8-sig", decimal=",")
    log.info("  Backup CSV: %s", destino.relative_to(RAIZ))


def exibir(base: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("BASE ANALITICA (valores em R$ milhoes)")
    print("=" * 78)

    v = base.copy()
    num = [
        "receita_liquida", "lucro_liquido", "ativo_total",
        "patrimonio_liquido", "capital_terceiros", "fluxo_caixa_operacional",
    ]
    for c in num:
        v[c] = (v[c] / 1_000_000).round(1)

    v = v.rename(columns={
        "receita_liquida": "receita", "lucro_liquido": "lucro",
        "ativo_total": "ativo", "patrimonio_liquido": "PL",
        "capital_terceiros": "cap_terc", "fluxo_caixa_operacional": "FCO",
    })

    print(v[["empresa", "ano", "cd_cvm", "receita", "lucro",
             "ativo", "PL", "cap_terc", "FCO"]].to_string(index=False))


# ===============================================================
def main() -> None:
    ap = argparse.ArgumentParser(description="Carga dos dados da CVM no SQLite.")
    ap.add_argument(
        "--somente-raw", action="store_true",
        help="Carrega apenas a camada bruta, sem montar financial_data.",
    )
    args = ap.parse_args()

    if not BANCO.exists():
        raise SystemExit(
            f"Banco nao encontrado em {BANCO}.\n"
            "Rode antes: python etl/04_criar_banco.py"
        )

    with sqlite3.connect(BANCO) as conn:
        carregar_raw(conn)

        if args.somente_raw:
            log.info("\nModo --somente-raw. Encerrando.")
            return

        df = extrair_indicadores(conn)
        df = aplicar_encadeamento(df)
        base = montar_base(df)
        auditar(base)
        gravar(conn, base)
        exibir(base)

    print("\n" + "=" * 78)
    print("CARGA CONCLUIDA")
    print("Confira: SELECT * FROM vw_base_analitica;")
    print("=" * 78)


if __name__ == "__main__":
    main()