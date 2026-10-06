# -*- coding: utf-8 -*-
"""
etl/00_baixar_dados_cvm.py

Projeto Integrador III - Fatec Cotia
Obtem os CSVs da CVM usados no projeto e os coloca em data/raw/<ano>/.

POR QUE EXISTE
--------------
data/raw/ fica fora do GitHub (cada arquivo da CVM tem de 6 a 22 MB). Sem
este script, quem clona o repositorio nao consegue reconstruir o banco.
Ele tambem registra ORIGEM, DATA e HASH de cada arquivo (metadados de
coleta exigidos na Sprint 1) em data/exports/coleta_cvm.csv.

DUAS FORMAS DE USO
------------------
  1) Baixar direto do Portal de Dados Abertos da CVM:
       python etl/00_baixar_dados_cvm.py

  2) Usar ZIPs que voce ja baixou (ex.: a pasta "Bases de dados"):
       python etl/00_baixar_dados_cvm.py --de-pasta "caminho/para/Bases de dados"

ATENCAO: a CVM republica os ZIPs quando alguma companhia reapresenta a DFP.
Baixar de novo pode trazer versoes mais novas; o ETL ja fica com a maior
VERSAO, mas os numeros podem mudar. Guarde o coleta_cvm.csv no Git.
"""

import argparse
import hashlib
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd

from config import ANOS, DEMONSTRACOES, DIR_EXPORTS, DIR_RAW, PADRAO_ARQUIVO, RAIZ

URL = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/DFP/DADOS/dfp_cia_aberta_{ano}.zip"
DIR_ZIPS = DIR_RAW / "_zips"


def baixar(ano: int) -> Path:
    """Baixa o ZIP do ano (requests, se instalado; senao urllib)."""
    url = URL.format(ano=ano)
    destino = DIR_ZIPS / f"dfp_cia_aberta_{ano}.zip"
    DIR_ZIPS.mkdir(parents=True, exist_ok=True)
    print(f"  {ano} | baixando {url}")
    try:
        import requests  # vem instalado junto com o streamlit
        with requests.get(url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(destino, "wb") as f:
                for bloco in r.iter_content(chunk_size=1 << 20):
                    f.write(bloco)
    except ImportError:
        from urllib.request import urlopen
        with urlopen(url, timeout=120) as r, open(destino, "wb") as f:
            shutil.copyfileobj(r, f)
    return destino


def extrair(zip_path: Path, ano: int, origem: str) -> list:
    """Extrai so os 4 CSVs consolidados usados pelo projeto."""
    pasta = DIR_RAW / str(ano)
    pasta.mkdir(parents=True, exist_ok=True)
    # data do ZIP = data do download (quando veio de uma pasta local, e a
    # data em que voce baixou o arquivo no seu computador)
    data_zip = datetime.fromtimestamp(zip_path.stat().st_mtime).isoformat(timespec="seconds")
    registros = []
    with zipfile.ZipFile(zip_path) as z:
        nomes = {Path(n).name: n for n in z.namelist()}
        for dem in DEMONSTRACOES:
            nome = PADRAO_ARQUIVO.format(demonstracao=dem, ano=ano)
            if nome not in nomes:
                print(f"  [!] {ano} | {nome} nao esta no ZIP")
                continue
            conteudo = z.read(nomes[nome])
            (pasta / nome).write_bytes(conteudo)
            registros.append({
                "ano": ano,
                "arquivo": nome,
                "origem": origem,
                "data_do_zip": data_zip,
                "extraido_em": datetime.now().isoformat(timespec="seconds"),
                "bytes": len(conteudo),
                "sha256": hashlib.sha256(conteudo).hexdigest(),
            })
    print(f"  {ano} | {len(registros)} arquivos em {pasta.relative_to(RAIZ)}")
    return registros


def main() -> None:
    ap = argparse.ArgumentParser(description="Obtem os CSVs da CVM (DFP).")
    ap.add_argument("--de-pasta", type=Path, default=None,
                    help="Pasta com os ZIPs dfp_cia_aberta_<ano>.zip ja baixados.")
    args = ap.parse_args()

    print("=" * 70)
    print("COLETA DOS DADOS DA CVM (DFP)")
    print("=" * 70)

    registros = []
    for ano in ANOS:
        if args.de_pasta:
            zip_path = args.de_pasta / f"dfp_cia_aberta_{ano}.zip"
            if not zip_path.exists():
                print(f"  [!] {ano} | nao encontrado: {zip_path}")
                continue
            origem = f"pasta local: {zip_path.name}"
        else:
            try:
                zip_path = baixar(ano)
            except Exception as erro:  # rede, SSL, URL alterada...
                print(f"  [!] {ano} | falha no download: {erro}")
                continue
            origem = URL.format(ano=ano)
        registros.extend(extrair(zip_path, ano, origem))

    if not registros:
        sys.exit("\nNenhum arquivo obtido. Confira a conexao ou o caminho informado.")

    destino = DIR_EXPORTS / "coleta_cvm.csv"
    pd.DataFrame(registros).to_csv(destino, index=False, sep=";", encoding="utf-8-sig")
    print(f"\n  Registro da coleta: {destino.relative_to(RAIZ)}")
    print("  Proximo passo: python etl/rodar_pipeline.py")


if __name__ == "__main__":
    main()
