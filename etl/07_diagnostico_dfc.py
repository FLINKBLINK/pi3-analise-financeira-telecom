# -*- coding: utf-8 -*-
"""
etl/07_diagnostico_dfc.py

Projeto Integrador III - Fatec Cotia
Diagnostico de anomalia no Fluxo de Caixa Operacional (DFC)

MOTIVO
------
A auditoria da base analitica revelou dois valores implausiveis para a
Desktop S.A. na conta 6.01 (Caixa Liquido das Atividades Operacionais):

    Empresa   Ano   FCO / Receita Liquida
    Desktop   2021          215,8%   <-- implausivel
    Desktop   2022           12,4%   <-- muito baixo

Para referencia, todas as demais observacoes da base ficam entre
26% e 54%, faixa tipica de operadoras de fibra (negocio intensivo
em capital, com forte geracao de caixa operacional).

Um FCO maior que o dobro da receita nao e possivel em operacao normal.
As hipoteses sao:

  H1. REAPRESENTACAO
      A CVM permite reapresentar demonstracoes. Se o valor de 2021
      publicado no arquivo de 2021 (como ULTIMO) diverge do publicado
      no arquivo de 2022 (como PENULTIMO), houve republicacao e o
      ETL pode ter capturado a versao antiga.

  H2. ESTRUTURA DE CONTA DIVERGENTE
      A empresa pode ter usado um elenco de contas diferente naquele
      exercicio, fazendo com que 6.01 represente outra coisa.

  H3. VALOR REAL ATIPICO
      Evento nao recorrente legitimo (ex.: variacao brusca de capital
      de giro, antecipacao de recebiveis).

O QUE ESTE SCRIPT FAZ
---------------------
1) Compara o valor de cada ano quando reportado como ULTIMO (no arquivo
   do proprio ano) e como PENULTIMO (no arquivo do ano seguinte).
   Divergencia = reapresentacao -> confirma H1.

2) Lista a estrutura completa da DFC da Desktop nos anos suspeitos,
   permitindo verificar se 6.01 esta no lugar esperado -> testa H2.

3) Confere se a DFC fecha: 6.01 + 6.02 + 6.03 deve ser igual a 6.05
   (variacao liquida do caixa). Se fechar, o valor e real -> H3.

Este script NAO altera o banco. E puramente diagnostico.

COMO RODAR
----------
  python etl/07_diagnostico_dfc.py
  python etl/07_diagnostico_dfc.py --empresa Desktop --anos 2021 2022
"""

import argparse
import sys

import pandas as pd

from config import (
    DIR_RAW, DIR_EXPORTS, RAIZ, ANOS, ENTIDADES,
    CSV_KWARGS, ESCALA, normalizar_cvm, caminho_arquivo,
)

# Contas de primeiro nivel da DFC (metodo indireto) no elenco da CVM
CONTAS_DFC = {
    "6.01": "Caixa Liquido Atividades Operacionais",
    "6.02": "Caixa Liquido Atividades de Investimento",
    "6.03": "Caixa Liquido Atividades de Financiamento",
    "6.04": "Variacao Cambial s/ Caixa e Equivalentes",
    "6.05": "Aumento (Reducao) de Caixa e Equivalentes",
}


# ---------------------------------------------------------------
def ler_dfc(ano: int) -> pd.DataFrame:
    """Le o arquivo DFC_MI de um ano, sem filtrar ORDEM_EXERC."""
    arq = caminho_arquivo("DFC_MI", ano)
    if not arq.exists():
        print(f"  [AUSENTE] {arq.name}")
        return pd.DataFrame()

    df = pd.read_csv(arq, **CSV_KWARGS)
    df["CD_CVM"] = normalizar_cvm(df["CD_CVM"])
    df = df[df["CD_CVM"].isin(ENTIDADES)].copy()
    if df.empty:
        return df

    valor = pd.to_numeric(
        df["VL_CONTA"].astype(str).str.strip().str.replace(",", ".", regex=False),
        errors="coerce",
    )
    fator = df["ESCALA_MOEDA"].str.upper().str.strip().map(ESCALA).fillna(1)
    df["valor"] = valor * fator

    df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce").fillna(0).astype(int)
    df["grupo"] = df["CD_CVM"].map(lambda c: ENTIDADES[c]["grupo"])
    df["ordem"] = df["ORDEM_EXERC"].str.strip().str.upper()
    df["CD_CONTA"] = df["CD_CONTA"].str.strip()
    df["arquivo_ano"] = ano

    # ano de competencia da linha
    df["ano_ref"] = pd.to_datetime(
        df["DT_FIM_EXERC"], errors="coerce"
    ).dt.year

    return df


# ---------------------------------------------------------------
# TESTE 1 - REAPRESENTACAO
# ---------------------------------------------------------------
def teste_reapresentacao(dados: dict, empresa: str) -> pd.DataFrame:
    print("\n" + "=" * 78)
    print("TESTE 1 | REAPRESENTACAO (H1)")
    print("=" * 78)
    print(
        "\nCompara o valor da conta 6.01 quando publicado como ULTIMO\n"
        "(arquivo do proprio ano) e como PENULTIMO (arquivo do ano seguinte).\n"
    )

    linhas = []
    for ano_arq, df in dados.items():
        if df.empty:
            continue
        sub = df[(df["grupo"] == empresa) & (df["CD_CONTA"] == "6.01")]
        for _, r in sub.iterrows():
            if pd.isna(r["ano_ref"]):
                continue
            linhas.append({
                "ano_competencia": int(r["ano_ref"]),
                "publicado_no_arquivo": ano_arq,
                "ordem": r["ordem"],
                "versao": r["VERSAO"],
                "valor": r["valor"],
            })

    if not linhas:
        print(f"  Nenhum dado de 6.01 encontrado para {empresa}.")
        return pd.DataFrame()

    df = pd.DataFrame(linhas)

    pivot = df.pivot_table(
        index="ano_competencia",
        columns="ordem",
        values="valor",
        aggfunc="first",
    )

    col_u = [c for c in pivot.columns if c.startswith("\u00da")]
    col_p = [c for c in pivot.columns if c.startswith("PEN")]

    if col_u and col_p:
        u, p = col_u[0], col_p[0]
        pivot["divergencia"] = pivot[p] - pivot[u]
        pivot["divergencia_%"] = (
            pivot["divergencia"] / pivot[u].abs().replace(0, pd.NA) * 100
        ).round(2)

    exibir = pivot.copy()
    for c in exibir.columns:
        if "%" not in str(c):
            exibir[c] = (exibir[c] / 1e6).round(1)

    print(exibir.to_string())
    print("\n(valores em R$ milhoes)")

    if col_u and col_p and "divergencia_%" in pivot.columns:
        div = pivot["divergencia_%"].abs().dropna()
        graves = div[div > 1]
        if not graves.empty:
            print("\n  [!] REAPRESENTACAO DETECTADA nos anos:")
            for ano, v in graves.items():
                print(f"      {int(ano)} | divergencia de {v:.2f}%")
            print(
                "\n      CONCLUSAO: o valor publicado originalmente foi\n"
                "      corrigido pela empresa depois. O ETL deve usar a\n"
                "      versao mais recente (PENULTIMO do arquivo seguinte)."
            )
        else:
            print("\n  [ok] Nenhuma reapresentacao relevante. H1 descartada.")

    return df


# ---------------------------------------------------------------
# TESTE 2 - ESTRUTURA DA DFC
# ---------------------------------------------------------------
def teste_estrutura(dados: dict, empresa: str, anos_alvo: list) -> None:
    print("\n" + "=" * 78)
    print("TESTE 2 | ESTRUTURA DA DFC (H2)")
    print("=" * 78)
    print(
        "\nMostra as contas de primeiro nivel da DFC nos anos suspeitos.\n"
        "Verifique se 6.01 corresponde mesmo a 'Atividades Operacionais'.\n"
    )

    for ano in anos_alvo:
        df = dados.get(ano, pd.DataFrame())
        if df.empty:
            continue

        sub = df[
            (df["grupo"] == empresa)
            & (df["ordem"].str.startswith("\u00da"))
            & (df["CD_CONTA"].isin(CONTAS_DFC))
        ].sort_values("CD_CONTA")

        if sub.empty:
            print(f"  {ano} | sem dados")
            continue

        print(f"\n--- {empresa} | exercicio {ano} ---")
        for _, r in sub.iterrows():
            esperado = CONTAS_DFC.get(r["CD_CONTA"], "")
            real = str(r["DS_CONTA"]).strip()
            marca = "ok " if esperado.split()[0].lower() in real.lower() else "[!]"
            print(
                f"  {marca} {r['CD_CONTA']:6s} | {real[:48]:48s} | "
                f"{r['valor']/1e6:10.1f} mi"
            )


# ---------------------------------------------------------------
# TESTE 3 - FECHAMENTO DA DFC
# ---------------------------------------------------------------
def teste_fechamento(dados: dict, empresa: str) -> None:
    print("\n" + "=" * 78)
    print("TESTE 3 | FECHAMENTO DA DFC (H3)")
    print("=" * 78)
    print(
        "\nA soma 6.01 + 6.02 + 6.03 (+6.04) deve ser igual a 6.05.\n"
        "Se fechar, o valor extraido esta correto e a anomalia e real.\n"
    )

    linhas = []
    for ano, df in dados.items():
        if df.empty:
            continue
        sub = df[
            (df["grupo"] == empresa)
            & (df["ordem"].str.startswith("\u00da"))
            & (df["CD_CONTA"].isin(CONTAS_DFC))
        ]
        if sub.empty:
            continue

        vals = sub.set_index("CD_CONTA")["valor"].to_dict()
        soma = sum(vals.get(c, 0) for c in ("6.01", "6.02", "6.03", "6.04"))
        total = vals.get("6.05")

        linhas.append({
            "ano": ano,
            "op_6.01": vals.get("6.01"),
            "inv_6.02": vals.get("6.02"),
            "fin_6.03": vals.get("6.03"),
            "soma": soma,
            "declarado_6.05": total,
            "diferenca": (soma - total) if total is not None else None,
        })

    if not linhas:
        print("  Sem dados.")
        return

    df = pd.DataFrame(linhas).sort_values("ano")
    exibir = df.copy()
    for c in exibir.columns:
        if c != "ano":
            exibir[c] = (exibir[c] / 1e6).round(1)

    print(exibir.to_string(index=False))
    print("\n(valores em R$ milhoes)")

    ruim = df[df["diferenca"].abs() > 1_000_000]
    if ruim.empty:
        print(
            "\n  [ok] A DFC fecha em todos os anos. A extracao esta correta.\n"
            "       Se o valor ainda parecer atipico, e um evento real da\n"
            "       empresa e deve ser investigado nas Notas Explicativas."
        )
    else:
        print(f"\n  [!] A DFC NAO fecha em {len(ruim)} ano(s). Investigar extracao.")


# ---------------------------------------------------------------
def contexto(dados: dict) -> None:
    """Razao FCO/Receita de todas as empresas, para dar referencia."""
    print("\n" + "=" * 78)
    print("CONTEXTO | FCO COMO % DA RECEITA (todas as empresas)")
    print("=" * 78)
    print(
        "\nFaixa tipica de operadoras de fibra: 25% a 55%.\n"
        "Valores fora disso merecem verificacao.\n"
    )
    print(
        "  Consulte no banco:\n"
        "    SELECT empresa, ano,\n"
        "           ROUND(fluxo_caixa_operacional * 100.0 / receita_liquida, 1)\n"
        "               AS fco_sobre_receita_pct\n"
        "    FROM financial_data\n"
        "    ORDER BY empresa, ano;"
    )


# ---------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(
        description="Diagnostica anomalias no Fluxo de Caixa Operacional."
    )
    ap.add_argument("--empresa", default="Desktop", help="Grupo a investigar.")
    ap.add_argument(
        "--anos", nargs="+", type=int, default=[2021, 2022],
        help="Anos suspeitos para inspecao detalhada.",
    )
    args = ap.parse_args()

    print("=" * 78)
    print("DIAGNOSTICO DO FLUXO DE CAIXA OPERACIONAL")
    print(f"Empresa: {args.empresa} | Anos suspeitos: {args.anos}")
    print("=" * 78)
    print(f"Lendo de: {DIR_RAW}")

    # le um ano a mais, para captar o PENULTIMO do ultimo exercicio
    anos_leitura = sorted(set(ANOS) | {max(ANOS) + 1})

    dados = {}
    for ano in anos_leitura:
        df = ler_dfc(ano)
        dados[ano] = df
        if not df.empty:
            print(f"  {ano} | {len(df):5d} linhas")

    if all(d.empty for d in dados.values()):
        sys.exit(f"\nERRO: nenhum dado lido. Confira {DIR_RAW}")

    reap = teste_reapresentacao(dados, args.empresa)
    teste_estrutura(dados, args.empresa, args.anos)
    teste_fechamento(dados, args.empresa)
    contexto(dados)

    if not reap.empty:
        destino = DIR_EXPORTS / f"diagnostico_dfc_{args.empresa.lower()}.csv"
        reap.to_csv(destino, index=False, sep=";", decimal=",", encoding="utf-8-sig")
        print(f"\n  Salvo: {destino.relative_to(RAIZ)}")

    print("\n" + "=" * 78)
    print("DIAGNOSTICO CONCLUIDO")
    print("=" * 78)


if __name__ == "__main__":
    main()