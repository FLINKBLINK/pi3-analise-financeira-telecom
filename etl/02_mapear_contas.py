# -*- coding: utf-8 -*-
"""
etl/02_mapear_contas.py

Projeto Integrador III - Fatec Cotia
Analise financeira de operadoras regionais de telecomunicacoes (CVM)

OBJETIVO
--------
Este script NAO trata nem carrega dados. Ele apenas INSPECIONA os CSVs brutos
da CVM para responder duas perguntas que definem todo o ETL da Sprint 2:

  1) Quais entidades de cada grupo economico aparecem em cada ano?
     (para detectar, por exemplo, holding + operacional da Brisanet)

  2) Quais sao os codigos de conta (CD_CONTA) reais de cada indicador,
     para cada empresa e cada ano?

SAIDA
-----
  data/exports/entidades_por_ano.csv   -> auditoria das razoes sociais
  data/exports/mapa_contas.csv         -> todas as contas candidatas
  data/exports/mapa_contas_sugerido.csv-> a conta escolhida por indicador

COMO RODAR
----------
  python etl/02_mapear_contas.py
"""

from pathlib import Path
import sys
import pandas as pd

# ---------------------------------------------------------------
# CAMINHOS - funcionam independente de onde voce rodar o script
# ---------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
DIR_RAW = RAIZ / "data" / "raw"
DIR_EXPORTS = RAIZ / "data" / "exports"
DIR_EXPORTS.mkdir(parents=True, exist_ok=True)

ANOS = [2020, 2021, 2022, 2023, 2024, 2025]

DEMONSTRACOES = ["DRE", "BPA", "BPP", "DFC_MI"]

# Termos usados para localizar as empresas em DENOM_CIA
GRUPOS = ["BRISANET", "UNIFIQUE", "DESKTOP"]

CSV_KWARGS = dict(sep=";", encoding="latin1", dtype=str)

# ---------------------------------------------------------------
# INDICADORES QUE PRECISAMOS LOCALIZAR
# Para cada um: em qual demonstracao procurar, o codigo esperado
# e palavras-chave para busca textual em DS_CONTA.
# ---------------------------------------------------------------
INDICADORES = {
    "receita_liquida": {
        "demonstracao": "DRE",
        "codigo_esperado": "3.01",
        "palavras": ["receita"],
    },
    "lucro_liquido": {
        "demonstracao": "DRE",
        "codigo_esperado": "3.11",
        "palavras": ["lucro", "prejuizo", "prejuízo", "resultado l"],
    },
    "ativo_total": {
        "demonstracao": "BPA",
        "codigo_esperado": "1",
        "palavras": ["ativo total"],
    },
    "passivo_total": {
        "demonstracao": "BPP",
        "codigo_esperado": "2",
        "palavras": ["passivo total"],
    },
    "patrimonio_liquido": {
        "demonstracao": "BPP",
        "codigo_esperado": "2.03",
        "palavras": ["patrim"],
    },
    "fluxo_caixa_operacional": {
        "demonstracao": "DFC_MI",
        "codigo_esperado": "6.01",
        "palavras": ["operacion"],
    },
}


# ---------------------------------------------------------------
# LEITURA
# ---------------------------------------------------------------
def caminho_arquivo(demonstracao: str, ano: int) -> Path:
    """Procura o CSV em data/raw/<ano>/ e, como alternativa, em data/raw/."""
    nome = f"dfp_cia_aberta_{demonstracao}_con_{ano}.csv"
    candidatos = [DIR_RAW / str(ano) / nome, DIR_RAW / nome]
    for c in candidatos:
        if c.exists():
            return c
    return candidatos[0]  # retorna o esperado, para a mensagem de erro


def ler(demonstracao: str, ano: int) -> pd.DataFrame:
    """Le um CSV da CVM e devolve apenas as linhas dos grupos analisados."""
    caminho = caminho_arquivo(demonstracao, ano)

    if not caminho.exists():
        print(f"  [AUSENTE] {caminho.relative_to(RAIZ)}")
        return pd.DataFrame()

    df = pd.read_csv(caminho, **CSV_KWARGS)

    padrao = "|".join(GRUPOS)
    df = df[df["DENOM_CIA"].str.contains(padrao, case=False, na=False)].copy()

    df["ano_arquivo"] = ano
    df["demonstracao"] = demonstracao
    return df


def grupo_da_empresa(denom: str) -> str:
    """Reduz a razao social ao nome do grupo (Brisanet / Unifique / Desktop)."""
    alvo = str(denom).upper()
    for g in GRUPOS:
        if g in alvo:
            return g.capitalize()
    return "?"


# ---------------------------------------------------------------
# ETAPA 1 - AUDITORIA DAS ENTIDADES
# ---------------------------------------------------------------
def auditar_entidades(dados: dict) -> pd.DataFrame:
    print("\n" + "=" * 74)
    print("ETAPA 1 | ENTIDADES ENCONTRADAS POR ANO")
    print("=" * 74)

    linhas = []
    for (dem, ano), df in dados.items():
        if df.empty:
            continue
        sub = df[["DENOM_CIA", "CNPJ_CIA", "CD_CVM"]].drop_duplicates()
        for _, r in sub.iterrows():
            linhas.append({
                "demonstracao": dem,
                "ano": ano,
                "grupo": grupo_da_empresa(r["DENOM_CIA"]),
                "denom_cia": r["DENOM_CIA"],
                "cnpj_cia": r["CNPJ_CIA"],
                "cd_cvm": r["CD_CVM"],
            })

    if not linhas:
        print("Nenhuma entidade encontrada. Verifique a pasta data/raw/.")
        return pd.DataFrame()

    ent = pd.DataFrame(linhas)

    # Uma linha por grupo/entidade, mostrando em quais anos aparece
    resumo = (
        ent.groupby(["grupo", "denom_cia", "cnpj_cia", "cd_cvm"])["ano"]
           .agg(lambda s: ", ".join(map(str, sorted(set(s)))))
           .reset_index()
           .rename(columns={"ano": "anos_em_que_aparece"})
           .sort_values(["grupo", "denom_cia"])
    )

    print(resumo.to_string(index=False))

    # ALERTA: mais de uma entidade no mesmo grupo = risco de duplicidade
    print("\n" + "-" * 74)
    for grupo, bloco in resumo.groupby("grupo"):
        n = bloco["cd_cvm"].nunique()
        if n > 1:
            print(f"  [!] ATENCAO | {grupo}: {n} entidades distintas na CVM.")
            print("      Voce precisa escolher UMA (normalmente a de maior")
            print("      Ativo Total, que e a consolidadora do grupo).")
        else:
            print(f"  [ok] {grupo}: entidade unica (CD_CVM {bloco['cd_cvm'].iloc[0]}).")

    destino = DIR_EXPORTS / "entidades_por_ano.csv"
    resumo.to_csv(destino, index=False, sep=";", encoding="utf-8-sig")
    print(f"\n  Salvo: {destino.relative_to(RAIZ)}")
    return resumo


# ---------------------------------------------------------------
# ETAPA 2 - MAPEAMENTO DAS CONTAS
# ---------------------------------------------------------------
def mapear_contas(dados: dict) -> pd.DataFrame:
    print("\n" + "=" * 74)
    print("ETAPA 2 | CONTAS CANDIDATAS POR INDICADOR")
    print("=" * 74)

    registros = []

    for indicador, cfg in INDICADORES.items():
        dem = cfg["demonstracao"]
        codigo = cfg["codigo_esperado"]
        palavras = cfg["palavras"]

        print(f"\n### {indicador.upper()}  (esperado: {dem} / conta {codigo})")

        partes = [df for (d, _a), df in dados.items() if d == dem and not df.empty]
        if not partes:
            print("  Sem dados para esta demonstracao.")
            continue

        df = pd.concat(partes, ignore_index=True)

        # apenas o exercicio de referencia, para nao poluir a inspecao
        if "ORDEM_EXERC" in df.columns:
            df = df[df["ORDEM_EXERC"].str.strip().str.upper().str.startswith("Ú")]

        df["grupo"] = df["DENOM_CIA"].map(grupo_da_empresa)
        df["CD_CONTA"] = df["CD_CONTA"].str.strip()
        df["DS_CONTA"] = df["DS_CONTA"].str.strip()

        # candidatos: bate o codigo exato OU contem alguma palavra-chave
        por_codigo = df["CD_CONTA"] == codigo
        por_texto = df["DS_CONTA"].str.lower().apply(
            lambda s: any(p in s for p in palavras)
        )
        cand = df[por_codigo | por_texto]

        if cand.empty:
            print("  [!] Nenhuma conta candidata encontrada.")
            continue

        resumo = (
            cand.groupby(["grupo", "CD_CONTA", "DS_CONTA"])
                .agg(
                    anos=("ano_arquivo", lambda s: ", ".join(map(str, sorted(set(s))))),
                    ocorrencias=("CD_CONTA", "size"),
                )
                .reset_index()
                .sort_values(["grupo", "CD_CONTA"])
        )
        resumo["indicador"] = indicador
        resumo["codigo_esperado"] = codigo
        resumo["bate_codigo_esperado"] = resumo["CD_CONTA"] == codigo

        # imprime so o essencial no terminal
        for grupo, bloco in resumo.groupby("grupo"):
            exato = bloco[bloco["bate_codigo_esperado"]]
            if not exato.empty:
                r = exato.iloc[0]
                print(f"  [ok] {grupo:9s} | {r['CD_CONTA']:6s} | {r['DS_CONTA'][:45]:45s} | anos {r['anos']}")
            else:
                print(f"  [!]  {grupo:9s} | conta {codigo} NAO existe. Candidatas por texto:")
                for _, r in bloco.head(6).iterrows():
                    print(f"         {r['CD_CONTA']:8s} | {r['DS_CONTA'][:55]}")

        registros.append(resumo)

    if not registros:
        return pd.DataFrame()

    mapa = pd.concat(registros, ignore_index=True)
    mapa = mapa[[
        "indicador", "grupo", "CD_CONTA", "DS_CONTA",
        "codigo_esperado", "bate_codigo_esperado", "anos", "ocorrencias",
    ]]

    destino = DIR_EXPORTS / "mapa_contas.csv"
    mapa.to_csv(destino, index=False, sep=";", encoding="utf-8-sig")
    print(f"\n  Salvo: {destino.relative_to(RAIZ)}")
    return mapa


# ---------------------------------------------------------------
# ETAPA 3 - SUGESTAO FINAL
# ---------------------------------------------------------------
def sugerir(mapa: pd.DataFrame) -> None:
    print("\n" + "=" * 74)
    print("ETAPA 3 | MAPEAMENTO SUGERIDO PARA O ETL")
    print("=" * 74)

    if mapa.empty:
        print("Sem dados para sugerir.")
        return

    # prioriza a conta que bate com o codigo esperado
    escolhidas = (
        mapa.sort_values(["indicador", "grupo", "bate_codigo_esperado"])
            .groupby(["indicador", "grupo"])
            .tail(1)
    )

    tabela = escolhidas[escolhidas["bate_codigo_esperado"]]
    faltando = escolhidas[~escolhidas["bate_codigo_esperado"]]

    if not tabela.empty:
        print("\nConfirmados:")
        print(
            tabela[["indicador", "grupo", "CD_CONTA", "DS_CONTA"]]
            .to_string(index=False)
        )

    if not faltando.empty:
        print("\n[!] Precisam de decisao manual:")
        print(
            faltando[["indicador", "grupo", "CD_CONTA", "DS_CONTA"]]
            .to_string(index=False)
        )

    destino = DIR_EXPORTS / "mapa_contas_sugerido.csv"
    escolhidas.to_csv(destino, index=False, sep=";", encoding="utf-8-sig")
    print(f"\n  Salvo: {destino.relative_to(RAIZ)}")


# ---------------------------------------------------------------
def main() -> None:
    print("=" * 74)
    print("MAPEAMENTO DE ENTIDADES E CONTAS CONTABEIS - CVM")
    print("Projeto Integrador III | Brisanet, Unifique, Desktop")
    print("=" * 74)
    print(f"Lendo de: {DIR_RAW}")

    dados = {}
    for dem in DEMONSTRACOES:
        print(f"\n[{dem}]")
        for ano in ANOS:
            df = ler(dem, ano)
            if not df.empty:
                grupos = ", ".join(sorted(df["DENOM_CIA"].map(grupo_da_empresa).unique()))
                print(f"  {ano} | {len(df):5d} linhas | {grupos}")
            dados[(dem, ano)] = df

    if all(df.empty for df in dados.values()):
        sys.exit(
            "\nERRO: nenhum dado lido.\n"
            f"Confira se os CSVs estao em {DIR_RAW} "
            "(direto na pasta ou em subpastas por ano)."
        )

    auditar_entidades(dados)
    mapa = mapear_contas(dados)
    sugerir(mapa)

    print("\n" + "=" * 74)
    print("CONCLUIDO. Revise os arquivos em data/exports/ antes do ETL.")
    print("=" * 74)


if __name__ == "__main__":
    main()