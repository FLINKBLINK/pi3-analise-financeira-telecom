# -*- coding: utf-8 -*-
"""Pagina inicial: destaques do ultimo ano e panorama das variaveis."""

import pandas as pd
import streamlit as st

import dados as d
import visual as v

painel = d.carregar_painel()
empresas, anos = d.filtros(painel)
df = d.filtrar(painel, empresas, anos)

st.title("📶 Operadoras regionais de fibra: panorama financeiro")
st.markdown(
    f"**{', '.join(empresas)}** · exercícios **{anos[0]}–{anos[1]}** · "
    "demonstrações financeiras consolidadas publicadas na CVM (formulário DFP)."
)

# ---------------------------------------------------------------
# DESTAQUES DO ULTIMO ANO SELECIONADO
# ---------------------------------------------------------------
ano_ref = anos[1]
st.subheader(f"Destaques de {ano_ref}")
st.caption(
    f"Variação em relação a {ano_ref - 1}: % para valores em R$ e pontos "
    "percentuais (p.p.) para indicadores."
)

destaques = ["receita_liquida", "lucro_liquido", "margem_liquida", "endividamento_geral"]
for coluna, empresa in zip(st.columns(len(empresas)), empresas):
    with coluna:
        st.markdown(f"#### {empresa}")
        for nome in destaques:
            atual = d.valor(painel, empresa, ano_ref, nome)
            anterior = d.valor(painel, empresa, ano_ref - 1, nome)
            st.metric(
                d.rotulo(nome),
                d.fmt_valor(nome, atual),
                delta=d.fmt_delta(nome, atual, anterior),
                delta_color=d.cor_delta(nome),
                help=d.INDICADORES[nome][3] if nome in d.INDICADORES else None,
            )

# ---------------------------------------------------------------
# PANORAMA
# ---------------------------------------------------------------
st.subheader("Evolução das principais variáveis (R$ milhões)")
variaveis = [
    "receita_liquida", "lucro_liquido", "ebitda",
    "patrimonio_liquido", "capital_terceiros", "fluxo_caixa_operacional",
]
st.plotly_chart(v.painel(df, variaveis), key="painel_geral")
st.caption(
    "Linha pontilhada: troca de entidade da Brisanet (2024). "
    f"IPOs das três empresas em julho de {d.ANO_IPO}. {d.FONTE}"
)

# ---------------------------------------------------------------
# LEITURAS RAPIDAS (geradas a partir dos dados filtrados)
# ---------------------------------------------------------------
st.subheader("Leituras rápidas do período")
if anos[1] - anos[0] < 1:
    st.info("Selecione um período com pelo menos dois anos para ver as leituras.")
else:
    itens = []

    cagr = {}
    for empresa in empresas:
        g = df[df["empresa"] == empresa].set_index("ano")["receita_liquida"]
        cagr[empresa] = d.cagr(g.get(anos[0]), g.get(anos[1]), anos[1] - anos[0])
    texto = "; ".join(f"{e} {d.fmt_pct(c)}" for e, c in cagr.items() if pd.notna(c))
    if texto:
        itens.append(f"**Receita líquida** – crescimento médio anual (CAGR) "
                     f"{anos[0]}–{anos[1]}: {texto}.")

    picos = []
    for empresa in empresas:
        g = df[df["empresa"] == empresa].dropna(subset=["lucro_liquido"])
        if g.empty:
            continue
        pico = g.loc[g["lucro_liquido"].idxmax()]
        ultimo = g.loc[g["ano"].idxmax()]
        if int(pico["ano"]) == int(ultimo["ano"]):
            picos.append(f"{empresa}: maior lucro no último ano "
                         f"({d.fmt_milhoes(pico['lucro_liquido'])})")
        else:
            picos.append(
                f"{empresa}: pico em {int(pico['ano'])} "
                f"({d.fmt_milhoes(pico['lucro_liquido'])}); em {int(ultimo['ano'])}, "
                f"{d.fmt_milhoes(ultimo['lucro_liquido'])}"
            )
    if picos:
        itens.append("**Lucro líquido** – " + "; ".join(picos) + ".")

    ultimo_ano = df[df["ano"] == anos[1]].dropna(subset=["margem_liquida"])
    if not ultimo_ano.empty:
        ordem = ultimo_ano.sort_values("margem_liquida", ascending=False)
        ranking = " > ".join(
            f"{r.empresa} ({d.fmt_pct(r.margem_liquida)})" for r in ordem.itertuples()
        )
        itens.append(f"**Margem líquida em {anos[1]}** – {ranking}.")

    saltos = []
    for empresa in empresas:
        g = df[df["empresa"] == empresa].set_index("ano")["patrimonio_liquido"]
        antes, depois = g.get(d.ANO_IPO - 1), g.get(d.ANO_IPO)
        if pd.notna(antes) and pd.notna(depois) and antes > 0:
            saltos.append(f"{empresa} +{d.num_br((depois / antes - 1) * 100, 0)}%")
    if saltos:
        itens.append(f"**Patrimônio líquido no ano dos IPOs ({d.ANO_IPO})** – "
                     + "; ".join(saltos) + ": efeito da captação, não do resultado.")

    for item in itens:
        st.markdown(f"- {item}")

with st.expander("Como ler este painel"):
    st.markdown(
        "- Todos os valores são **nominais** (sem correção pela inflação), em R$ "
        "milhões nos gráficos.\n"
        "- A **Brisanet** tem duas entidades na CVM: até 2023 a série usa a "
        "Brisanet Participações (holding); a partir de 2024, a Brisanet Serviços, "
        "que incorporou a holding em 04/12/2024.\n"
        "- **2021** é o ano dos IPOs: o salto do patrimônio líquido vem da "
        "captação e reduz mecanicamente indicadores como o ROE.\n"
        "- Valores atípicos (ex.: FCO da Desktop em 2021) foram **mantidos como "
        "publicados** e estão sinalizados nas páginas de indicadores."
    )
