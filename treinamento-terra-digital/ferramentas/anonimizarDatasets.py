"""Gera a versão anonimizada dos CSVs do miniserver, a que a equipe usa nas práticas.

Os CSVs originais de terraGeoDataMiniServer/datasets/ trazem nomes de pessoas
físicas e ficam só com a coordenação. Este script grava uma cópia em que, na
malha fundiária:

- o nome de pessoa física vira "PESSOA EXEMPLO 000123", mantendo "ESPOLIO DE"
  e os sufixos ME, MEI, EPP e EIRELI; o de pessoa jurídica vira
  "<termo> EXEMPLO 000012", com a forma jurídica; entes públicos (prefeituras,
  INCRA, IDACE...) ficam como estão. A regra de privacidade do miniserver
  classifica cada pseudônimo como o nome original, e o mesmo nome vira sempre
  o mesmo pseudônimo, o que preserva o agrupamento por proprietário do Gini;
- pessoa_id ganha uma numeração nova;
- o nome do imóvel, que costuma carregar o nome do dono, vira "SITIO EXEMPLO 000045";
- numero_incra e numero_titulo viram números sorteados, no mesmo formato;
- ponto_de_referencia, texto livre, fica vazio.

Geometrias, áreas e datas ficam como estão. O polígono ainda permite a
reidentificação (M13), por isso os arquivos gerados também não saem da
máquina de trabalho. Os outros CSVs não têm dados pessoais e são copiados.
A correspondência entre originais e pseudônimos não é gravada em lugar nenhum.

Uso, na pasta treinamento-terra-digital, com o submódulo do miniserver no superprojeto:

    python ferramentas/anonimizarDatasets.py --saida ~/datasets-anonimizados

O destino não pode ficar dentro do superprojeto, para os arquivos não irem
parar num commit.
"""

import argparse
import csv
import random
import re
import shutil
import string
import sys
import types
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SUPERPROJETO = RAIZ.parent
MINISERVER = SUPERPROJETO / "terraGeoDataMiniServer"
ARQUIVO_MALHA = "malha_fundiaria_ceara.csv"

ENTES_PUBLICOS = re.compile(
    r"\b(?:PREFEITURA|MUNICIPIO|CAMARA MUNICIPAL|ESTADO DO CEARA|GOVERNO|UNIAO FEDERAL|SECRETARIA"
    r"|INCRA|IDACE|DNOCS|CAGECE|COGERH|EMBRAPA|UNIVERSIDADE)\b"
)
ESPOLIO = re.compile(r"^ESPOLIO\b")
EMPRESARIO_INDIVIDUAL = re.compile(r"\b(ME|MEI|EPP|EIRELI)\.?$")
TIPOS_DE_IMOVEL = {"SITIO", "FAZENDA", "CHACARA", "LOTE", "GLEBA", "IMOVEL", "PROPRIEDADE", "TERRENO", "AREA", "POSSE", "GRANJA", "RANCHO"}

LEIA_ME = """Versão anonimizada dos CSVs do terraGeoDataMiniServer, gerada em {data}
por treinamento-terra-digital/ferramentas/anonimizarDatasets.py.

Copie os arquivos .csv para terraGeoDataMiniServer/datasets/ na sua máquina.

Nomes de proprietários e de imóveis, identificadores e pontos de referência
são fictícios. Os polígonos, as áreas e as datas são reais e ainda permitem
chegar a uma pessoa: mantenha os arquivos só na máquina de trabalho e nunca
os envie para repositórios, nuvens particulares ou ferramentas de IA externas.
"""


def carregarRegraDePrivacidade():
    """Importa do miniserver a regra que separa pessoa física de pessoa jurídica.

    O módulo lê `config.settings`, que exige o .env do miniserver. As funções
    usadas aqui não dependem das configurações, então um `config` vazio basta.
    """
    if not (MINISERVER / "data_service" / "privacidade.py").exists():
        sys.exit(f"Não encontrei o miniserver em {MINISERVER}. Rode `git submodule update --init` no superprojeto.")
    sys.modules.setdefault("config", types.SimpleNamespace(settings=types.SimpleNamespace(PSEUDONIMIZACAO_SECRET="", JWT_SECRET="")))
    sys.path.insert(0, str(MINISERVER))
    from data_service import privacidade

    return privacidade


class Anonimizador:
    def __init__(self, privacidade):
        self.privacidade = privacidade
        self.aleatorio = random.SystemRandom()
        self.proprietarios = {}
        self.pessoas = {}
        self.imoveis = {}
        self.identificadores = {}
        self.contagem = {"pessoas físicas": 0, "pessoas jurídicas": 0, "entes públicos mantidos": 0, "imóveis": 0, "pessoa_id": 0}

    def numerar(self, chave):
        self.contagem[chave] += 1
        return f"{self.contagem[chave]:06d}"

    def nomeProprietario(self, nome):
        if not nome.strip():
            return nome
        chave = self.privacidade.normalizar_nome(nome)
        if chave not in self.proprietarios:
            self.proprietarios[chave] = self.pseudonimoProprietario(nome)
        return self.proprietarios[chave]

    def pseudonimoProprietario(self, nome):
        normalizado = self.privacidade._normalizar_para_regra(nome)
        juridica = self.privacidade.eh_pessoa_juridica(nome)
        if juridica and ENTES_PUBLICOS.search(normalizado):
            self.contagem["entes públicos mantidos"] += 1
            return nome
        if juridica:
            termo = self.privacidade._REGEX_INSTITUCIONAL.search(normalizado)
            forma = self.privacidade._REGEX_FORMA_JURIDICA.search(normalizado)
            pseudonimo = f"{termo.group(0) if termo else 'EMPRESA'} EXEMPLO {self.numerar('pessoas jurídicas')}"
            if forma:
                pseudonimo += " " + forma.group(0).strip()
        else:
            pseudonimo = f"PESSOA EXEMPLO {self.numerar('pessoas físicas')}"
            if ESPOLIO.search(normalizado):
                pseudonimo = "ESPOLIO DE " + pseudonimo
            sufixo = EMPRESARIO_INDIVIDUAL.search(normalizado)
            if sufixo:
                pseudonimo += " " + sufixo.group(1)
        # Garantia: o painel trata o pseudônimo exatamente como trataria o nome original.
        if self.privacidade.eh_pessoa_juridica(pseudonimo) != juridica:
            raise RuntimeError(f"O pseudônimo {pseudonimo!r} mudou a classificação da regra de privacidade.")
        return pseudonimo

    def pessoaId(self, valor):
        if not valor.strip():
            return valor
        if valor not in self.pessoas:
            self.pessoas[valor] = str(100000 + int(self.numerar("pessoa_id")))
        return self.pessoas[valor]

    def nomeImovel(self, nome):
        if not nome.strip():
            return nome
        normalizado = self.privacidade._normalizar_para_regra(nome)
        if normalizado not in self.imoveis:
            palavras = re.findall(r"[A-Z]+", normalizado)
            tipo = palavras[0] if palavras and palavras[0] in TIPOS_DE_IMOVEL else "IMOVEL"
            self.imoveis[normalizado] = f"{tipo} EXEMPLO {self.numerar('imóveis')}"
        return self.imoveis[normalizado]

    def identificador(self, valor):
        """Sorteia outro valor com o mesmo formato: dígito por dígito, letra por letra."""
        # Sem dígito nem letra (vazio, "____") não há o que esconder nem o que sortear.
        if not any(c.isalnum() for c in valor):
            return valor
        if valor not in self.identificadores:
            sorteado = valor
            while sorteado == valor:
                sorteado = "".join(
                    self.aleatorio.choice(string.digits) if c.isdigit()
                    else self.aleatorio.choice(string.ascii_uppercase) if c.isalpha()
                    else c
                    for c in valor
                )
            self.identificadores[valor] = sorteado
        return self.identificadores[valor]

    def linha(self, registro):
        registro["nome_proprietario"] = self.nomeProprietario(registro["nome_proprietario"])
        registro["pessoa_id"] = self.pessoaId(registro["pessoa_id"])
        registro["imovel"] = self.nomeImovel(registro["imovel"])
        registro["numero_incra"] = self.identificador(registro["numero_incra"])
        registro["numero_titulo"] = self.identificador(registro["numero_titulo"])
        registro["ponto_de_referencia"] = ""
        return registro


def anonimizarMalha(origem, destino, anonimizador):
    csv.field_size_limit(sys.maxsize)
    with open(origem, encoding="utf-8-sig", newline="") as entrada, open(destino, "w", encoding="utf-8", newline="") as saida:
        leitor = csv.DictReader(entrada)
        faltando = {"nome_proprietario", "pessoa_id", "imovel", "numero_incra", "numero_titulo", "ponto_de_referencia"} - set(leitor.fieldnames or [])
        if faltando:
            sys.exit(f"{origem.name} não tem as colunas {sorted(faltando)}. O formato mudou; revise este script.")
        escritor = csv.DictWriter(saida, fieldnames=leitor.fieldnames, lineterminator="\n")
        escritor.writeheader()
        linhas = 0
        for registro in leitor:
            escritor.writerow(anonimizador.linha(registro))
            linhas += 1
    return linhas


def conferirDestino(destino):
    if destino == SUPERPROJETO or SUPERPROJETO in destino.parents:
        sys.exit(f"O destino {destino} fica dentro do superprojeto. Escolha uma pasta fora dele, como ~/datasets-anonimizados.")


def main():
    parser = argparse.ArgumentParser(description="Gera a versão anonimizada dos CSVs do miniserver.")
    parser.add_argument("--origem", type=Path, default=MINISERVER / "datasets", help="pasta com os CSVs originais")
    parser.add_argument("--saida", type=Path, required=True, help="pasta de destino, fora do superprojeto")
    argumentos = parser.parse_args()

    origem = argumentos.origem.expanduser().resolve()
    saida = argumentos.saida.expanduser().resolve()
    conferirDestino(saida)
    if not (origem / ARQUIVO_MALHA).exists():
        sys.exit(f"Não encontrei {ARQUIVO_MALHA} em {origem}.")

    anonimizador = Anonimizador(carregarRegraDePrivacidade())
    saida.mkdir(parents=True, exist_ok=True)
    for arquivo in sorted(origem.glob("*.csv")):
        if arquivo.name == ARQUIVO_MALHA:
            linhas = anonimizarMalha(arquivo, saida / arquivo.name, anonimizador)
            print(f"{arquivo.name}: {linhas} linhas anonimizadas.")
        else:
            shutil.copy2(arquivo, saida / arquivo.name)
            print(f"{arquivo.name}: copiado, sem dados pessoais.")
    (saida / "LEIA-ME.txt").write_text(LEIA_ME.format(data=date.today().strftime("%d/%m/%Y")), encoding="utf-8")

    print("Pseudônimos criados: " + ", ".join(f"{quantidade} {nome}" for nome, quantidade in anonimizador.contagem.items()) + ".")
    print(f"Arquivos em {saida}. Entregue-os à equipe sem passar por repositórios ou nuvens particulares.")


if __name__ == "__main__":
    main()
