# Projeto Integrador III – Análise financeira de operadoras regionais de telecom

Fatec Cotia · Tecnologia em Ciência de Dados

Análise comparativa da situação financeira de **Brisanet, Desktop e Unifique**
(2020–2025) a partir das Demonstrações Financeiras Padronizadas (DFP)
consolidadas publicadas no Portal de Dados Abertos da CVM.

**Questão central (Sprint 2, seção 7.3):** por que, entre operadoras regionais de
fibra que abriram capital em julho de 2021 e cresceram a receita de forma
parecida, apenas uma sustentou a trajetória de rentabilidade?

---

## Arquitetura

```
CVM (CSV) → ETL Python (etl/) → SQLite (database/telecom.db) → Indicadores → Dashboard Streamlit (dashboard/)
```

```
├── .streamlit/config.toml      tema do dashboard (vai para o GitHub)
├── dashboard/
│   ├── app.py                  PONTO DE ENTRADA do Streamlit (filtros globais + navegação)
│   ├── dados.py                leitura do banco, metadados e formatação (padrão BR)
│   ├── visual.py               gráficos Plotly padronizados
│   └── paginas/                visão geral, indicadores, análise descritiva,
│                               hipóteses, dados e metodologia
├── data/
│   ├── raw/<ano>/              CSVs da CVM (NÃO vão para o GitHub)
│   └── exports/                tabelas geradas pelo ETL (vão para o GitHub)
├── database/telecom.db         banco SQLite lido pelo dashboard (VAI para o GitHub)
├── docs/REVISAO_SPRINT3.md     revisão de ponta a ponta das Sprints 1 e 2
├── etl/                        scripts numerados do pipeline (ver tabela abaixo)
├── graficos/                   gráficos estáticos (Sprint 2) e graficos/sprint3/ (relatório)
└── requirements.txt
```

## Como rodar no seu computador

Use **Python 3.12** (o 3.9 ainda roda com Streamlit 1.50, mas já está fora de suporte).

```bash
# 1. ambiente virtual e dependências
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. dados brutos da CVM -> data/raw/<ano>/
python etl/00_baixar_dados_cvm.py                                # baixa do portal da CVM
# ou, se você já tem os ZIPs (ex.: pasta "Bases de dados"):
python etl/00_baixar_dados_cvm.py --de-pasta "caminho/Bases de dados"

# 3. pipeline completo (banco, base analítica, EDA, diagnóstico e indicadores)
python etl/rodar_pipeline.py

# 4. dashboard
streamlit run dashboard/app.py
```

> ⚠️ Não abra os CSVs da CVM no Excel antes de processar: ele corrompe os valores.

## Publicar no Streamlit Community Cloud

O dashboard lê **apenas** `database/telecom.db`. Por isso o banco precisa estar no
GitHub (o `.gitignore` já libera esse arquivo e bloqueia os dados brutos).

1. Rode o pipeline, depois faça commit e push de `database/telecom.db`,
   `data/exports/`, `dashboard/`, `.streamlit/config.toml` e `requirements.txt`.
   Confira com `git ls-files database` (deve listar `database/telecom.db`).
2. Em [share.streamlit.io](https://share.streamlit.io) → **Create app** → escolha o
   repositório e a branch.
3. **Main file path:** `dashboard/app.py`
4. **Advanced settings → Python version:** 3.12
5. **Deploy.** Para atualizar os dados depois: rode o pipeline, faça commit do banco
   e push – o app se atualiza sozinho.

## Pipeline (pasta `etl/`)

| Script | O que faz |
|---|---|
| `config.py` | Parâmetros centrais: anos, empresas (CD_CVM), contas, encadeamento da Brisanet, observações de auditoria |
| `00_baixar_dados_cvm.py` | Baixa (ou extrai de ZIPs locais) os 4 CSVs consolidados por ano e registra origem, data e hash em `data/exports/coleta_cvm.csv` |
| `01_inspecionar_dados.py` | Inspeção rápida de um arquivo da CVM |
| `02_mapear_contas.py` | Confirma entidades e códigos de conta em todos os anos |
| `03_comparar_brisanet.py` | Compara Brisanet Participações × Serviços (ano de sobreposição) |
| `04_criar_banco.py` | Cria o banco **e migra bancos antigos** (colunas novas, views) |
| `05_carga.py` | CSVs → camada raw → `financial_data` (com validações e observações) |
| `06_eda.py` | Gráficos e tabelas descritivas da Sprint 2 |
| `07_diagnostico_dfc.py` | Fechamento da DFC e diagnóstico do valor atípico da Desktop (2021) |
| `08_indicadores.py` | **Sprint 3:** indicadores, alertas, estatísticas descritivas e CAGR |
| `09_graficos_sprint3.py` | **Sprint 3:** figuras do relatório em `graficos/sprint3/` |
| `rodar_pipeline.py` | Roda 04 → 09 em ordem (com `--inspecao`, roda 02 e 03 antes) |

## Indicadores (Sprint 3)

| Grupo | Indicador | Fórmula |
|---|---|---|
| Rentabilidade | Margem líquida | Lucro líquido ÷ Receita líquida |
| | ROE | Lucro líquido ÷ PL médio |
| | ROA | Lucro líquido ÷ Ativo total médio |
| | Margem EBITDA | (EBIT + D&A) ÷ Receita líquida |
| Estrutura de capital | Endividamento geral | Capital de terceiros (2.01 + 2.02) ÷ Ativo total |
| | Composição do endividamento | Passivo circulante ÷ Capital de terceiros |
| | Dívida líquida / EBITDA | (Dívida bruta − Caixa − Aplicações) ÷ EBITDA |
| Liquidez | Liquidez corrente | Ativo circulante ÷ Passivo circulante |
| Geração de caixa | Cobertura de caixa | FCO ÷ Lucro líquido |
| | Margem FCO | FCO ÷ Receita líquida |
| Apoio às hipóteses | Peso do resultado financeiro | − Resultado financeiro ÷ EBIT |
| | Depreciação / Receita | D&A ÷ Receita líquida |

Saldo médio = (saldo inicial + saldo final) ÷ 2, com o saldo inicial publicado como
comparativo na própria DFP do ano. Valores atípicos são mantidos como publicados e
registrados na tabela `alertas_indicadores`.

## Decisões metodológicas e limitações

- **Passivo total (conta 2)** inclui o PL; o endividamento usa 2.01 + 2.02.
- **Brisanet:** série encadeada – Participações (026085) até 2023, Serviços (027693)
  a partir de 2024 (incorporação eficaz em 04/12/2024).
- **Duplicatas na origem:** a DFP 2023 da Brisanet Serviços vem com linhas repetidas
  nos quatro arquivos da CVM; elas são removidas na carga.
- Valores **nominais** (sem correção pela inflação); só dados contábeis; seis
  exercícios por empresa.

## Roadmap

- [x] Sprint 1 – problema, referencial e dados
- [x] Sprint 2 – coleta, tratamento, banco SQLite e EDA
- [x] Sprint 3 – indicadores, análise descritiva e dashboard Streamlit
- [ ] Sprint 4 – análise inferencial (testes das hipóteses) e projeções
