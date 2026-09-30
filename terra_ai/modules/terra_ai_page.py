# modules/terra_ai_page.py
import os

import streamlit as st

from . import terra_api_client
from .terra_ai_agent import responder

CHAVE_HISTORICO = "terra_ai_historico"

PERGUNTAS_SUGERIDAS = [
    "Quantas propriedades tem em Sobral?",
    "O que é posse por simples ocupação?",
    "Quais os tipos de situação jurídica mais comuns no Ceará?",
    "Me mostre 5 propriedades grandes em Itapipoca",
]


def _checar_configuracao() -> list[str]:
    pendencias = []
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pendencias.append("Falta configurar `ANTHROPIC_API_KEY` no `.env` do dashboard.")
    if not os.environ.get("TGDM_JWT_SECRET"):
        pendencias.append("Falta configurar `TGDM_JWT_SECRET` no `.env` do dashboard.")
    if not pendencias and not terra_api_client.health():
        pendencias.append(
            f"Não consegui falar com o terraGeoDataMiniServer em "
            f"{os.environ.get('TGDM_BASE_URL', 'http://localhost:8000')}. Confirme se ele está rodando."
        )
    return pendencias


def render_terra_ai() -> None:
    st.subheader("🌱 Terra-AI — pergunte sobre as terras do Ceará")
    st.caption(
        "Protótipo (prova de conceito). Responde com base no cadastro fundiário do IDACE — "
        "ainda não tem acesso a processos ou documentos individuais."
    )

    pendencias = _checar_configuracao()
    if pendencias:
        for p in pendencias:
            st.error(p)
        return

    st.session_state.setdefault(CHAVE_HISTORICO, [])
    historico = st.session_state[CHAVE_HISTORICO]

    if st.sidebar.button("Limpar conversa"):
        st.session_state[CHAVE_HISTORICO] = []
        st.rerun()

    pergunta_pendente = None

    if not historico:
        st.markdown("**Experimente perguntar:**")
        colunas = st.columns(2)
        for i, sugestao in enumerate(PERGUNTAS_SUGERIDAS):
            if colunas[i % 2].button(sugestao, key=f"sugestao_{i}"):
                pergunta_pendente = sugestao

    for m in historico:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    digitada = st.chat_input("Escreva sua pergunta sobre as terras do Ceará...")
    if digitada:
        pergunta_pendente = digitada

    if pergunta_pendente:
        with st.chat_message("user"):
            st.markdown(pergunta_pendente)

        with st.chat_message("assistant"):
            with st.spinner("Consultando os dados..."):
                resultado = responder(pergunta_pendente, historico)
            st.markdown(resultado.texto)
            if resultado.ferramentas_usadas:
                with st.expander("Dados consultados"):
                    st.json(resultado.ferramentas_usadas)

        historico.append({"role": "user", "content": pergunta_pendente})
        historico.append({"role": "assistant", "content": resultado.texto})
