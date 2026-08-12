# modules/terra_api_client.py
import datetime as dt
import os

import jwt
import pandas as pd
import requests
import streamlit as st

COMMON_PROPERTY_COLUMNS = [
    "numero_lote", "numero_incra", "situacao_juridica",
    "modulo_fiscal", "area", "nome_municipio", "nome_proprietario",
    "nome_distrito", "numero_titulo", "regiao_administrativa",
    "categoria", "nome_municipio_original", "imovel",
]


class TerraApiError(RuntimeError):
    pass


def _base_url() -> str:
    return os.environ.get("TGDM_BASE_URL", "http://localhost:8000")


def gerar_token(expira_minutos: int = 30) -> str:
    segredo = os.environ.get("TGDM_JWT_SECRET")
    if not segredo:
        raise TerraApiError(
            "TGDM_JWT_SECRET não configurado. Copie o valor de JWT_SECRET do "
            ".env do terraGeoDataMiniServer (sem aspas) para o .env do dashboard."
        )
    algoritmo = os.environ.get("TGDM_JWT_ALGORITHM", "HS256")
    agora = dt.datetime.now(dt.timezone.utc)
    payload = {
        "sub": "terra-ai-dashboard",
        "iat": agora,
        "exp": agora + dt.timedelta(minutes=expira_minutos),
    }
    return jwt.encode(payload, segredo, algorithm=algoritmo)


def _headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {gerar_token()}"}


def _get(caminho: str, params: dict | None = None, timeout: int = 60):
    url = f"{_base_url()}{caminho}"
    try:
        resp = requests.get(url, params=params, headers=_headers(), timeout=timeout)
    except requests.exceptions.ConnectionError as e:
        raise TerraApiError(
            f"Não consegui me conectar ao terraGeoDataMiniServer em {_base_url()}. "
            "Confirme se o serviço está rodando."
        ) from e
    except requests.exceptions.Timeout as e:
        raise TerraApiError("A consulta ao terraGeoDataMiniServer demorou demais.") from e

    if resp.status_code == 401:
        raise TerraApiError("Token JWT rejeitado pelo terraGeoDataMiniServer (TGDM_JWT_SECRET incorreto?).")
    if resp.status_code == 404:
        return None
    if not resp.ok:
        raise TerraApiError(f"terraGeoDataMiniServer devolveu erro {resp.status_code}: {resp.text[:200]}")

    return resp.json()


def health() -> bool:
    try:
        resp = requests.get(f"{_base_url()}/health", timeout=10)
        return resp.ok
    except requests.exceptions.RequestException:
        return False


@st.cache_data(ttl=3600, show_spinner=False)
def listar_municipios_slugs() -> list[str]:
    dados = _get("/municipios_todos")
    if not dados:
        return []
    return dados.get("municipios", [])


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_dados_municipio(municipio_slug: str) -> pd.DataFrame:
    dados = _get("/dados_fundiarios", params={"municipio": municipio_slug})
    if not dados:
        return pd.DataFrame(columns=COMMON_PROPERTY_COLUMNS)

    df = pd.DataFrame(dados)
    for col in COMMON_PROPERTY_COLUMNS:
        if col not in df.columns:
            df[col] = None

    df["area_ha"] = pd.to_numeric(df["area"], errors="coerce")
    df["modulo_fiscal"] = pd.to_numeric(df["modulo_fiscal"], errors="coerce")
    return df
