# -*- coding: utf-8 -*-
"""Estatisticas descritivas, distribuicao, variacoes anuais e rankings."""

import numpy as np
import pandas as pd
import streamlit as st

import dados as d
import visual as v

painel = d.carregar_painel()
alertas = d.carregar_alertas()
empresas, anos = d.filtros(painel)
df = d.filtrar(painel, empresas, anos)

st.title("🔎 Análise descritiva")
st.markdown(
    "Medidas de posição e dispersão, distribuição e variações de cada variável "
    "no período e nas empresas selecionadas. Caráter **descritivo**: a análise "
    "inferencial e as projeções ficam para a Sprint 4."
)

# ---------------------------------------------------------------
# ESCOLHA DA VARIAVEL
# ---------------------------------------------------------------
c1, c2 = st.columns([1, 2])
with c1:
    tipo = st.radio("Tipo", ["Indicadores", "Valores em R$"], horizontal=True,
                    key="desc_tipo")
opcoes = list(d.INDICADORES) if tipo == "Indicadores" else list(d.VARIAVEIS)
with c2:
    var = st.selectbox("Variável", opcoes, format_func=d.rotulo, key="desc_var")
unid = d.unidade(var)

base = df.copy()
if tipo == "Indicadores":
    excluir = st.toggle(
        "Excluir das estatísticas os valores sinalizados como atípicos ou distorcidos",
        value=False, key="desc_excluir",
        help="Ex.: FCO da Desktop em 2021 e cobertura de caixa da Brisanet em 2021. "
             "Os valores continuam no banco como publicados.",
    )
    if excluir and not alertas.empty:
        sinal = alertas[(alertas["indicador"] == var)
                        & alertas["tipo"].isin(["atipico", "distorcido"])]
        chaves = set(zip(sinal["empresa"], sinal["ano"]))
        mascara = [(e, a) in chaves for e, a in zip(base["empresa"], base["ano"])]
        if any(mascara):
            base.loc[mascara, var] = np.nan
            st.caption(f"{sum(mascara)} valor(es) excluído(s) desta análise.")

if base[var].notna().sum() == 0:
    st.warning("Não há valores para esta variável no filtro atual.")
    st.stop()

# ---------------------------------------------------------------
# 1. ESTATISTICAS DESCRITIVAS
# ---------------------------------------------------------------
st.subheader(f"1. Estatísticas descritivas – {d.rotulo(var)}")
stats = d.estatisticas(base, var)
if unid == "R$":
    stats["CAGR"] = [d.cagr(r["_inicial"], r["_final"], r["_anos"]) for _, r in stats.iterrows()]
    formatos = {c: "R$" for c in ("Média", "Mediana", "Desvio-padrão", "Mínimo",
                                  "Máximo", "Valor inicial", "Valor final")}
    formatos["CAGR"] = "%"
else:
    stats["Variação no período"] = stats["_final"] - stats["_inicial"]
    formatos = {c: unid for c in ("Média", "Mediana", "Desvio-padrão", "Mínimo",
                                  "Máximo", "Valor inicial", "Valor final",
                                  "Variação no período")}
formatos["CV"] = "%"
visiveis = [c for c in stats.columns if not c.startswith("_")]
st.dataframe(d.formatar_tabela(stats[visiveis], formatos), hide_index=True)
st.caption(
    "CV = coeficiente de variação (desvio-padrão ÷ |média|): quanto maior, mais "
    "instável a série. CAGR = crescimento médio anual composto (só com valores "
    "positivos). Com no máximo 6 observações por empresa, as medidas são "
    "descritivas e sensíveis a valores extremos – compare média e mediana."
)

# ---------------------------------------------------------------
# 2. DISTRIBUICAO E EVOLUCAO
# ---------------------------------------------------------------
st.subheader("2. Distribuição e evolução")
g1, g2 = st.columns(2)
with g1:
    st.plotly_chart(v.caixa(base, var, titulo="Distribuição no período (box plot)"),
                    key="desc_box")
    st.caption("Caixa: 1º ao 3º quartil · traço contínuo: mediana · tracejado: média · "
               "pontos: cada ano.")
with g2:
    st.plotly_chart(v.linha(base, var, titulo="Evolução anual"), key="desc_linha")

# ---------------------------------------------------------------
# 3. VARIACAO ANO A ANO
# ---------------------------------------------------------------
st.subheader("3. Variação em relação ao ano anterior")
largo = base.pivot(index="empresa", columns="ano", values=var).sort_index(axis=1)
if unid == "R$":
    variacao = largo.apply(d.variacao_segura, axis=1)
    texto = variacao.apply(lambda col: col.map(lambda x: d.fmt_pct(x, 0)))
    explicacao = ("Variação % sobre o valor absoluto do ano anterior (o sinal fica "
                  "correto mesmo quando a base é negativa).")
elif unid == "%":
    variacao = largo.diff(axis=1)
    texto = variacao.apply(lambda col: col.map(
        lambda x: "–" if pd.isna(x) else f"{'+' if x >= 0 else ''}{d.num_br(x * 100)} p.p."))
    explicacao = "Diferença em pontos percentuais (p.p.) em relação ao ano anterior."
else:
    variacao = largo.diff(axis=1)
    texto = variacao.apply(lambda col: col.map(
        lambda x: "–" if pd.isna(x) else f"{'+' if x >= 0 else ''}{d.num_br(x, 2)}x"))
    explicacao = "Diferença em vezes (x) em relação ao ano anterior."

variacao = variacao.iloc[:, 1:]
texto = texto.iloc[:, 1:]
if variacao.empty or variacao.notna().sum().sum() == 0:
    st.info("Selecione um período com pelo menos dois anos.")
else:
    sinal = 1
    if var in d.INDICADORES and d.INDICADORES[var][5] == "menor":
        sinal = -1  # verde = melhora (queda de endividamento, por exemplo)
    st.plotly_chart(
        v.mapa_calor(variacao * sinal, texto, altura=120 + 45 * len(variacao)),
        key="desc_calor",
    )
    st.caption(explicacao + " Verde = movimento favorável; vermelho = desfavorável"
               + (" (para este indicador, cair é favorável)." if sinal == -1 else "."))

# ---------------------------------------------------------------
# 4. RANKING POR ANO
# ---------------------------------------------------------------
if len(empresas) > 1:
    st.subheader("4. Posição relativa por ano")
    melhor = d.INDICADORES[var][5] if var in d.INDICADORES else "maior"
    if melhor is None:
        st.caption("Para este indicador não existe 'melhor' universal: o ranking "
                   "ordena do maior para o menor valor.")
    crescente = melhor == "menor"
    ranking = largo.rank(axis=0, ascending=crescente, method="min")
    ranking.columns = [str(c) for c in ranking.columns]
    st.dataframe(
        d.formatar_tabela(ranking.reset_index().rename(columns={"empresa": "Empresa"}),
                          {c: "int" for c in ranking.columns}),
        hide_index=True,
    )
    st.caption("1 = melhor posição no ano"
               + (" (menor valor)." if crescente else " (maior valor)."))

# ---------------------------------------------------------------
# 5. RELACAO ENTRE DUAS VARIAVEIS
# ---------------------------------------------------------------
st.subheader("5. Relação entre duas variáveis")
todas = list(d.INDICADORES) + list(d.VARIAVEIS)
x1, x2 = st.columns(2)
with x1:
    eixo_x = st.selectbox("Eixo X", todas, index=todas.index("endividamento_geral"),
                          format_func=d.rotulo, key="disp_x")
with x2:
    eixo_y = st.selectbox("Eixo Y", todas, index=todas.index("margem_liquida"),
                          format_func=d.rotulo, key="disp_y")
st.plotly_chart(v.dispersao(df, eixo_x, eixo_y), key="desc_disp")
pares = df[[eixo_x, eixo_y]].dropna()
if len(pares) >= 3 and eixo_x != eixo_y:
    r = pares[eixo_x].corr(pares[eixo_y])
    st.caption(
        f"Correlação de Pearson (todas as observações do filtro, n = {len(pares)}): "
        f"**{d.num_br(r, 2)}**. Medida apenas descritiva: com poucas observações e "
        "séries com tendência, não indica causalidade nem significância estatística "
        "(teste previsto para a Sprint 4)."
    )

st.caption(d.FONTE)
