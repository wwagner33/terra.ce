# modules/terra_ai_tools.py
import difflib
import unicodedata
from typing import Callable

import pandas as pd

from . import terra_ai_glossario
from . import terra_api_client


def _limpar(valor):
    """Converte NaN/NaT do pandas em None (JSON-serializável como null)."""
    if pd.isna(valor):
        return None
    return valor

PANORAMA_CE = {
    "data_referencia": "dataset malha_fundiaria_ceara (levantamento IDACE), retrato fixo, não é consulta ao vivo",
    "total_propriedades": 233366,
    "municipios_com_dados": 154,
    "por_situacao_juridica": [
        {"situacao": "Posse por Simples Ocupação", "percentual": 74.8},
        {"situacao": "Área Registrada (Domínio)", "percentual": 18.5},
        {"situacao": "Indefinido", "percentual": 5.2},
        {"situacao": "Posse a Justo Título", "percentual": 1.5},
    ],
    "por_categoria": [
        {"categoria": "Pequena Propriedade < 1 MF", "percentual": 84.0},
    ],
    "preenchimento": {
        "nome_proprietario_nulo_pct": 9.2,
        "numero_incra_nulo_pct": 27.6,
        "numero_titulo_nulo_pct": 43.9,
    },
}

_PREPOSICOES = {"de", "do", "da", "dos", "das", "e"}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode("ascii")
    return texto.strip().lower()


def slugificar_municipio(nome: str) -> str:
    norm = _normalizar(nome)
    partes = [p for p in norm.replace("-", " ").split() if p]
    return "_".join(partes)


def humanizar_municipio(slug: str) -> str:
    partes = slug.split("_")
    return " ".join(
        p if p in _PREPOSICOES else p.capitalize()
        for p in partes
    )


def resolver_municipio(nome: str) -> tuple[str | None, list[str]]:
    slug_buscado = slugificar_municipio(nome)
    todos = terra_api_client.listar_municipios_slugs()

    if slug_buscado in todos:
        return slug_buscado, []

    candidatos = difflib.get_close_matches(slug_buscado, todos, n=5, cutoff=0.7)
    return None, [humanizar_municipio(s) for s in candidatos]


# ==================== Tools ====================

def listar_municipios_disponiveis(filtro: str | None = None) -> dict:
    todos = terra_api_client.listar_municipios_slugs()
    if filtro:
        slug_filtro = slugificar_municipio(filtro)
        todos = [s for s in todos if slug_filtro in s]

    total = len(todos)
    if total > 60:
        return {
            "total": total,
            "amostra": [humanizar_municipio(s) for s in todos[:30]],
            "instrucao": "Muitos resultados — peça ao usuário para refinar com um filtro (ex: parte do nome).",
        }
    return {"total": total, "municipios": [humanizar_municipio(s) for s in todos]}


def estatisticas_municipio(municipio: str) -> dict:
    slug, sugestoes = resolver_municipio(municipio)
    if not slug:
        return {"erro": f"Não encontrei o município '{municipio}'.", "sugestoes": sugestoes}

    df = terra_api_client.buscar_dados_municipio(slug)
    if df.empty:
        return {"erro": f"Não há dados cadastrais para '{humanizar_municipio(slug)}'."}

    total = len(df)
    area_total = float(df["area_ha"].sum(skipna=True))
    area_media = float(df["area_ha"].mean(skipna=True)) if total else 0.0
    area_mediana = float(df["area_ha"].median(skipna=True)) if total else 0.0
    modulo_fiscal = float(df["modulo_fiscal"].dropna().iloc[0]) if df["modulo_fiscal"].notna().any() else None

    por_situacao = []
    for situacao, grupo in df.groupby("situacao_juridica", dropna=False):
        por_situacao.append({
            "situacao": situacao if situacao else "Não informado",
            "quantidade": int(len(grupo)),
            "percentual": round(100 * len(grupo) / total, 1),
            "area_total_ha": round(float(grupo["area_ha"].sum(skipna=True)), 1),
        })
    por_situacao.sort(key=lambda x: -x["quantidade"])

    por_categoria = []
    for categoria, grupo in df.groupby("categoria", dropna=False):
        por_categoria.append({
            "categoria": categoria if categoria else "Não informado",
            "quantidade": int(len(grupo)),
            "percentual": round(100 * len(grupo) / total, 1),
        })
    por_categoria.sort(key=lambda x: -x["quantidade"])

    regiao = df["regiao_administrativa"].dropna().iloc[0] if df["regiao_administrativa"].notna().any() else None

    return {
        "municipio": humanizar_municipio(slug),
        "regiao_administrativa": regiao,
        "total_propriedades": total,
        "area_total_ha": round(area_total, 1),
        "area_media_ha": round(area_media, 1),
        "area_mediana_ha": round(area_mediana, 1),
        "modulo_fiscal_ha": modulo_fiscal,
        "por_situacao_juridica": por_situacao,
        "por_categoria": por_categoria,
        "registros_sem_nome_proprietario": int(df["nome_proprietario"].isna().sum()),
        "registros_sem_numero_incra": int(df["numero_incra"].isna().sum()),
        "registros_sem_numero_titulo": int(df["numero_titulo"].isna().sum()),
    }


def buscar_propriedades(
    municipio: str,
    situacao_juridica: str | None = None,
    categoria: str | None = None,
    area_minima_ha: float | None = None,
    area_maxima_ha: float | None = None,
    limite: int = 10,
) -> dict:
    slug, sugestoes = resolver_municipio(municipio)
    if not slug:
        return {"erro": f"Não encontrei o município '{municipio}'.", "sugestoes": sugestoes}

    df = terra_api_client.buscar_dados_municipio(slug)
    if df.empty:
        return {"erro": f"Não há dados cadastrais para '{humanizar_municipio(slug)}'."}

    filtros_aplicados = {}
    if situacao_juridica:
        alvo = _normalizar(situacao_juridica)
        df = df[df["situacao_juridica"].apply(lambda v: alvo in _normalizar(v) if v else False)]
        filtros_aplicados["situacao_juridica"] = situacao_juridica
    if categoria:
        alvo = _normalizar(categoria)
        df = df[df["categoria"].apply(lambda v: alvo in _normalizar(v) if v else False)]
        filtros_aplicados["categoria"] = categoria
    if area_minima_ha is not None:
        df = df[df["area_ha"] >= area_minima_ha]
        filtros_aplicados["area_minima_ha"] = area_minima_ha
    if area_maxima_ha is not None:
        df = df[df["area_ha"] <= area_maxima_ha]
        filtros_aplicados["area_maxima_ha"] = area_maxima_ha

    total_encontrado = len(df)
    limite = max(1, min(limite, 25))
    amostra = df.head(limite)

    propriedades = []
    for _, row in amostra.iterrows():
        area = row.get("area_ha")
        propriedades.append({
            "numero_lote": _limpar(row.get("numero_lote")),
            "nome_proprietario": _limpar(row.get("nome_proprietario")),
            "imovel": _limpar(row.get("imovel")),
            "area_ha": None if pd.isna(area) else round(float(area), 1),
            "situacao_juridica": _limpar(row.get("situacao_juridica")),
            "categoria": _limpar(row.get("categoria")),
            "numero_incra": _limpar(row.get("numero_incra")),
            "numero_titulo": _limpar(row.get("numero_titulo")),
        })

    return {
        "municipio": humanizar_municipio(slug),
        "filtros_aplicados": filtros_aplicados,
        "total_encontrado": total_encontrado,
        "mostrando": len(propriedades),
        "propriedades": propriedades,
    }


def detalhar_propriedade(municipio: str, numero_lote: str) -> dict:
    slug, sugestoes = resolver_municipio(municipio)
    if not slug:
        return {"erro": f"Não encontrei o município '{municipio}'.", "sugestoes": sugestoes}

    df = terra_api_client.buscar_dados_municipio(slug)
    if df.empty:
        return {"erro": f"Não há dados cadastrais para '{humanizar_municipio(slug)}'."}

    encontrados = df[df["numero_lote"].astype(str) == str(numero_lote)]
    if encontrados.empty:
        return {
            "municipio": humanizar_municipio(slug),
            "encontrados": 0,
            "propriedades": [],
        }

    propriedades = []
    for _, row in encontrados.head(5).iterrows():
        area = row.get("area_ha")
        propriedades.append({
            "numero_lote": _limpar(row.get("numero_lote")),
            "nome_proprietario": _limpar(row.get("nome_proprietario")),
            "imovel": _limpar(row.get("imovel")),
            "area_ha": None if pd.isna(area) else round(float(area), 1),
            "situacao_juridica": _limpar(row.get("situacao_juridica")),
            "categoria": _limpar(row.get("categoria")),
            "numero_incra": _limpar(row.get("numero_incra")),
            "numero_titulo": _limpar(row.get("numero_titulo")),
            "regiao_administrativa": _limpar(row.get("regiao_administrativa")),
        })

    return {
        "municipio": humanizar_municipio(slug),
        "encontrados": int(len(encontrados)),
        "propriedades": propriedades,
    }


def explicar_termo(termo: str) -> dict:
    return terra_ai_glossario.explicar_termo(termo)


def panorama_estadual() -> dict:
    return PANORAMA_CE


TOOL_FUNCS: dict[str, Callable[..., dict]] = {
    "listar_municipios_disponiveis": listar_municipios_disponiveis,
    "estatisticas_municipio": estatisticas_municipio,
    "buscar_propriedades": buscar_propriedades,
    "detalhar_propriedade": detalhar_propriedade,
    "explicar_termo": explicar_termo,
    "panorama_estadual": panorama_estadual,
}

TOOLS = [
    {
        "name": "listar_municipios_disponiveis",
        "description": (
            "Lista os municípios do Ceará que têm dados cadastrais disponíveis. Use quando o "
            "usuário perguntar quais municípios existem, ou quando precisar confirmar o nome "
            "exato de um município antes de consultar seus dados. Aceita um filtro de texto "
            "opcional (parte do nome) para reduzir a lista."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "filtro": {"type": "string", "description": "Parte do nome do município para filtrar (opcional)."},
            },
        },
    },
    {
        "name": "estatisticas_municipio",
        "description": (
            "Use esta ferramenta sempre que o usuário perguntar quantidade, área total, ou "
            "distribuição de propriedades (por situação jurídica ou categoria) de UM município "
            "específico do Ceará. Aceita o nome do município escrito de forma natural, com ou "
            "sem acento (ex: 'Farias Brito', 'sao benedito')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "municipio": {"type": "string", "description": "Nome do município."},
            },
            "required": ["municipio"],
        },
    },
    {
        "name": "buscar_propriedades",
        "description": (
            "Use para listar propriedades individuais de um município, opcionalmente filtrando "
            "por situação jurídica, categoria (ex: 'Grande Propriedade') ou faixa de área em "
            "hectares. Devolve no máximo 25 propriedades por chamada — sempre informa o total "
            "real encontrado, mesmo que maior que o limite."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "municipio": {"type": "string", "description": "Nome do município."},
                "situacao_juridica": {"type": "string", "description": "Filtro opcional de situação jurídica."},
                "categoria": {"type": "string", "description": "Filtro opcional de categoria da propriedade."},
                "area_minima_ha": {"type": "number", "description": "Área mínima em hectares (opcional)."},
                "area_maxima_ha": {"type": "number", "description": "Área máxima em hectares (opcional)."},
                "limite": {"type": "integer", "description": "Quantidade máxima de resultados (padrão 10, máximo 25)."},
            },
            "required": ["municipio"],
        },
    },
    {
        "name": "detalhar_propriedade",
        "description": (
            "Use para pegar todos os detalhes de uma propriedade específica dado o número do "
            "lote e o município. O número do lote pode se repetir dentro do mesmo município, "
            "por isso pode devolver mais de um resultado."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "municipio": {"type": "string", "description": "Nome do município."},
                "numero_lote": {"type": "string", "description": "Número do lote a buscar."},
            },
            "required": ["municipio", "numero_lote"],
        },
    },
    {
        "name": "explicar_termo",
        "description": (
            "Use sempre que o usuário perguntar o significado de um termo técnico/jurídico "
            "relacionado a terras (ex: 'posse por simples ocupação', 'módulo fiscal', "
            "'regularização fundiária'). NUNCA explique esses termos de cabeça — sempre chame "
            "esta ferramenta primeiro."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {"type": "string", "description": "O termo a explicar."},
            },
            "required": ["termo"],
        },
    },
    {
        "name": "panorama_estadual",
        "description": (
            "Use quando o usuário perguntar sobre números do Ceará como um todo (ex: 'quais os "
            "tipos de situação jurídica mais comuns no Ceará', 'quantas propriedades tem no "
            "estado todo'). Devolve um retrato fixo já calculado do dataset completo — não é "
            "uma consulta ao vivo, não tente somar dados de vários municípios para responder "
            "isso."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]


def executar_tool(nome: str, argumentos: dict) -> dict:
    funcao = TOOL_FUNCS.get(nome)
    if funcao is None:
        return {"erro": f"Ferramenta desconhecida: {nome}"}
    try:
        return funcao(**argumentos)
    except terra_api_client.TerraApiError as e:
        return {"erro": str(e)}
    except Exception as e:  # nunca propagar exceção pro loop do Claude
        return {"erro": f"Erro inesperado ao executar '{nome}': {e}"}
