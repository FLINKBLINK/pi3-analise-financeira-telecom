# -*- coding: utf-8 -*-
"""
etl/rodar_pipeline.py

Projeto Integrador III - Fatec Cotia
Executa o pipeline completo, na ordem certa, parando no primeiro erro.

  04_criar_banco   -> estrutura do banco (e migracao de bancos antigos)
  05_carga         -> CSVs da CVM -> camada raw -> financial_data
  06_eda           -> graficos e tabelas descritivas (Sprint 2)
  07_diagnostico_dfc -> fechamento da DFC e valor atipico da Desktop
  08_indicadores   -> indicadores financeiros (Sprint 3)
  09_graficos_sprint3 -> figuras do relatorio da Sprint 3

Com --inspecao, roda antes os scripts de verificacao 02 e 03.

Cada etapa roda em um processo separado (cada script configura o proprio
log). Pre-requisito: CSVs da CVM em data/raw/<ano>/ (veja o README).

COMO RODAR
----------
  python etl/rodar_pipeline.py
  python etl/rodar_pipeline.py --inspecao
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

PASTA = Path(__file__).resolve().parent

ETAPAS = [
    "04_criar_banco.py",
    "05_carga.py",
    "06_eda.py",
    "07_diagnostico_dfc.py",
    "08_indicadores.py",
    "09_graficos_sprint3.py",
]
INSPECAO = ["02_mapear_contas.py", "03_comparar_brisanet.py"]


def main() -> None:
    ap = argparse.ArgumentParser(description="Roda o pipeline completo do projeto.")
    ap.add_argument("--inspecao", action="store_true",
                    help="Roda antes os scripts de verificacao (02 e 03).")
    args = ap.parse_args()

    etapas = (INSPECAO if args.inspecao else []) + ETAPAS
    inicio = time.time()

    for script in etapas:
        print("\n" + "#" * 78)
        print(f"# {script}")
        print("#" * 78, flush=True)
        retorno = subprocess.run([sys.executable, str(PASTA / script)], cwd=PASTA.parent)
        if retorno.returncode != 0:
            sys.exit(f"\nPipeline interrompido: {script} terminou com erro "
                     f"(codigo {retorno.returncode}).")

    print("\n" + "=" * 78)
    print(f"PIPELINE CONCLUIDO em {time.time() - inicio:.0f}s")
    print("Dashboard: streamlit run dashboard/app.py")
    print("=" * 78)


if __name__ == "__main__":
    main()
