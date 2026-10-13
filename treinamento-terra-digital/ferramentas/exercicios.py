"""Ferramentas dos exercícios do Treinamento Terra Digital.

Uso, sempre a partir da pasta treinamento-terra-digital:

    python ferramentas/exercicios.py indice   # gera indiceExercicios.js (só biblioteca padrão)
    python ferramentas/exercicios.py validar  # confere o YAML de todos os exercícios (requer PyYAML)
    python ferramentas/exercicios.py testar   # valida e roda as soluções de Python e SQL

O "indice" roda sozinho antes de cada render (pre-render do _quarto.yml) e
alimenta a página "Meu progresso". "validar" e "testar" rodam na integração
contínua: um exercício com YAML errado ou com solução que não passa nos
próprios testes reprova o pull request.
"""

import json
import re
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARQUIVO_INDICE = RAIZ / "indiceExercicios.js"
ARQUIVO_DADOS_SQL = RAIZ / "_extensions" / "exercicios" / "dadosSql.js"
ARQUIVO_EXECUTOR = RAIZ / "_extensions" / "exercicios" / "executor.py"
PASTAS_IGNORADAS = {"_site", "_extensions", ".quarto", ".venv", "ferramentas"}

TIPOS = {"escolha", "multipla", "numero", "texto", "ordenar", "associar", "python", "sql", "aberta", "checklist"}
CAMPOS_COMUNS = {"id", "tipo", "pergunta", "explicacao", "dica"}
CAMPOS_POR_TIPO = {
    "escolha": {"opcoes"},
    "multipla": {"opcoes"},
    "numero": {"resposta", "tolerancia", "unidade"},
    "texto": {"respostas", "regex"},
    "ordenar": {"itens"},
    "associar": {"pares"},
    "python": {"inicial", "testes", "solucao"},
    "sql": {"dados", "inicial", "solucao", "ordem"},
    "aberta": {"resposta"},
    "checklist": {"itens"},
}
FORMATO_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
ABERTURA = re.compile(r"^(?P<cerca>`{3,}|~{3,})\s*(?:\{\s*\.exercicio[^}]*\}|exercicio)\s*$")
QUALQUER_CERCA = re.compile(r"^\s{0,3}(?P<cerca>`{3,}|~{3,})")
TEMPO_LIMITE_SEGUNDOS = 120


@dataclass
class Bloco:
    arquivo: Path
    linha: int
    texto: str
    cerca: str


@dataclass
class Relatorio:
    erros: list = field(default_factory=list)
    avisos: list = field(default_factory=list)

    def erro(self, bloco, mensagem):
        self.erros.append(f"{bloco.arquivo.relative_to(RAIZ)}:{bloco.linha}: {mensagem}")

    def aviso(self, bloco, mensagem):
        self.avisos.append(f"{bloco.arquivo.relative_to(RAIZ)}:{bloco.linha}: {mensagem}")


# --------------------------------------------------------------- leitura


def listarPaginas():
    """Arquivos .qmd do site, na ordem em que aparecem no _quarto.yml."""
    configuracao = (RAIZ / "_quarto.yml").read_text(encoding="utf-8")
    ordem = []
    for caminho in re.findall(r"([\w./-]+\.qmd)", configuracao):
        if caminho not in ordem:
            ordem.append(caminho)
    todos = sorted(
        str(p.relative_to(RAIZ))
        for p in RAIZ.rglob("*.qmd")
        if not PASTAS_IGNORADAS.intersection(p.relative_to(RAIZ).parts)
    )
    return [RAIZ / c for c in ordem if (RAIZ / c).exists()] + [RAIZ / c for c in todos if c not in ordem]


def extrairBlocos(arquivo):
    """Blocos ~~~exercicio do arquivo. Exemplos dentro de outros blocos de código são ignorados."""
    linhas = arquivo.read_text(encoding="utf-8").splitlines()
    blocos = []
    i = 0
    while i < len(linhas):
        qualquerCerca = QUALQUER_CERCA.match(linhas[i])
        if not qualquerCerca:
            i += 1
            continue
        cerca = qualquerCerca.group("cerca")
        fechamento = re.compile(r"^\s{0,3}" + re.escape(cerca[0]) + "{" + str(len(cerca)) + r",}\s*$")
        ehExercicio = bool(ABERTURA.match(linhas[i]))
        inicio = i + 1
        i += 1
        while i < len(linhas) and not fechamento.match(linhas[i]):
            i += 1
        if ehExercicio:
            blocos.append(Bloco(arquivo, inicio, "\n".join(linhas[inicio:i]), cerca))
        i += 1
    return blocos


def tituloDaPagina(arquivo):
    texto = arquivo.read_text(encoding="utf-8")
    cabecalho = re.match(r"^---\n(.*?)\n---", texto, re.S)
    if cabecalho:
        titulo = re.search(r"^title:\s*(.+)$", cabecalho.group(1), re.M)
        if titulo:
            return titulo.group(1).strip().strip("\"'")
    return arquivo.stem


def campoDeTopo(texto, nome):
    encontrado = re.search(r"^" + nome + r":\s*(.+?)\s*$", texto, re.M)
    return encontrado.group(1).strip().strip("\"'") if encontrado else ""


# ----------------------------------------------------------------- índice


def gerarIndice():
    paginas = []
    for arquivo in listarPaginas():
        exercicios = [
            {"id": campoDeTopo(b.texto, "id"), "tipo": campoDeTopo(b.texto, "tipo")} for b in extrairBlocos(arquivo)
        ]
        paginas.append(
            {
                "caminho": arquivo.relative_to(RAIZ).with_suffix(".html").as_posix(),
                "titulo": tituloDaPagina(arquivo),
                "exercicios": [ex for ex in exercicios if ex["id"]],
            }
        )
    conteudo = (
        "/* Gerado por ferramentas/exercicios.py antes de cada render. Não edite à mão. */\n"
        "window.TerraDigitalIndice = " + json.dumps({"paginas": paginas}, ensure_ascii=False, indent=1) + ";\n"
    )
    ARQUIVO_INDICE.write_text(conteudo, encoding="utf-8")
    total = sum(len(p["exercicios"]) for p in paginas)
    print(f"indiceExercicios.js: {total} atividades em {len(paginas)} páginas.")


# --------------------------------------------------------------- validação


def carregarYaml(texto):
    try:
        import yaml
    except ImportError:
        sys.exit("PyYAML não instalado. Rode: pip install -r requirements.txt")
    return yaml.safe_load(texto)


def ehTexto(valor):
    return isinstance(valor, str) and valor.strip() != ""


def validarOpcoes(dados, bloco, relatorio, umaCorreta):
    opcoes = dados.get("opcoes")
    if not isinstance(opcoes, list) or len(opcoes) < 2:
        relatorio.erro(bloco, '"opcoes" precisa ser uma lista com pelo menos duas opções')
        return
    corretas = 0
    for opcao in opcoes:
        if isinstance(opcao, str):
            continue
        if not isinstance(opcao, dict) or not ehTexto(opcao.get("texto")):
            relatorio.erro(bloco, 'cada opção deve ser um texto ou ter o campo "texto"')
            continue
        if opcao.get("correta") is True:
            corretas += 1
    if umaCorreta and corretas != 1:
        relatorio.erro(bloco, f"exercício de escolha precisa de exatamente uma opção correta (tem {corretas})")
    if not umaCorreta and corretas < 1:
        relatorio.erro(bloco, "exercício de múltipla escolha precisa de pelo menos uma opção correta")


def validarBloco(bloco, relatorio, idsVistos):
    if bloco.cerca.startswith("`") and re.search(r"^\s*```", bloco.texto, re.M):
        relatorio.erro(bloco, "o exercício contém ``` dentro: abra e feche o bloco com ~~~exercicio")
    try:
        dados = carregarYaml(bloco.texto)
    except Exception as erro:  # noqa: BLE001 - qualquer erro do YAML vira mensagem
        relatorio.erro(bloco, f"YAML inválido: {erro}")
        return None
    if not isinstance(dados, dict):
        relatorio.erro(bloco, "o bloco precisa ser um mapa YAML (campo: valor)")
        return None

    identificador = str(dados.get("id", ""))
    if not FORMATO_ID.match(identificador):
        relatorio.erro(bloco, f'"id" ausente ou fora do formato (minúsculas, números e hífens): {identificador!r}')
    elif identificador in idsVistos:
        relatorio.erro(bloco, f'"id" repetido: {identificador} (também em {idsVistos[identificador]})')
    else:
        idsVistos[identificador] = f"{bloco.arquivo.relative_to(RAIZ)}:{bloco.linha}"

    tipo = dados.get("tipo")
    if tipo not in TIPOS:
        relatorio.erro(bloco, f'"tipo" deve ser um de: {", ".join(sorted(TIPOS))}')
        return None
    if not ehTexto(dados.get("pergunta")):
        relatorio.erro(bloco, 'falta "pergunta"')

    desconhecidos = set(dados) - CAMPOS_COMUNS - CAMPOS_POR_TIPO[tipo]
    if desconhecidos:
        relatorio.aviso(bloco, f"campos ignorados para o tipo {tipo}: {', '.join(sorted(desconhecidos))}")
    if tipo not in {"checklist", "aberta"} and not ehTexto(dados.get("explicacao")):
        relatorio.aviso(bloco, 'sem "explicacao": quem acerta não recebe o comentário')

    if tipo == "escolha":
        validarOpcoes(dados, bloco, relatorio, umaCorreta=True)
    elif tipo == "multipla":
        validarOpcoes(dados, bloco, relatorio, umaCorreta=False)
    elif tipo == "numero":
        if not isinstance(dados.get("resposta"), (int, float)) or isinstance(dados.get("resposta"), bool):
            relatorio.erro(bloco, '"resposta" precisa ser um número')
        tolerancia = dados.get("tolerancia", 0)
        if not isinstance(tolerancia, (int, float)) or tolerancia < 0:
            relatorio.erro(bloco, '"tolerancia" precisa ser um número maior ou igual a zero')
    elif tipo == "texto":
        respostas = dados.get("respostas")
        if not (isinstance(respostas, list) and respostas and all(ehTexto(str(r)) for r in respostas)) and not ehTexto(dados.get("regex")):
            relatorio.erro(bloco, 'informe "respostas" (lista) ou "regex"')
        if ehTexto(dados.get("regex")):
            try:
                re.compile(dados["regex"])
            except re.error as erro:
                relatorio.erro(bloco, f'"regex" inválida: {erro}')
    elif tipo in {"ordenar", "checklist"}:
        itens = dados.get("itens")
        minimo = 2 if tipo == "ordenar" else 1
        if not isinstance(itens, list) or len(itens) < minimo or not all(ehTexto(str(i)) for i in itens):
            relatorio.erro(bloco, f'"itens" precisa ser uma lista com pelo menos {minimo} texto(s)')
        elif tipo == "ordenar" and len(set(map(str, itens))) != len(itens):
            relatorio.erro(bloco, '"itens" repetidos tornam a ordem ambígua')
    elif tipo == "associar":
        pares = dados.get("pares")
        if not isinstance(pares, list) or len(pares) < 2:
            relatorio.erro(bloco, '"pares" precisa ser uma lista com pelo menos dois pares')
        elif not all(isinstance(p, dict) and ehTexto(str(p.get("termo", ""))) and ehTexto(str(p.get("definicao", ""))) for p in pares):
            relatorio.erro(bloco, 'cada par precisa de "termo" e "definicao"')
        elif len({str(p["definicao"]) for p in pares}) != len(pares):
            relatorio.erro(bloco, 'as definições dos "pares" precisam ser diferentes entre si')
    elif tipo == "python":
        testes = dados.get("testes")
        if not isinstance(testes, list) or not testes or not all(
            isinstance(t, dict) and ehTexto(t.get("nome")) and ehTexto(t.get("codigo")) for t in testes
        ):
            relatorio.erro(bloco, '"testes" precisa ser uma lista de {nome, codigo}')
        if not ehTexto(dados.get("solucao")):
            relatorio.erro(bloco, 'falta "solucao"')
    elif tipo == "sql":
        if dados.get("dados") not in carregarDadosSql():
            relatorio.erro(bloco, f'"dados" deve ser um de: {", ".join(carregarDadosSql())}')
        if not ehTexto(dados.get("solucao")):
            relatorio.erro(bloco, 'falta "solucao"')
    elif tipo == "aberta":
        if not ehTexto(dados.get("resposta")):
            relatorio.erro(bloco, 'falta "resposta" (a resposta comentada)')
    return dados


# ----------------------------------------------------------------- testes


def carregarDadosSql():
    texto = ARQUIVO_DADOS_SQL.read_text(encoding="utf-8")
    return json.loads(texto[texto.index("{") : texto.rindex("}") + 1])


PROGRAMA_DE_TESTE = """
import json, sys
sys.path.insert(0, {pasta!r})
from executor import executarExercicio
dados = json.loads(sys.stdin.read())
print(executarExercicio(dados["codigo"], json.dumps(dados["testes"])))
"""


def rodarPython(codigo, testes):
    programa = PROGRAMA_DE_TESTE.format(pasta=str(ARQUIVO_EXECUTOR.parent))
    processo = subprocess.run(
        [sys.executable, "-c", programa],
        input=json.dumps({"codigo": codigo, "testes": testes}),
        capture_output=True,
        text=True,
        timeout=TEMPO_LIMITE_SEGUNDOS,
        cwd=RAIZ,
    )
    if processo.returncode != 0:
        return {"erro": processo.stderr.strip() or "o processo terminou com erro", "testes": []}
    return json.loads(processo.stdout.strip().splitlines()[-1])


def testarPython(dados, bloco, relatorio):
    try:
        resultado = rodarPython(dados["solucao"], dados["testes"])
    except subprocess.TimeoutExpired:
        relatorio.erro(bloco, "a solução passou do tempo limite")
        return
    if resultado["erro"]:
        relatorio.erro(bloco, f"a solução parou com erro:\n{resultado['erro']}")
        return
    falhas = [t for t in resultado["testes"] if not t["passou"]]
    for falha in falhas:
        relatorio.erro(bloco, f'a solução não passa em "{falha["nome"]}": {falha["mensagem"]}')
    if ehTexto(dados.get("inicial")):
        try:
            inicial = rodarPython(dados["inicial"], dados["testes"])
        except subprocess.TimeoutExpired:
            return
        if not inicial["erro"] and all(t["passou"] for t in inicial["testes"]):
            relatorio.aviso(bloco, "o código inicial já passa em todas as verificações: os testes estão fracos")


def consultarSql(script, consulta):
    conexao = sqlite3.connect(":memory:")
    try:
        conexao.executescript(script)
        return conexao.execute(consulta).fetchall()
    finally:
        conexao.close()


def testarSql(dados, bloco, relatorio):
    script = carregarDadosSql().get(dados.get("dados"), "")
    try:
        linhas = consultarSql(script, dados["solucao"])
    except sqlite3.Error as erro:
        relatorio.erro(bloco, f"a solução SQL tem erro: {erro}")
        return
    if not linhas:
        relatorio.aviso(bloco, "a solução SQL não devolve nenhuma linha")
    if ehTexto(dados.get("inicial")):
        try:
            if consultarSql(script, dados["inicial"]) == linhas:
                relatorio.aviso(bloco, "a consulta inicial já dá o resultado esperado")
        except sqlite3.Error:
            pass


# ---------------------------------------------------------------- comandos


def validar(testar=False):
    relatorio = Relatorio()
    idsVistos = {}
    total = 0
    for arquivo in listarPaginas():
        for bloco in extrairBlocos(arquivo):
            total += 1
            dados = validarBloco(bloco, relatorio, idsVistos)
            if testar and dados and not any(e.startswith(f"{bloco.arquivo.relative_to(RAIZ)}:{bloco.linha}:") for e in relatorio.erros):
                if dados["tipo"] == "python":
                    testarPython(dados, bloco, relatorio)
                elif dados["tipo"] == "sql":
                    testarSql(dados, bloco, relatorio)
    for aviso in relatorio.avisos:
        print(f"aviso: {aviso}")
    for erro in relatorio.erros:
        print(f"ERRO: {erro}")
    situacao = "com erros" if relatorio.erros else "ok"
    print(f"{total} atividades verificadas, {len(relatorio.erros)} erro(s), {len(relatorio.avisos)} aviso(s): {situacao}.")
    return 1 if relatorio.erros else 0


def main(argumentos):
    comando = argumentos[0] if argumentos else "indice"
    if comando == "indice":
        gerarIndice()
        return 0
    if comando == "validar":
        return validar(testar=False)
    if comando == "testar":
        return validar(testar=True)
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
