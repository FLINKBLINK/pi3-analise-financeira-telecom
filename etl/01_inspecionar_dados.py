# -*- coding: utf-8 -*-
"""
etl/01_inspecionar_dados.py

Projeto Integrador III - Fatec Cotia
Inspecao inicial da estrutura de um arquivo da CVM.

CORRECAO (revisao Sprint 3)
---------------------------
A versao anterior quebrava com NameError quando o arquivo nao existia:
o filtro das empresas ficava FORA do bloco "else" e usava a variavel
"df", que nunca tinha sido criada. Agora o script encerra com uma
mensagem clara.

COMO RODAR
----------
  python etl/01_inspecionar_dados.py              (DRE do ultimo ano)
  python etl/01_inspecionar_dados.py BPP 2023     (outra demonstracao/ano)
"""

import sys

import pandas as pd

from config import ANOS, CSV_KWARGS, RAIZ, caminho_arquivo

GRUPOS = "BRISANET|UNIFIQUE|DESKTOP"


def main() -> None:
    demonstracao = sys.argv[1] if len(sys.argv) > 1 else "DRE"
    ano = int(sys.argv[2]) if len(sys.argv) > 2 else max(ANOS)

    arquivo = caminho_arquivo(demonstracao, ano)
    if not arquivo.exists():
        sys.exit(
            f"Arquivo nao encontrado: {arquivo.relative_to(RAIZ)}\n"
            "Coloque os CSVs da CVM em data/raw/<ano>/ (veja o README)."
        )

    df = pd.read_csv(arquivo, **CSV_KWARGS)

    print(f"Arquivo: {arquivo.relative_to(RAIZ)}")
    print(f"Linhas: {len(df):,}".replace(",", "."))
    print("Colunas:", df.columns.tolist())
    print("\nTotal de empresas:", df["DENOM_CIA"].nunique())

    empresas = (
        df[df["DENOM_CIA"].str.contains(GRUPOS, case=False, na=False)]
        [["DENOM_CIA", "CD_CVM", "CNPJ_CIA", "VERSAO"]]
        .drop_duplicates()
        .sort_values("DENOM_CIA")
    )
    print("\nEmpresas do projeto encontradas:")
    print(empresas.to_string(index=False))


if __name__ == "__main__":
    main()
