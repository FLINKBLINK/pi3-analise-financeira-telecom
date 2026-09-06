# -*- coding: utf-8 -*-
"""
etl/06_eda.py

Projeto Integrador III - Fatec Cotia
Analise Exploratoria de Dados (EDA) - encerramento da Sprint 2

ESCOPO
------
Este script DESCREVE os dados. Ele NAO calcula indicadores financeiros
(ROE, ROA, margem, endividamento) - isso e escopo da Sprint 3.

O objetivo aqui e observar tendencias e documentar o comportamento das
variaveis, sem tirar conclusoes analiticas.

ENTRADA
-------
  database/telecom.db  ->  tabela financial_data

SAIDAS
------
  graficos/evolucao_<indicador>.png     serie temporal por empresa
  graficos/comparativo_<indicador>.png  barras agrupadas por ano
  graficos/painel_geral.png             visao consolidada 2x3
  data/exports/estatisticas_descritivas.csv
  data/exports/variacoes_anuais.csv
  data/exports/resumo_eda.csv

OBSERVACAO METODOLOGICA
-----------------------
Os graficos da Brisanet recebem uma marcacao vertical em 2024, ano em
que a serie muda de entidade (Participacoes -> Servicos) por conta da
incorporacao societaria. Isso e exigencia de transparencia: o leitor
precisa saber que ha uma quebra na origem do dado.

COMO RODAR
----------
  python etl/06_eda.py
"""

import logging
import sqlite3

import matplotlib
matplotlib.use("Agg")  # backend sem interface grafica
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from config import (
    BANCO, DIR_LOGS, DIR_EXPORTS, RAIZ, ANOS, QUEBRA_ENTIDADE,
)

DIR_GRAFICOS = RAIZ / "graficos"
DIR_GRAFICOS.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(DIR_LOGS / "06_eda.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------
# CONFIGURACAO VISUAL
# ---------------------------------------------------------------
# Cores fixas por empresa, para manter consistencia entre todos os
# graficos do relatorio e, depois, do dashboard Streamlit.
CORES = {
    "Brisanet": "#1f77b4",
    "Unifique": "#2ca02c",
    "Desktop":  "#ff7f0e",
}

TITULOS = {
    "receita_liquida":         "Receita Liquida",
    "lucro_liquido":           "Lucro Liquido",
    "ativo_total":             "Ativo Total",
    "ativo_circulante":        "Ativo Circulante",
    "patrimonio_liquido":      "Patrimonio Liquido",
    "capital_terceiros":       "Capital de Terceiros",
    "passivo_circulante":      "Passivo Circulante",
    "passivo_nao_circulante":  "Passivo Nao Circulante",
    "fluxo_caixa_operacional": "Fluxo de Caixa Operacional",
}

# Indicadores destacados no painel consolidado
PAINEL = [
    "receita_liquida", "lucro_liquido", "ativo_total",
    "patrimonio_liquido", "capital_terceiros", "fluxo_caixa_operacional",
]

plt.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 150,
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


# ---------------------------------------------------------------
def carregar() -> pd.DataFrame:
    """Le a base analitica direto do SQLite."""
    if not BANCO.exists():
        raise SystemExit(
            f"Banco nao encontrado em {BANCO}.\n"
            "Rode antes: python etl/04_criar_banco.py && python etl/05_carga.py"
        )

    with sqlite3.connect(BANCO) as conn:
        df = pd.read_sql(
            "SELECT * FROM financial_data ORDER BY empresa, ano", conn
        )

    if df.empty:
        raise SystemExit("financial_data esta vazia. Rode etl/05_carga.py.")

    log.info(
        "Base carregada | %d linhas | %d empresas | anos %d-%d",
        len(df), df["empresa"].nunique(), df["ano"].min(), df["ano"].max(),
    )
    return df


def milhoes(valor, _pos=None) -> str:
    """Formata o eixo Y em R$ milhoes com separador brasileiro."""
    return f"{valor / 1_000_000:,.0f}".replace(",", ".")


def marcar_quebra(ax, empresas) -> None:
    """
    Sinaliza o ano em que a serie muda de entidade juridica.
    Sem isso, o grafico esconde uma descontinuidade metodologica.
    """
    for empresa, ano in QUEBRA_ENTIDADE.items():
        if empresa in empresas:
            ax.axvline(
                ano - 0.5, color=CORES.get(empresa, "grey"),
                linestyle=":", linewidth=1.4, alpha=0.7, zorder=0,
            )
            ax.annotate(
                f"{empresa}: troca de entidade",
                xy=(ano - 0.5, 0.97), xycoords=("data", "axes fraction"),
                fontsize=7.5, color=CORES.get(empresa, "grey"),
                rotation=90, va="top", ha="right", alpha=0.85,
            )


# ---------------------------------------------------------------
# GRAFICOS
# ---------------------------------------------------------------
def grafico_evolucao(base: pd.DataFrame, coluna: str) -> None:
    """Serie temporal - uma linha por empresa."""
    fig, ax = plt.subplots(figsize=(9, 5))

    for empresa, grupo in base.groupby("empresa"):
        g = grupo.sort_values("ano")
        ax.plot(
            g["ano"], g[coluna], marker="o", linewidth=2.2,
            markersize=6, label=empresa,
            color=CORES.get(empresa),
        )

    ax.set_title(
        f"{TITULOS[coluna]} | Operadoras Regionais de Telecomunicacoes",
        fontsize=12, pad=12,
    )
    ax.set_xlabel("Exercicio")
    ax.set_ylabel("R$ milhoes")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(milhoes))
    ax.set_xticks(ANOS)
    ax.axhline(0, color="grey", linewidth=0.8, zorder=0)
    marcar_quebra(ax, set(base["empresa"]))
    ax.legend(frameon=False)

    fig.text(
        0.01, 0.01,
        "Fonte: CVM - Formulario DFP (consolidado). Elaboracao propria.",
        fontsize=7, color="grey",
    )
    fig.tight_layout(rect=[0, 0.03, 1, 1])

    destino = DIR_GRAFICOS / f"evolucao_{coluna}.png"
    fig.savefig(destino)
    plt.close(fig)
    log.info("  %s", destino.name)


def grafico_comparativo(base: pd.DataFrame, coluna: str) -> None:
    """Barras agrupadas - comparacao direta ano a ano."""
    pivot = base.pivot(index="ano", columns="empresa", values=coluna)
    cores = [CORES.get(c, None) for c in pivot.columns]

    fig, ax = plt.subplots(figsize=(9, 5))
    pivot.plot(kind="bar", ax=ax, width=0.78, color=cores, edgecolor="none")

    ax.set_title(f"{TITULOS[coluna]} | comparativo anual", fontsize=12, pad=12)
    ax.set_xlabel("Exercicio")
    ax.set_ylabel("R$ milhoes")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(milhoes))
    ax.tick_params(axis="x", rotation=0)
    ax.axhline(0, color="grey", linewidth=0.8)
    ax.legend(frameon=False, title=None)
    ax.grid(axis="x", visible=False)

    fig.text(
        0.01, 0.01,
        "Fonte: CVM - Formulario DFP (consolidado). Elaboracao propria.",
        fontsize=7, color="grey",
    )
    fig.tight_layout(rect=[0, 0.03, 1, 1])

    destino = DIR_GRAFICOS / f"comparativo_{coluna}.png"
    fig.savefig(destino)
    plt.close(fig)
    log.info("  %s", destino.name)


def painel_geral(base: pd.DataFrame) -> None:
    """Visao consolidada 2x3 - util para a apresentacao da sprint."""
    fig, axes = plt.subplots(2, 3, figsize=(16, 9))

    for ax, coluna in zip(axes.flat, PAINEL):
        for empresa, grupo in base.groupby("empresa"):
            g = grupo.sort_values("ano")
            ax.plot(
                g["ano"], g[coluna], marker="o", linewidth=2,
                markersize=4.5, label=empresa, color=CORES.get(empresa),
            )
        ax.set_title(TITULOS[coluna], fontsize=11)
        ax.yaxis.set_major_formatter(mticker.FuncFormatter(milhoes))
        ax.set_xticks(ANOS)
        ax.tick_params(labelsize=8)
        ax.axhline(0, color="grey", linewidth=0.7, zorder=0)

    axes.flat[0].legend(frameon=False, fontsize=9)

    fig.suptitle(
        "Panorama Financeiro | Brisanet, Unifique e Desktop | "
        f"{min(ANOS)}-{max(ANOS)}  (valores em R$ milhoes)",
        fontsize=13.5, y=0.985,
    )
    fig.text(
        0.01, 0.01,
        "Fonte: CVM - Formulario DFP (consolidado). Elaboracao propria. "
        "Serie da Brisanet encadeada: Participacoes ate 2023, Servicos a partir de 2024.",
        fontsize=8, color="grey",
    )
    fig.tight_layout(rect=[0, 0.025, 1, 0.97])

    destino = DIR_GRAFICOS / "painel_geral.png"
    fig.savefig(destino)
    plt.close(fig)
    log.info("  %s", destino.name)


# ---------------------------------------------------------------
# ESTATISTICAS
# ---------------------------------------------------------------
def estatisticas(base: pd.DataFrame) -> None:
    """Estatisticas descritivas por empresa."""
    colunas = list(TITULOS)

    stats = (
        base.groupby("empresa")[colunas]
            .agg(["count", "mean", "std", "min", "median", "max"])
            .T
    )
    destino = DIR_EXPORTS / "estatisticas_descritivas.csv"
    stats.to_csv(destino, sep=";", decimal=",", encoding="utf-8-sig")
    log.info("Estatisticas descritivas salvas")


def variacoes(base: pd.DataFrame) -> pd.DataFrame:
    """Variacao percentual ano a ano - descritivo, sem interpretacao."""
    colunas = list(TITULOS)
    var = base.sort_values(["empresa", "ano"]).copy()

    for col in colunas:
        var[f"var_{col}_%"] = (
            var.groupby("empresa")[col].pct_change() * 100
        ).round(2)

    destino = DIR_EXPORTS / "variacoes_anuais.csv"
    cols = ["empresa", "ano"] + [f"var_{c}_%" for c in colunas]
    var[cols].to_csv(
        destino, index=False, sep=";", decimal=",", encoding="utf-8-sig"
    )
    log.info("Variacoes anuais salvas")
    return var


def resumo(base: pd.DataFrame) -> None:
    """
    Resumo de crescimento acumulado no periodo.
    Descritivo: mostra o quanto cada variavel cresceu, sem explicar por que.
    """
    linhas = []
    ano_ini, ano_fim = base["ano"].min(), base["ano"].max()

    for empresa, grupo in base.groupby("empresa"):
        ini = grupo[grupo["ano"] == ano_ini]
        fim = grupo[grupo["ano"] == ano_fim]
        if ini.empty or fim.empty:
            continue

        for col in PAINEL:
            v0 = ini[col].iloc[0]
            v1 = fim[col].iloc[0]
            if pd.isna(v0) or pd.isna(v1) or v0 == 0:
                continue

            linhas.append({
                "empresa": empresa,
                "indicador": TITULOS[col],
                f"{ano_ini}_mi": round(v0 / 1e6, 1),
                f"{ano_fim}_mi": round(v1 / 1e6, 1),
                "crescimento_%": round((v1 / v0 - 1) * 100, 1),
            })

    df = pd.DataFrame(linhas)
    destino = DIR_EXPORTS / "resumo_eda.csv"
    df.to_csv(destino, index=False, sep=";", decimal=",", encoding="utf-8-sig")

    print("\n" + "=" * 78)
    print(f"CRESCIMENTO ACUMULADO {ano_ini}-{ano_fim}")
    print("=" * 78)
    print(df.to_string(index=False))
    return df


def observacoes(base: pd.DataFrame) -> None:
    """
    Observacoes descritivas geradas a partir dos dados.
    Sao CONSTATACOES, nao conclusoes analiticas - a interpretacao
    fica para a Sprint 3, apos o calculo dos indicadores.
    """
    print("\n" + "=" * 78)
    print("OBSERVACOES DESCRITIVAS (para o relatorio da Sprint 2)")
    print("=" * 78)

    ano_ini, ano_fim = base["ano"].min(), base["ano"].max()

    # 1. trajetoria da receita
    print("\n1. RECEITA LIQUIDA")
    for empresa, g in base.groupby("empresa"):
        g = g.sort_values("ano")
        cresc = (g["receita_liquida"].diff().dropna() > 0).all()
        print(
            f"   {empresa:9s} | {g['receita_liquida'].iloc[0]/1e6:7.1f} -> "
            f"{g['receita_liquida'].iloc[-1]/1e6:7.1f} mi | "
            f"{'crescimento continuo' if cresc else 'oscilacao'}"
        )

    # 2. ano de pico do lucro
    print("\n2. LUCRO LIQUIDO - ano de maior resultado")
    for empresa, g in base.groupby("empresa"):
        idx = g["lucro_liquido"].idxmax()
        pico_ano = int(g.loc[idx, "ano"])
        pico_val = g.loc[idx, "lucro_liquido"] / 1e6
        ultimo = g[g["ano"] == ano_fim]["lucro_liquido"].iloc[0] / 1e6
        situacao = "pico no ultimo ano" if pico_ano == ano_fim else \
                   f"pico em {pico_ano}, {ano_fim} em {ultimo:.1f} mi"
        print(f"   {empresa:9s} | {pico_val:7.1f} mi | {situacao}")

    # 3. salto do patrimonio liquido
    print("\n3. PATRIMONIO LIQUIDO - maior variacao anual")
    for empresa, g in base.groupby("empresa"):
        g = g.sort_values("ano").copy()
        g["var"] = g["patrimonio_liquido"].pct_change() * 100
        if g["var"].notna().any():
            idx = g["var"].idxmax()
            print(
                f"   {empresa:9s} | {int(g.loc[idx,'ano'])} | "
                f"+{g.loc[idx,'var']:.0f}%"
            )

    # 4. caixa operacional x lucro
    print("\n4. FCO vs LUCRO LIQUIDO (razao media no periodo)")
    for empresa, g in base.groupby("empresa"):
        razao = (g["fluxo_caixa_operacional"] / g["lucro_liquido"]).replace(
            [float("inf"), float("-inf")], pd.NA
        ).dropna()
        if not razao.empty:
            print(f"   {empresa:9s} | {razao.mean():5.1f}x")

    print(
        "\nNOTA: a razao FCO/Lucro acima e apenas descritiva. A analise de\n"
        "qualidade do resultado sera feita na Sprint 3, com os indicadores."
    )


# ---------------------------------------------------------------
def main() -> None:
    log.info("=" * 70)
    log.info("ANALISE EXPLORATORIA DE DADOS - Sprint 2")
    log.info("=" * 70)

    base = carregar()

    log.info("\nGerando graficos de evolucao:")
    for coluna in TITULOS:
        if base[coluna].notna().any():
            grafico_evolucao(base, coluna)
        else:
            log.warning("  Sem dados para %s", coluna)

    log.info("\nGerando graficos comparativos:")
    for coluna in PAINEL:
        if base[coluna].notna().any():
            grafico_comparativo(base, coluna)

    log.info("\nGerando painel consolidado:")
    painel_geral(base)

    log.info("\nGerando estatisticas:")
    estatisticas(base)
    variacoes(base)

    resumo(base)
    observacoes(base)

    print("\n" + "=" * 78)
    print("EDA CONCLUIDA")
    print(f"  Graficos : {DIR_GRAFICOS.relative_to(RAIZ)}/")
    print(f"  Tabelas  : {DIR_EXPORTS.relative_to(RAIZ)}/")
    print("\nSprint 2 encerrada. Proximo passo: Sprint 3 (indicadores).")
    print("=" * 78)


if __name__ == "__main__":
    main()