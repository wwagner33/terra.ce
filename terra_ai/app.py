# app.py — Terra-AI (protótipo standalone)
#
# Interface própria para o assistente Terra-AI, separada do dashboard
# ccTerra. Consulta os dados fundiários sempre via terraGeoDataMiniServer
# (API HTTP autenticada por JWT) -> Postgres/PostGIS, nunca via CSV local.
import os

import streamlit as st

from modules.terra_ai_page import render_terra_ai

st.set_page_config(
    page_title="Terra-AI :: Assistente Fundiário do Ceará",
    page_icon="🌱",
    layout="centered",
    initial_sidebar_state="expanded",
)

_style_path = os.path.join(os.path.dirname(__file__), "style.css")
if os.path.exists(_style_path):
    with open(_style_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

_logo_path = os.path.join(os.path.dirname(__file__), "assets", "CC_Terra.png")
if os.path.exists(_logo_path):
    st.logo(_logo_path, size="large")

render_terra_ai()
