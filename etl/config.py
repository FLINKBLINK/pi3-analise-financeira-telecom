# -*- coding: utf-8 -*-
"""
etl/config.py

Projeto Integrador III - Fatec Cotia
Analise financeira de operadoras regionais de telecomunicacoes (CVM)

Parametros centrais do projeto. Todo ajuste de escopo (anos, empresas,
contas contabeis) deve ser feito AQUI, nunca dentro dos scripts.
"""

from pathlib import Path

# ---------------------------------------------------------------
# 1. CAMINHOS
# ---------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent

DIR_RAW = RAIZ / "data" / "raw"
DIR_PROCESSED = RAIZ / "data" / "processed"
DIR_EXPORTS = RAIZ / "data" / "exports"
DIR_DATABASE = RAIZ / "database"
DIR_LOGS = RAIZ / "logs"

BANCO = DIR_DATABASE / "telecom.db"

for _d in (DIR_PROCESSED, DIR_EXPORTS, DIR_DATABASE, DIR_LOGS):
    _d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------
# 2. PERIODO ANALISADO
# ---------------------------------------------------------------
# 2020 incluido por ser o exercicio pre-IPO das companhias,
# o que permite avaliar o efeito da abertura de capital.
ANOS = [2020, 2021, 2022, 2023, 2024, 2025]

# ---------------------------------------------------------------
# 3. DEMONSTRACOES UTILIZADAS
# ---------------------------------------------------------------
DEMONSTRACOES = ["DRE", "BPA", "BPP", "DFC_MI"]

PADRAO_ARQUIVO = "dfp_cia_aberta_{demonstracao}_con_{ano}.csv"

# ---------------------------------------------------------------
# 4. EMPRESAS - identificadas por CD_CVM, nunca pelo nome
# ---------------------------------------------------------------
# O CD_CVM e o identificador estavel. Razoes sociais mudam.
ENTIDADES = {
    "026085": {
        "grupo": "Brisanet",
        "razao_social": "BRISANET PARTICIPACOES S.A.",
        "cnpj": "19.796.586/0001-70",
    },
    "027693": {
        "grupo": "Brisanet",
        "razao_social": "BRISANET SERVICOS DE TELECOMUNICACOES S.A.",
        "cnpj": "04.601.397/0001-28",
    },
    "026050": {
        "grupo": "Unifique",
        "razao_social": "UNIFIQUE TELECOMUNICACOES S.A.",
        "cnpj": "02.255.187/0001-08",
    },
    "026026": {
        "grupo": "Desktop",
        "razao_social": "DESKTOP S.A.",
        "cnpj": "08.170.849/0001-15",
    },
}

# ---------------------------------------------------------------
# 5. SERIE ENCADEADA - Brisanet
# ---------------------------------------------------------------
# A Brisanet Participacoes (holding) foi incorporada pela Brisanet
# Servicos (operacional), com eficacia em 04/12/2024. As acoes BRIT3
# deixaram de ser negociadas e a Servicos passou a ser a companhia
# listada (BRST3), sucessora legal da Participacoes.
#
# Em 2023 AMBAS reportaram DFP. A comparacao empirica mostrou:
#   receita_liquida    0,00% de divergencia
#   ativo_total       -0,03%
#   passivo_total     -0,03%
#   patrimonio_liq.    2,09%
#   fluxo_caixa_op.    2,94%
#   lucro_liquido      5,41%  (R$ 8,8 mi sobre base pequena)
#
# Conclusao: series equivalentes. O encadeamento e defensavel.
#
# Regra: para cada grupo, qual CD_CVM usar em cada ano.
ENCADEAMENTO = {
    "Brisanet": {
        2020: "026085",
        2021: "026085",
        2022: "026085",
        2023: "026085",   # ano de sobreposicao: fica a holding
        2024: "027693",   # incorporacao eficaz em 04/12/2024
        2025: "027693",
    },
    "Unifique": {ano: "026050" for ano in ANOS},
    "Desktop": {ano: "026026" for ano in ANOS},
}

# Ano da quebra de entidade - usado para anotar nos graficos
QUEBRA_ENTIDADE = {"Brisanet": 2024}

# ---------------------------------------------------------------
# 6. MAPEAMENTO DAS CONTAS CONTABEIS
# ---------------------------------------------------------------
# Confirmado empiricamente para as 3 empresas em todos os anos.
#
# ATENCAO sobre a conta "2" (Passivo Total):
# Na estrutura da CVM ela representa o TOTAL DO LADO DIREITO do
# balanco, ou seja, JA INCLUI o Patrimonio Liquido:
#
#     Ativo Total (1) == Passivo Total (2)
#
# Por isso ela serve apenas como VALIDACAO da extracao.
# O capital de terceiros deve ser calculado como:
#
#     passivo_circulante (2.01) + passivo_nao_circulante (2.02)
#
CONTAS = {
    # indicador                  demonstracao  codigo   obrigatorio
    "receita_liquida":          ("DRE",       "3.01",  True),
    "lucro_liquido":            ("DRE",       "3.11",  True),
    "ativo_total":              ("BPA",       "1",     True),
    "ativo_circulante":         ("BPA",       "1.01",  True),
    "passivo_total":            ("BPP",       "2",     True),
    "passivo_circulante":       ("BPP",       "2.01",  True),
    "passivo_nao_circulante":   ("BPP",       "2.02",  True),
    "patrimonio_liquido":       ("BPP",       "2.03",  True),
    "fluxo_caixa_operacional":  ("DFC_MI",    "6.01",  True),
}

# Ordem das colunas na tabela financial_data
ORDEM_INDICADORES = list(CONTAS.keys())

# ---------------------------------------------------------------
# 7. LEITURA DOS CSVs DA CVM
# ---------------------------------------------------------------
# NUNCA abra estes arquivos no Excel antes de processar: ele corrompe
# os valores numericos. Separador ";", encoding Latin-1.
CSV_KWARGS = dict(sep=";", encoding="latin1", dtype=str)

# Cada arquivo traz o exercicio de referencia (ULTIMO) e o anterior
# (PENULTIMO). Usar apenas ULTIMO evita duplicar anos entre arquivos.
ORDEM_EXERCICIO = "\u00daLTIMO"

ESCALA = {"UNIDADE": 1, "MIL": 1_000, "MILHAO": 1_000_000}

COLUNAS_UTEIS = [
    "CNPJ_CIA", "DT_REFER", "VERSAO", "DENOM_CIA", "CD_CVM",
    "MOEDA", "ESCALA_MOEDA", "ORDEM_EXERC",
    "DT_INI_EXERC", "DT_FIM_EXERC",
    "CD_CONTA", "DS_CONTA", "VL_CONTA", "ST_CONTA_FIXA",
]


# ---------------------------------------------------------------
# 8. UTILITARIOS
# ---------------------------------------------------------------
def normalizar_cvm(serie):
    """
    CD_CVM vem com zeros a esquerda inconsistentes entre arquivos
    da CVM (ex.: '26085' em um ano, '026085' em outro).
    Sem esta normalizacao o filtro falha silenciosamente.
    """
    return serie.astype(str).str.strip().str.zfill(6)


def caminho_arquivo(demonstracao: str, ano: int) -> Path:
    """Aceita CSVs em data/raw/<ano>/ ou soltos em data/raw/."""
    nome = PADRAO_ARQUIVO.format(demonstracao=demonstracao, ano=ano)
    for c in (DIR_RAW / str(ano) / nome, DIR_RAW / nome):
        if c.exists():
            return c
    return DIR_RAW / str(ano) / nome


def entidade_do_ano(grupo: str, ano: int):
    """Retorna o CD_CVM que deve ser usado para o grupo naquele ano."""
    return ENCADEAMENTO.get(grupo, {}).get(ano)