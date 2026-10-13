-- Filtro dos exercícios autocorrigidos.
--
-- Cada bloco de código marcado como ```exercicio vira um <div class="exercicio">
-- com o YAML original guardado num <script type="text/x-yaml">. O exercicios.js
-- lê esse YAML no navegador e monta o exercício. A validação completa do YAML
-- fica em ferramentas/exercicios.py, que roda na integração contínua.

local function adicionarDependencias()
  quarto.doc.add_html_dependency({
    name = "exercicios",
    version = "1.0.0",
    scripts = { "js-yaml.min.js", "dadosSql.js", "exercicios.js" },
    stylesheets = { "exercicios.css" },
    resources = { "trabalhadorPython.js", "executor.py" },
  })
end

local function escaparParaScript(texto)
  -- "</script" fecharia a tag antes da hora; o exercicios.js desfaz a troca.
  return (texto:gsub("</", "<\\/"))
end

function CodeBlock(bloco)
  if not bloco.classes:includes("exercicio") then
    return nil
  end
  if not quarto.doc.is_format("html") then
    return pandoc.Div(
      { pandoc.Para({ pandoc.Emph({ pandoc.Str("Exercício interativo disponível na versão web.") }) }) },
      pandoc.Attr("", { "exercicio-fora-da-web" })
    )
  end
  local html = '<div class="exercicio">'
    .. '<script type="text/x-yaml" class="exercicio-dados">'
    .. escaparParaScript(bloco.text)
    .. "</script>"
    .. '<noscript><p class="exercicio-sem-js">Ative o JavaScript para resolver este exercício.</p></noscript>'
    .. "</div>"
  return pandoc.RawBlock("html", html)
end

-- Todas as páginas carregam o motor: ele também cuida do resumo de progresso.
function Pandoc(documento)
  if quarto.doc.is_format("html") then
    adicionarDependencias()
  end
  return documento
end
