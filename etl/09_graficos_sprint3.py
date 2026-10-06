# -*- coding: utf-8 -*-
"""
etl/09_graficos_sprint3.py

Projeto Integrador III - Fatec Cotia
SPRINT 3 - Figuras estaticas do relatorio (indicadores e hipoteses).

O dashboard Streamlit e interativo; este script gera as MESMAS leituras em
PNG para o relatorio da Sprint 3, a partir do banco (sem recalcular nada).

ENTRADA : database/telecom.db (vw_base_analitica + vw_indicadores)
SAIDA   : graficos/sprint3/fig1 ... fig6 (.png)

COMO RODAR
----------
  python etl/09_graficos_sprint3.py
"""

import logging
import sqlite3
import sys
from contextlib import closing

import matplotlib
matplotlib.use("Agg")  # backend sem interface grafica
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from config import BANCO, DIR_LOGS, RAIZ, ANOS, QUEBRA_ENTIDADE

DIR_FIGURAS = RAIZ / "graficos" / "sprint3"
DIR_FIGURAS.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(DIR_LOGS / "09_graficos_sprint3.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# mesmas cores dos graficos da Sprint 2 e do dashboard
CORES = {"Brisanet": "#1f77b4", "Desktop": "#ff7f0e", "Unifique": "#2ca02c"}
EMPRESAS = ["Brisanet", "Desktop", "Unifique"]
FONTE = "Fonte: CVM – Formulário DFP (consolidado). Elaboração própria."

plt.rcParams.update({
    "figure.dpi": 110,
    "savefig.dpi": 160,
    "font.size": 10,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
})


# ---------------------------------------------------------------
# FORMATACAO (padrao brasileiro)
# ---------------------------------------------------------------
def _br(valor: float, casas: int) -> str:
    texto = f"{valor:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


FMT = {
    "%": mticker.FuncFormatter(lambda v, _p: f"{_br(v * 100, 0)}%"),
    "x": mticker.FuncFormatter(lambda v, _p: f"{_br(v, 1)}x"),
    "R$": mticker.FuncFormatter(lambda v, _p: _br(v / 1e6, 0)),
}


def carregar() -> pd.DataFrame:
    if not BANCO.exists():
        sys.exit("Banco nao encontrado. Rode antes: python etl/rodar_pipeline.py")
    with closing(sqlite3.connect(BANCO)) as conn:
        base = pd.read_sql("SELECT * FROM vw_base_analitica", conn)
        ind = pd.read_sql("SELECT * FROM vw_indicadores", conn)
    if ind.empty:
        sys.exit("Indicadores vazios. Rode antes: python etl/08_indicadores.py")
    ind = ind.drop(columns=["observacao"], errors="ignore")
    return base.merge(ind, on=["empresa", "ano"], how="left")


def marcar_quebra(ax) -> None:
    for empresa, ano in QUEBRA_ENTIDADE.items():
        ax.axvline(ano - 0.5, color=CORES.get(empresa, "grey"), linestyle=":",
                   linewidth=1.3, alpha=0.7, zorder=0)


def painel_linhas(ax, df, coluna, titulo, unidade) -> None:
    for empresa in EMPRESAS:
        g = df[df["empresa"] == empresa].sort_values("ano")
        ax.plot(g["ano"], g[coluna], marker="o", linewidth=2.2, markersize=5.5,
                color=CORES[empresa], label=empresa)
    ax.set_title(titulo, fontsize=11)
    ax.yaxis.set_major_formatter(FMT[unidade])
    ax.set_xticks(ANOS)
    ax.axhline(0, color="grey", linewidth=0.8, zorder=0)
    marcar_quebra(ax)


def salvar(fig, nome: str, nota: str = "") -> None:
    texto = FONTE + (" " + nota if nota else "")
    fig.text(0.01, 0.01, texto, fontsize=7.5, color="grey")
    fig.tight_layout(rect=[0, 0.035, 1, 1])
    destino = DIR_FIGURAS / nome
    fig.savefig(destino)
    plt.close(fig)
    log.info("  %s", destino.relative_to(RAIZ))


NOTA_QUEBRA = "Linha pontilhada: troca de entidade da Brisanet (2024)."


# ---------------------------------------------------------------
# FIGURAS
# ---------------------------------------------------------------
def fig_margens(df) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
    painel_linhas(axes[0], df, "margem_ebitda", "Margem EBITDA", "%")
    painel_linhas(axes[1], df, "margem_liquida", "Margem líquida", "%")
    axes[0].legend(frameon=False)
    salvar(fig, "fig1_margens.png", NOTA_QUEBRA)


def fig_rentabilidade(df) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    painel_linhas(axes[0], df, "roe", "ROE (lucro ÷ PL médio)", "%")
    painel_linhas(axes[1], df, "roa", "ROA (lucro ÷ ativo médio)", "%")
    axes[0].legend(frameon=False)
    salvar(fig, "fig2_rentabilidade.png",
           "Desktop 2020 sem cálculo: a DFP 2020 não traz o saldo inicial de 2019. "
           + NOTA_QUEBRA)


def fig_estrutura(df) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    painel_linhas(axes[0, 0], df, "endividamento_geral",
                  "Endividamento geral (capital de terceiros ÷ ativo)", "%")
    painel_linhas(axes[0, 1], df, "composicao_endividamento",
                  "Composição do endividamento (curto prazo)", "%")
    painel_linhas(axes[1, 0], df, "divida_liquida_ebitda",
                  "Dívida líquida ÷ EBITDA (negativo = caixa líquido)", "x")
    painel_linhas(axes[1, 1], df, "liquidez_corrente", "Liquidez corrente", "x")
    axes[0, 0].legend(frameon=False)
    salvar(fig, "fig3_estrutura_liquidez.png", NOTA_QUEBRA)


def fig_ponte(df, ano: int) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.6), sharey=True)
    for ax, empresa in zip(axes, EMPRESAS):
        r = df[(df["empresa"] == empresa) & (df["ano"] == ano)].iloc[0]
        rec = r["receita_liquida"]
        etapas = [
            ("EBITDA", r["ebitda"] / rec),
            ("Deprec.", -r["depreciacao_amortizacao"] / rec),
            ("Res. fin.", r["resultado_financeiro"] / rec),
            ("IR/CS e\noutros",
             (r["lucro_liquido"] - r["resultado_operacional"] - r["resultado_financeiro"]) / rec),
        ]
        acumulado = 0.0
        for i, (rotulo, valor) in enumerate(etapas):
            if i == 0:
                base, altura, cor = 0.0, valor, CORES[empresa]
            else:
                base = acumulado + min(valor, 0)
                altura, cor = abs(valor), ("#d62728" if valor < 0 else "#2ca02c")
            ax.bar(rotulo, altura, bottom=base, color=cor, width=0.62)
            topo = base + altura
            ax.text(i, topo + 0.01, f"{_br(valor * 100, 1)}%", ha="center",
                    va="bottom", fontsize=8.5)
            acumulado += valor
        ll = r["lucro_liquido"] / rec
        ax.bar("Lucro\nlíquido", ll, color=CORES[empresa], alpha=0.55, width=0.62)
        ax.text(len(etapas), ll + 0.01, f"{_br(ll * 100, 1)}%", ha="center",
                va="bottom", fontsize=8.5, fontweight="bold")
        ax.set_title(f"{empresa} · {ano}", fontsize=11)
        ax.yaxis.set_major_formatter(FMT["%"])
        ax.grid(axis="x", visible=False)
        ax.tick_params(axis="x", labelsize=8.5)
    salvar(fig, f"fig4_ponte_margens_{ano}.png",
           "Percentuais sobre a receita líquida. EBITDA − depreciação = EBIT; "
           "EBIT + resultado financeiro = lucro antes do IR.")


def fig_hipoteses(df) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    painel_linhas(axes[0], df, "peso_resultado_financeiro",
                  "H1 · Resultado financeiro ÷ EBIT", "%")
    painel_linhas(axes[1], df, "depreciacao_receita",
                  "H2 · Depreciação e amortização ÷ receita", "%")
    axes[0].legend(frameon=False)
    salvar(fig, "fig5_hipoteses_h1_h2.png", NOTA_QUEBRA)


def fig_caixa(df) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), sharey=True)
    largura = 0.38
    for ax, empresa in zip(axes, EMPRESAS):
        g = df[df["empresa"] == empresa].sort_values("ano")
        ax.bar(g["ano"] - largura / 2, g["fluxo_caixa_operacional"], width=largura,
               color=CORES[empresa], label="FCO")
        ax.bar(g["ano"] + largura / 2, g["lucro_liquido"], width=largura,
               color="#7f7f7f", label="Lucro líquido")
        ax.set_title(f"H3 · {empresa}: FCO x lucro líquido", fontsize=11)
        ax.yaxis.set_major_formatter(FMT["R$"])
        ax.set_xticks(ANOS)
        ax.tick_params(axis="x", labelsize=8.5)
        ax.grid(axis="x", visible=False)
    axes[0].set_ylabel("R$ milhões")
    axes[0].legend(frameon=False)
    salvar(fig, "fig6_hipotese_h3_caixa.png",
           "Desktop 2021: FCO atípico (215,8% da receita), mantido como publicado.")


def main() -> None:
    df = carregar()
    log.info("Gerando figuras da Sprint 3:")
    fig_margens(df)
    fig_rentabilidade(df)
    fig_estrutura(df)
    fig_ponte(df, int(df["ano"].max()))
    fig_hipoteses(df)
    fig_caixa(df)
    print(f"\nFiguras salvas em {DIR_FIGURAS.relative_to(RAIZ)}/")


if __name__ == "__main__":
    main()
