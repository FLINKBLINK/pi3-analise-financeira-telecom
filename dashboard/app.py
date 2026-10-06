# -*- coding: utf-8 -*-
"""
dashboard/app.py  ->  ponto de entrada do Streamlit

Projeto Integrador III - Fatec Cotia | Sprint 3
Dashboard da analise financeira de Brisanet, Desktop e Unifique (CVM/DFP).

RODAR LOCALMENTE (na raiz do repositorio)
-----------------------------------------
  streamlit run dashboard/app.py

DEPLOY (Streamlit Community Cloud)
----------------------------------
  Main file path: dashboard/app.py   |   Python: 3.12 (Advanced settings)

Os filtros da barra lateral ficam aqui, no ponto de entrada, para valerem
em todas as paginas (st.navigation). As paginas estao em dashboard/paginas/.
"""

from pathlib import Path

import streamlit as st

import dados

st.set_page_config(
    page_title="PI III · Telecom regionais",
    page_icon="📶",
    layout="wide",
)

PASTA = Path(__file__).resolve().parent / "paginas"

paginas = {
    "Painel": [
        st.Page(str(PASTA / "visao_geral.py"), title="Visão geral", icon="📊",
                default=True),
        st.Page(str(PASTA / "indicadores.py"), title="Indicadores financeiros",
                icon="📈", url_path="indicadores"),
        st.Page(str(PASTA / "analise_descritiva.py"), title="Análise descritiva",
                icon="🔎", url_path="analise-descritiva"),
        st.Page(str(PASTA / "hipoteses.py"), title="Hipóteses da pesquisa",
                icon="🧪", url_path="hipoteses"),
    ],
    "Sobre os dados": [
        st.Page(str(PASTA / "dados_metodologia.py"), title="Dados e metodologia",
                icon="📁", url_path="dados-e-metodologia"),
    ],
}
navegacao = st.navigation(paginas)

# ---------------------------------------------------------------
# FILTROS GLOBAIS (barra lateral)
# ---------------------------------------------------------------
painel = dados.carregar_painel()
ano_min, ano_max = int(painel["ano"].min()), int(painel["ano"].max())

with st.sidebar:
    st.markdown("### Filtros")
    st.multiselect(
        "Empresas",
        options=dados.EMPRESAS,
        default=dados.EMPRESAS,
        key="empresas",
    )
    st.slider(
        "Período",
        min_value=ano_min,
        max_value=ano_max,
        value=(ano_min, ano_max),
        step=1,
        key="periodo",
    )
    st.caption(
        "Valores nominais (sem correção pela inflação). Série da Brisanet "
        "encadeada: Participações até 2023 e Serviços a partir de 2024."
    )
    st.caption(dados.FONTE)

navegacao.run()
