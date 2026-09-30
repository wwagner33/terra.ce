# Implantação da stack do Terra.Ce no Portainer

A stack atual foi criada pela linha de comando do servidor (`docker compose`), e
por isso o Portainer avisa que o controle sobre ela é limitado. Este roteiro
recria a stack pelo Portainer, que passa a gerenciá-la por completo, **sem
perder os dados**: o volume do Postgres é reaproveitado.

Arquivos usados, na raiz do superprojeto:

- `docker-compose.stack.yml`: a stack para colar no Portainer;
- `stack.env.example`: o modelo das variáveis.

A indisponibilidade esperada é de 5 a 15 minutos, quase toda para a carga
inicial do miniserver.

## 1. Inventário (antes de parar qualquer coisa)

No Portainer, anote os valores abaixo. Todos aparecem na página de cada
container, na seção *Env*, ou em *Inspect*.

| Onde | O que anotar | Variável da stack |
|---|---|---|
| Container `terra_postgis` | `PG_MAJOR` e `POSTGIS_VERSION` | `POSTGIS_TAG`, no formato `PG_MAJOR-POSTGIS maior.menor`, por exemplo `17-3.5` |
| Container `terra_postgis` | `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` | mesmos nomes |
| Container `terra_postgis`, seção *Volumes* | nome do volume montado em `/var/lib/postgresql/data` | `POSTGRES_VOLUME` |
| Container `terra_geodata_mini_server` | `JWT_SECRET` e os `TABLE_*` | mesmos nomes |
| Container `dashboard_fundiario_ce` | `CARTO_API_KEY`, se existir | `CARTO_API_KEY` |

Confira que a tag de `POSTGIS_TAG` existe em <https://hub.docker.com/r/postgis/postgis/tags>.
Ela precisa ter **a mesma versão principal do Postgres** que está rodando hoje;
outra versão principal não abre o volume atual.

Copie `stack.env.example` para um arquivo **fora do repositório** (por exemplo
`stack.env` no seu computador) e preencha. Sem aspas em nenhum valor. Os
`TABLE_*` só precisam ser preenchidos se forem diferentes dos padrões do modelo.

## 2. Backup do banco

No Portainer, abra o console do `terra_postgis` (*Console*, `/bin/bash`, *Connect*) e rode:

```bash
pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /var/lib/postgresql/data/backup_antes_portainer.dump
```

O arquivo fica dentro do volume, que será mantido. Se você tiver SSH no
servidor, prefira tirar a cópia para fora:

```bash
docker exec terra_postgis pg_dump -U terra -d geodata -Fc > geodata_$(date +%F).dump
```

## 3. Remover os containers antigos (não os volumes)

Em *Containers*, selecione `dashboard_fundiario_ce`, `terra_geodata_mini_server`
e `terra_postgis`, clique em *Stop* e depois em *Remove*. **Não marque** a opção
de remover volumes. Não remova a stack antiga pela tela de *Stacks* nem o volume
em *Volumes*.

Isso libera os nomes dos containers para a stack nova.

## 4. Criar a stack no Portainer

1. *Stacks → Add stack*.
2. Nome: `terrace` (ou outro de sua preferência).
3. *Build method*: *Web editor*. Cole o conteúdo de `docker-compose.stack.yml`.
4. Em *Environment variables*, use *Load variables from .env file* e escolha o
   arquivo preenchido. Confira que os valores aparecem sem aspas.
5. Clique em *Deploy the stack*.

Se faltar uma variável obrigatória, o Portainer recusa a implantação com uma
mensagem que diz qual é.

## 5. Acompanhar a subida

1. `terra_postgis` fica *healthy* em segundos.
2. `terra_geodata_mini_server` refaz a carga dos CSVs antes de responder. Nos
   logs aparece `RESUMO DA IMPORTAÇÃO UNIFICADA` e depois `Iniciando Gunicorn`.
   Leva de 2 a 5 minutos; o healthcheck espera até 15.
3. `dashboard_fundiario_ce` sobe logo. Até o miniserver terminar, as páginas de
   dados mostram "Não foi possível carregar os dados".

## 6. Conferir

- <https://terrace.virtual.ufc.br/paineis> abre todas as páginas com dados.
- Os mapas usam o fundo da CARTO. Se aparecer o do OpenStreetMap, falta
  `CARTO_API_KEY`.
- A Malha Fundiária mostra "Pessoa física (protegido pela LGPD)" no lugar dos
  nomes de pessoas físicas.
- O mapa de Assentamentos mostra o número real de assentamentos. Se havia
  duplicatas, a contagem cai.
- Os três containers aparecem como *healthy* ou *running*.

Depois de conferir, apague o backup de dentro do volume, se tiver criado:
`rm /var/lib/postgresql/data/backup_antes_portainer.dump` no console do `terra_postgis`.

## Atualizações futuras

As imagens estão fixadas por versão. Para atualizar, em *Stacks → terrace*,
mude `TGDM_TAG` e `DFUNDCE_TAG` nas variáveis e clique em *Update the stack*
com *Re-pull image* ligado. Atualize sempre os dois juntos.

## Voltar à versão anterior

Mude `TGDM_TAG=1.1.0` e `DFUNDCE_TAG=1.1.1` e atualize a stack. O volume é
compatível. Atenção: o miniserver 1.1.0 volta a duplicar assentamentos,
reservatórios e regiões a cada reinício.

## Observações

- As portas 5432 (Postgres) e 8000 (miniserver) agora só aceitam conexão da
  própria máquina do servidor. O dashboard usa a rede interna `terra_network`.
  Se algo de fora do servidor usava essas portas, use um túnel SSH ou tire o
  `127.0.0.1:` da linha correspondente.
- O Terra-AI não faz parte desta stack. Se ele rodar no mesmo servidor, continua
  acessando o miniserver em `http://localhost:8000`.
- Rotação de segredos: veja `dashboard_fundiario_ceara/doc/rotacao_segredos.md`.
  Com a stack no Portainer, basta mudar as variáveis e atualizar a stack. A
  senha do Postgres precisa antes ser trocada por SQL (`ALTER USER`), porque
  `POSTGRES_PASSWORD` só vale na criação do banco.
