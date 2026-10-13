# Terra Digital: treinamento da Plataforma Terra.Ce

Material didático web para a equipe da Plataforma Terra.Ce: 17 módulos (do
domínio fundiário à IA aplicada), exercícios corrigidos no próprio navegador,
um projeto integrador e o manual de contribuição para programadores e
designers.

O site é gerado com o [Quarto](https://quarto.org). Os exercícios de Python
rodam no navegador com o [Pyodide](https://pyodide.org) e os de SQL com o
[sql.js](https://sql.js.org); o progresso de cada pessoa fica no
armazenamento local do navegador.

## Rodar localmente

Requer o [Quarto](https://quarto.org/docs/get-started/) 1.8 ou mais novo e,
para testar os exercícios, o Python 3.13 (a versão do Pyodide que os roda no
navegador).

```bash
# na pasta treinamento-terra-digital
./rodar.sh             # abre o site e recarrega a cada arquivo salvo
./rodar.sh ajuda       # lista os outros comandos
```

## Antes de abrir um pull request

```bash
./rodar.sh verificar   # o mesmo que a CI: testa os exercícios e gera o site
```

Na primeira vez, o script cria o `.venv/` e instala as bibliotecas do
`requirements.txt`.

## Publicação

O workflow `.github/workflows/treinamento.yml` do superprojeto valida e
renderiza o site em cada pull request e publica no GitHub Pages a cada push
na `main`. Para ativar, em *Settings → Pages*, escolha *Source: GitHub
Actions*.

## Estrutura

| Caminho | Conteúdo |
|---|---|
| `index.qmd`, `comece/`, `progresso.qmd` | página inicial, como estudar, cronograma e progresso |
| `modulos/` | os módulos M0 a M16 |
| `manual/` | manual de contribuição: pull request, design, revisão, publicação e edição do material |
| `projeto-integrador.qmd`, `glossario.qmd`, `referencias.qmd` | fechamento do treinamento |
| `estilos/` | tema claro, tema escuro e layout comum |
| `_extensions/exercicios/` | o motor dos exercícios autocorrigidos |
| `ferramentas/` | índice, validação e teste dos exercícios; gerador do banco sintético; verificador de links |
| `rodar.sh` | abre, testa, constrói e serve o site na sua máquina |

O guia completo de autoria, com o formato de cada tipo de exercício, está em
`manual/material-didatico.qmd`.

## Autor

**Prof. Wellington Sarmento (SMD/IUVI/UFC)** - [wwagner33](https://github.com/wwagner33/)

*Material desenvolvido no Projeto Cientista Chefe Terra, parceria entre o IDACE, a UFC e a Funcap.*

## Licença

O conteúdo deste material está sob a licença
[CC BY-NC-ND 4.0](https://creativecommons.org/licenses/by-nc-nd/4.0/) (texto
completo em [`LICENSE`](LICENSE)). Contribuições enviadas por pull request são
distribuídas sob a mesma licença.

Os trechos de código citados da plataforma pertencem aos repositórios
[`dashboard_fundiario_ceara`](https://github.com/Projeto-Cientista-Chefe-Terra/dashboard_fundiario_ceara)
e [`terraGeoDataMiniServer`](https://github.com/Projeto-Cientista-Chefe-Terra/terraGeoDataMiniServer)
e seguem a licença deles, GPL-3.0.

## Licenças de terceiros

`_extensions/exercicios/js-yaml.min.js` é o [js-yaml](https://github.com/nodeca/js-yaml) 4.1.0, licença MIT.
O Pyodide e o sql.js são carregados de CDNs públicos (jsDelivr e cdnjs) quando
um exercício de Python ou SQL é executado.
