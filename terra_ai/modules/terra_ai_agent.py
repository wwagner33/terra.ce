# modules/terra_ai_agent.py
import json
import os
from dataclasses import dataclass, field

import anthropic

from .terra_ai_tools import TOOLS, executar_tool

MODELO_PADRAO = os.environ.get("TERRA_AI_MODELO", "claude-opus-5")
MAX_TOKENS = 8000
MAX_ITERACOES = 6

SYSTEM_PROMPT = """\
Você é o Terra-AI, um assistente que explica dados de terras rurais do Ceará
para pessoas comuns — agricultores, famílias, lideranças comunitárias. Muitas
delas têm pouca escolaridade.

COMO RESPONDER
- Português simples e direto. Frases curtas. Nada de juridiquês.
- De 2 a 5 frases. Vá direto ao ponto: primeiro a resposta, depois o detalhe.
- Se precisar usar um termo técnico, explique em seguida com suas palavras.
- Áreas sempre em hectares, escrevendo "hectares".
- Números grandes com ponto de milhar (2.164 propriedades).

DE ONDE VÊM AS INFORMAÇÕES
- Você SÓ pode afirmar números, nomes e situações que vieram do retorno de uma
  ferramenta nesta conversa. Nunca estime, nunca arredonde de cabeça, nunca
  complete com conhecimento geral.
- Antes de dar qualquer número, chame a ferramenta correspondente.
- Se uma ferramenta devolver "erro", explique com naturalidade o que aconteceu
  e ofereça as sugestões que ela trouxe.
- Se você não sabe ou o dado não existe na base, diga isso claramente:
  "essa informação não está no cadastro que eu consulto".

O QUE A BASE TEM E O QUE NÃO TEM
- Tem: dados de cadastro (situação jurídica, área, categoria, município,
  nome do proprietário, números de INCRA e de título).
- NÃO tem: andamento de processo, prazo, documento digitalizado, ou qualquer
  informação sobre pedidos individuais feitos ao IDACE.
- Se perguntarem sobre processo ou documento, diga que ainda não tem acesso a
  isso e oriente a procurar o IDACE.

LIMITES
- Você não dá orientação jurídica e não diz a ninguém o que fazer no caso dele.
  Você explica o que os dados mostram e o que os termos significam.
- Para regularizar a terra, o caminho é o IDACE.
"""


@dataclass
class RespostaTerraAI:
    texto: str
    ferramentas_usadas: list[dict] = field(default_factory=list)
    erro: str | None = None


def criar_cliente() -> anthropic.Anthropic:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError(
            "ANTHROPIC_API_KEY não configurada. Preencha essa variável no .env do dashboard."
        )
    return anthropic.Anthropic()


def responder(
    pergunta: str,
    historico: list[dict],
    modelo: str = MODELO_PADRAO,
    max_iteracoes: int = MAX_ITERACOES,
) -> RespostaTerraAI:
    try:
        client = criar_cliente()
    except RuntimeError as e:
        return RespostaTerraAI(texto=str(e), erro="config")

    mensagens = list(historico) + [{"role": "user", "content": pergunta}]
    usadas: list[dict] = []
    resp = None

    for _ in range(max_iteracoes):
        try:
            resp = client.messages.create(
                model=modelo,
                max_tokens=MAX_TOKENS,
                system=[{
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }],
                output_config={"effort": os.environ.get("TERRA_AI_EFFORT", "low")},
                tools=TOOLS,
                messages=mensagens,
            )
        except anthropic.APIError as e:
            return RespostaTerraAI(
                texto=f"Não consegui falar com o Claude agora: {e}",
                ferramentas_usadas=usadas,
                erro="api",
            )

        if resp.stop_reason == "refusal":
            return RespostaTerraAI(
                texto="Não consegui responder a essa pergunta.",
                ferramentas_usadas=usadas,
                erro="refusal",
            )

        mensagens.append({"role": "assistant", "content": resp.content})

        if resp.stop_reason != "tool_use":
            break

        resultados = []
        for bloco in resp.content:
            if bloco.type == "tool_use":
                saida = executar_tool(bloco.name, bloco.input)
                usadas.append({"nome": bloco.name, "argumentos": bloco.input, "resultado": saida})
                resultados.append({
                    "type": "tool_result",
                    "tool_use_id": bloco.id,
                    "content": json.dumps(saida, ensure_ascii=False, default=str),
                })
        mensagens.append({"role": "user", "content": resultados})

    if resp is None:
        return RespostaTerraAI(texto="Não consegui gerar uma resposta.", ferramentas_usadas=usadas)

    texto = "".join(b.text for b in resp.content if b.type == "text")
    if not texto:
        texto = "Não consegui formular uma resposta clara para essa pergunta."
    return RespostaTerraAI(texto=texto, ferramentas_usadas=usadas)
