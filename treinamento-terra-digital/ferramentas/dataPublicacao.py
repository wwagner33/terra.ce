"""Grava a data de publicação do site em _variables.yml, para o rodapé.

Roda sozinho antes de cada render (pre-render do _quarto.yml). Como a CI
renderiza e publica o site a cada push na main, a data do render é a data de
publicação. O horário é o de Fortaleza (UTC-3, sem horário de verão), para um
render feito à noite não sair com a data do dia seguinte.

Uso: python ferramentas/dataPublicacao.py
"""

from datetime import datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "_variables.yml"
FORTALEZA = timezone(timedelta(hours=-3))


def main():
    hoje = datetime.now(FORTALEZA).strftime("%d/%m/%Y")
    DESTINO.write_text(
        "# Gerado por ferramentas/dataPublicacao.py antes de cada render. Não edite à mão.\n"
        f'publicacao: "{hoje}"\n',
        encoding="utf-8",
    )
    print(f"{DESTINO.name}: publicação em {hoje}.")


if __name__ == "__main__":
    main()
