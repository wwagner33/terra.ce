#!/usr/bin/env bash
# Roda o site do treinamento Terra Digital na sua máquina.
#
# Uso, na pasta treinamento-terra-digital:
#   ./rodar.sh             abre o site no navegador e recarrega a cada arquivo salvo
#   ./rodar.sh testar      valida o YAML dos exercícios e roda as soluções
#   ./rodar.sh verificar   faz o que a CI faz num pull request: testar e construir
#   ./rodar.sh construir   gera o site completo em _site/
#   ./rodar.sh servir      serve o _site/ como no GitHub Pages
#   ./rodar.sh links       confere os links externos (leva alguns minutos)
#   ./rodar.sh limpar      apaga os arquivos gerados (_site/, .quarto/ e o índice)
#   ./rodar.sh ajuda       mostra esta ajuda
#
# Opções, por variável de ambiente:
#   PORTA=5000 ./rodar.sh                  porta do servidor local (padrão: 4200)
#   SEM_NAVEGADOR=1 ./rodar.sh             não abre o navegador
#   PYTHON=python3.13 ./rodar.sh testar    Python usado para criar o .venv

set -euo pipefail

cd "$(dirname "$0")"
ESTE_SCRIPT="$(basename "$0")"

PORTA="${PORTA:-4200}"
QUARTO_MINIMO="1.8"
PYTHON_RECOMENDADO="3.13"
PASTA_VENV=".venv"
MARCA_REQUISITOS="$PASTA_VENV/.requisitos.sha256"

if [ -t 1 ] && [ -z "${NO_COLOR:-}" ]; then
  VERDE=$'\033[32m'; AMARELO=$'\033[33m'; VERMELHO=$'\033[31m'; NEGRITO=$'\033[1m'; NORMAL=$'\033[0m'
else
  VERDE=""; AMARELO=""; VERMELHO=""; NEGRITO=""; NORMAL=""
fi

informar() { printf '%s==>%s %s\n' "$VERDE$NEGRITO" "$NORMAL" "$*"; }
avisar() { printf '%saviso:%s %s\n' "$AMARELO" "$NORMAL" "$*" >&2; }
falhar() { printf '%serro:%s %s\n' "$VERMELHO" "$NORMAL" "$*" >&2; exit 1; }

mostrarAjuda() {
  sed -n '2,/^$/p' "$ESTE_SCRIPT" | sed 's/^# \{0,1\}//'
}

# Compara só maior.menor: versaoMaiorOuIgual 1.8.26 1.8 é verdadeiro.
versaoMaiorOuIgual() {
  local atualMaior atualMenor minimaMaior minimaMenor
  atualMaior="${1%%.*}"; atualMenor="${1#*.}"; atualMenor="${atualMenor%%.*}"
  minimaMaior="${2%%.*}"; minimaMenor="${2#*.}"; minimaMenor="${minimaMenor%%.*}"
  [ "$atualMaior" -gt "$minimaMaior" ] ||
    { [ "$atualMaior" -eq "$minimaMaior" ] && [ "$atualMenor" -ge "$minimaMenor" ]; }
}

conferirQuarto() {
  command -v quarto >/dev/null 2>&1 ||
    falhar "o Quarto não está instalado. Instale a versão $QUARTO_MINIMO ou mais nova: https://quarto.org/docs/get-started/"
  local versao
  versao="$(quarto --version 2>/dev/null | head -n 1)"
  case "$versao" in
    [0-9]*.[0-9]*) ;;
    *) falhar "não consegui ler a versão do Quarto (\"$versao\")." ;;
  esac
  versaoMaiorOuIgual "$versao" "$QUARTO_MINIMO" ||
    falhar "o Quarto $versao é antigo para este material. Instale a versão $QUARTO_MINIMO ou mais nova: https://quarto.org/docs/get-started/"
}

# Primeiro Python 3.10+ disponível, preferindo o da CI. PYTHON=... escolhe outro.
encontrarPython() {
  local candidato
  if [ -n "${PYTHON:-}" ]; then
    command -v "$PYTHON" >/dev/null 2>&1 || falhar "PYTHON=$PYTHON não foi encontrado."
    command -v "$PYTHON"
    return
  fi
  for candidato in "python$PYTHON_RECOMENDADO" python3 python; do
    if command -v "$candidato" >/dev/null 2>&1 &&
      "$candidato" -c 'import sys; sys.exit(sys.version_info < (3, 10))' >/dev/null 2>&1; then
      command -v "$candidato"
      return
    fi
  done
  falhar "não encontrei o Python 3.10 ou mais novo. Instale o Python $PYTHON_RECOMENDADO: https://www.python.org/downloads/"
}

pythonDoVenv() {
  if [ -x "$PASTA_VENV/bin/python" ]; then
    echo "$PWD/$PASTA_VENV/bin/python"
  elif [ -x "$PASTA_VENV/Scripts/python.exe" ]; then
    echo "$PWD/$PASTA_VENV/Scripts/python.exe"
  else
    return 1
  fi
}

versaoDoPython() {
  "$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null
}

# Os testes usam o Python da CI, o mesmo do Pyodide 0.29 que roda os exercícios
# no navegador: as versões do requirements.txt são as do Pyodide e não têm
# pacote pronto para outras versões do Python.
encontrarPythonDosTestes() {
  local candidato
  if [ -n "${PYTHON:-}" ]; then
    encontrarPython
    return
  fi
  for candidato in "python$PYTHON_RECOMENDADO" python3 python; do
    if command -v "$candidato" >/dev/null 2>&1 &&
      [ "$(versaoDoPython "$candidato")" = "$PYTHON_RECOMENDADO" ]; then
      command -v "$candidato"
      return
    fi
  done
  falhar "os exercícios são testados com o Python $PYTHON_RECOMENDADO, a versão do Pyodide que os roda no navegador, e ele não foi encontrado. Instale-o (pelo gerenciador de pacotes do sistema, pyenv, asdf ou uv) ou indique o caminho: PYTHON=/caminho/do/python$PYTHON_RECOMENDADO ./rodar.sh testar"
}

# Cria o .venv na primeira vez e reinstala as bibliotecas quando o requirements.txt muda.
prepararVenv() {
  local python hashAtual versao
  if ! pythonDoVenv >/dev/null; then
    python="$(encontrarPythonDosTestes)"
    informar "Criando o ambiente Python em $PASTA_VENV/ com o $("$python" --version 2>&1)"
    "$python" -m venv "$PASTA_VENV"
  fi
  PYTHON_VENV="$(pythonDoVenv)" ||
    falhar "o ambiente $PASTA_VENV/ está incompleto. Apague a pasta ($PASTA_VENV/) e rode de novo."
  versao="$(versaoDoPython "$PYTHON_VENV")"
  if [ "$versao" != "$PYTHON_RECOMENDADO" ]; then
    avisar "o $PASTA_VENV/ usa o Python $versao, e os testes são feitos com o $PYTHON_RECOMENDADO. Se algo falhar, apague o $PASTA_VENV/ e rode de novo."
  fi
  hashAtual="$("$PYTHON_VENV" -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' requirements.txt)"
  if [ ! -f "$MARCA_REQUISITOS" ] || [ "$(cat "$MARCA_REQUISITOS")" != "$hashAtual" ]; then
    informar "Instalando as bibliotecas do requirements.txt (na primeira vez leva cerca de um minuto)"
    "$PYTHON_VENV" -m pip install --disable-pip-version-check -r requirements.txt ||
      falhar "a instalação das bibliotecas falhou. Confira a conexão com a internet; para recomeçar do zero, apague o $PASTA_VENV/ e rode de novo."
    echo "$hashAtual" > "$MARCA_REQUISITOS"
  fi
}

# O Quarto roda ferramentas/exercicios.py antes de cada render; ele só usa a biblioteca padrão.
prepararPythonDoQuarto() {
  if [ -z "${QUARTO_PYTHON:-}" ]; then
    QUARTO_PYTHON="$(pythonDoVenv || encontrarPython)"
    export QUARTO_PYTHON
  fi
}

conferirPorta() {
  case "$PORTA" in
    '' | *[!0-9]*) falhar "PORTA precisa ser um número (recebi \"$PORTA\")." ;;
  esac
  "$1" - "$PORTA" <<'FIM' || falhar "a porta $PORTA está ocupada. Escolha outra, por exemplo: PORTA=$((PORTA + 1)) ./rodar.sh"
import socket, sys
with socket.socket() as s:
    try:
        s.bind(("127.0.0.1", int(sys.argv[1])))
    except OSError:
        sys.exit(1)
FIM
}

abrirNavegador() {
  if [ -n "${SEM_NAVEGADOR:-}" ]; then
    return 0
  fi
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$1" >/dev/null 2>&1 || true
  elif command -v open >/dev/null 2>&1; then
    open "$1" || true
  elif command -v cmd.exe >/dev/null 2>&1; then
    cmd.exe /c start "" "$1" || true
  fi
}

abrirSite() {
  conferirQuarto
  prepararPythonDoQuarto
  conferirPorta "$QUARTO_PYTHON"
  informar "Abrindo o site em http://localhost:$PORTA/ (Ctrl+C para parar)"
  if [ -n "${SEM_NAVEGADOR:-}" ]; then
    exec quarto preview --port "$PORTA" --no-browser
  fi
  exec quarto preview --port "$PORTA"
}

testarExercicios() {
  prepararVenv
  informar "Validando o YAML e rodando as soluções dos exercícios"
  "$PYTHON_VENV" ferramentas/exercicios.py testar
}

construirSite() {
  conferirQuarto
  prepararPythonDoQuarto
  informar "Gerando o site em _site/"
  quarto render
}

servirSite() {
  local python
  python="$(encontrarPython)"
  if [ ! -f _site/index.html ]; then
    construirSite
  fi
  conferirPorta "$python"
  informar "Servindo o _site/ em http://localhost:$PORTA/, como no GitHub Pages (Ctrl+C para parar)"
  avisar "este modo não recarrega sozinho. Depois de editar, rode ./rodar.sh construir."
  (sleep 1 && abrirNavegador "http://localhost:$PORTA/") &
  exec "$python" -m http.server "$PORTA" --bind 127.0.0.1 --directory _site
}

conferirLinks() {
  local python
  python="$(encontrarPython)"
  informar "Conferindo os links externos dos arquivos .qmd"
  "$python" ferramentas/verificarLinks.py
}

limpar() {
  informar "Apagando _site/, .quarto/ e indiceExercicios.js"
  rm -rf _site .quarto indiceExercicios.js
  informar "O ambiente Python ($PASTA_VENV/) foi mantido. Para apagá-lo também: rm -rf $PASTA_VENV"
}

comando="${1:-abrir}"
case "$comando" in
  abrir) abrirSite ;;
  testar) testarExercicios ;;
  construir) construirSite ;;
  verificar)
    testarExercicios
    construirSite
    informar "Tudo certo: exercícios passando e site gerado. Pode abrir o pull request."
    ;;
  servir) servirSite ;;
  links) conferirLinks ;;
  limpar) limpar ;;
  ajuda | -h | --help) mostrarAjuda ;;
  *)
    mostrarAjuda >&2
    falhar "comando desconhecido: $comando"
    ;;
esac
