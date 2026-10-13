"""Executa o código de um exercício Python e as verificações dele.

O mesmo arquivo roda em dois lugares:

- no navegador, dentro do Pyodide (ver trabalhadorPython.js);
- na integração contínua, por ferramentas/exercicios.py, que confere se a
  solução oficial de cada exercício passa nas próprias verificações.

Os nomes seguem a convenção camelCase do projeto.
"""

import contextlib
import io
import json
import sys
import traceback

ARQUIVO_DO_ALUNO = "<seu código>"
LIMITE_DA_SAIDA = 8000


def resumirErro(linhasDoAluno):
    """Mensagem curta: a linha do código do aluno onde o erro aconteceu e o erro em si."""
    tipo, valor, rastro = sys.exc_info()
    quadros = [quadro for quadro in traceback.extract_tb(rastro) if quadro.filename == ARQUIVO_DO_ALUNO]
    partes = []
    if quadros:
        numero = quadros[-1].lineno
        trecho = linhasDoAluno[numero - 1].strip() if 0 < numero <= len(linhasDoAluno) else ""
        partes.append(f"Linha {numero}: {trecho}" if trecho else f"Linha {numero}")
    partes.extend(linha.rstrip("\n") for linha in traceback.format_exception_only(tipo, valor))
    return "\n".join(partes).strip()


def executarExercicio(codigo, testesJson):
    """Roda o código do aluno e depois cada verificação no mesmo espaço de nomes.

    ``testesJson`` é uma lista JSON de ``{"nome": ..., "codigo": ...}``. Devolve
    um JSON com a saída impressa, o erro (se houver) e o resultado de cada teste.
    """
    testes = json.loads(testesJson)
    espaco = {"__name__": "__main__"}
    saida = io.StringIO()
    resultado = {"saida": "", "erro": None, "testes": []}
    linhasDoAluno = codigo.splitlines()

    with contextlib.redirect_stdout(saida), contextlib.redirect_stderr(saida):
        try:
            exec(compile(codigo, ARQUIVO_DO_ALUNO, "exec"), espaco)
        except BaseException:
            resultado["erro"] = resumirErro(linhasDoAluno)

    if resultado["erro"] is None:
        for teste in testes:
            descarte = io.StringIO()
            with contextlib.redirect_stdout(descarte), contextlib.redirect_stderr(descarte):
                try:
                    exec(compile(teste["codigo"], "<verificação>", "exec"), espaco)
                    resultado["testes"].append({"nome": teste["nome"], "passou": True})
                except AssertionError as erro:
                    mensagem = str(erro) or "A verificação não passou."
                    resultado["testes"].append({"nome": teste["nome"], "passou": False, "mensagem": mensagem})
                except BaseException:
                    resultado["testes"].append(
                        {"nome": teste["nome"], "passou": False, "mensagem": resumirErro(linhasDoAluno)}
                    )

    resultado["saida"] = saida.getvalue()[-LIMITE_DA_SAIDA:]
    return json.dumps(resultado, ensure_ascii=False, default=str)
