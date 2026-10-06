# -*- coding: utf-8 -*-
"""
etl/07_diagnostico_dfc.py

Projeto Integrador III - Fatec Cotia
Diagnostico da Demonstracao de Fluxo de Caixa (DFC).

Citado na secao 8.1 do relatorio da Sprint 2, mas ausente do repositorio
revisado - recriado na revisao da Sprint 3 para que as secoes 6.2 e 6.4
do relatorio sejam REPRODUTIVEIS a partir do codigo.

O QUE FAZ
---------
  1. Fechamento da DFC em todas as empresas/anos da serie encadeada:
       6.01 + 6.02 + 6.03 + 6.04 (variacao cambial) = 6.05
       6.05.01 (saldo inicial) + 6.05 = 6.05.02 (saldo final)
  2. Razao FCO / Receita de cada observacao, sinalizando as que ficam
     fora da faixa citada no relatorio (26% a 54%).
  3. Testa as 3 hipoteses para o valor atipico da Desktop em 2021:
       H1 reapresentacao     -> 2021 no arquivo de 2021 x no arquivo de 2022
       H2 conta divergente   -> descricao da conta 6.01 em 2021
       H3 valor reportado    -> fechamento da DFC de 2021

ENTRADA : database/telecom.db (camada raw - nao precisa dos CSVs)
SAIDA   : data/exports/diagnostico_dfc.csv

COMO RODAR
----------
  python etl/07_diagnostico_dfc.py
"""

import sqlite3
import sys
from contextlib import closing

import pandas as pd

from config import (
    BANCO, DIR_EXPORTS, RAIZ, ENCADEAMENTO, ANOS,
    ORDEM_EXERCICIO, ORDEM_EXERCICIO_ANTERIOR,
)

FAIXA_FCO_RECEITA = (0.26, 0.54)   # faixa citada na secao 6.4 do relatorio
TOLERANCIA = 1_000                 # R$ 1 mil (1 unidade na escala da CVM)


def ler_contas(conn, tabela: str, contas: list) -> pd.DataFrame:
    """Le contas da camada raw (ULTIMO e PENULTIMO), sem duplicatas."""
    marcadores = ",".join("?" * len(contas))
    df = pd.read_sql(
        f"""
        SELECT cd_cvm, ano_arquivo, versao, ordem_exerc, dt_fim_exerc,
               TRIM(cd_conta) AS cd_conta, ds_conta, vl_conta
        FROM {tabela}
        WHERE TRIM(cd_conta) IN ({marcadores})
        """,
        conn,
        params=contas,
    )
    df["ordem_exerc"] = df["ordem_exerc"].str.strip().str.upper()
    df["ano"] = pd.to_datetime(df["dt_fim_exerc"], errors="coerce").dt.year
    return (
        df.sort_values("versao", kind="stable")
          .drop_duplicates(
              subset=["cd_cvm", "ano_arquivo", "ordem_exerc", "cd_conta"],
              keep="last",
          )
    )


def valor(df, cd, ano_arquivo, ordem, conta):
    s = df[
        (df["cd_cvm"] == cd) & (df["ano_arquivo"] == ano_arquivo)
        & (df["ordem_exerc"] == ordem) & (df["cd_conta"] == conta)
    ]["vl_conta"]
    return float(s.iloc[0]) if len(s) else float("nan")


def fechamento(dfc, dre) -> pd.DataFrame:
    linhas = []
    for grupo, regra in ENCADEAMENTO.items():
        for ano in ANOS:
            cd = regra.get(ano)
            if cd is None:
                continue
            v = {c: valor(dfc, cd, ano, ORDEM_EXERCICIO, c)
                 for c in ("6.01", "6.02", "6.03", "6.04", "6.05", "6.05.01", "6.05.02")}
            cambial = 0.0 if pd.isna(v["6.04"]) else v["6.04"]
            receita = valor(dre, cd, ano, ORDEM_EXERCICIO, "3.01")
            soma = v["6.01"] + v["6.02"] + v["6.03"] + cambial
            linhas.append({
                "empresa": grupo,
                "ano": ano,
                "cd_cvm": cd,
                "fco": v["6.01"],
                "fci": v["6.02"],
                "fcf": v["6.03"],
                "variacao_cambial": cambial,
                "variacao_caixa": v["6.05"],
                "dif_fechamento": soma - v["6.05"],
                "dif_saldos": (v["6.05.01"] + v["6.05"]) - v["6.05.02"],
                "receita_liquida": receita,
                "fco_receita": v["6.01"] / receita if receita else float("nan"),
            })
    df = pd.DataFrame(linhas)
    df["fechamento_ok"] = (
        (df["dif_fechamento"].abs() <= TOLERANCIA)
        & (df["dif_saldos"].abs() <= TOLERANCIA)
    )
    lo, hi = FAIXA_FCO_RECEITA
    # compara com 1 casa decimal em pontos percentuais (como e exibido)
    pct = df["fco_receita"].round(3)
    df["fora_da_faixa"] = (pct < lo) | (pct > hi)
    return df


def hipoteses_desktop(dfc, base: pd.DataFrame) -> None:
    cd, ano = ENCADEAMENTO["Desktop"][2021], 2021
    print("\n" + "=" * 78)
    print("VALOR ATIPICO | DESKTOP 2021 (secao 6.4 do relatorio da Sprint 2)")
    print("=" * 78)

    publicado = valor(dfc, cd, ano, ORDEM_EXERCICIO, "6.01")
    comparativo = valor(dfc, cd, ano + 1, ORDEM_EXERCICIO_ANTERIOR, "6.01")
    print(f"\nH1 reapresentacao | arquivo 2021: {publicado / 1e6:,.1f} mi | "
          f"comparativo no arquivo 2022: {comparativo / 1e6:,.1f} mi")
    print("   -> " + ("DESCARTADA (valores identicos)"
                      if abs(publicado - comparativo) <= TOLERANCIA
                      else "POSSIVEL (valores diferentes)"))

    desc = dfc[
        (dfc["cd_cvm"] == cd) & (dfc["ano_arquivo"] == ano)
        & (dfc["ordem_exerc"] == ORDEM_EXERCICIO) & (dfc["cd_conta"] == "6.01")
    ]["ds_conta"]
    print(f"\nH2 conta divergente | descricao da 6.01: "
          f"'{desc.iloc[0] if len(desc) else '?'}'")

    linha = base[(base["empresa"] == "Desktop") & (base["ano"] == ano)].iloc[0]
    print(f"\nH3 valor reportado | 6.01 + 6.02 + 6.03 + 6.04 - 6.05 = "
          f"{linha['dif_fechamento']:,.0f}")
    print("   -> " + ("CONFIRMADA (a DFC fecha: o valor e o publicado)"
                      if linha["fechamento_ok"] else "NAO confirmada"))


def main() -> None:
    if not BANCO.exists():
        sys.exit("Banco nao encontrado. Rode antes: python etl/04_criar_banco.py "
                 "&& python etl/05_carga.py")

    with closing(sqlite3.connect(BANCO)) as conn:
        dfc = ler_contas(conn, "raw_dfc_mi",
                         ["6.01", "6.02", "6.03", "6.04", "6.05", "6.05.01", "6.05.02"])
        dre = ler_contas(conn, "raw_dre", ["3.01"])

    if dfc.empty:
        sys.exit("Camada raw vazia. Rode antes: python etl/05_carga.py")

    base = fechamento(dfc, dre)

    print("=" * 78)
    print("FECHAMENTO DA DFC (6.01 + 6.02 + 6.03 + 6.04 = 6.05)")
    print("=" * 78)
    ok = int(base["fechamento_ok"].sum())
    print(f"  {ok} de {len(base)} observacoes fecham (tolerancia R$ 1 mil)")
    for _, r in base[~base["fechamento_ok"]].iterrows():
        print(f"  [!] {r['empresa']} {r['ano']}: diferenca {r['dif_fechamento']:,.0f}")

    lo, hi = FAIXA_FCO_RECEITA
    print("\n" + "=" * 78)
    print(f"FCO / RECEITA (faixa de referencia {lo:.0%} a {hi:.0%})")
    print("=" * 78)
    for _, r in base.iterrows():
        marca = "[!]" if r["fora_da_faixa"] else "   "
        print(f"  {marca} {r['empresa']:9s} {r['ano']} | {r['fco_receita']:7.1%}")
    dentro = int((~base["fora_da_faixa"]).sum())
    print(f"\n  {dentro} de {len(base)} observacoes dentro da faixa.")

    hipoteses_desktop(dfc, base)

    destino = DIR_EXPORTS / "diagnostico_dfc.csv"
    base.to_csv(destino, index=False, sep=";", decimal=",", encoding="utf-8-sig")
    print(f"\n  Salvo: {destino.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
