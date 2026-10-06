# -*- coding: utf-8 -*-
"""
dashboard/visual.py

Projeto Integrador III - Fatec Cotia | Sprint 3
Graficos Plotly padronizados (cores fixas por empresa, numeros no padrao
brasileiro e marcacao da troca de entidade da Brisanet em 2024).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from dados import CORES, EMPRESAS, QUEBRA_ENTIDADE, rotulo, unidade

# formato do eixo e do hover para cada unidade
FORMATOS = {
    "%": {"tick": ".0%", "hover": "%{y:.1%}", "titulo": ""},
    "x": {"tick": ".1f", "hover": "%{y:.2f}x", "titulo": "vezes"},
    "R$": {"tick": ",.0f", "hover": "R$ %{y:,.1f} mi", "titulo": "R$ milhões"},
}


def _escala(serie: pd.Series, unid: str) -> pd.Series:
    """Valores em R$ sao exibidos em milhoes."""
    return serie / 1e6 if unid == "R$" else serie


def _ordenar(empresas) -> list:
    return [e for e in EMPRESAS if e in set(empresas)]


def layout_padrao(fig: go.Figure, titulo: str = "", altura: int = 380) -> go.Figure:
    fig.update_layout(
        title=titulo or None,
        height=altura,
        margin=dict(l=10, r=10, t=60 if titulo else 40, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left",
                    x=0, title=dict(text="")),
        hovermode="x unified",
        separators=",.",  # decimal com virgula e milhar com ponto
    )
    return fig


def marcar_quebra(fig: go.Figure, df: pd.DataFrame, subplots: bool = False) -> None:
    """Linha pontilhada entre 2023 e 2024 quando a Brisanet esta no grafico."""
    for empresa, ano in QUEBRA_ENTIDADE.items():
        anos = df.loc[df["empresa"] == empresa, "ano"]
        if anos.empty or not (anos.min() < ano <= anos.max()):
            continue
        extra = {"row": "all", "col": "all"} if subplots else {
            "annotation_text": f"{empresa}: troca de entidade",
            "annotation_position": "top left",
            "annotation_font_size": 10,
            "annotation_font_color": CORES.get(empresa, "grey"),
        }
        fig.add_vline(x=ano - 0.5, line_dash="dot", line_width=1.5,
                      line_color=CORES.get(empresa, "grey"), opacity=0.7, **extra)


def linha(df: pd.DataFrame, coluna: str, titulo: str = "", altura: int = 380) -> go.Figure:
    """Serie temporal: uma linha por empresa."""
    unid = unidade(coluna)
    fmt = FORMATOS[unid]
    dados = df[["empresa", "ano", coluna]].dropna()
    fig = go.Figure()
    for empresa in _ordenar(dados["empresa"]):
        d = dados[dados["empresa"] == empresa].sort_values("ano")
        fig.add_trace(go.Scatter(
            x=d["ano"], y=_escala(d[coluna], unid), name=empresa,
            mode="lines+markers",
            line=dict(color=CORES[empresa], width=3), marker=dict(size=8),
            hovertemplate=f"{empresa}: {fmt['hover']}<extra></extra>",
        ))
    layout_padrao(fig, titulo, altura)
    fig.update_xaxes(dtick=1, title_text="")
    fig.update_yaxes(tickformat=fmt["tick"], title_text=fmt["titulo"],
                     zeroline=True, zerolinecolor="#bbbbbb")
    marcar_quebra(fig, dados)
    return fig


def barras(df: pd.DataFrame, coluna: str, titulo: str = "", altura: int = 380) -> go.Figure:
    """Barras agrupadas por ano."""
    unid = unidade(coluna)
    fmt = FORMATOS[unid]
    dados = df[["empresa", "ano", coluna]].dropna()
    fig = go.Figure()
    for empresa in _ordenar(dados["empresa"]):
        d = dados[dados["empresa"] == empresa].sort_values("ano")
        fig.add_trace(go.Bar(
            x=d["ano"], y=_escala(d[coluna], unid), name=empresa,
            marker_color=CORES[empresa],
            hovertemplate=f"{empresa}: {fmt['hover']}<extra></extra>",
        ))
    layout_padrao(fig, titulo, altura)
    fig.update_layout(barmode="group")
    fig.update_xaxes(dtick=1, title_text="")
    fig.update_yaxes(tickformat=fmt["tick"], title_text=fmt["titulo"])
    return fig


def painel(df: pd.DataFrame, colunas: list, ncols: int = 3, altura: int = 560) -> go.Figure:
    """Grade de pequenos graficos de linha (visao geral)."""
    nrows = -(-len(colunas) // ncols)  # divisao arredondando para cima
    fig = make_subplots(rows=nrows, cols=ncols,
                        subplot_titles=[rotulo(c) for c in colunas],
                        horizontal_spacing=0.07, vertical_spacing=0.14)
    empresas = _ordenar(df["empresa"])
    for i, coluna in enumerate(colunas):
        r, c = i // ncols + 1, i % ncols + 1
        unid = unidade(coluna)
        for empresa in empresas:
            d = df[df["empresa"] == empresa].sort_values("ano")
            fig.add_trace(go.Scatter(
                x=d["ano"], y=_escala(d[coluna], unid), name=empresa,
                mode="lines+markers", legendgroup=empresa, showlegend=(i == 0),
                line=dict(color=CORES[empresa], width=2.5), marker=dict(size=6),
                hovertemplate=f"{empresa}: {FORMATOS[unid]['hover']}<extra></extra>",
            ), row=r, col=c)
        fig.update_yaxes(tickformat=FORMATOS[unid]["tick"], row=r, col=c)
    layout_padrao(fig, altura=altura)
    fig.update_xaxes(dtick=1)
    marcar_quebra(fig, df, subplots=True)
    return fig


def caixa(df: pd.DataFrame, coluna: str, titulo: str = "", altura: int = 360) -> go.Figure:
    """Distribuicao por empresa (box plot com todos os pontos)."""
    unid = unidade(coluna)
    dados = df[["empresa", "ano", coluna]].dropna()
    fig = go.Figure()
    for empresa in _ordenar(dados["empresa"]):
        d = dados[dados["empresa"] == empresa]
        fig.add_trace(go.Box(
            y=_escala(d[coluna], unid), name=empresa, text=d["ano"].astype(str),
            boxpoints="all", jitter=0.35, pointpos=0, boxmean=True,
            marker_color=CORES[empresa], line_color=CORES[empresa],
            hovertemplate="%{text}: " + FORMATOS[unid]["hover"] + "<extra></extra>",
        ))
    layout_padrao(fig, titulo, altura)
    fig.update_layout(showlegend=False, hovermode="closest")
    fig.update_yaxes(tickformat=FORMATOS[unid]["tick"], title_text=FORMATOS[unid]["titulo"])
    return fig


def mapa_calor(matriz: pd.DataFrame, texto: pd.DataFrame, titulo: str = "",
               altura: int = 260, simetrico: bool = True) -> go.Figure:
    """Heatmap empresa x ano (variacoes)."""
    z = matriz.astype(float)
    valores = np.abs(z.to_numpy().ravel())
    valores = valores[~np.isnan(valores)]
    # escala de cor limitada ao percentil 90: um unico valor extremo
    # (ex.: FCO da Desktop em 2021) nao "apaga" as demais cores
    limite = float(np.quantile(valores, 0.9)) if valores.size else 1.0
    limite = limite or 1.0
    fig = go.Figure(go.Heatmap(
        z=z.values, x=[str(c) for c in z.columns], y=list(z.index),
        text=texto.values, texttemplate="%{text}", hoverinfo="skip",
        colorscale="RdYlGn",
        zmin=-limite if simetrico else None, zmax=limite if simetrico else None,
        showscale=False,
    ))
    layout_padrao(fig, titulo, altura)
    fig.update_layout(hovermode=False)
    fig.update_xaxes(type="category")
    return fig


def dispersao(df: pd.DataFrame, x: str, y: str, altura: int = 420) -> go.Figure:
    ux, uy = unidade(x), unidade(y)
    dados = df[["empresa", "ano", x, y]].dropna()
    fig = go.Figure()
    for empresa in _ordenar(dados["empresa"]):
        d = dados[dados["empresa"] == empresa].sort_values("ano")
        fig.add_trace(go.Scatter(
            x=_escala(d[x], ux), y=_escala(d[y], uy), name=empresa,
            mode="markers+text+lines", text=d["ano"].astype(str),
            textposition="top center", textfont=dict(size=10),
            line=dict(color=CORES[empresa], width=1, dash="dot"),
            marker=dict(color=CORES[empresa], size=11),
            hovertemplate=f"{empresa} %{{text}}<br>{rotulo(x)}: "
            + FORMATOS[ux]["hover"].replace("%{y", "%{x")
            + f"<br>{rotulo(y)}: " + FORMATOS[uy]["hover"] + "<extra></extra>",
        ))
    layout_padrao(fig, altura=altura)
    fig.update_layout(hovermode="closest")
    fig.update_xaxes(title_text=rotulo(x), tickformat=FORMATOS[ux]["tick"])
    fig.update_yaxes(title_text=rotulo(y), tickformat=FORMATOS[uy]["tick"])
    return fig


def cascata(etapas: list, titulo: str = "", cor: str = "#1f77b4", altura: int = 360) -> go.Figure:
    """
    Ponte de margens (waterfall). etapas = [(rotulo, valor_fracao, medida)],
    medida = 'absolute' | 'relative' | 'total'.
    """
    rotulos = [e[0] for e in etapas]
    valores = [e[1] for e in etapas]
    medidas = [e[2] for e in etapas]
    fig = go.Figure(go.Waterfall(
        x=rotulos, y=valores, measure=medidas,
        text=[f"{v * 100:+.1f}%".replace(".", ",") if m == "relative"
              else f"{v * 100:.1f}%".replace(".", ",") for v, m in zip(valores, medidas)],
        textposition="outside",
        connector=dict(line=dict(color="#999999", width=1)),
        increasing=dict(marker=dict(color="#2ca02c")),
        decreasing=dict(marker=dict(color="#d62728")),
        totals=dict(marker=dict(color=cor)),
        hoverinfo="skip",
    ))
    layout_padrao(fig, titulo, altura)
    fig.update_layout(showlegend=False, hovermode=False)
    fig.update_yaxes(tickformat=".0%")
    return fig
