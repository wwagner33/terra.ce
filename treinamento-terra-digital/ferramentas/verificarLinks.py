"""Confere os links externos do material.

Uso, a partir da pasta treinamento-terra-digital:

    python ferramentas/verificarLinks.py

Visita cada endereço http(s) citado nos arquivos .qmd e lista os que não
respondem. Vídeos do YouTube são conferidos pelo oEmbed, porque a página de um
vídeo removido continua respondendo 200. Só usa a biblioteca padrão. Não roda
na CI de cada pull request (sites externos oscilam); rode antes de uma
revisão geral do material.
"""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTAS_IGNORADAS = {"_site", "_extensions", ".quarto", ".venv"}
PADRAO_URL = re.compile(r"https?://[^\s)<>\"'`\]]+")
IGNORADOS = re.compile(r"^https?://(localhost|127\.0\.0\.1|x/|miniserver/)")
CABECALHOS = {"User-Agent": "Mozilla/5.0 (verificador de links do Terra Digital)", "Accept-Language": "pt-BR,pt;q=0.9"}
TEMPO_LIMITE = 25


def coletarLinks():
    links = {}
    for arquivo in sorted(RAIZ.rglob("*.qmd")):
        if PASTAS_IGNORADAS.intersection(arquivo.relative_to(RAIZ).parts):
            continue
        for numero, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), start=1):
            for url in PADRAO_URL.findall(linha):
                url = url.rstrip(".,;:")
                if "{" in url or IGNORADOS.match(url):
                    continue
                links.setdefault(url, []).append(f"{arquivo.relative_to(RAIZ)}:{numero}")
    return links


def idDoYoutube(url):
    partes = urllib.parse.urlparse(url)
    if partes.netloc.endswith("youtube.com") and partes.path == "/watch":
        return urllib.parse.parse_qs(partes.query).get("v", [None])[0]
    return None


def conferir(url):
    video = idDoYoutube(url)
    alvo = url
    if video:
        alvo = "https://www.youtube.com/oembed?format=json&url=" + urllib.parse.quote(f"https://www.youtube.com/watch?v={video}")
    for metodo in ("HEAD", "GET"):
        pedido = urllib.request.Request(alvo, headers=CABECALHOS, method=metodo)
        try:
            with urllib.request.urlopen(pedido, timeout=TEMPO_LIMITE) as resposta:
                if video:
                    titulo = json.loads(resposta.read().decode("utf-8")).get("title", "")
                    return url, resposta.status, titulo
                return url, resposta.status, ""
        except urllib.error.HTTPError as erro:
            # Alguns servidores recusam HEAD (405, 403); tenta de novo com GET.
            if metodo == "HEAD" and erro.code in (400, 403, 404, 405, 429, 500, 501, 503):
                continue
            return url, erro.code, str(erro.reason)
        except Exception as erro:  # noqa: BLE001 - qualquer falha de rede vira relatório
            if metodo == "HEAD":
                continue
            return url, None, str(erro)
    return url, None, "sem resposta"


def main():
    links = coletarLinks()
    print(f"{len(links)} links únicos para conferir...")
    problemas = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for url, status, detalhe in executor.map(conferir, links):
            if status is None or status >= 400:
                problemas.append((url, status, detalhe))
    for url, status, detalhe in sorted(problemas):
        print(f"FALHOU {status} {url} ({detalhe})")
        for origem in links[url]:
            print(f"    em {origem}")
    print(f"{len(links) - len(problemas)} ok, {len(problemas)} com problema.")
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
