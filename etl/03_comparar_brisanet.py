# -*- coding: utf-8 -*-
"""
etl/03_comparar_brisanet.py

Projeto Integrador III - Fatec Cotia
Analise financeira de operadoras regionais de telecomunicacoes (CVM)

CONTEXTO
--------
O grupo Brisanet possui DUAS entidades registradas na CVM:

  Brisanet Participacoes S.A.              CNPJ 19.796.586/0001-70  CD_CVM 026085
  Brisanet Servicos de Telecomunicacoes    CNPJ 04.601.397/0001-28  CD_CVM 027693

A Participacoes (holding) foi INCORPORADA pela Servicos (operacional), com
eficacia em 04/12/2024. A partir dai, a Servicos e a companhia listada (BRST3)
e sucessora legal da Participacoes.

Como as duas entidades reportaram DFP no mesmo periodo (sobreposicao), e
necessario montar uma SERIE ENCADEADA e justificar metodologicamente a
transicao.

OBJETIVO DESTE SCRIPT
---------------------
1) Extrair os 6 indicadores para AMBAS as entidades Brisanet, ano a ano.
2) Comparar os valores nos anos em que as duas reportaram (sobreposicao).
3) Calcular a divergencia percentual entre elas.
4) Recomendar o ponto de corte da serie encadeada.

Este script NAO grava no banco. E uma analise de decisao metodologica,
cujo resultado deve ser documentado no relatorio da Sprint 2.

COMO RODAR
----------
  python etl/03_comparar_brisanet.py
"""

from pathlib import Path
import sys
import pandas as pd

# ---------------------------------------------------------------
# CAMINHOS
# ---------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_EXPORTS = RAIZ / "data" / "exports"
DIR_EXPORTS.mkdir(parents=True, exist_ok=True)

# Periodo ampliado: os dados incluem 2020 (exercicio pre-IPO)
ANOS = [2020, 2021, 2022, 2023, 2024, 2025]

CSV_KWARGS = dict(sep=";", encoding="latin1", dtype=str)

# ---------------------------------------------------------------
# ENTIDADES BRISANET (identificadas pelo CD_CVM, nao pelo nome)
# ---------------------------------------------------------------
BRISANET = {
    "026085": "Brisanet Participacoes",
    "027693": "Brisanet Servicos",
}

# ---------------------------------------------------------------
# CONTAS CONFIRMADAS NA ETAPA ANTERIOR
# ---------------------------------------------------------------
INDICADORES = {
    "receita_liquida":         ("DRE",    "3.01"),
    "lucro_liquido":           ("DRE",    "3.11"),
    "ativo_total":             ("BPA",    "1"),
    "passivo_total":           ("BPP",    "2"),
    "patrimonio_liquido":      ("BPP",    "2.03"),
    "fluxo_caixa_operacional": ("DFC_MI", "6.01"),
}

ESCALA = {"UNIDADE": 1, "MIL": 1_000, "MILHAO": 1_000_000}


# ---------------------------------------------------------------
def caminho(demonstracao: str, ano: int) -> Path:
    """Aceita CSVs em data/raw/<ano>/ ou soltos em data/raw/."""
    nome = f"dfp_cia_aberta_{demonstracao}_con_{ano}.csv"
    for c in (DIR_RAW / str(ano) / nome, DIR_RAW / nome):
        if c.exists():
            return c
    return DIR_RAW / str(ano) / nome


def normalizar_cvm(serie: pd.Series) -> pd.Series:
    """CD_CVM vem com zeros a esquerda inconsistentes entre arquivos."""
    return serie.astype(str).str.strip().str.zfill(6)


def extrair(demonstracao: str, ano: int, codigo: str, indicador: str) -> pd.DataFrame:
    """Le um arquivo e devolve o valor da conta para as entidades Brisanet."""
    arq = caminho(demonstracao, ano)
    if not arq.exists():
        return pd.DataFrame()

    df = pd.read_csv(arq, **CSV_KWARGS)
    df["CD_CVM"] = normalizar_cvm(df["CD_CVM"])

    # apenas as duas entidades Brisanet
    df = df[df["CD_CVM"].isin(BRISANET)].copy()
    if df.empty:
        return pd.DataFrame()

    # apenas o exercicio de referencia do arquivo
    if "ORDEM_EXERC" in df.columns:
        df = df[df["ORDEM_EXERC"].str.strip().str.upper().str.startswith("\u00da")]

    # a conta especifica
    df = df[df["CD_CONTA"].str.strip() == codigo].copy()
    if df.empty:
        return pd.DataFrame()

    # reapresentacoes: fica a maior VERSAO
    df["VERSAO"] = pd.to_numeric(df["VERSAO"], errors="coerce").fillna(0)
    df = df.sort_values("VERSAO").drop_duplicates(subset=["CD_CVM"], keep="last")

    # valor com escala aplicada
    valor = pd.to_numeric(
        df["VL_CONTA"].astype(str).str.strip().str.replace(",", ".", regex=False),
        errors="coerce",
    )
    fator = df["ESCALA_MOEDA"].str.upper().str.strip().map(ESCALA).fillna(1)

    return pd.DataFrame({
        "entidade": df["CD_CVM"].map(BRISANET).values,
        "cd_cvm": df["CD_CVM"].values,
        "ano": ano,
        "indicador": indicador,
        "valor": (valor * fator).values,
    })


# ---------------------------------------------------------------
def coletar() -> pd.DataFrame:
    print("=" * 78)
    print("COMPARACAO DAS ENTIDADES BRISANET NA CVM")
    print("Projeto Integrador III | Sprint 2")
    print("=" * 78)

    partes = []
    for indicador, (dem, codigo) in INDICADORES.items():
        for ano in ANOS:
            r = extrair(dem, ano, codigo, indicador)
            if not r.empty:
                partes.append(r)

    if not partes:
        sys.exit(f"\nERRO: nenhum dado lido. Confira os CSVs em {DIR_RAW}")

    return pd.concat(partes, ignore_index=True)


def mostrar_cobertura(df: pd.DataFrame) -> list:
    print("\n" + "-" * 78)
    print("COBERTURA POR ENTIDADE E ANO")
    print("-" * 78)

    cob = (
        df.pivot_table(
            index="ano", columns="entidade", values="indicador",
            aggfunc="count", fill_value=0,
        )
    )
    print(cob.to_string())
    print("\n(numero de indicadores encontrados; o esperado e 6 por ano)")

    # anos em que AMBAS reportaram
    sobrepostos = [
        int(ano) for ano, linha in cob.iterrows()
        if (linha > 0).all() and len(cob.columns) > 1
    ]

    if sobrepostos:
        print(f"\n  [!] Anos com sobreposicao das duas entidades: {sobrepostos}")
    else:
        print("\n  [ok] Nenhum ano com sobreposicao.")

    return sobrepostos


def comparar(df: pd.DataFrame, anos: list) -> pd.DataFrame:
    if not anos:
        return pd.DataFrame()

    print("\n" + "=" * 78)
    print("COMPARACAO NOS ANOS DE SOBREPOSICAO")
    print("=" * 78)

    sub = df[df["ano"].isin(anos)]
    pivot = sub.pivot_table(
        index=["ano", "indicador"], columns="entidade", values="valor"
    ).reset_index()

    col_p = "Brisanet Participacoes"
    col_s = "Brisanet Servicos"

    if col_p not in pivot.columns or col_s not in pivot.columns:
        print("Nao foi possivel comparar: falta uma das entidades.")
        return pd.DataFrame()

    pivot["diferenca"] = pivot[col_s] - pivot[col_p]
    pivot["divergencia_%"] = (
        pivot["diferenca"] / pivot[col_p].replace(0, pd.NA) * 100
    )

    exibir = pivot.copy()
    for c in (col_p, col_s, "diferenca"):
        exibir[c] = (exibir[c] / 1_000_000).round(1)
    exibir["divergencia_%"] = exibir["divergencia_%"].round(2)
    exibir = exibir.rename(columns={
        col_p: "Participacoes (R$ mi)",
        col_s: "Servicos (R$ mi)",
        "diferenca": "Dif. (R$ mi)",
    })

    print()
    print(exibir.to_string(index=False))

    return pivot


def recomendar(pivot: pd.DataFrame, df: pd.DataFrame) -> None:
    print("\n" + "=" * 78)
    print("RECOMENDACAO METODOLOGICA")
    print("=" * 78)

    anos_p = sorted(df[df["entidade"] == "Brisanet Participacoes"]["ano"].unique())
    anos_s = sorted(df[df["entidade"] == "Brisanet Servicos"]["ano"].unique())

    print(f"\nParticipacoes reporta em: {anos_p}")
    print(f"Servicos reporta em:      {anos_s}")

    if not pivot.empty:
        div = pivot["divergencia_%"].abs().dropna()
        if not div.empty:
            print(f"\nDivergencia media absoluta: {div.mean():.2f}%")
            print(f"Divergencia maxima:         {div.max():.2f}%")

            if div.max() < 5:
                print(
                    "\n  [ok] Divergencia baixa (<5%). As series sao praticamente\n"
                    "       equivalentes, o que era esperado: a Participacoes era\n"
                    "       holding cujo ativo relevante era a propria Servicos.\n"
                    "       O encadeamento da serie e defensavel."
                )
            else:
                print(
                    "\n  [!] Divergencia relevante (>5%). Verifique indicador a\n"
                    "      indicador antes de encadear. Pode haver itens que so\n"
                    "      existiam no nivel da holding (ex.: divida de aquisicao)."
                )

    print(
        "\nCRITERIO SUGERIDO PARA A SERIE ENCADEADA 'Brisanet':\n"
        "  - ate 2023  -> Brisanet Participacoes (CD_CVM 026085)\n"
        "  - de 2024   -> Brisanet Servicos      (CD_CVM 027693)\n"
        "\nJustificativa: a incorporacao teve eficacia em 04/12/2024, quando as\n"
        "acoes BRIT3 deixaram de ser negociadas e a Servicos passou a ser a\n"
        "companhia listada (BRST3), sucessora legal da Participacoes.\n"
        "\nIMPORTANTE: registre esta decisao no relatorio da Sprint 2 e adicione\n"
        "uma nota nos graficos indicando a quebra de entidade em 2024."
    )

    destino = DIR_EXPORTS / "comparacao_brisanet.csv"
    if not pivot.empty:
        pivot.to_csv(destino, index=False, sep=";", encoding="utf-8-sig", decimal=",")
        print(f"\n  Salvo: {destino.relative_to(RAIZ)}")

    serie = DIR_EXPORTS / "brisanet_series_por_entidade.csv"
    df.sort_values(["indicador", "ano", "entidade"]).to_csv(
        serie, index=False, sep=";", encoding="utf-8-sig", decimal=","
    )
    print(f"  Salvo: {serie.relative_to(RAIZ)}")


# ---------------------------------------------------------------
def main() -> None:
    df = coletar()
    anos = mostrar_cobertura(df)
    pivot = comparar(df, anos)
    recomendar(pivot, df)

    print("\n" + "=" * 78)
    print("CONCLUIDO. Revise data/exports/comparacao_brisanet.csv")
    print("=" * 78)


if __name__ == "__main__":
    main()