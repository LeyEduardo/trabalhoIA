import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory
from google import genai
from google.genai import errors, types

from web_tools import make_tools

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

app = Flask(__name__, static_folder="static", static_url_path="/static")
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
# Modelos reserva, tentados em ordem quando o principal esta sem cota (429) ou sobrecarregado (503)
FALLBACK_MODELS = [
    name.strip()
    for name in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-3-flash-preview,gemini-3.5-flash-lite,gemini-flash-latest").split(",")
    if name.strip() and name.strip() != MODEL_NAME
]
# Como o agente acessa a internet:
#   google     -> Pesquisa Google integrada do Gemini; exige plano com cota para "grounding"
#   off        -> sem internet
WEB_SEARCH = os.getenv("GEMINI_WEB_SEARCH", "duckduckgo").strip().lower()
SYSTEM_INSTRUCTION = """Voce e o Boleiro, um assistente conversacional especialista no Campeonato
Brasileiro de Futebol - Serie A. Converse naturalmente em portugues brasileiro.

Responda livremente as perguntas do usuario sobre clubes, jogadores, partidas,
rodadas, tabela, classificacao, artilharia, regulamento, campeoes, historia,
estatisticas, rivalidades, analises e curiosidades. Pense no contexto da conversa
antes de responder e responda diretamente, sem seguir respostas prontas.

Explique seu raciocinio quando o usuario pedir uma analise. Diferencie fatos,
opinioes e previsoes. Nao invente resultados, classificacoes, noticias ou dados.
{internet}
Se o usuario fornecer uma tabela, texto ou numeros, use esses dados para analisar
a pergunta.

Mantenha o foco no Brasileirao Serie A, mas responda com naturalidade quando a
pergunta tiver relacao com futebol brasileiro. Nao use tabelas em Markdown: para
classificacoes e listas, use uma linha por item (ex.: "1. Flamengo - 60 pts").
Hoje e {today}."""

INTERNET_ON = """Voce tem acesso a pesquisa na internet. Para qualquer informacao atual ou que
possa ter mudado (tabela, classificacao, rodada, resultados, proximos jogos,
artilharia, elenco, tecnicos, transferencias, lesoes, noticias), PESQUISE antes
de responder e traga a informacao completa: numeros, datas, placares e nomes.
Faca uma unica pesquisa bem especifica: os primeiros resultados ja vem com o texto
da pagina. So use ler_pagina ou pesquise de novo se esses dados nao bastarem. Confira se o dado e da
temporada atual. Para conversa casual ou historia consolidada, responda sem pesquisar.
Nao escreva uma lista de fontes ou links no final: o sistema acrescenta as fontes
automaticamente."""

INTERNET_OFF = """Voce nao tem acesso a internet nem a tabelas em tempo real: quando a pergunta
depender de informacao atual, diga isso claramente e indique uma fonte oficial."""


def get_client():
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key.startswith("cole_sua_chave"):
        return None
    # Poucas tentativas por modelo: se um estiver sobrecarregado, e mais rapido passar para o proximo
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(
        timeout=90_000,
        retry_options=types.HttpRetryOptions(attempts=2, initial_delay=1.0),
    ))


def now():
    return datetime.now().strftime("%H:%M")


MAX_MESSAGE_CHARS = 4000
HISTORY_LIMIT = 12  # ultimas mensagens enviadas ao modelo como contexto


@app.get("/")
def index():
    # O historico das conversas fica no localStorage do navegador (ver index.html)
    return send_from_directory(BASE_DIR, "index.html")


def clean_history(raw):
    """Valida o historico enviado pelo navegador: so aceita papeis e textos conhecidos."""
    if not isinstance(raw, list):
        return []
    history = []
    for item in raw[-HISTORY_LIMIT:]:
        if not isinstance(item, dict) or item.get("role") not in {"user", "model"}:
            continue
        text = str(item.get("text", "")).strip()[:MAX_MESSAGE_CHARS * 2]
        if text:
            history.append({"role": item["role"], "text": text})
    return history


def ask_model(message, conversation):
    client = get_client()
    if client is None:
        raise RuntimeError("Configure a GEMINI_API_KEY no arquivo .env.")

    history = [
        types.Content(role=item["role"], parts=[types.Part(text=item["text"])])
        for item in conversation
    ]
    history.append(types.Content(role="user", parts=[types.Part(text=message)]))

    models = [MODEL_NAME, *FALLBACK_MODELS]
    for index, model in enumerate(models):
        try:
            return call_model(client, model, history)
        except errors.APIError as error:
            # 429 = limite de uso; 503 = modelo sobrecarregado. Tenta o proximo modelo da lista.
            if error.code not in {429, 503} or index == len(models) - 1:
                raise
            app.logger.warning("%s indisponivel (%s); tentando %s", model, error.code, models[index + 1])


def call_model(client, model, history):
    system = SYSTEM_INSTRUCTION.format(
        internet=INTERNET_OFF if WEB_SEARCH == "off" else INTERNET_ON,
        today=datetime.now().strftime("%d/%m/%Y"),
    )
    sources = []
    if WEB_SEARCH == "google":
        tools = [types.Tool(google_search=types.GoogleSearch())]
    elif WEB_SEARCH == "duckduckgo":
        tools = make_tools(sources)
    else:
        tools = None

    response = client.models.generate_content(
        model=model,
        contents=history,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.4,
            max_output_tokens=4096,
            tools=tools,
            # O SDK executa sozinho as funcoes que o modelo pedir. Cada rodada gasta uma
            # requisicao da cota do Gemini (so 20 por dia por modelo no plano gratuito).
            automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=4),
        ),
    )
    answer = (response.text or "").strip()
    if not answer:
        return "Não consegui formular uma resposta agora. Pode reformular a pergunta?"
    sources += grounding_sources(response)
    sources = unique_sources(sources)
    if sources:
        answer += "\n\nFontes:\n" + "\n".join(f"- {title} — {url}" for title, url in sources)
    return answer


def grounding_sources(response):
    """Fontes da Pesquisa Google integrada (modo "google")."""
    candidate = (response.candidates or [None])[0]
    metadata = getattr(candidate, "grounding_metadata", None)
    return [
        (chunk.web.title or chunk.web.domain or "fonte", chunk.web.uri)
        for chunk in getattr(metadata, "grounding_chunks", None) or []
        if chunk.web and chunk.web.uri
    ]


def unique_sources(sources, limit=3):
    result, seen = [], set()
    for title, url in sources:
        if url not in seen:
            seen.add(url)
            result.append((title.strip(), url))
    return result[:limit]


def friendly_error(error):
    code = getattr(error, "code", None)
    text = str(error).lower()
    if code == 404 or "not found" in text:
        return f"O modelo '{MODEL_NAME}' não está disponível no Gemini. Ajuste GEMINI_MODEL no arquivo .env."
    if code in {400, 401, 403} and ("api key" in text or "api_key" in text or "permission" in text):
        return "A chave do Gemini é inválida ou sem permissão. Confira GEMINI_API_KEY no arquivo .env."
    if code == 429:
        return "O limite de uso gratuito do Gemini foi atingido. Aguarde um pouco e tente novamente."
    if code == 503 or "timeout" in text or "timed out" in text:
        return "O Gemini está sobrecarregado ou demorando. Aguarde alguns segundos e tente novamente."
    return "Não consegui consultar o Gemini agora. Tente novamente em instantes."


@app.post("/api/chat")
def chat_api():
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()

    if not message:
        return jsonify({"error": "Escreva uma mensagem antes de enviar."}), 400
    if len(message) > MAX_MESSAGE_CHARS:
        return jsonify({"error": "Sua mensagem precisa ter no máximo 4.000 caracteres."}), 400

    try:
        answer = ask_model(message, clean_history(payload.get("history")))
    except RuntimeError as error:
        return jsonify({"error": str(error)}), 503
    except Exception as error:
        app.logger.exception("Erro ao consultar o Gemini")
        return jsonify({"error": friendly_error(error)}), 502
    return jsonify({"answer": answer, "time": now()})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
