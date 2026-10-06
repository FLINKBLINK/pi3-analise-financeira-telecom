# -*- coding: utf-8 -*-
"""
Hipoteses da secao 7.3 do relatorio da Sprint 2:
"Por que, entre operadoras que captaram capital em ofertas simultaneas e
cresceram a receita de forma parecida, apenas uma sustentou a rentabilidade?"

Evidencias DESCRITIVAS. Testes estatisticos ficam para a Sprint 4.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import dados as d
import visual as v

painel = d.carregar_painel()
alertas = d.carregar_alertas()
empresas, anos = d.filtros(painel)
df = d.filtrar(painel, empresas, anos)

st.title("🧪 Hipóteses da pesquisa")
st.markdown(
    "> *Por que, entre operadoras regionais de fibra que abriram capital em "
    "julho de 2021 e cresceram a receita de forma parecida, apenas uma "
    "sustentou a trajetória de rentabilidade?* — questão da seção 7.3 do "
    "relatório da Sprint 2."
)
st.caption(
    "Esta página reúne evidências **descritivas** para as três hipóteses. Ela "
    "não testa significância estatística: isso é escopo da Sprint 4."
)


def lista_valores(nome: str, ano: int) -> str:
    partes = [f"{e} {d.fmt_valor(nome, d.valor(df, e, ano, nome))}" for e in empresas]
    return "; ".join(partes)


ano_ref = anos[1]

# ---------------------------------------------------------------
# CONTEXTO: margens operacionais parecidas, margens liquidas distantes
# ---------------------------------------------------------------
st.header("Ponto de partida")
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(v.linha(df, "margem_ebitda", titulo="Margem EBITDA", altura=330),
                    key="h_ebitda")
with c2:
    st.plotly_chart(v.linha(df, "margem_liquida", titulo="Margem líquida", altura=330),
                    key="h_liquida")
st.markdown(
    f"Em **{ano_ref}**, margem EBITDA: {lista_valores('margem_ebitda', ano_ref)}. "
    f"Margem líquida: {lista_valores('margem_liquida', ano_ref)}."
)

# ---------------------------------------------------------------
# PONTE DE MARGENS
# ---------------------------------------------------------------
st.subheader("Da margem EBITDA à margem líquida")
anos_disp = sorted(df["ano"].unique().tolist())
ano_ponte = st.select_slider("Ano da comparação", options=anos_disp,
                             value=anos_disp[-1], key="h_ano_ponte")
colunas = st.columns(len(empresas))
for coluna, empresa in zip(colunas, empresas):
    linha = df[(df["empresa"] == empresa) & (df["ano"] == ano_ponte)]
    with coluna:
        if linha.empty:
            st.info(f"{empresa}: sem dados em {ano_ponte}.")
            continue
        r = linha.iloc[0]
        rec = r["receita_liquida"]
        etapas = [
            ("EBITDA", r["ebitda"] / rec, "absolute"),
            ("Depreciação", -r["depreciacao_amortizacao"] / rec, "relative"),
            ("Res. financeiro", r["resultado_financeiro"] / rec, "relative"),
            ("IR/CS e outros",
             (r["lucro_liquido"] - r["resultado_operacional"] - r["resultado_financeiro"]) / rec,
             "relative"),
            ("Lucro líquido", r["lucro_liquido"] / rec, "total"),
        ]
        if any(pd.isna(e[1]) for e in etapas):
            st.info(f"{empresa}: dados incompletos para a ponte em {ano_ponte}.")
            continue
        st.plotly_chart(
            v.cascata(etapas, titulo=f"{empresa} · {ano_ponte}", cor=d.CORES[empresa]),
            key=f"h_ponte_{empresa}",
        )
st.caption(
    "Cada barra é uma fração da receita líquida. EBITDA − depreciação = EBIT; "
    "EBIT + resultado financeiro = lucro antes do IR; o restante é IR/CS "
    "(e operações descontinuadas, quando houver)."
)

# ---------------------------------------------------------------
# H1 - ENDIVIDAMENTO
# ---------------------------------------------------------------
st.header("H1 · Estrutura de endividamento")
st.markdown(
    "*O custo do capital de terceiros, ampliado pelas aquisições, comprimiria o "
    "resultado por meio da despesa financeira.*"
)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(v.linha(df, "peso_resultado_financeiro",
                            titulo="Peso do resultado financeiro sobre o EBIT", altura=330),
                    key="h1_peso")
with c2:
    st.plotly_chart(v.linha(df, "divida_liquida_ebitda",
                            titulo="Dívida líquida / EBITDA", altura=330),
                    key="h1_alav")
st.markdown(
    f"- Em **{ano_ref}**, o resultado financeiro consumiu do EBIT: "
    f"{lista_valores('peso_resultado_financeiro', ano_ref)}.\n"
    f"- Dívida líquida / EBITDA em {ano_ref}: "
    f"{lista_valores('divida_liquida_ebitda', ano_ref)}."
)
st.plotly_chart(v.barras(df, "despesas_financeiras",
                         titulo="Despesas financeiras (R$ milhões, valores negativos)",
                         altura=320), key="h1_desp")

# ---------------------------------------------------------------
# H2 - INTENSIDADE DE CAPITAL
# ---------------------------------------------------------------
st.header("H2 · Intensidade de capital")
st.markdown(
    "*O investimento em expansão de rede geraria depreciação elevada, com "
    "impacto sobre o lucro contábil.*"
)
c1, c2 = st.columns(2)
with c1:
    st.plotly_chart(v.linha(df, "depreciacao_receita",
                            titulo="Depreciação e amortização / Receita", altura=330),
                    key="h2_dep")
with c2:
    st.plotly_chart(v.barras(df, "depreciacao_amortizacao",
                             titulo="Depreciação e amortização (R$ milhões)", altura=330),
                    key="h2_dep_rs")
st.markdown(
    f"- Depreciação e amortização sobre a receita em **{ano_ref}**: "
    f"{lista_valores('depreciacao_receita', ano_ref)}."
)

# ---------------------------------------------------------------
# H3 - QUALIDADE DO RESULTADO
# ---------------------------------------------------------------
st.header("H3 · Qualidade do resultado")
st.markdown(
    "*A comparação entre o fluxo de caixa operacional e o lucro líquido indicaria "
    "a consistência entre resultado contábil e geração efetiva de caixa.*"
)
c1, c2 = st.columns([1, 2])
with c1:
    empresa_h3 = st.selectbox("Empresa", empresas, key="h3_empresa")
with c2:
    st.caption(
        "Barras: FCO e lucro líquido em R$ milhões. Quando o FCO fica acima do "
        "lucro, o resultado contábil está 'lastreado' em caixa."
    )
g = df[df["empresa"] == empresa_h3].sort_values("ano")
fig = go.Figure()
fig.add_trace(go.Bar(x=g["ano"], y=g["fluxo_caixa_operacional"] / 1e6, name="FCO",
                     marker_color=d.CORES[empresa_h3],
                     hovertemplate="FCO: R$ %{y:,.1f} mi<extra></extra>"))
fig.add_trace(go.Bar(x=g["ano"], y=g["lucro_liquido"] / 1e6, name="Lucro líquido",
                     marker_color="#7f7f7f",
                     hovertemplate="Lucro: R$ %{y:,.1f} mi<extra></extra>"))
v.layout_padrao(fig, titulo=f"{empresa_h3}: FCO x lucro líquido", altura=340)
fig.update_layout(barmode="group")
fig.update_xaxes(dtick=1)
fig.update_yaxes(tickformat=",.0f", title_text="R$ milhões")
st.plotly_chart(fig, key="h3_barras")

st.plotly_chart(v.linha(df, "margem_fco", titulo="Margem FCO (FCO / receita)",
                        altura=330), key="h3_margem")
resumo = []
for empresa in empresas:
    s = df[df["empresa"] == empresa]
    validos = s.dropna(subset=["fluxo_caixa_operacional", "lucro_liquido"])
    acima = int((validos["fluxo_caixa_operacional"] > validos["lucro_liquido"]).sum())
    resumo.append(f"{empresa}: FCO acima do lucro em {acima} de {len(validos)} anos")
st.markdown("- " + "; ".join(resumo) + ".")
sub = alertas[alertas["indicador"].isin(["margem_fco", "cobertura_caixa"])
              & alertas["empresa"].isin(empresas)
              & alertas["ano"].between(anos[0], anos[1])] if not alertas.empty else alertas
for a in sub.drop_duplicates(subset=["empresa", "ano", "tipo"]).itertuples():
    st.caption(f"⚠️ {a.empresa} {a.ano}: {a.motivo}")

# ---------------------------------------------------------------
st.header("Próximos passos (Sprint 4)")
st.markdown(
    "- Testar estatisticamente as relações sugeridas aqui (ex.: correlação e "
    "regressão em painel entre endividamento, resultado financeiro e margem "
    "líquida), considerando o tamanho pequeno da amostra.\n"
    "- Projetar receita, EBITDA e lucro a partir das séries históricas, com "
    "intervalos de confiança e análise de sensibilidade.\n"
    "- Avaliar a correção pela inflação (IPCA) para comparar valores reais."
)
st.caption(d.FONTE)
