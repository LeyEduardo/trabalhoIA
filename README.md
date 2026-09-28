# Boleiro — Chatbot do Brasileirão Série A

Agente conversacional em Python para responder perguntas sobre o Campeonato Brasileiro de Futebol — Série A. O projeto usa Flask, Gemini e busca na web para responder com contexto, sem inventar informações, e mantém uma conversa natural em português.

## Objetivo

Criar um assistente especializado em futebol brasileiro que:

- responde perguntas em linguagem natural;
- entende contexto da conversa;
- verifica dados atuais quando necessário;
- busca informações na web e informa as fontes consultadas;
- evita inventar resultados, tabela, artilharia ou fatos sem suporte.

## Funcionalidades

- Chat web em Flask;
- integração com a API Gemini;
- pesquisa na web com DuckDuckGo;
- leitura de páginas para extrair texto relevante;
- histórico persistido no navegador via localStorage;
- mensagens de erro amigáveis;
- modelos de fallback quando o principal está indisponível.

## Tecnologias

- Python 3
- Flask
- python-dotenv
- Google GenAI
- DuckDuckGo (`ddgs`)
- HTML, CSS e JavaScript

## Estrutura do projeto

```text
chatbot-brasileirao/
├── app.py
├── web_tools.py
├── index.html
├── static/
│   └── style.css
├── requirements.txt
├── .env
├── README.md
└── .gitignore
```

## Requisitos

- Python 3.10 ou superior
- Chave da API do Google Gemini
- Acesso à internet para busca e leitura de páginas

## Como rodar

1. Abra o terminal na pasta do projeto:

```powershell
cd "C:\Users\Usuário\OneDrive\Desktop\IA\chatbot-brasileirao"
```

2. Crie e ative o ambiente virtual (se ainda não existir):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Se você já tiver uma venv na pasta `IA\.venv`, ela também será encontrada pelo
launcher do projeto.

3. Instale as dependências:

```powershell
pip install -r requirements.txt
```

4. Crie o arquivo `.env` na pasta do projeto com o conteúdo abaixo:

```env
GEMINI_API_KEY=sua_chave_aqui
GEMINI_MODEL=gemini-3.5-flash
GEMINI_FALLBACK_MODELS=gemini-3-flash-preview,gemini-3.5-flash-lite,gemini-flash-latest
GEMINI_WEB_SEARCH=duckduckgo
PORT=5000
```

5. Inicie o servidor usando a venv do projeto:

```powershell
.\run.ps1
```

Se o PowerShell bloquear scripts, execute:

```powershell
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Ou execute manualmente, usando a venv criada:

```powershell
.\.venv\Scripts\python.exe app.py
```

6. Acesse no navegador:

```text
http://127.0.0.1:5000
```

## Observações importantes

- O arquivo `.env` não deve ser enviado para o Git.
- Se o modelo principal estiver indisponível, o sistema tenta outros modelos de fallback.
- Se `GEMINI_WEB_SEARCH=duckduckgo`, a aplicação usa busca gratuita e leitura de páginas para dados atuais.
- Se quiser desligar a internet, use `GEMINI_WEB_SEARCH=off`.

## Exemplos de perguntas

- Quem está líder do Brasileirão?
- Qual foi o último resultado do Palmeiras?
- Quem é o artilheiro do campeonato?
- Quando é o próximo jogo do Flamengo?
- Compare Flamengo e Palmeiras neste ano.

## Licença

Este projeto é de uso local e acadêmico. Ajuste conforme a necessidade do seu uso.

## Melhorias futuras

- suporte a streaming de respostas;
- autenticação de usuários;
- banco de dados para armazenar conversas;
- integração com API oficial de futebol;
- deploy em servidor web.
