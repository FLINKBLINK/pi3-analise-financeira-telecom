# -*- coding: utf-8 -*-
"""
etl/08_indicadores.py

Projeto Integrador III - Fatec Cotia
SPRINT 3 - Calculo dos indicadores financeiros e estatisticas descritivas.

ENTRADA
-------
  database/telecom.db -> financial_data (+ camada raw para os saldos iniciais)

SAIDAS
------
  financial_indicators (tabela)                 -> consumida pelo dashboard
  alertas_indicadores  (tabela)                 -> avisos de interpretacao
  data/exports/financial_indicators.csv
  data/exports/alertas_indicadores.csv
  data/exports/estatisticas_indicadores.csv     (media, mediana, desvio...)
  data/exports/crescimento_variaveis.csv        (variacao total e CAGR)

INDICADORES (percentuais gravados como fracao: 0,125 = 12,5%)
-----------
 Rentabilidade
   margem_liquida            = lucro liquido / receita liquida
   roe                       = lucro liquido / PL medio          (def. Sprint 1)
   roa                       = lucro liquido / ativo total medio
   margem_ebitda             = (EBIT + D&A) / receita liquida
 Estrutura de capital
   endividamento_geral       = capital de terceiros / ativo total (Sprint 2, 4.1)
   composicao_endividamento  = passivo circulante / capital de terceiros
   divida_liquida_ebitda     = (divida bruta - caixa - aplicacoes) / EBITDA
 Liquidez
   liquidez_corrente         = ativo circulante / passivo circulante
 Geracao de caixa
   cobertura_caixa           = FCO / lucro liquido
   margem_fco                = FCO / receita liquida
 Apoio as hipoteses da secao 7.3 (Sprint 2)
   peso_resultado_financeiro = - resultado financeiro / EBIT
   depreciacao_receita       = D&A / receita liquida

SALDOS MEDIOS (ROE e ROA)
-------------------------
media = (saldo inicial + saldo final) / 2. O saldo inicial e o comparativo
(PENULTIMO) publicado NA PROPRIA DFP do ano. Assim a media sempre usa a
mesma entidade (importante na troca da Brisanet em 2024) e ja incorpora
eventuais reapresentacoes do ano anterior. Comparativo ZERADO significa
"nao divulgado" (caso da DFP 2020 da Desktop): o indicador fica nulo e
um alerta e registrado - nada e inventado.

COMO RODAR
----------
  python etl/08_indicadores.py
"""

import logging
import sqlite3
import sys

import numpy as np
import pandas as pd

from config import BANCO, DIR_EXPORTS, DIR_LOGS, RAIZ, ORDEM_EXERCICIO_ANTERIOR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(DIR_LOGS / "08_indicadores.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger(__name__)

# |lucro| abaixo de 1% da receita: razoes com o lucro no denominador explodem
LIMITE_LUCRO_PROXIMO_ZERO = 0.01

INDICADORES = [
    "margem_liquida", "roe", "roa",
    "endividamento_geral", "composicao_endividamento",
    "liquidez_corrente", "cobertura_caixa",
    "margem_ebitda", "margem_fco", "divida_liquida_ebitda",
    "peso_resultado_financeiro", "depreciacao_receita",
]

# Indicadores expressos em "vezes" (os demais sao percentuais)
EM_VEZES = {"liquidez_corrente", "cobertura_caixa", "divida_liquida_ebitda"}

VARIAVEIS_CRESCIMENTO = [
    "receita_liquida", "lucro_liquido", "ebitda", "fluxo_caixa_operacional",
    "ativo_total", "patrimonio_liquido", "capital_terceiros", "divida_bruta",
]


# ---------------------------------------------------------------
# LEITURA
# ---------------------------------------------------------------
def verificar_estrutura(conn: sqlite3.Connection) -> None:
    """Garante que o banco ja passou pela migracao do 04_criar_banco.py."""
    colunas = {r[1] for r in conn.execute("PRAGMA table_info(financial_indicators)")}
    faltando = [c for c in INDICADORES + ["observacao"] if c not in colunas]
    tabelas = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table'")}
    if faltando or "alertas_indicadores" not in tabelas:
        sys.exit(
            "O banco esta com a estrutura antiga.\n"
            "Rode antes: python etl/04_criar_banco.py  (aplica a migracao)\n"
            "e depois:   python etl/05_carga.py"
        )


def carregar(conn: sqlite3.Connection) -> pd.DataFrame:
    base = pd.read_sql("SELECT * FROM financial_data ORDER BY empresa, ano", conn)
    if base.empty:
        sys.exit("financial_data esta vazia. Rode antes: python etl/05_carga.py")
    if "ebitda" not in base.columns or base["ebitda"].isna().all():
        sys.exit("Variaveis complementares ausentes. Rode: python etl/05_carga.py")
    log.info("Base carregada | %d linhas | %d empresas",
             len(base), base["empresa"].nunique())
    return base


def saldos_iniciais(conn: sqlite3.Connection, base: pd.DataFrame) -> pd.DataFrame:
    """Comparativo (PENULTIMO) de PL e ativo total publicado na DFP do ano."""
    ini = pd.read_sql(
        """
        SELECT cd_cvm, ano_arquivo, versao, TRIM(cd_conta) AS cd_conta, vl_conta
        FROM raw_bpp
        WHERE TRIM(cd_conta) = '2.03' AND UPPER(TRIM(ordem_exerc)) = ?
        UNION ALL
        SELECT cd_cvm, ano_arquivo, versao, TRIM(cd_conta) AS cd_conta, vl_conta
        FROM raw_bpa
        WHERE TRIM(cd_conta) = '1' AND UPPER(TRIM(ordem_exerc)) = ?
        """,
        conn,
        params=(ORDEM_EXERCICIO_ANTERIOR, ORDEM_EXERCICIO_ANTERIOR),
    )
    ini = (
        ini.sort_values("versao", kind="stable")
           .drop_duplicates(subset=["cd_cvm", "ano_arquivo", "cd_conta"], keep="last")
    )
    largo = (
        ini.pivot_table(index=["cd_cvm", "ano_arquivo"], columns="cd_conta",
                        values="vl_conta", aggfunc="first")
           .reset_index()
           .rename(columns={"ano_arquivo": "ano", "2.03": "pl_inicial",
                            "1": "ativo_inicial"})
    )
    largo.columns.name = None
    for col in ("pl_inicial", "ativo_inicial"):
        if col not in largo.columns:
            largo[col] = np.nan
        # comparativo zerado = nao divulgado (ex.: DFP 2020 da Desktop)
        largo[col] = largo[col].where(largo[col] != 0)

    return base.merge(
        largo[["cd_cvm", "ano", "pl_inicial", "ativo_inicial"]],
        on=["cd_cvm", "ano"], how="left",
    )


# ---------------------------------------------------------------
# CALCULO
# ---------------------------------------------------------------
def dividir(numerador: pd.Series, denominador: pd.Series) -> pd.Series:
    """Divisao segura: denominador zero ou nulo resulta em nulo."""
    den = pd.to_numeric(denominador, errors="coerce")
    return pd.to_numeric(numerador, errors="coerce") / den.where(den != 0)


def calcular(b: pd.DataFrame) -> pd.DataFrame:
    pl_medio = (b["patrimonio_liquido"] + b["pl_inicial"]) / 2
    ativo_medio = (b["ativo_total"] + b["ativo_inicial"]) / 2
    lucro_positivo = b["lucro_liquido"].where(b["lucro_liquido"] > 0)
    ebitda_positivo = b["ebitda"].where(b["ebitda"] > 0)
    ebit_positivo = b["resultado_operacional"].where(b["resultado_operacional"] > 0)

    ind = pd.DataFrame({"empresa": b["empresa"], "ano": b["ano"]})
    ind["margem_liquida"] = dividir(b["lucro_liquido"], b["receita_liquida"])
    ind["roe"] = dividir(b["lucro_liquido"], pl_medio)
    ind["roa"] = dividir(b["lucro_liquido"], ativo_medio)
    ind["endividamento_geral"] = dividir(b["capital_terceiros"], b["ativo_total"])
    ind["composicao_endividamento"] = dividir(b["passivo_circulante"], b["capital_terceiros"])
    ind["liquidez_corrente"] = dividir(b["ativo_circulante"], b["passivo_circulante"])
    ind["cobertura_caixa"] = dividir(b["fluxo_caixa_operacional"], lucro_positivo)
    ind["margem_ebitda"] = dividir(b["ebitda"], b["receita_liquida"])
    ind["margem_fco"] = dividir(b["fluxo_caixa_operacional"], b["receita_liquida"])
    ind["divida_liquida_ebitda"] = dividir(b["divida_liquida"], ebitda_positivo)
    ind["peso_resultado_financeiro"] = dividir(-b["resultado_financeiro"], ebit_positivo)
    ind["depreciacao_receita"] = dividir(b["depreciacao_amortizacao"], b["receita_liquida"])
    return ind


def pct_br(valor: float) -> str:
    """0.0031 -> '0,3%' (formato brasileiro, usado nos textos de alerta)."""
    return f"{valor:.1%}".replace(".", ",")


def gerar_alertas(b: pd.DataFrame) -> pd.DataFrame:
    """Avisos de interpretacao. O valor publicado nunca e alterado."""
    alertas = []

    def add(r, indicador, tipo, motivo):
        alertas.append({"empresa": r["empresa"], "ano": int(r["ano"]),
                        "indicador": indicador, "tipo": tipo, "motivo": motivo})

    for _, r in b.iterrows():
        receita, lucro = r["receita_liquida"], r["lucro_liquido"]
        fco = r["fluxo_caixa_operacional"]

        if pd.isna(r["pl_inicial"]):
            add(r, "roe", "nao_calculado",
                "PL inicial não divulgado na DFP do ano: média indisponível.")
        if pd.isna(r["ativo_inicial"]):
            add(r, "roa", "nao_calculado",
                "Ativo inicial não divulgado na DFP do ano: média indisponível.")

        if pd.notna(lucro) and lucro <= 0:
            add(r, "cobertura_caixa", "nao_calculado",
                "Lucro líquido menor ou igual a zero: razão sem significado.")
        elif pd.notna(lucro) and receita and lucro / receita < LIMITE_LUCRO_PROXIMO_ZERO:
            add(r, "cobertura_caixa", "distorcido",
                f"Lucro líquido próximo de zero ({pct_br(lucro / receita)} da "
                "receita): a razão FCO/lucro fica inflada.")

        if pd.notna(fco) and receita and fco > receita:
            for nome in ("margem_fco", "cobertura_caixa"):
                add(r, nome, "atipico",
                    "FCO maior que a receita do ano: valor atípico, mantido como "
                    "publicado (ver etl/07_diagnostico_dfc.py).")

        if pd.notna(r["ebitda"]) and r["ebitda"] <= 0:
            add(r, "divida_liquida_ebitda", "nao_calculado", "EBITDA menor ou igual a zero.")
        elif pd.notna(r["divida_liquida"]) and r["divida_liquida"] < 0:
            add(r, "divida_liquida_ebitda", "contexto",
                "Caixa líquido: caixa e aplicações superam a dívida bruta "
                "(indicador negativo).")

        if pd.notna(r["resultado_operacional"]) and r["resultado_operacional"] <= 0:
            add(r, "peso_resultado_financeiro", "nao_calculado", "EBIT menor ou igual a zero.")
        elif pd.notna(r["resultado_financeiro"]) and r["resultado_financeiro"] > 0:
            add(r, "peso_resultado_financeiro", "contexto",
                "Resultado financeiro positivo: receitas financeiras superaram as "
                "despesas (indicador negativo).")

    return pd.DataFrame(
        alertas, columns=["empresa", "ano", "indicador", "tipo", "motivo"]
    )


def anexar_observacao(ind: pd.DataFrame, alertas: pd.DataFrame) -> pd.DataFrame:
    ind = ind.copy()
    if alertas.empty:
        ind["observacao"] = None
        return ind
    texto = (
        alertas.assign(t=alertas["indicador"] + ": " + alertas["motivo"])
               .groupby(["empresa", "ano"])["t"]
               .apply(lambda s: " | ".join(s))
               .rename("observacao")
               .reset_index()
    )
    return ind.merge(texto, on=["empresa", "ano"], how="left")


# ---------------------------------------------------------------
# ESTATISTICAS DESCRITIVAS
# ---------------------------------------------------------------
def resumo_serie(s: pd.Series) -> dict:
    """s: valores indexados pelo ano, sem nulos."""
    media = s.mean()
    desvio = s.std(ddof=1) if len(s) > 1 else np.nan
    return {
        "n": int(len(s)),
        "media": media,
        "mediana": s.median(),
        "desvio_padrao": desvio,
        "coef_variacao": desvio / abs(media) if media else np.nan,
        "minimo": s.min(),
        "ano_minimo": int(s.idxmin()),
        "maximo": s.max(),
        "ano_maximo": int(s.idxmax()),
        "ano_inicial": int(s.index.min()),
        "valor_inicial": s.loc[s.index.min()],
        "ano_final": int(s.index.max()),
        "valor_final": s.loc[s.index.max()],
        "variacao_no_periodo": s.loc[s.index.max()] - s.loc[s.index.min()],
    }


def estatisticas(ind: pd.DataFrame, alertas: pd.DataFrame) -> pd.DataFrame:
    """
    Duas amostras por indicador/empresa:
      'todas'          -> todos os valores publicados
      'sem_sinalizados'-> exclui valores com alerta 'atipico' ou 'distorcido'
    Comparar as duas mostra o quanto um valor atipico pesa na descricao
    (tratamento previsto na secao 6.4 do relatorio da Sprint 2).
    """
    sinalizados = set()
    if not alertas.empty:
        sub = alertas[alertas["tipo"].isin(["atipico", "distorcido"])]
        sinalizados = set(zip(sub["empresa"], sub["ano"], sub["indicador"]))

    linhas = []
    for nome in INDICADORES:
        for empresa, g in ind.groupby("empresa"):
            serie = g.set_index("ano")[nome].dropna().sort_index()
            limpa = serie[[(empresa, a, nome) not in sinalizados for a in serie.index]]
            for amostra, s in (("todas", serie), ("sem_sinalizados", limpa)):
                if s.empty:
                    continue
                if amostra == "sem_sinalizados" and len(s) == len(serie):
                    continue  # nada foi excluido: linha seria repetida
                linhas.append({
                    "indicador": nome,
                    "unidade": "x" if nome in EM_VEZES else "fracao",
                    "empresa": empresa,
                    "amostra": amostra,
                    **resumo_serie(s),
                })
    return pd.DataFrame(linhas)


def crescimento(base: pd.DataFrame) -> pd.DataFrame:
    """Variacao total e CAGR das variaveis em R$ (so com base positiva)."""
    linhas = []
    for empresa, g in base.groupby("empresa"):
        g = g.set_index("ano").sort_index()
        for var in VARIAVEIS_CRESCIMENTO:
            s = g[var].dropna()
            if len(s) < 2:
                continue
            a0, a1 = int(s.index.min()), int(s.index.max())
            v0, v1 = s.loc[a0], s.loc[a1]
            positivos = v0 > 0 and v1 > 0
            linhas.append({
                "empresa": empresa,
                "variavel": var,
                "ano_inicial": a0,
                "valor_inicial": v0,
                "ano_final": a1,
                "valor_final": v1,
                "variacao_total": v1 / v0 - 1 if v0 > 0 else np.nan,
                "cagr": (v1 / v0) ** (1 / (a1 - a0)) - 1 if positivos else np.nan,
            })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------
# GRAVACAO E EXIBICAO
# ---------------------------------------------------------------
def gravar(conn, ind, alertas, stats, cresc) -> None:
    conn.execute("DELETE FROM financial_indicators")
    ind[["empresa", "ano", *INDICADORES, "observacao"]].to_sql(
        "financial_indicators", conn, if_exists="append", index=False)

    conn.execute("DELETE FROM alertas_indicadores")
    if not alertas.empty:
        alertas.to_sql("alertas_indicadores", conn, if_exists="append", index=False)

    conn.execute(
        "INSERT INTO etl_log (etapa, detalhe, registros) VALUES (?,?,?)",
        ("08_indicadores", "financial_indicators", len(ind)),
    )
    conn.commit()
    log.info("financial_indicators gravada: %d linhas | %d alertas",
             len(ind), len(alertas))

    kw = dict(index=False, sep=";", decimal=",", encoding="utf-8-sig")
    saidas = {
        "financial_indicators.csv": ind,
        "alertas_indicadores.csv": alertas,
        "estatisticas_indicadores.csv": stats,
        "crescimento_variaveis.csv": cresc,
    }
    for nome, df in saidas.items():
        df.to_csv(DIR_EXPORTS / nome, **kw)
        log.info("  Salvo: %s", (DIR_EXPORTS / nome).relative_to(RAIZ))


def exibir(ind: pd.DataFrame, alertas: pd.DataFrame, cresc: pd.DataFrame) -> None:
    ultimo = int(ind["ano"].max())
    print("\n" + "=" * 78)
    print(f"INDICADORES {ultimo} (percentuais em %, demais em vezes)")
    print("=" * 78)
    tab = ind[ind["ano"] == ultimo].set_index("empresa")[INDICADORES].T
    for nome in tab.index:
        fator, suf = (1, "x") if nome in EM_VEZES else (100, "%")
        valores = " | ".join(
            f"{e}: {v * fator:7.1f}{suf}" if pd.notna(v) else f"{e}:     n/d"
            for e, v in tab.loc[nome].items()
        )
        print(f"  {nome:26s} {valores}")

    print("\n" + "=" * 78)
    print("CRESCIMENTO MEDIO ANUAL (CAGR) NO PERIODO")
    print("=" * 78)
    piv = cresc.pivot(index="variavel", columns="empresa", values="cagr") * 100
    print(piv.round(1).to_string())

    if not alertas.empty:
        print("\n" + "=" * 78)
        print(f"ALERTAS DE INTERPRETACAO ({len(alertas)})")
        print("=" * 78)
        for _, a in alertas.iterrows():
            print(f"  [{a['tipo']:13s}] {a['empresa']:9s} {a['ano']} | "
                  f"{a['indicador']}: {a['motivo']}")


# ---------------------------------------------------------------
def main() -> None:
    if not BANCO.exists():
        sys.exit("Banco nao encontrado. Rode antes: python etl/04_criar_banco.py")

    conn = sqlite3.connect(BANCO)
    try:
        verificar_estrutura(conn)
        base = saldos_iniciais(conn, carregar(conn))
        ind = calcular(base)
        alertas = gerar_alertas(base)
        ind = anexar_observacao(ind, alertas)
        stats = estatisticas(ind, alertas)
        cresc = crescimento(base)
        gravar(conn, ind, alertas, stats, cresc)
    finally:
        conn.close()

    exibir(ind, alertas, cresc)
    print("\n" + "=" * 78)
    print("INDICADORES CALCULADOS. Proximo passo: streamlit run dashboard/app.py")
    print("=" * 78)


if __name__ == "__main__":
    main()
