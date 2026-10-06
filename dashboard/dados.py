# -*- coding: utf-8 -*-
"""
dashboard/dados.py

Projeto Integrador III - Fatec Cotia | Sprint 3
Acesso ao banco, metadados das variaveis/indicadores e formatacao.

O dashboard le APENAS o arquivo database/telecom.db (views
vw_base_analitica e vw_indicadores, mais a tabela alertas_indicadores).
Por isso o banco precisa estar versionado no GitHub para o deploy no
Streamlit Community Cloud. Para atualizar os dados, rode o pipeline
(python etl/rodar_pipeline.py) e faca commit do banco.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parent.parent
BANCO = RAIZ / "database" / "telecom.db"

# ---------------------------------------------------------------
# IDENTIDADE VISUAL (mesmas cores dos graficos da Sprint 2)
# ---------------------------------------------------------------
EMPRESAS = ["Brisanet", "Desktop", "Unifique"]
CORES = {"Brisanet": "#1f77b4", "Desktop": "#ff7f0e", "Unifique": "#2ca02c"}
QUEBRA_ENTIDADE = {"Brisanet": 2024}  # troca Participacoes -> Servicos
ANO_IPO = 2021                        # IPOs das tres empresas (julho/2021)
FONTE = "Fonte: CVM – Formulário DFP (demonstrações consolidadas). Elaboração própria."

# ---------------------------------------------------------------
# METADADOS
# ---------------------------------------------------------------
# Variaveis em R$ (financial_data)
VARIAVEIS = {
    "receita_liquida": ("Receita líquida", "DRE 3.01"),
    "lucro_liquido": ("Lucro líquido", "DRE 3.11"),
    "ebitda": ("EBITDA", "EBIT (DRE 3.05) + D&A (DFC)"),
    "resultado_operacional": ("EBIT (resultado operacional)", "DRE 3.05"),
    "resultado_financeiro": ("Resultado financeiro", "DRE 3.06"),
    "despesas_financeiras": ("Despesas financeiras", "DRE 3.06.02"),
    "depreciacao_amortizacao": ("Depreciação e amortização", "DFC 6.01.01.*"),
    "ativo_total": ("Ativo total", "BPA 1"),
    "ativo_circulante": ("Ativo circulante", "BPA 1.01"),
    "patrimonio_liquido": ("Patrimônio líquido", "BPP 2.03"),
    "capital_terceiros": ("Capital de terceiros", "BPP 2.01 + 2.02"),
    "passivo_circulante": ("Passivo circulante", "BPP 2.01"),
    "passivo_nao_circulante": ("Passivo não circulante", "BPP 2.02"),
    "divida_bruta": ("Dívida bruta", "BPP 2.01.04 + 2.02.01"),
    "divida_liquida": ("Dívida líquida", "Dívida bruta − caixa − aplicações"),
    "fluxo_caixa_operacional": ("Fluxo de caixa operacional (FCO)", "DFC 6.01"),
    "fluxo_caixa_investimento": ("Fluxo de caixa de investimento", "DFC 6.02"),
    "fluxo_caixa_financiamento": ("Fluxo de caixa de financiamento", "DFC 6.03"),
}

GRUPOS = [
    "Rentabilidade",
    "Estrutura de capital",
    "Liquidez",
    "Geração de caixa",
    "Apoio às hipóteses",
]

# nome: (rotulo, grupo, unidade, formula, leitura, "maior"/"menor" e melhor/None)
INDICADORES = {
    "margem_liquida": (
        "Margem líquida", "Rentabilidade", "%",
        "Lucro líquido ÷ Receita líquida",
        "Quanto de cada R$ 1 de receita vira lucro.", "maior"),
    "roe": (
        "ROE", "Rentabilidade", "%",
        "Lucro líquido ÷ Patrimônio líquido médio",
        "Retorno sobre o capital dos acionistas. Média = (saldo inicial + final) ÷ 2.",
        "maior"),
    "roa": (
        "ROA", "Rentabilidade", "%",
        "Lucro líquido ÷ Ativo total médio",
        "Retorno sobre todos os recursos aplicados na empresa.", "maior"),
    "margem_ebitda": (
        "Margem EBITDA", "Rentabilidade", "%",
        "(EBIT + Depreciação e amortização) ÷ Receita líquida",
        "Geração operacional antes de depreciação, juros e impostos.", "maior"),
    "endividamento_geral": (
        "Endividamento geral", "Estrutura de capital", "%",
        "Capital de terceiros ÷ Ativo total",
        "Parcela do ativo financiada por terceiros. Não usa a conta 2 (Passivo "
        "Total), que inclui o PL e daria sempre 100%.", "menor"),
    "composicao_endividamento": (
        "Composição do endividamento", "Estrutura de capital", "%",
        "Passivo circulante ÷ Capital de terceiros",
        "Quanto da dívida com terceiros vence no curto prazo.", "menor"),
    "divida_liquida_ebitda": (
        "Dívida líquida / EBITDA", "Estrutura de capital", "x",
        "(Dívida bruta − Caixa − Aplicações) ÷ EBITDA",
        "Anos de geração operacional para quitar a dívida líquida. Negativo = "
        "caixa maior que a dívida.", "menor"),
    "liquidez_corrente": (
        "Liquidez corrente", "Liquidez", "x",
        "Ativo circulante ÷ Passivo circulante",
        "Recursos de curto prazo para cada R$ 1 de obrigação de curto prazo.",
        "maior"),
    "cobertura_caixa": (
        "Cobertura de caixa", "Geração de caixa", "x",
        "Fluxo de caixa operacional ÷ Lucro líquido",
        "Quantas vezes o caixa das operações supera o lucro contábil. Instável "
        "quando o lucro é próximo de zero.", None),
    "margem_fco": (
        "Margem FCO", "Geração de caixa", "%",
        "Fluxo de caixa operacional ÷ Receita líquida",
        "Caixa gerado pelas operações para cada R$ 1 de receita.", "maior"),
    "peso_resultado_financeiro": (
        "Peso do resultado financeiro", "Apoio às hipóteses", "%",
        "− Resultado financeiro ÷ EBIT",
        "Parcela do resultado operacional consumida por juros e encargos "
        "líquidos (hipótese 1).", "menor"),
    "depreciacao_receita": (
        "Depreciação / Receita", "Apoio às hipóteses", "%",
        "Depreciação e amortização ÷ Receita líquida",
        "Intensidade de capital: peso do desgaste da rede sobre a receita "
        "(hipótese 2).", None),
}


def rotulo(nome: str) -> str:
    if nome in INDICADORES:
        return INDICADORES[nome][0]
    if nome in VARIAVEIS:
        return VARIAVEIS[nome][0]
    return nome


def unidade(nome: str) -> str:
    """'%', 'x' ou 'R$'."""
    return INDICADORES[nome][2] if nome in INDICADORES else "R$"


def indicadores_do_grupo(grupo: str) -> list:
    return [k for k, v in INDICADORES.items() if v[1] == grupo]


# ---------------------------------------------------------------
# LEITURA DO BANCO
# ---------------------------------------------------------------
def _versao_banco() -> float:
    """Data de modificacao do banco: invalida o cache quando o ETL roda."""
    return BANCO.stat().st_mtime if BANCO.exists() else 0.0


@st.cache_data(show_spinner=False)
def _consultar(sql: str, versao: float) -> pd.DataFrame:
    # mode=ro: somente leitura e erro (em vez de banco vazio) se nao existir
    uri = BANCO.resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        return pd.read_sql(sql, conn)


def garantir_banco() -> None:
    """Interrompe a pagina com uma mensagem clara se o banco nao existir."""
    if not BANCO.exists():
        st.error(
            "Banco de dados não encontrado em `database/telecom.db`.\n\n"
            "Rode o pipeline (`python etl/rodar_pipeline.py`) e confirme que o "
            "arquivo foi enviado ao GitHub (ele não pode estar no .gitignore)."
        )
        st.stop()


def carregar_painel() -> pd.DataFrame:
    """Uma linha por empresa/ano com variaveis em R$ e indicadores."""
    garantir_banco()
    versao = _versao_banco()
    base = _consultar("SELECT * FROM vw_base_analitica", versao)
    ind = _consultar("SELECT * FROM vw_indicadores", versao)
    if base.empty or ind.empty:
        st.error(
            "O banco existe, mas está sem dados de indicadores. Rode "
            "`python etl/rodar_pipeline.py` e faça commit do banco atualizado."
        )
        st.stop()
    ind = ind.rename(columns={"observacao": "observacao_indicadores"})
    df = base.merge(ind, on=["empresa", "ano"], how="left")
    df["ano"] = df["ano"].astype(int)
    return df.sort_values(["empresa", "ano"]).reset_index(drop=True)


def carregar_alertas() -> pd.DataFrame:
    garantir_banco()
    try:
        df = _consultar("SELECT * FROM alertas_indicadores", _versao_banco())
    except Exception:  # banco de versao anterior, sem a tabela
        return pd.DataFrame(columns=["empresa", "ano", "indicador", "tipo", "motivo"])
    if not df.empty:
        df["ano"] = df["ano"].astype(int)
    return df


# ---------------------------------------------------------------
# FILTROS (definidos na barra lateral do app.py)
# ---------------------------------------------------------------
def filtros(df: pd.DataFrame) -> tuple:
    """Le os filtros da barra lateral; se faltar algo, usa tudo."""
    empresas = st.session_state.get("empresas") or []
    anos = st.session_state.get("periodo") or (int(df["ano"].min()), int(df["ano"].max()))
    if not empresas:
        st.warning("Selecione ao menos uma empresa na barra lateral.")
        st.stop()
    ordenadas = [e for e in EMPRESAS if e in set(empresas)]  # ordem fixa
    return ordenadas, (int(anos[0]), int(anos[1]))


def filtrar(df: pd.DataFrame, empresas: list, anos: tuple) -> pd.DataFrame:
    return df[df["empresa"].isin(empresas) & df["ano"].between(anos[0], anos[1])].copy()


# ---------------------------------------------------------------
# CALCULOS DESCRITIVOS
# ---------------------------------------------------------------
def variacao_segura(serie: pd.Series) -> pd.Series:
    """Variacao % sobre o valor ABSOLUTO anterior (sinal correto com base negativa)."""
    anterior = serie.shift(1)
    return (serie - anterior) / anterior.abs().replace(0, np.nan)


def cagr(v0: float, v1: float, anos: int) -> float:
    if anos <= 0 or pd.isna(v0) or pd.isna(v1) or v0 <= 0 or v1 <= 0:
        return np.nan
    return (v1 / v0) ** (1 / anos) - 1


def estatisticas(df: pd.DataFrame, coluna: str) -> pd.DataFrame:
    """Estatisticas descritivas por empresa (valores ja filtrados)."""
    linhas = []
    for empresa, g in df.groupby("empresa"):
        s = g.set_index("ano")[coluna].dropna().sort_index()
        if s.empty:
            continue
        media = s.mean()
        desvio = s.std(ddof=1) if len(s) > 1 else np.nan
        a0, a1 = int(s.index.min()), int(s.index.max())
        linhas.append({
            "Empresa": empresa,
            "n": len(s),
            "Média": media,
            "Mediana": s.median(),
            "Desvio-padrão": desvio,
            "CV": desvio / abs(media) if media else np.nan,
            "Mínimo": s.min(),
            "Ano mín.": int(s.idxmin()),
            "Máximo": s.max(),
            "Ano máx.": int(s.idxmax()),
            "Ano inicial": a0,
            "Valor inicial": s.loc[a0],
            "Ano final": a1,
            "Valor final": s.loc[a1],
            "_inicial": s.loc[a0],
            "_final": s.loc[a1],
            "_anos": a1 - a0,
        })
    return pd.DataFrame(linhas)


def valor(df: pd.DataFrame, empresa: str, ano: int, coluna: str) -> float:
    s = df[(df["empresa"] == empresa) & (df["ano"] == ano)][coluna]
    return float(s.iloc[0]) if len(s) and pd.notna(s.iloc[0]) else np.nan


# ---------------------------------------------------------------
# FORMATACAO (padrao brasileiro)
# ---------------------------------------------------------------
def num_br(v, casas: int = 1) -> str:
    if v is None or pd.isna(v):
        return "–"
    texto = f"{v:,.{casas}f}"
    return texto.replace(",", "§").replace(".", ",").replace("§", ".")


def fmt_milhoes(v, casas: int = 1) -> str:
    return "–" if v is None or pd.isna(v) else f"R$ {num_br(v / 1e6, casas)} mi"


def fmt_pct(v, casas: int = 1) -> str:
    return "–" if v is None or pd.isna(v) else f"{num_br(v * 100, casas)}%"


def fmt_vezes(v, casas: int = 2) -> str:
    return "–" if v is None or pd.isna(v) else f"{num_br(v, casas)}x"


def fmt_valor(nome: str, v) -> str:
    u = unidade(nome)
    if u == "%":
        return fmt_pct(v)
    if u == "x":
        return fmt_vezes(v)
    return fmt_milhoes(v)


def fmt_delta(nome: str, atual, anterior):
    """Texto de variacao para st.metric (None quando nao ha base)."""
    if pd.isna(atual) or pd.isna(anterior):
        return None
    u = unidade(nome)
    if u == "%":
        d = (atual - anterior) * 100
        return f"{'+' if d >= 0 else ''}{num_br(d)} p.p."
    if u == "x":
        d = atual - anterior
        return f"{'+' if d >= 0 else ''}{num_br(d, 2)}x"
    if anterior == 0:
        return None
    d = (atual - anterior) / abs(anterior) * 100
    return f"{'+' if d >= 0 else ''}{num_br(d)}%"


def cor_delta(nome: str) -> str:
    """'inverse' quando subir e ruim (ex.: endividamento)."""
    if nome in INDICADORES:
        melhor = INDICADORES[nome][5]
        if melhor == "menor":
            return "inverse"
        if melhor is None:
            return "off"
    return "normal"


def formatar_tabela(df: pd.DataFrame, formatos: dict):
    """Styler com numeros no padrao brasileiro (o dado continua numerico)."""
    funcoes = {}
    for coluna, tipo in formatos.items():
        if coluna not in df.columns:
            continue
        if tipo == "%":
            funcoes[coluna] = fmt_pct
        elif tipo == "x":
            funcoes[coluna] = fmt_vezes
        elif tipo == "R$":
            funcoes[coluna] = fmt_milhoes
        elif tipo == "mi":
            funcoes[coluna] = lambda v: num_br(v / 1e6) if pd.notna(v) else "–"
        elif tipo == "int":
            funcoes[coluna] = lambda v: "–" if pd.isna(v) else str(int(v))
        else:
            funcoes[coluna] = lambda v, c=tipo: num_br(v, int(c)) if pd.notna(v) else "–"
    return df.style.format(funcoes, na_rep="–")


def csv_download(df: pd.DataFrame) -> bytes:
    """CSV no padrao que o Excel brasileiro abre direto (; e virgula)."""
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")
