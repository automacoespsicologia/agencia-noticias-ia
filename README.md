# 🚀 Agência de Notícias Espaciais (Sala 1C)

Sistema autônomo de monitoramento, coleta e curadoria de notícias aeroespaciais utilizando a API do Gemini.

## 📁 Estrutura do Projeto

- `src/`: Scripts principais da agência (`coletor.py` e `editor.py`).
- `data/`: Configurações e persistência de dados.
- `reports/`: Relatórios gerados em Markdown para leitura humana.
- `docs/`: Documentação e planejamento.
- `legacy/`: Versões anteriores e arquivos depreciados.

## 🛠️ Como Funciona

1.  **Coletor (`src/coletor.py`)**: Varre feeds RSS em busca de novidades e salva no pool (`data/pool_de_noticias.json`).
2.  **Editor (`src/editor.py`)**: Utiliza o Gemini para analisar o pool, selecionar as melhores notícias e gerar um relatório formatado em `reports/Relatorio_do_Dia.md`.

## 🚀 Como Executar Localmente

1. Instale as dependências:
   ```bash
   pip install google-genai requests python-dotenv
   ```
2. Configure seu `GEMINI_API_KEY` no arquivo `.env` na raiz.
3. Execute o script de atalho:
   ```bash
   python run_agency.py
   ```

## 🤖 Automação via GitHub Actions

O projeto está configurado para rodar diariamente através do GitHub Actions. Os resultados são salvos automaticamente na pasta `reports/`.
