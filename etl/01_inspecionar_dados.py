import pandas as pd
import os

# Obtém o diretório do script atual
base_dir = os.path.dirname(os.path.abspath(__file__))
arquivo = os.path.join(base_dir, "../data/raw/2025/dfp_cia_aberta_DRE_con_2025.csv")

# Verifica se o arquivo existe
if not os.path.exists(arquivo):
    print(f"Arquivo não encontrado: {arquivo}")
else:
    df = pd.read_csv(
        arquivo,
        sep=";",
        encoding="latin1"
    )

    print(df.columns.tolist())
    print("\nTotal de empresas:", df["DENOM_CIA"].nunique())

    

empresas = df[
    df["DENOM_CIA"].str.contains(
        "BRISANET|UNIFIQUE|DESKTOP",
        case=False,
        na=False
    )
]["DENOM_CIA"].unique()

print(empresas)