"""Gera o banco sintético usado nos exercícios de SQL (_extensions/exercicios/dadosSql.js).

Os municípios existem, mas módulos fiscais, imóveis, áreas, situações e
assentamentos são fictícios. Nenhum nome de pessoa aparece: o proprietário é
um pseudônimo ("P001"), como o id_proprietario do miniserver.

Uso: python ferramentas/gerarDadosSinteticos.py
"""

import json
import random
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "_extensions" / "exercicios" / "dadosSql.js"
SEMENTE = 2026

MUNICIPIOS = [
    # nome, região, módulo fiscal fictício (ha)
    ("Crato", "Cariri", 50),
    ("Barbalha", "Cariri", 50),
    ("Juazeiro do Norte", "Cariri", 40),
    ("Quixadá", "Sertão Central", 60),
    ("Quixeramobim", "Sertão Central", 60),
    ("Russas", "Vale do Jaguaribe", 55),
    ("Limoeiro do Norte", "Vale do Jaguaribe", 55),
    ("Aracati", "Litoral Leste", 35),
]

SITUACOES = ["Titulado", "Posse", "Em regularização"]

ASSENTAMENTOS = [
    # nome fictício, município, famílias, área (ha)
    ("Boa Esperança", "Quixadá", 42, 2150.0),
    ("Nova Vida", "Quixeramobim", 35, 1880.5),
    ("Santa Luzia", "Russas", 28, 960.0),
    ("Terra Livre", "Crato", 51, 3010.0),
    ("Vale Verde", "Limoeiro do Norte", 19, 740.25),
    ("Mandacaru", "Quixadá", 23, 1200.0),
]


def gerarLotes(aleatorio):
    lotes = []
    proximoId = 1
    for nome, _regiao, moduloFiscal in MUNICIPIOS:
        for _ in range(aleatorio.randint(6, 9)):
            # Muitos imóveis pequenos e poucos grandes, como na malha real.
            area = round(moduloFiscal * aleatorio.choice([0.3, 0.6, 0.8, 1.5, 2.5, 3.5, 6, 10, 18, 30]) * aleatorio.uniform(0.85, 1.15), 2)
            lotes.append(
                {
                    "id": proximoId,
                    "municipio": nome,
                    "area_ha": area,
                    "situacao_juridica": aleatorio.choice(SITUACOES),
                    "id_proprietario": f"P{aleatorio.randint(1, 45):03d}",
                }
            )
            proximoId += 1
    return lotes


def textoSql(valor):
    if isinstance(valor, str):
        return "'" + valor.replace("'", "''") + "'"
    return repr(valor)


def montarScript(lotes):
    linhas = [
        "CREATE TABLE municipios (nome TEXT PRIMARY KEY, regiao TEXT NOT NULL, modulo_fiscal_ha REAL NOT NULL);",
        "CREATE TABLE lotes (id INTEGER PRIMARY KEY, municipio TEXT NOT NULL REFERENCES municipios(nome), "
        "area_ha REAL, situacao_juridica TEXT, id_proprietario TEXT);",
        "CREATE TABLE assentamentos (id INTEGER PRIMARY KEY, nome TEXT NOT NULL, municipio TEXT NOT NULL REFERENCES municipios(nome), "
        "familias INTEGER, area_ha REAL);",
    ]
    for nome, regiao, moduloFiscal in MUNICIPIOS:
        linhas.append(f"INSERT INTO municipios VALUES ({textoSql(nome)}, {textoSql(regiao)}, {moduloFiscal});")
    for lote in lotes:
        valores = ", ".join(textoSql(lote[c]) for c in ("id", "municipio", "area_ha", "situacao_juridica", "id_proprietario"))
        linhas.append(f"INSERT INTO lotes VALUES ({valores});")
    for i, (nome, municipio, familias, area) in enumerate(ASSENTAMENTOS, start=1):
        linhas.append(f"INSERT INTO assentamentos VALUES ({i}, {textoSql(nome)}, {textoSql(municipio)}, {familias}, {area});")
    return "\n".join(linhas)


def main():
    aleatorio = random.Random(SEMENTE)
    script = montarScript(gerarLotes(aleatorio))
    conteudo = (
        "/* Gerado por ferramentas/gerarDadosSinteticos.py. Não edite à mão.\n"
        " * Banco sintético dos exercícios de SQL: municípios reais, valores fictícios. */\n"
        "window.TerraDigitalDadosSql = " + json.dumps({"fundiario": script}, ensure_ascii=False, indent=2) + ";\n"
    )
    DESTINO.write_text(conteudo, encoding="utf-8")
    print(f"{DESTINO.relative_to(RAIZ)} gerado.")


if __name__ == "__main__":
    main()
