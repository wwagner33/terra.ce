/* Executa o código Python dos exercícios com o Pyodide, fora da thread da página.
 *
 * A página (exercicios.js) manda {id, codigo, testes, urlPyodide} e recebe
 * mensagens de estado e, no fim, o resultado de executor.py. As execuções
 * entram numa fila: uma de cada vez. Se o código travar, a página encerra este
 * trabalhador e cria outro.
 */
"use strict";

let carregamento = null;
let fila = Promise.resolve();

function carregar(urlPyodide) {
  if (!carregamento) {
    importScripts(urlPyodide + "pyodide.js");
    carregamento = (async () => {
      const pyodide = await loadPyodide({ indexURL: urlPyodide });
      const resposta = await fetch(new URL("executor.py", self.location.href));
      if (!resposta.ok) throw new Error("não foi possível baixar o executor.py (HTTP " + resposta.status + ")");
      pyodide.FS.writeFile("/home/pyodide/executor.py", await resposta.text());
      pyodide.runPython("import sys; sys.path.insert(0, '/home/pyodide'); from executor import executarExercicio");
      return pyodide;
    })();
    carregamento.catch(() => {
      carregamento = null;
    });
  }
  return carregamento;
}

async function processar(mensagem) {
  const { id, codigo, testes, urlPyodide } = mensagem;
  const estado = (fase, texto) => self.postMessage({ id, tipo: "estado", fase, mensagem: texto });
  try {
    estado("carregando", "Carregando o Python no navegador (na primeira vez leva alguns segundos)…");
    const pyodide = await carregar(urlPyodide);
    estado("pacotes", "Carregando as bibliotecas usadas no código…");
    const todoCodigo = [codigo].concat(testes.map((teste) => teste.codigo)).join("\n");
    await pyodide.loadPackagesFromImports(todoCodigo);
    estado("executando", "Executando…");
    const executar = pyodide.globals.get("executarExercicio");
    try {
      const resultado = executar(codigo, JSON.stringify(testes));
      self.postMessage({ id, tipo: "resultado", resultado: JSON.parse(resultado) });
    } finally {
      executar.destroy();
    }
  } catch (erro) {
    self.postMessage({ id, tipo: "erro", mensagem: String((erro && erro.message) || erro) });
  }
}

self.onmessage = (evento) => {
  fila = fila.then(() => processar(evento.data));
};
