/* Motor dos exercícios autocorrigidos do Treinamento Terra Digital.
 *
 * O filtro exercicios.lua transforma cada bloco ```exercicio em
 * <div class="exercicio"> com o YAML do exercício dentro de um <script>. Este
 * arquivo lê esse YAML, monta a interface conforme o "tipo", corrige a resposta
 * e guarda o progresso no localStorage do navegador.
 *
 * Tipos: escolha, multipla, numero, texto, ordenar, associar, python, sql,
 * aberta e checklist. O formato de cada um está em manual/material-didatico.qmd.
 */
(function () {
  "use strict";

  const CHAVE_PROGRESSO = "terraDigital.progresso.v1";
  const VERSAO_PYODIDE = "0.29.3";
  const URL_PYODIDE = "https://cdn.jsdelivr.net/pyodide/v" + VERSAO_PYODIDE + "/full/";
  const URL_SQLJS = "https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.12.0/";
  const TEMPO_LIMITE_PYTHON_MS = 30000;
  const LINHAS_MAXIMAS_TABELA = 20;

  const PASTA_DO_SCRIPT = (function () {
    const atual = document.currentScript && document.currentScript.src;
    return atual ? atual.slice(0, atual.lastIndexOf("/") + 1) : "";
  })();

  const NOMES_DOS_TIPOS = {
    escolha: "Escolha uma opção",
    multipla: "Marque todas as corretas",
    numero: "Resposta numérica",
    texto: "Resposta curta",
    ordenar: "Coloque em ordem",
    associar: "Associe as colunas",
    python: "Código Python",
    sql: "Consulta SQL",
    aberta: "Resposta aberta",
    checklist: "Prática guiada",
  };

  // ---------------------------------------------------------------- progresso

  const progresso = {
    ler() {
      try {
        const dados = JSON.parse(localStorage.getItem(CHAVE_PROGRESSO) || "{}") || {};
        return { exercicios: dados.exercicios || {}, rascunhos: dados.rascunhos || {} };
      } catch (erro) {
        return { exercicios: {}, rascunhos: {} };
      }
    },
    gravar(dados) {
      try {
        localStorage.setItem(CHAVE_PROGRESSO, JSON.stringify(dados));
      } catch (erro) {
        // Navegador sem armazenamento (janela anônima, bloqueio): o exercício
        // continua funcionando, só não lembra o resultado.
      }
      document.dispatchEvent(new CustomEvent("terraDigital:progresso"));
    },
    situacao(id) {
      return this.ler().exercicios[id];
    },
    registrarTentativa(id, acertou) {
      const dados = this.ler();
      const anterior = dados.exercicios[id] || { acertou: false, tentativas: 0 };
      dados.exercicios[id] = {
        acertou: anterior.acertou || acertou,
        tentativas: (anterior.tentativas || 0) + 1,
        atualizadoEm: new Date().toISOString(),
      };
      this.gravar(dados);
    },
    definirConcluido(id, concluido) {
      const dados = this.ler();
      const anterior = dados.exercicios[id] || { tentativas: 0 };
      dados.exercicios[id] = { ...anterior, acertou: concluido, atualizadoEm: new Date().toISOString() };
      this.gravar(dados);
    },
    lerRascunho(id) {
      return this.ler().rascunhos[id];
    },
    gravarRascunho(id, valor) {
      const dados = this.ler();
      dados.rascunhos[id] = valor;
      this.gravar(dados);
    },
    apagarRascunho(id) {
      const dados = this.ler();
      delete dados.rascunhos[id];
      this.gravar(dados);
    },
    exportar() {
      return JSON.stringify({ formato: CHAVE_PROGRESSO, exportadoEm: new Date().toISOString(), ...this.ler() }, null, 2);
    },
    importar(texto) {
      const dados = JSON.parse(texto);
      if (!dados || typeof dados.exercicios !== "object") {
        throw new Error("O arquivo não parece ser um progresso exportado deste site.");
      }
      const atual = this.ler();
      for (const [id, valor] of Object.entries(dados.exercicios)) {
        const anterior = atual.exercicios[id];
        if (!anterior || (valor && valor.acertou && !anterior.acertou)) {
          atual.exercicios[id] = valor;
        }
      }
      Object.assign(atual.rascunhos, dados.rascunhos || {});
      this.gravar(atual);
    },
    apagarTudo() {
      try {
        localStorage.removeItem(CHAVE_PROGRESSO);
      } catch (erro) {
        // nada a apagar
      }
      document.dispatchEvent(new CustomEvent("terraDigital:progresso"));
    },
  };

  // ------------------------------------------------------------ utilitários

  function escaparHtml(texto) {
    return String(texto ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /** Markdown de uma linha: `código`, **negrito**, *itálico* e [link](url). */
  function renderizarInline(texto) {
    const trechosDeCodigo = [];
    let html = escaparHtml(texto).replace(/`([^`]+)`/g, (_, codigo) => {
      trechosDeCodigo.push(codigo);
      return "\u0000" + (trechosDeCodigo.length - 1) + "\u0000";
    });
    html = html
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?!\w)/g, "$1<em>$2</em>")
      .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (trecho, rotulo, endereco) =>
        // Só http(s) e caminhos relativos: nada de "javascript:" vindo do YAML.
        /^(https?:\/\/|\.{0,2}\/|#)/.test(endereco) || !/^[a-z][a-z0-9+.-]*:/i.test(endereco)
          ? '<a href="' + endereco + '" target="_blank" rel="noopener">' + rotulo + "</a>"
          : rotulo
      );
    return html.replace(/\u0000(\d+)\u0000/g, (_, i) => "<code>" + trechosDeCodigo[Number(i)] + "</code>");
  }

  /** Markdown simples em blocos: parágrafos, listas e blocos de código cercados. */
  function renderizarMarkdown(texto) {
    const linhas = String(texto ?? "").replace(/\r\n/g, "\n").split("\n");
    const html = [];
    const ehItem = (linha) => /^\s*[-*] /.test(linha);
    const ehItemNumerado = (linha) => /^\s*\d+[.)] /.test(linha);
    let i = 0;
    while (i < linhas.length) {
      const linha = linhas[i];
      if (/^\s*```/.test(linha)) {
        const bloco = [];
        i += 1;
        while (i < linhas.length && !/^\s*```/.test(linhas[i])) {
          bloco.push(linhas[i]);
          i += 1;
        }
        i += 1;
        html.push('<pre class="exercicio-trecho"><code>' + escaparHtml(bloco.join("\n")) + "</code></pre>");
      } else if (ehItem(linha) || ehItemNumerado(linha)) {
        const numerada = ehItemNumerado(linha);
        const itens = [];
        while (i < linhas.length && (numerada ? ehItemNumerado(linhas[i]) : ehItem(linhas[i]))) {
          itens.push(linhas[i].replace(/^\s*(?:[-*]|\d+[.)]) /, ""));
          i += 1;
        }
        const tag = numerada ? "ol" : "ul";
        html.push("<" + tag + ">" + itens.map((item) => "<li>" + renderizarInline(item) + "</li>").join("") + "</" + tag + ">");
      } else if (linha.trim() === "") {
        i += 1;
      } else {
        const paragrafo = [];
        while (
          i < linhas.length &&
          linhas[i].trim() !== "" &&
          !/^\s*```/.test(linhas[i]) &&
          !ehItem(linhas[i]) &&
          !ehItemNumerado(linhas[i])
        ) {
          paragrafo.push(linhas[i].trim());
          i += 1;
        }
        html.push("<p>" + renderizarInline(paragrafo.join(" ")) + "</p>");
      }
    }
    return html.join("");
  }

  function criar(tag, atributos, conteudoHtml) {
    const elemento = document.createElement(tag);
    for (const [nome, valor] of Object.entries(atributos || {})) {
      if (valor === undefined || valor === null || valor === false) continue;
      if (nome === "classe") elemento.className = valor;
      else elemento.setAttribute(nome, valor === true ? "" : valor);
    }
    if (conteudoHtml !== undefined) elemento.innerHTML = conteudoHtml;
    return elemento;
  }

  function botao(rotulo, classe) {
    return criar("button", { type: "button", classe: "btn btn-sm " + (classe || "btn-outline-secondary") }, rotulo);
  }

  function normalizarTexto(texto) {
    return String(texto ?? "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .replace(/[`"'“”‘’]/g, "")
      .replace(/\s+/g, " ")
      .trim()
      .replace(/[.;!?]+$/, "")
      .trim();
  }

  /** Lê "0,4", "0.4", "1.234,5" ou "12 ha" como número. */
  function lerNumero(texto) {
    const encontrado = String(texto ?? "").replace(/\s+/g, "").match(/[-+]?\d[\d.,]*(?:[eE][-+]?\d+)?/);
    if (!encontrado) return NaN;
    let numero = encontrado[0];
    const virgula = numero.lastIndexOf(",");
    const ponto = numero.lastIndexOf(".");
    if (virgula > -1 && ponto > -1) {
      numero = virgula > ponto ? numero.replace(/\./g, "").replace(",", ".") : numero.replace(/,/g, "");
    } else if (virgula > -1) {
      numero = numero.replace(/,/g, ".");
    }
    return Number(numero);
  }

  function formatarNumero(numero) {
    return Number(numero).toLocaleString("pt-BR", { maximumFractionDigits: 6 });
  }

  function hashTexto(texto) {
    let hash = 2166136261;
    for (let i = 0; i < texto.length; i += 1) {
      hash ^= texto.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return hash >>> 0;
  }

  /** Embaralhamento estável: o mesmo exercício sempre aparece na mesma ordem. */
  function embaralhar(lista, semente) {
    const copia = lista.slice();
    let estado = hashTexto(String(semente));
    const aleatorio = () => {
      estado = (estado + 0x6d2b79f5) | 0;
      let t = Math.imul(estado ^ (estado >>> 15), 1 | estado);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
    for (let i = copia.length - 1; i > 0; i -= 1) {
      const j = Math.floor(aleatorio() * (i + 1));
      [copia[i], copia[j]] = [copia[j], copia[i]];
    }
    return copia;
  }

  function textoDaOpcao(opcao) {
    return typeof opcao === "string" ? opcao : String(opcao.texto ?? "");
  }

  function prepararEditor(areaDeTexto) {
    // Tab insere quatro espaços. Esc seguido de Tab sai do editor (sem prender o teclado).
    let liberarTab = false;
    areaDeTexto.addEventListener("keydown", (evento) => {
      if (evento.key === "Escape") {
        liberarTab = true;
        return;
      }
      if (evento.key === "Tab" && !evento.shiftKey && !liberarTab) {
        evento.preventDefault();
        const inicio = areaDeTexto.selectionStart;
        const fim = areaDeTexto.selectionEnd;
        areaDeTexto.setRangeText("    ", inicio, fim, "end");
        areaDeTexto.dispatchEvent(new Event("input"));
      }
      if (evento.key !== "Tab") liberarTab = false;
    });
    const ajustarAltura = () => {
      const linhas = areaDeTexto.value.split("\n").length;
      areaDeTexto.rows = Math.min(Math.max(linhas + 1, 4), 30);
    };
    areaDeTexto.addEventListener("input", ajustarAltura);
    ajustarAltura();
  }

  // ------------------------------------------------------ executor de Python

  const executorPython = {
    trabalhador: null,
    proximoId: 1,
    pendentes: new Map(),

    obterTrabalhador() {
      if (!this.trabalhador) {
        this.trabalhador = new Worker(PASTA_DO_SCRIPT + "trabalhadorPython.js");
        this.trabalhador.onmessage = (evento) => this.receber(evento.data);
        this.trabalhador.onerror = (evento) => {
          evento.preventDefault();
          this.reiniciar("O Python do navegador parou com erro: " + (evento.message || "erro desconhecido") + ".");
        };
      }
      return this.trabalhador;
    },

    executar(codigo, testes, aoMudarEstado) {
      return new Promise((resolver, rejeitar) => {
        const id = this.proximoId;
        this.proximoId += 1;
        this.pendentes.set(id, { resolver, rejeitar, aoMudarEstado, cronometro: null });
        try {
          this.obterTrabalhador().postMessage({ id, codigo, testes: testes || [], urlPyodide: URL_PYODIDE });
        } catch (erro) {
          this.pendentes.delete(id);
          rejeitar(new Error("Este navegador não conseguiu iniciar o Python. Abra o site por um endereço http(s), não como arquivo local."));
        }
      });
    },

    receber(mensagem) {
      const pendente = this.pendentes.get(mensagem.id);
      if (!pendente) return;
      if (mensagem.tipo === "estado") {
        if (pendente.aoMudarEstado) pendente.aoMudarEstado(mensagem.mensagem);
        if (mensagem.fase === "executando" && !pendente.cronometro) {
          pendente.cronometro = setTimeout(
            () => this.reiniciar("Tempo esgotado (" + TEMPO_LIMITE_PYTHON_MS / 1000 + " s). Seu código pode ter um laço que não termina."),
            TEMPO_LIMITE_PYTHON_MS
          );
        }
        return;
      }
      clearTimeout(pendente.cronometro);
      this.pendentes.delete(mensagem.id);
      if (mensagem.tipo === "resultado") pendente.resolver(mensagem.resultado);
      else pendente.rejeitar(new Error(mensagem.mensagem));
    },

    reiniciar(motivo) {
      if (this.trabalhador) this.trabalhador.terminate();
      this.trabalhador = null;
      for (const pendente of this.pendentes.values()) {
        clearTimeout(pendente.cronometro);
        pendente.rejeitar(new Error(motivo));
      }
      this.pendentes.clear();
    },
  };

  // --------------------------------------------------------- executor de SQL

  const executorSql = {
    carregamento: null,

    carregar() {
      if (!this.carregamento) {
        this.carregamento = new Promise((resolver, rejeitar) => {
          const script = document.createElement("script");
          script.src = URL_SQLJS + "sql-wasm.js";
          script.onload = () =>
            window.initSqlJs({ locateFile: (arquivo) => URL_SQLJS + arquivo }).then(resolver, rejeitar);
          script.onerror = () => rejeitar(new Error("Não foi possível baixar o SQLite do navegador (sql.js). Confira a conexão."));
          document.head.appendChild(script);
        }).catch((erro) => {
          this.carregamento = null;
          throw erro;
        });
      }
      return this.carregamento;
    },

    async consultar(nomeDados, consulta) {
      const SQL = await this.carregar();
      const banco = new SQL.Database();
      try {
        const script = (window.TerraDigitalDadosSql || {})[nomeDados];
        if (nomeDados && !script) throw new Error('Conjunto de dados "' + nomeDados + '" não encontrado.');
        if (script) banco.exec(script);
        const resultados = banco.exec(consulta);
        return resultados.length ? resultados[resultados.length - 1] : { columns: [], values: [] };
      } finally {
        banco.close();
      }
    },
  };

  function valorSqlComparavel(valor) {
    if (typeof valor === "number") return Math.round(valor * 1e6) / 1e6;
    if (valor === null || valor === undefined) return null;
    return String(valor);
  }

  function compararResultadosSql(obtido, esperado, considerarOrdem) {
    if (obtido.columns.length !== esperado.columns.length) {
      return "Sua consulta devolveu " + obtido.columns.length + " coluna(s); o esperado são " + esperado.columns.length + ".";
    }
    if (obtido.values.length !== esperado.values.length) {
      return "Sua consulta devolveu " + obtido.values.length + " linha(s); o esperado são " + esperado.values.length + ".";
    }
    const linhas = (resultado) => resultado.values.map((linha) => JSON.stringify(linha.map(valorSqlComparavel)));
    const a = linhas(obtido);
    const b = linhas(esperado);
    if (a.every((linha, i) => linha === b[i])) return null;
    const ordenadasA = a.slice().sort();
    const ordenadasB = b.slice().sort();
    const mesmasLinhas = ordenadasA.every((linha, i) => linha === ordenadasB[i]);
    if (mesmasLinhas) return considerarOrdem ? "As linhas estão certas, mas a ordem não. Confira o ORDER BY." : null;
    return "Os valores não conferem com o esperado.";
  }

  function tabelaSql(resultado) {
    if (!resultado.columns.length) return '<p class="exercicio-nota">A consulta não devolveu nenhuma tabela.</p>';
    const cabecalho = resultado.columns.map((coluna) => "<th>" + escaparHtml(coluna) + "</th>").join("");
    const linhas = resultado.values
      .slice(0, LINHAS_MAXIMAS_TABELA)
      .map((linha) => "<tr>" + linha.map((valor) => "<td>" + escaparHtml(valor === null ? "NULL" : valor) + "</td>").join("") + "</tr>")
      .join("");
    const restante = resultado.values.length - LINHAS_MAXIMAS_TABELA;
    const aviso = restante > 0 ? '<p class="exercicio-nota">… e mais ' + restante + " linha(s).</p>" : "";
    return (
      '<div class="table-responsive"><table class="table table-sm exercicio-tabela"><thead><tr>' +
      cabecalho +
      "</tr></thead><tbody>" +
      linhas +
      "</tbody></table></div>" +
      aviso
    );
  }

  // ------------------------------------------------------------ tipos

  const TIPOS = {
    escolha: {
      montar(ex) {
        const opcoes = ex.dados.opcoes || [];
        const nome = ex.id + "-opcao";
        ex.corpo.innerHTML = opcoes
          .map(
            (opcao, i) =>
              '<label class="exercicio-opcao"><input type="radio" name="' + escaparHtml(nome) + '" value="' + i + '"> <span>' +
              renderizarInline(textoDaOpcao(opcao)) +
              "</span></label>"
          )
          .join("");
      },
      verificar(ex) {
        const marcada = ex.corpo.querySelector("input:checked");
        if (!marcada) return { neutro: true, html: "Escolha uma das opções." };
        const opcao = ex.dados.opcoes[Number(marcada.value)];
        const acertou = typeof opcao === "object" && opcao.correta === true;
        const explicacaoDaOpcao = typeof opcao === "object" && opcao.explicacao ? renderizarMarkdown(opcao.explicacao) : "";
        return { acertou, html: explicacaoDaOpcao };
      },
      solucao(ex) {
        const correta = (ex.dados.opcoes || []).find((opcao) => typeof opcao === "object" && opcao.correta);
        return correta ? "<p>Resposta: <strong>" + renderizarInline(textoDaOpcao(correta)) + "</strong></p>" : "";
      },
      recomecar(ex) {
        ex.corpo.querySelectorAll("input").forEach((entrada) => (entrada.checked = false));
      },
    },

    multipla: {
      montar(ex) {
        ex.corpo.innerHTML = (ex.dados.opcoes || [])
          .map(
            (opcao, i) =>
              '<label class="exercicio-opcao"><input type="checkbox" value="' + i + '"> <span>' +
              renderizarInline(textoDaOpcao(opcao)) +
              "</span></label>"
          )
          .join("");
      },
      verificar(ex) {
        const marcadas = new Set(Array.from(ex.corpo.querySelectorAll("input:checked")).map((entrada) => Number(entrada.value)));
        if (!marcadas.size) return { neutro: true, html: "Marque pelo menos uma opção." };
        const opcoes = ex.dados.opcoes || [];
        let erradas = 0;
        const comentarios = [];
        opcoes.forEach((opcao, i) => {
          const correta = typeof opcao === "object" && opcao.correta === true;
          if (correta !== marcadas.has(i)) erradas += 1;
          if (marcadas.has(i) && !correta && typeof opcao === "object" && opcao.explicacao) {
            comentarios.push("<li>" + renderizarInline(textoDaOpcao(opcao)) + ": " + renderizarInline(opcao.explicacao) + "</li>");
          }
        });
        if (!erradas) return { acertou: true, html: "" };
        const resumo = "<p>" + erradas + (erradas === 1 ? " opção está" : " opções estão") + " marcada(s) ou desmarcada(s) por engano.</p>";
        return { acertou: false, html: resumo + (comentarios.length ? "<ul>" + comentarios.join("") + "</ul>" : "") };
      },
      solucao(ex) {
        const corretas = (ex.dados.opcoes || []).filter((opcao) => typeof opcao === "object" && opcao.correta);
        return "<p>Corretas:</p><ul>" + corretas.map((opcao) => "<li>" + renderizarInline(textoDaOpcao(opcao)) + "</li>").join("") + "</ul>";
      },
      recomecar(ex) {
        ex.corpo.querySelectorAll("input").forEach((entrada) => (entrada.checked = false));
      },
    },

    numero: {
      montar(ex) {
        const unidade = ex.dados.unidade ? '<span class="input-group-text">' + escaparHtml(ex.dados.unidade) + "</span>" : "";
        ex.corpo.innerHTML =
          '<div class="input-group input-group-sm exercicio-campo-curto"><input type="text" inputmode="decimal" class="form-control" aria-label="Sua resposta" placeholder="Sua resposta">' +
          unidade +
          "</div>";
        ex.corpo.querySelector("input").addEventListener("keydown", (evento) => {
          if (evento.key === "Enter") ex.verificar();
        });
      },
      verificar(ex) {
        const texto = ex.corpo.querySelector("input").value;
        if (!texto.trim()) return { neutro: true, html: "Digite um número." };
        const valor = lerNumero(texto);
        if (Number.isNaN(valor)) return { neutro: true, html: "Não consegui ler um número em “" + escaparHtml(texto) + "”." };
        const tolerancia = Number(ex.dados.tolerancia || 0);
        const acertou = Math.abs(valor - Number(ex.dados.resposta)) <= tolerancia + 1e-12;
        return { acertou, html: acertou ? "" : "<p>Você respondeu " + formatarNumero(valor) + ".</p>" };
      },
      solucao(ex) {
        const unidade = ex.dados.unidade ? " " + escaparHtml(ex.dados.unidade) : "";
        return "<p>Resposta: <strong>" + formatarNumero(ex.dados.resposta) + unidade + "</strong></p>";
      },
      recomecar(ex) {
        ex.corpo.querySelector("input").value = "";
      },
    },

    texto: {
      montar(ex) {
        ex.corpo.innerHTML =
          '<input type="text" class="form-control form-control-sm exercicio-campo-curto" aria-label="Sua resposta" placeholder="Sua resposta" autocomplete="off" spellcheck="false">';
        ex.corpo.querySelector("input").addEventListener("keydown", (evento) => {
          if (evento.key === "Enter") ex.verificar();
        });
      },
      verificar(ex) {
        const texto = ex.corpo.querySelector("input").value;
        if (!texto.trim()) return { neutro: true, html: "Digite sua resposta." };
        const normalizado = normalizarTexto(texto);
        const aceitas = (ex.dados.respostas || []).map(normalizarTexto);
        let acertou = aceitas.includes(normalizado);
        if (!acertou && ex.dados.regex) acertou = new RegExp(ex.dados.regex, "i").test(texto.trim());
        return { acertou, html: "" };
      },
      solucao(ex) {
        const respostas = ex.dados.respostas || [];
        return respostas.length ? "<p>Resposta esperada: <strong>" + renderizarInline(respostas[0]) + "</strong></p>" : "";
      },
      recomecar(ex) {
        ex.corpo.querySelector("input").value = "";
      },
    },

    ordenar: {
      montar(ex) {
        const itens = (ex.dados.itens || []).map((texto, indice) => ({ texto, indice }));
        let ordem = embaralhar(itens, ex.id);
        if (ordem.length > 1 && ordem.every((item, i) => item.indice === i)) ordem = ordem.slice(1).concat(ordem[0]);
        ex.ordemAtual = ordem;
        this.desenhar(ex);
      },
      desenhar(ex) {
        const lista = criar("ol", { classe: "exercicio-ordenar" });
        ex.ordemAtual.forEach((item, posicao) => {
          const linha = criar("li", {}, '<span class="exercicio-ordenar-texto">' + renderizarInline(item.texto) + "</span>");
          const controles = criar("span", { classe: "exercicio-ordenar-controles" });
          const subir = botao("↑", "btn-outline-secondary");
          const descer = botao("↓", "btn-outline-secondary");
          subir.setAttribute("aria-label", "Subir: " + item.texto);
          descer.setAttribute("aria-label", "Descer: " + item.texto);
          subir.disabled = posicao === 0;
          descer.disabled = posicao === ex.ordemAtual.length - 1;
          subir.addEventListener("click", () => this.mover(ex, posicao, -1));
          descer.addEventListener("click", () => this.mover(ex, posicao, 1));
          controles.append(subir, descer);
          linha.append(controles);
          lista.append(linha);
        });
        ex.corpo.replaceChildren(lista);
      },
      mover(ex, posicao, deslocamento) {
        const destino = posicao + deslocamento;
        [ex.ordemAtual[posicao], ex.ordemAtual[destino]] = [ex.ordemAtual[destino], ex.ordemAtual[posicao]];
        this.desenhar(ex);
        const botoes = ex.corpo.querySelectorAll(".exercicio-ordenar li")[destino].querySelectorAll("button");
        (deslocamento < 0 ? botoes[0] : botoes[1]).focus();
      },
      verificar(ex) {
        const certos = ex.ordemAtual.filter((item, i) => item.indice === i).length;
        const total = ex.ordemAtual.length;
        return { acertou: certos === total, html: certos === total ? "" : "<p>" + certos + " de " + total + " itens estão na posição certa.</p>" };
      },
      solucao(ex) {
        return "<ol>" + (ex.dados.itens || []).map((item) => "<li>" + renderizarInline(item) + "</li>").join("") + "</ol>";
      },
      recomecar(ex) {
        this.montar(ex);
      },
    },

    associar: {
      montar(ex) {
        const pares = ex.dados.pares || [];
        const definicoes = embaralhar(pares.map((par, i) => ({ texto: par.definicao, indice: i })), ex.id + "-definicoes");
        const opcoesHtml =
          '<option value="">Escolha…</option>' +
          definicoes.map((d) => '<option value="' + d.indice + '">' + escaparHtml(d.texto) + "</option>").join("");
        ex.corpo.innerHTML =
          '<div class="exercicio-associar">' +
          pares
            .map(
              (par, i) =>
                '<label class="exercicio-associar-linha"><span class="exercicio-associar-termo">' +
                renderizarInline(par.termo) +
                '</span><select class="form-select form-select-sm" data-par="' +
                i +
                '">' +
                opcoesHtml +
                "</select></label>"
            )
            .join("") +
          "</div>";
      },
      verificar(ex) {
        const selecoes = Array.from(ex.corpo.querySelectorAll("select"));
        if (selecoes.some((s) => s.value === "")) return { neutro: true, html: "Associe todos os itens antes de verificar." };
        const certos = selecoes.filter((s) => s.value === s.dataset.par).length;
        selecoes.forEach((s) => s.classList.toggle("is-invalid", s.value !== s.dataset.par));
        return { acertou: certos === selecoes.length, html: certos === selecoes.length ? "" : "<p>" + certos + " de " + selecoes.length + " associações corretas. As erradas estão destacadas.</p>" };
      },
      solucao(ex) {
        return (
          "<ul>" +
          (ex.dados.pares || []).map((par) => "<li>" + renderizarInline(par.termo) + " → " + renderizarInline(par.definicao) + "</li>").join("") +
          "</ul>"
        );
      },
      recomecar(ex) {
        ex.corpo.querySelectorAll("select").forEach((s) => {
          s.value = "";
          s.classList.remove("is-invalid");
        });
      },
    },

    python: {
      montar(ex) {
        const rascunho = progresso.lerRascunho(ex.id);
        const area = criar("textarea", {
          classe: "form-control exercicio-editor",
          spellcheck: "false",
          autocapitalize: "off",
          autocomplete: "off",
          "aria-label": "Editor de código Python. Tab insere espaços; Esc e depois Tab sai do editor.",
        });
        area.value = typeof rascunho === "string" ? rascunho : String(ex.dados.inicial || "");
        let temporizador = null;
        area.addEventListener("input", () => {
          clearTimeout(temporizador);
          temporizador = setTimeout(() => progresso.gravarRascunho(ex.id, area.value), 600);
        });
        ex.editor = area;
        ex.saida = criar("div", { classe: "exercicio-saida", hidden: true });
        ex.corpo.replaceChildren(area, ex.saida);
        prepararEditor(area);
        const executar = botao("▶ Executar", "btn-outline-primary");
        executar.addEventListener("click", () => this.rodar(ex, false));
        ex.acoesExtras.push(executar);
      },
      async rodar(ex, comTestes) {
        ex.ocupado(true);
        ex.saida.hidden = false;
        ex.saida.innerHTML = '<p class="exercicio-nota">Preparando…</p>';
        try {
          const resultado = await executorPython.executar(ex.editor.value, comTestes ? ex.dados.testes : [], (mensagem) => {
            ex.saida.innerHTML = '<p class="exercicio-nota">' + escaparHtml(mensagem) + "</p>";
          });
          return this.mostrarResultado(ex, resultado, comTestes);
        } catch (erro) {
          ex.saida.innerHTML = '<pre class="exercicio-erro">' + escaparHtml(erro.message) + "</pre>";
          return { neutro: true, html: "Não foi possível executar o código." };
        } finally {
          ex.ocupado(false);
        }
      },
      mostrarResultado(ex, resultado, comTestes) {
        const partes = [];
        if (resultado.saida) partes.push('<div class="exercicio-rotulo">Saída</div><pre class="exercicio-console">' + escaparHtml(resultado.saida) + "</pre>");
        if (resultado.erro) partes.push('<div class="exercicio-rotulo">Erro</div><pre class="exercicio-erro">' + escaparHtml(resultado.erro) + "</pre>");
        if (comTestes && !resultado.erro) {
          const itens = resultado.testes
            .map(
              (teste) =>
                '<li class="' + (teste.passou ? "passou" : "falhou") + '">' +
                (teste.passou ? "✓ " : "✗ ") +
                escaparHtml(teste.nome) +
                (teste.passou ? "" : '<div class="exercicio-teste-mensagem">' + escaparHtml(teste.mensagem) + "</div>") +
                "</li>"
            )
            .join("");
          partes.push('<div class="exercicio-rotulo">Verificações</div><ul class="exercicio-testes">' + itens + "</ul>");
        }
        if (!partes.length) partes.push('<p class="exercicio-nota">O código rodou sem imprimir nada.</p>');
        ex.saida.innerHTML = partes.join("");
        if (!comTestes) return null;
        if (resultado.erro) return { acertou: false, html: "<p>O código parou com erro antes das verificações.</p>" };
        const falhas = resultado.testes.filter((teste) => !teste.passou).length;
        return { acertou: falhas === 0, html: falhas ? "<p>" + falhas + " verificação(ões) não passaram.</p>" : "" };
      },
      verificar(ex) {
        return this.rodar(ex, true);
      },
      solucao(ex) {
        return '<pre class="exercicio-trecho"><code>' + escaparHtml(ex.dados.solucao || "") + "</code></pre>";
      },
      recomecar(ex) {
        ex.editor.value = String(ex.dados.inicial || "");
        ex.editor.dispatchEvent(new Event("input"));
        progresso.apagarRascunho(ex.id);
        ex.saida.hidden = true;
      },
    },

    sql: {
      montar(ex) {
        const rascunho = progresso.lerRascunho(ex.id);
        const area = criar("textarea", {
          classe: "form-control exercicio-editor",
          spellcheck: "false",
          autocapitalize: "off",
          "aria-label": "Editor de consulta SQL",
        });
        area.value = typeof rascunho === "string" ? rascunho : String(ex.dados.inicial || "");
        let temporizador = null;
        area.addEventListener("input", () => {
          clearTimeout(temporizador);
          temporizador = setTimeout(() => progresso.gravarRascunho(ex.id, area.value), 600);
        });
        ex.editor = area;
        ex.saida = criar("div", { classe: "exercicio-saida", hidden: true });
        ex.corpo.replaceChildren(area, ex.saida);
        prepararEditor(area);
        const executar = botao("▶ Executar", "btn-outline-primary");
        executar.addEventListener("click", () => this.rodar(ex, false));
        ex.acoesExtras.push(executar);
      },
      async rodar(ex, comparar) {
        ex.ocupado(true);
        ex.saida.hidden = false;
        ex.saida.innerHTML = '<p class="exercicio-nota">Carregando o SQLite do navegador…</p>';
        try {
          const obtido = await executorSql.consultar(ex.dados.dados, ex.editor.value);
          ex.saida.innerHTML = '<div class="exercicio-rotulo">Resultado</div>' + tabelaSql(obtido);
          if (!comparar) return null;
          const esperado = await executorSql.consultar(ex.dados.dados, ex.dados.solucao);
          const problema = compararResultadosSql(obtido, esperado, ex.dados.ordem === true);
          return { acertou: problema === null, html: problema ? "<p>" + escaparHtml(problema) + "</p>" : "" };
        } catch (erro) {
          ex.saida.innerHTML = '<pre class="exercicio-erro">' + escaparHtml(erro.message) + "</pre>";
          return comparar ? { acertou: false, html: "<p>A consulta tem erro. Leia a mensagem acima.</p>" } : null;
        } finally {
          ex.ocupado(false);
        }
      },
      verificar(ex) {
        return this.rodar(ex, true);
      },
      solucao(ex) {
        return '<pre class="exercicio-trecho"><code>' + escaparHtml(ex.dados.solucao || "") + "</code></pre>";
      },
      recomecar(ex) {
        ex.editor.value = String(ex.dados.inicial || "");
        ex.editor.dispatchEvent(new Event("input"));
        progresso.apagarRascunho(ex.id);
        ex.saida.hidden = true;
      },
    },

    aberta: {
      textoDoBotao: "Comparar com a resposta comentada",
      montar(ex) {
        const rascunho = progresso.lerRascunho(ex.id);
        const area = criar("textarea", { classe: "form-control exercicio-resposta-aberta", rows: 5, "aria-label": "Sua resposta" });
        area.value = typeof rascunho === "string" ? rascunho : "";
        let temporizador = null;
        area.addEventListener("input", () => {
          clearTimeout(temporizador);
          temporizador = setTimeout(() => progresso.gravarRascunho(ex.id, area.value), 600);
        });
        ex.corpo.replaceChildren(area);
        ex.respostaAberta = area;
      },
      verificar(ex) {
        if (!ex.respostaAberta.value.trim()) return { neutro: true, html: "Escreva sua resposta antes de comparar." };
        const caixa = criar(
          "div",
          { classe: "exercicio-comentada" },
          '<div class="exercicio-rotulo">Resposta comentada</div>' + renderizarMarkdown(ex.dados.resposta || "")
        );
        const confirmacao = criar(
          "label",
          { classe: "exercicio-opcao" },
          '<input type="checkbox"> <span>Minha resposta cobre os pontos principais.</span>'
        );
        const marcador = confirmacao.querySelector("input");
        marcador.checked = Boolean((progresso.situacao(ex.id) || {}).acertou);
        marcador.addEventListener("change", () => {
          progresso.definirConcluido(ex.id, marcador.checked);
          ex.atualizarSituacao();
        });
        caixa.append(confirmacao);
        return { neutro: true, html: "", elemento: caixa, semRegistro: true };
      },
      solucao() {
        return "";
      },
      recomecar(ex) {
        ex.respostaAberta.value = "";
        progresso.apagarRascunho(ex.id);
      },
    },

    checklist: {
      semBotaoVerificar: true,
      montar(ex) {
        const marcados = progresso.lerRascunho(ex.id) || [];
        ex.corpo.innerHTML = (ex.dados.itens || [])
          .map(
            (item, i) =>
              '<label class="exercicio-opcao"><input type="checkbox" value="' + i + '"' + (marcados[i] ? " checked" : "") + "> <span>" +
              renderizarInline(item) +
              "</span></label>"
          )
          .join("");
        ex.corpo.querySelectorAll("input").forEach((entrada) =>
          entrada.addEventListener("change", () => {
            const estado = Array.from(ex.corpo.querySelectorAll("input")).map((e) => e.checked);
            progresso.gravarRascunho(ex.id, estado);
            progresso.definirConcluido(ex.id, estado.every(Boolean));
            ex.atualizarSituacao();
          })
        );
      },
      verificar() {
        return null;
      },
      solucao() {
        return "";
      },
      recomecar(ex) {
        ex.corpo.querySelectorAll("input").forEach((entrada) => (entrada.checked = false));
        progresso.apagarRascunho(ex.id);
        progresso.definirConcluido(ex.id, false);
        ex.atualizarSituacao();
      },
    },
  };

  // ------------------------------------------------------------- exercício

  class Exercicio {
    constructor(raiz, dados, numero) {
      this.raiz = raiz;
      this.dados = dados;
      this.id = String(dados.id);
      this.numero = numero;
      this.tipo = TIPOS[dados.tipo];
      this.acoesExtras = [];
      this.botoes = [];
    }

    montar() {
      const raiz = this.raiz;
      raiz.id = "exercicio-" + this.id;
      raiz.dataset.tipo = this.dados.tipo;
      raiz.dataset.exercicio = this.id;
      raiz.setAttribute("role", "group");
      raiz.setAttribute("aria-labelledby", raiz.id + "-titulo");

      const cabecalho = criar(
        "div",
        { classe: "exercicio-cabecalho" },
        '<span class="exercicio-numero" id="' + raiz.id + '-titulo">' +
          (this.dados.tipo === "checklist" ? "Prática" : "Exercício") + " " + this.numero +
          '</span><span class="exercicio-tipo">' +
          escaparHtml(NOMES_DOS_TIPOS[this.dados.tipo]) +
          '</span><span class="exercicio-situacao" aria-live="polite"></span>'
      );
      this.selo = cabecalho.querySelector(".exercicio-situacao");
      const enunciado = criar("div", { classe: "exercicio-enunciado" }, renderizarMarkdown(this.dados.pergunta));
      this.corpo = criar("div", { classe: "exercicio-corpo" });
      this.acoes = criar("div", { classe: "exercicio-acoes" });
      this.retorno = criar("div", { classe: "exercicio-retorno", role: "status", "aria-live": "polite" });
      this.areaDica = criar("div", { classe: "exercicio-dica", hidden: true }, renderizarMarkdown(this.dados.dica || ""));
      this.areaSolucao = criar("div", { classe: "exercicio-solucao", hidden: true });

      raiz.replaceChildren(cabecalho, enunciado, this.corpo, this.acoes, this.areaDica, this.retorno, this.areaSolucao);
      this.tipo.montar(this);

      if (!this.tipo.semBotaoVerificar) {
        const verificar = botao(this.tipo.textoDoBotao || "Verificar", "btn-primary");
        verificar.addEventListener("click", () => this.verificar());
        this.acoes.append(verificar);
        this.botoes.push(verificar);
      }
      this.acoesExtras.forEach((extra) => {
        this.acoes.append(extra);
        this.botoes.push(extra);
      });
      if (this.dados.dica) {
        const dica = botao("Dica", "btn-outline-secondary");
        dica.setAttribute("aria-expanded", "false");
        dica.addEventListener("click", () => {
          this.areaDica.hidden = !this.areaDica.hidden;
          dica.setAttribute("aria-expanded", String(!this.areaDica.hidden));
        });
        this.acoes.append(dica);
      }
      const solucaoHtml = this.tipo.solucao(this);
      if (solucaoHtml || this.dados.explicacao) {
        this.botaoSolucao = botao("Ver solução", "btn-outline-secondary");
        this.botaoSolucao.hidden = !(progresso.situacao(this.id) || {}).tentativas;
        this.botaoSolucao.addEventListener("click", () => this.mostrarSolucao());
        this.acoes.append(this.botaoSolucao);
      }
      const recomecar = botao("Recomeçar", "btn-link");
      recomecar.addEventListener("click", () => {
        this.tipo.recomecar(this);
        this.retorno.replaceChildren();
        this.retorno.className = "exercicio-retorno";
        this.areaSolucao.hidden = true;
      });
      this.acoes.append(recomecar);
      this.atualizarSituacao();
    }

    ocupado(estado) {
      this.botoes.forEach((b) => (b.disabled = estado));
      this.raiz.classList.toggle("exercicio-ocupado", estado);
    }

    atualizarSituacao() {
      const situacao = progresso.situacao(this.id) || {};
      this.raiz.classList.toggle("exercicio-resolvido", Boolean(situacao.acertou));
      this.selo.textContent = situacao.acertou ? (this.dados.tipo === "checklist" ? "✓ Concluída" : "✓ Resolvido") : "";
    }

    async verificar() {
      let resultado;
      try {
        resultado = await this.tipo.verificar(this);
      } catch (erro) {
        resultado = { neutro: true, html: escaparHtml(erro.message) };
      }
      if (!resultado) return;
      this.retorno.replaceChildren();
      if (resultado.neutro) {
        this.retorno.className = "exercicio-retorno neutro";
        if (resultado.html) this.retorno.innerHTML = "<p>" + resultado.html + "</p>";
        if (resultado.elemento) this.retorno.append(resultado.elemento);
        if (!resultado.semRegistro) return;
      } else {
        progresso.registrarTentativa(this.id, resultado.acertou);
        this.retorno.className = "exercicio-retorno " + (resultado.acertou ? "certo" : "errado");
        const titulo = resultado.acertou ? "<p><strong>Correto!</strong></p>" : "<p><strong>Ainda não.</strong> Revise e tente de novo.</p>";
        const explicacao = resultado.acertou && this.dados.explicacao ? renderizarMarkdown(this.dados.explicacao) : "";
        this.retorno.innerHTML = titulo + (resultado.html || "") + explicacao;
        if (this.botaoSolucao) this.botaoSolucao.hidden = false;
      }
      this.atualizarSituacao();
    }

    mostrarSolucao() {
      const explicacao = this.dados.explicacao ? renderizarMarkdown(this.dados.explicacao) : "";
      this.areaSolucao.innerHTML = '<div class="exercicio-rotulo">Solução</div>' + this.tipo.solucao(this) + explicacao;
      this.areaSolucao.hidden = false;
      this.areaSolucao.scrollIntoView({ block: "nearest", behavior: "smooth" });
    }
  }

  function lerDados(raiz) {
    const script = raiz.querySelector("script.exercicio-dados");
    const texto = script ? script.textContent.replace(/<\\\//g, "</") : "";
    const dados = window.jsyaml.load(texto);
    if (!dados || typeof dados !== "object") throw new Error("o bloco está vazio ou não é um mapa YAML");
    if (!dados.id) throw new Error('falta o campo "id"');
    if (!TIPOS[dados.tipo]) throw new Error('tipo "' + dados.tipo + '" desconhecido');
    if (!dados.pergunta) throw new Error('falta o campo "pergunta"');
    return dados;
  }

  // ------------------------------------------------------ resumo da página

  function montarResumoDaPagina(ids) {
    if (!ids.length) return;
    const resumo = criar("aside", { classe: "resumo-exercicios", "aria-live": "polite" });
    const alvo = document.querySelector("#title-block-header") || document.querySelector("main h1");
    if (alvo) alvo.insertAdjacentElement("afterend", resumo);
    else (document.querySelector("main") || document.body).prepend(resumo);
    const linkProgresso = document.querySelector('a.nav-link[href$="progresso.html"]');
    const atualizar = () => {
      const feitos = ids.filter((id) => (progresso.situacao(id) || {}).acertou).length;
      const porcentagem = Math.round((100 * feitos) / ids.length);
      resumo.innerHTML =
        '<div class="resumo-exercicios-texto"><strong>Atividades desta página:</strong> ' + feitos + " de " + ids.length + " concluídas" +
        (linkProgresso ? ' · <a href="' + linkProgresso.getAttribute("href") + '">ver todo o progresso</a>' : "") +
        '</div><div class="progress" role="progressbar" aria-label="Progresso da página" aria-valuenow="' + porcentagem +
        '" aria-valuemin="0" aria-valuemax="100"><div class="progress-bar" style="width: ' + porcentagem + '%"></div></div>';
    };
    document.addEventListener("terraDigital:progresso", atualizar);
    atualizar();
  }

  // ----------------------------------------------------- painel de progresso

  function montarPainelDeProgresso(painel) {
    const indice = window.TerraDigitalIndice;
    if (!indice) {
      painel.innerHTML = '<div class="alert alert-warning">O índice de exercícios não foi gerado. Rode <code>quarto render</code> de novo.</div>';
      return;
    }
    const desenhar = () => {
      const dados = progresso.ler();
      let feitosNoTotal = 0;
      let totalGeral = 0;
      const linhas = indice.paginas
        .filter((pagina) => pagina.exercicios.length)
        .map((pagina) => {
          const total = pagina.exercicios.length;
          const feitos = pagina.exercicios.filter((ex) => (dados.exercicios[ex.id] || {}).acertou).length;
          feitosNoTotal += feitos;
          totalGeral += total;
          const porcentagem = Math.round((100 * feitos) / total);
          return (
            '<tr><td><a href="' + escaparHtml(pagina.caminho) + '">' + escaparHtml(pagina.titulo) + "</a></td><td>" + feitos + " / " + total +
            '</td><td class="painel-barra"><div class="progress" role="progressbar" aria-label="' + escaparHtml(pagina.titulo) +
            '" aria-valuenow="' + porcentagem + '" aria-valuemin="0" aria-valuemax="100"><div class="progress-bar" style="width:' +
            porcentagem + '%"></div></div></td></tr>'
          );
        })
        .join("");
      const porcentagemGeral = totalGeral ? Math.round((100 * feitosNoTotal) / totalGeral) : 0;
      painel.innerHTML =
        '<p class="painel-total"><strong>' + feitosNoTotal + " de " + totalGeral + "</strong> atividades concluídas (" + porcentagemGeral + "%).</p>" +
        '<div class="table-responsive"><table class="table painel-tabela"><thead><tr><th>Página</th><th>Concluídas</th><th>Progresso</th></tr></thead><tbody>' +
        linhas +
        "</tbody></table></div>" +
        '<div class="painel-acoes"></div><div class="painel-mensagem" role="status" aria-live="polite"></div>';
      const acoes = painel.querySelector(".painel-acoes");
      const mensagem = painel.querySelector(".painel-mensagem");

      const exportar = botao("Baixar meu progresso (JSON)", "btn-outline-primary");
      exportar.addEventListener("click", () => {
        const arquivo = new Blob([progresso.exportar()], { type: "application/json" });
        const link = criar("a", { href: URL.createObjectURL(arquivo), download: "progresso-terra-digital.json" });
        document.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(link.href), 1000);
      });

      const seletor = criar("input", { type: "file", accept: "application/json,.json", hidden: true });
      const importar = botao("Carregar progresso salvo", "btn-outline-secondary");
      importar.addEventListener("click", () => seletor.click());
      seletor.addEventListener("change", async () => {
        const arquivo = seletor.files && seletor.files[0];
        if (!arquivo) return;
        try {
          progresso.importar(await arquivo.text());
          mensagem.textContent = "Progresso carregado.";
        } catch (erro) {
          mensagem.textContent = "Não foi possível carregar: " + erro.message;
        }
      });

      const apagar = botao("Apagar meu progresso", "btn-outline-danger");
      let confirmando = false;
      apagar.addEventListener("click", () => {
        if (!confirmando) {
          confirmando = true;
          apagar.textContent = "Clique de novo para apagar tudo";
          setTimeout(() => {
            confirmando = false;
            apagar.textContent = "Apagar meu progresso";
          }, 5000);
          return;
        }
        progresso.apagarTudo();
      });
      acoes.append(exportar, importar, seletor, apagar);
    };
    document.addEventListener("terraDigital:progresso", desenhar);
    desenhar();
  }

  // ---------------------------------------------------------------- início

  function iniciar() {
    const raizes = Array.from(document.querySelectorAll("div.exercicio"));
    const ids = [];
    raizes.forEach((raiz, i) => {
      try {
        if (!window.jsyaml) throw new Error("a biblioteca js-yaml não carregou");
        const dados = lerDados(raiz);
        new Exercicio(raiz, dados, i + 1).montar();
        ids.push(String(dados.id));
      } catch (erro) {
        raiz.classList.add("exercicio-com-erro");
        raiz.innerHTML = '<p class="exercicio-erro">Este exercício não pôde ser montado: ' + escaparHtml(erro.message) + ".</p>";
      }
    });
    montarResumoDaPagina(ids);
    const painel = document.getElementById("painel-progresso");
    if (painel) montarPainelDeProgresso(painel);
  }

  window.TerraDigital = { progresso, renderizarMarkdown, lerNumero, normalizarTexto };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", iniciar);
  else iniciar();
})();
