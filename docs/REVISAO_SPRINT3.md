# Revisão de ponta a ponta – Sprints 1 e 2 (início da Sprint 3)

Revisão feita sobre o repositório `pi3_revisao`, os dados brutos (`Bases de dados`)
e os relatórios das Sprints 1 e 2. O pipeline foi executado do zero a partir dos
CSVs da CVM e cada valor da base analítica foi conferido por uma extração
independente.

## 1. Resultado geral

- **O ETL roda do início ao fim sem erro** e reproduz exatamente os arquivos de
  `data/exports/` e a tabela `financial_data` que estavam no repositório (a única
  diferença foi o último dígito de um desvio-padrão, ruído de ponto flutuante).
- Os 24 CSVs de `Bases de dados/DADOS <ano>` são **idênticos byte a byte** aos
  ZIPs originais da CVM: não houve corrupção por Excel.
- Os 9 valores × 18 observações (3 empresas × 6 anos) conferem com a extração
  independente. A identidade **PC + PNC + PL = Ativo** fecha em 18/18 e a
  **DFC fecha** (6.01 + 6.02 + 6.03 + 6.04 = 6.05) em 18/18.

## 2. Problemas que impediriam a publicação no Streamlit (corrigidos)

| # | Problema | Correção |
|---|---|---|
| 1 | `.gitignore` ignorava `*.db`, `data/exports/*` e a pasta `.streamlit/` inteira: o app no Streamlit Cloud não teria nenhum dado | Banco `database/telecom.db` e `data/exports/` liberados; só `secrets.toml` continua ignorado |
| 2 | `requirements.txt` era um `pip freeze` de Python 3.9 (ex.: `numpy==2.0.2`, sem pacote pronto para Python 3.13+). O Community Cloud só oferece versões de Python ainda com suporte, e o Streamlit 1.51+ não roda em 3.9 | Arquivo enxuto com faixas de versão; deploy com Python 3.12 |
| 3 | Pasta `dashboard/` vazia | Dashboard criado (`dashboard/app.py` + 5 páginas) |

## 3. Erros e riscos de execução no código (corrigidos)

| # | Arquivo | Problema | Correção |
|---|---|---|---|
| 4 | `01_inspecionar_dados.py` | Se o arquivo não existe, quebra com `NameError: name 'df' is not defined` (o filtro ficava fora do `else`) | Mensagem clara e saída; aceita demonstração/ano por parâmetro |
| 5 | `05_carga.py` | O log dizia "1 reapresentação removida", mas na verdade a CVM publicou **linhas duplicadas** da DFP 2023 da Brisanet Serviços (54 no DRE, 122 no BPA, 218 no BPP, 114 na DFC). A camada raw guardava as duplicatas | Duplicatas exatas removidas na leitura, com log próprio |
| 6 | `04_criar_banco.py` | `CREATE TABLE IF NOT EXISTS` nunca acrescenta colunas novas a um banco existente, e a view nunca era atualizada | Função `migrar()` (`ALTER TABLE ... ADD COLUMN`) e views recriadas a cada execução |
| 7 | `02` e `03` | Tinham cópias próprias de anos, demonstrações e escala, contrariando a regra do `config.py` ("todo ajuste de escopo deve ser feito aqui") | Passam a importar do `config.py` (saídas idênticas às anteriores) |
| 8 | `06_eda.py` | "Razão média FCO/Lucro" da Brisanet = 30,0x, inflada por 2021 (lucro de R$ 2,2 mi → 144x) | Mediana (8,0x) e razão agregada (6,6x) |
| 9 | `06_eda.py` | `pct_change()` inverte o sinal quando a base é negativa (ex.: prejuízo) | Variação sobre o valor absoluto do ano anterior (mesmo resultado nos dados atuais) |

## 4. Divergências entre o relatório da Sprint 2 e o código

| # | O relatório diz | O que havia no repositório | Situação |
|---|---|---|---|
| 10 | Existe `07_diagnostico_dfc.py` (seção 8.1) | Arquivo ausente | Recriado: reproduz as seções 6.2 e 6.4 |
| 11 | `financial_data` tem a coluna `observacao` e o `config.py` tem "observações de auditoria" (5.2, 8.1) | Não existiam | Criadas (`config.OBSERVACOES`) |
| 12 | O `04_criar_banco.py` faz "migração de versões anteriores" | Não fazia | Implementado (item 6) |
| 13 | Teste de identidade PC + PNC + PL = AT (6.1) e fechamento da DFC (6.2) | O código só comparava conta 1 × conta 2, que é sempre igual por definição | Identidade gravada em `validacao_identidade_ok`; DFC no `07` |
| 14 | Mapeamento "confirmado sem exceções" das contas 1.01, 2.01 e 2.02 | O `02_mapear_contas.py` não verificava essas contas | Agora verifica (todas confirmadas) |

## 5. Ajustes sugeridos no TEXTO do relatório da Sprint 2

| Seção | Texto atual | Sugestão (conferida nos dados) |
|---|---|---|
| 2.3 | "vinte arquivos processados (quatro demonstrações × cinco anos)" | **24 arquivos** (4 demonstrações × 6 anos) |
| 4.2.2 | Lucro: "R$ 8,8 milhões – a menor diferença observada na tabela" | Receita (R$ 0,0 mi) e ativo/passivo (R$ 1,0 mi) têm diferenças menores; R$ 8,8 mi é menor que as do PL (R$ 31,6 mi) e do FCO (R$ 15,2 mi). Vale citar também que o próprio `03_comparar_brisanet.py` sinaliza "divergência relevante (>5%)" por causa dos 5,41% do lucro e justificar a decisão |
| 6.4 | "dezessete das dezoito observações situam-se entre 26% e 54%" | **14 de 18**: ficam fora Desktop 2021 (215,8%), 2022 (12,4%), 2023 (20,9%) e 2024 (25,6%) |
| 7.3 | "Até 2023, as três companhias apresentam trajetória ascendente de resultado" | A Brisanet caiu de R$ 29,1 mi (2020) para R$ 2,2 mi (2021), −92%, antes de subir |
| 7.3 | "realizaram ofertas públicas na mesma semana" | Desktop em 21/07/2021, Unifique e Brisanet no fim de julho: "no mesmo mês" |
| 8.4 | Banco e artefatos fora do versionamento | Para o deploy no Streamlit, o banco e os exports passam a ser versionados |

Da Sprint 1, vale registrar na Sprint 3: a fórmula "Endividamento = Passivo Total ÷
Ativo Total" daria sempre 100% (já corrigida na seção 4.1 da Sprint 2); o ROE
segue a definição da Sprint 1 (PL **médio**); os valores ficam em R$ no banco e
em R$ milhões nos gráficos (a Sprint 1 citava R$ mil).

## 6. O que foi acrescentado para a Sprint 3

- **Variáveis complementares** (contas fixas da CVM, conferidas em todos os anos):
  EBIT (3.05), resultado financeiro (3.06), despesas financeiras (3.06.02), caixa
  (1.01.01), aplicações (1.01.02), empréstimos CP/LP (2.01.04 / 2.02.01), FCI
  (6.02), FCF (6.03) e depreciação e amortização (DFC, localizada pela descrição).
  Derivadas: EBITDA, dívida bruta e dívida líquida.
- **`08_indicadores.py`**: 12 indicadores, alertas de interpretação, estatísticas
  descritivas (com e sem valores sinalizados) e CAGR.
- **Saldos médios**: o saldo inicial vem do comparativo publicado na própria DFP do
  ano. A DFP 2020 da Desktop não traz o comparativo de 2019 (valores zerados),
  então ROE/ROA de 2020 da Desktop ficam sem cálculo, com alerta.
- **`00_baixar_dados_cvm.py`**: recria `data/raw/` (download da CVM ou ZIPs locais)
  e registra origem, data e hash. A CVM republica os ZIPs periodicamente; os de
  2022–2025 foram atualizados em 04/10/2026.
- **`rodar_pipeline.py`**: executa tudo na ordem certa.
- **Dashboard Streamlit**: visão geral, indicadores, análise descritiva, hipóteses
  da pesquisa e dados/metodologia.
