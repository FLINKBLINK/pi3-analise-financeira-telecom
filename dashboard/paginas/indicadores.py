# -*- coding: utf-8 -*-
"""Indicadores financeiros por grupo, com formula, leitura e alertas."""

import streamlit as st

import dados as d
import visual as v

painel = d.carregar_painel()
alertas = d.carregar_alertas()
empresas, anos = d.filtros(painel)
df = d.filtrar(painel, empresas, anos)

st.title("📈 Indicadores financeiros")
st.markdown(
    "Indicadores calculados pelo `etl/08_indicadores.py` a partir da base "
    "analítica. Percentuais em %, demais em vezes (x). Passe o mouse nos "
    "gráficos para ver os valores."
)

ICONE_ALERTA = {
    "atipico": "🟠 Valor atípico",
    "distorcido": "🟡 Leitura distorcida",
    "nao_calculado": "⚪ Não calculado",
    "contexto": "🔵 Contexto",
}


def bloco_indicador(nome: str) -> None:
    rot, _grupo, unid, formula, leitura, _melhor = d.INDICADORES[nome]
    st.markdown(f"### {rot}")
    graf, info = st.columns([2.2, 1])
    with graf:
        st.plotly_chart(v.linha(df, nome, altura=340), key=f"graf_{nome}")
    with info:
        st.markdown(f"**Fórmula:** {formula}")
        st.caption(leitura)
        ano_ref = anos[1]
        st.markdown(f"**{ano_ref}:**")
        for empresa in empresas:
            st.markdown(
                f"- {empresa}: **{d.fmt_valor(nome, d.valor(df, empresa, ano_ref, nome))}**"
            )
        sub = alertas[
            (alertas["indicador"] == nome)
            & alertas["empresa"].isin(empresas)
            & alertas["ano"].between(anos[0], anos[1])
        ] if not alertas.empty else alertas
        for a in sub.itertuples():
            st.caption(f"{ICONE_ALERTA.get(a.tipo, a.tipo)} · {a.empresa} {a.ano}: {a.motivo}")

    with st.expander(f"Tabela – {rot}"):
        tabela = df.pivot(index="empresa", columns="ano", values=nome)
        tabela.columns = [str(c) for c in tabela.columns]
        st.dataframe(
            d.formatar_tabela(tabela.reset_index(), {c: unid for c in tabela.columns}),
            hide_index=True,
        )
    st.divider()


abas = st.tabs(d.GRUPOS)
for aba, grupo in zip(abas, d.GRUPOS):
    with aba:
        if grupo == "Apoio às hipóteses":
            st.info(
                "Indicadores criados na Sprint 3 para testar as hipóteses da seção "
                "7.3 do relatório da Sprint 2. Veja a página **Hipóteses da pesquisa**."
            )
        for nome in d.indicadores_do_grupo(grupo):
            bloco_indicador(nome)

st.caption(d.FONTE)
