"""Ferramentas de internet que o Gemini pode chamar: pesquisar na web e ler uma pagina.

Usadas quando a Pesquisa Google integrada do Gemini nao esta disponivel (plano gratuito).
A busca usa o DuckDuckGo, que e gratuito e nao exige chave.
"""
import ipaddress
import socket
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

from ddgs import DDGS

MAX_PAGE_CHARS = 8000
PREVIEW_PAGES = 2  # paginas lidas automaticamente junto com a pesquisa
PREVIEW_CHARS = 3500
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


class _TextExtractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "head", "nav", "footer", "form"}

    def __init__(self):
        super().__init__()
        self.parts, self.skipping = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skipping += 1
        elif tag in {"tr", "li", "p", "br", "h1", "h2", "h3", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skipping:
            self.skipping -= 1

    def handle_data(self, data):
        if not self.skipping and data.strip():
            self.parts.append(data.strip() + " ")

    def text(self):
        lines = (" ".join(line.split()) for line in "".join(self.parts).splitlines())
        return "\n".join(line for line in lines if line)


def _is_public_url(url):
    """Evita que o modelo acesse enderecos internos (localhost, rede local)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        for info in socket.getaddrinfo(parsed.hostname, None):
            if not ipaddress.ip_address(info[4][0]).is_global:
                return False
    except (socket.gaierror, ValueError):
        return False
    return True


def _read_page(url, max_chars):
    if not _is_public_url(url):
        return None
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=10) as response:
            html = response.read(1_500_000).decode(response.headers.get_content_charset() or "utf-8", "replace")
    except Exception:
        return None
    parser = _TextExtractor()
    parser.feed(html)
    return parser.text()[:max_chars] or None


def make_tools(sources):
    """Cria as funcoes que o Gemini pode chamar. Cada URL usada e registrada em `sources`."""

    def pesquisar_web(consulta: str) -> list[dict]:
        """Pesquisa na internet e retorna titulo, link e resumo de cada resultado.
        Os primeiros resultados ja vem com o texto da pagina (campo "texto_da_pagina").

        Args:
            consulta: termos da pesquisa, em portugues. Ex.: "classificacao Brasileirao Serie A 2026".
        """
        try:
            results = DDGS().text(consulta, region="br-pt", max_results=6)
        except Exception as error:
            return [{"erro": f"Falha na pesquisa: {error}"}]
        # Ja le as primeiras paginas para o modelo nao precisar de outra rodada (economiza cota da API)
        items, previews = [], 0
        for result in results:
            item = {"titulo": result.get("title"), "link": result.get("href"), "resumo": result.get("body")}
            if previews < PREVIEW_PAGES:
                text = _read_page(result["href"], PREVIEW_CHARS)
                if text:
                    item["texto_da_pagina"] = text
                    previews += 1
                    sources.append((result.get("title") or result["href"], result["href"]))
            items.append(item)
        return items

    def ler_pagina(url: str) -> str:
        """Abre uma pagina da internet e retorna o texto dela. Use so quando o texto_da_pagina
        da pesquisa nao bastar, para ler tabelas, placares e detalhes.

        Args:
            url: endereco completo da pagina (http ou https), normalmente um link vindo de pesquisar_web.
        """
        text = _read_page(url, MAX_PAGE_CHARS)
        if not text:
            return "Nao consegui abrir essa pagina (endereco invalido, bloqueado ou sem texto)."
        sources.insert(0, (urlparse(url).hostname, url))
        return text

    return [pesquisar_web, ler_pagina]
