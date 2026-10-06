# -*- coding: utf-8 -*-
"""Base de dados, qualidade, alertas e metodologia (com download em CSV)."""

import pandas as pd
import streamlit as st

import dados as d

painel = d.carregar_painel()
alertas = d.carregar_alertas()
empresas, anos = d.filtros(painel)
df = d.filtrar(painel, empresas, anos)

st.title("📁 Dados e metodologia")

abas = st.tabs(["Base analítica", "Indicadores", "Qualidade dos dados", "Metodologia"])

# ---------------------------------------------------------------
with abas[0]:
    st.markdown("Valores em **R$ milhões** na tela; o download traz os valores em reais.")
    colunas = ["empresa", "ano", "cd_cvm"] + [c for c in d.VARIAVEIS if c in df.columns]
    tela = df[colunas].rename(columns={c: d.rotulo(c) for c in d.VARIAVEIS})
    st.dataframe(
        d.formatar_tabela(tela, {d.rotulo(c): "mi" for c in d.VARIAVEIS}),
        hide_index=True,
    )
    st.download_button(
        "Baixar base analítica (CSV)",
        data=d.csv_download(df[colunas]),
        file_name="base_analitica.csv",
        mime="text/csv",
        key="dl_base",
    )

# ---------------------------------------------------------------
with abas[1]:
    st.markdown("Percentuais em %, demais em vezes (x).")
    nomes = list(d.INDICADORES)
    tela = df[["empresa", "ano"] + nomes].rename(columns={c: d.rotulo(c) for c in nomes})
    st.dataframe(
        d.formatar_tabela(tela, {d.rotulo(c): d.unidade(c) for c in nomes}),
        hide_index=True,
    )
    st.download_button(
        "Baixar indicadores (CSV, percentuais como fração)",
        data=d.csv_download(df[["empresa", "ano"] + nomes]),
        file_name="indicadores.csv",
        mime="text/csv",
        key="dl_ind",
    )
    st.markdown("**Fórmulas**")
    formulas = pd.DataFrame(
        [(v[0], v[1], v[3]) for v in d.INDICADORES.values()],
        columns=["Indicador", "Grupo", "Fórmula"],
    )
    st.dataframe(formulas, hide_index=True)

# ---------------------------------------------------------------
with abas[2]:
    total = len(df)
    c1, c2, c3 = st.columns(3)
    c1.metric("Observações (empresa × ano)", total)
    c2.metric("Ativo = Passivo total", f"{int(df['validacao_balanco_ok'].fillna(0).sum())}/{total}")
    c3.metric("PC + PNC + PL = Ativo",
              f"{int(df['validacao_identidade_ok'].fillna(0).sum())}/{total}")
    st.caption(
        "O segundo teste é mais forte: confere, um a um, os componentes do lado "
        "direito do balanço extraídos da CVM (seção 6.1 do relatório da Sprint 2). "
        "O fechamento da DFC é verificado pelo etl/07_diagnostico_dfc.py."
    )

    st.markdown("**Observações de auditoria (base analítica)**")
    obs = df.dropna(subset=["observacao"])[["empresa", "ano", "observacao"]]
    if obs.empty:
        st.caption("Nenhuma observação no filtro atual.")
    else:
        st.dataframe(obs.rename(columns={"empresa": "Empresa", "ano": "Ano",
                                         "observacao": "Observação"}),
                     hide_index=True)

    st.markdown("**Alertas de interpretação dos indicadores**")
    sub = alertas[alertas["empresa"].isin(empresas)
                  & alertas["ano"].between(anos[0], anos[1])] if not alertas.empty else alertas
    if sub.empty:
        st.caption("Nenhum alerta no filtro atual.")
    else:
        sub = sub.assign(indicador=sub["indicador"].map(d.rotulo))
        st.dataframe(sub.rename(columns={"empresa": "Empresa", "ano": "Ano",
                                         "indicador": "Indicador", "tipo": "Tipo",
                                         "motivo": "Motivo"}),
                     hide_index=True)

# ---------------------------------------------------------------
with abas[3]:
    st.markdown(
        """
**Fonte.** Formulário de Demonstrações Financeiras Padronizadas (DFP) do Portal
de Dados Abertos da CVM, demonstrações **consolidadas**, exercícios 2020 a 2025.

**Pipeline.** CSVs da CVM → ETL em Python (`etl/`) → banco SQLite
(`database/telecom.db`) → indicadores (`etl/08_indicadores.py`) → este dashboard.

**Regras de tratamento**
- Apenas o exercício de referência de cada arquivo (`ORDEM_EXERC = ÚLTIMO`).
- Linhas duplicadas na origem removidas (a DFP 2023 da Brisanet Serviços vem
  repetida nos quatro arquivos da CVM).
- Maior `VERSAO` em caso de reapresentação.
- Escala monetária aplicada (R$ mil → R$); empresas identificadas pelo `CD_CVM`.

**Decisões metodológicas**
- **Passivo total (conta 2)** inclui o patrimônio líquido; por isso o
  endividamento usa o capital de terceiros (2.01 + 2.02).
- **Brisanet**: série encadeada – Participações (CD_CVM 026085) até 2023 e
  Serviços (027693) a partir de 2024, após a incorporação de 04/12/2024.
- **ROE e ROA** sobre saldos médios: (saldo inicial + final) ÷ 2, com o saldo
  inicial publicado como comparativo na própria DFP do ano. A DFP 2020 da
  Desktop não traz o comparativo de 2019, então ROE/ROA de 2020 não são
  calculados para ela.
- **Depreciação e amortização** não é conta fixa na CVM: é localizada pela
  descrição dentro do grupo 6.01.01 da DFC, exigindo exatamente uma conta por
  empresa/ano.
- **Valores atípicos** são mantidos como publicados e sinalizados (ex.: FCO da
  Desktop em 2021).

**Limitações**
- Valores nominais, sem correção pela inflação.
- Apenas dados contábeis: não há variáveis operacionais (acessos, ARPU,
  domicílios cobertos).
- Seis exercícios por empresa: as estatísticas são descritivas e sensíveis a
  valores extremos.
        """
    )

st.caption(d.FONTE)
