# modules/terra_ai_glossario.py
import unicodedata

GLOSSARIO: dict[str, dict[str, str]] = {
    "posse por simples ocupacao": {
        "termo": "Posse por Simples Ocupação",
        "explicacao": (
            "A família ocupa e usa a terra, muitas vezes há muitos anos, mas não tem "
            "documento registrado em cartório que prove que a terra é dela. É a situação "
            "mais comum no Ceará (cerca de 3 em cada 4 propriedades cadastradas)."
        ),
        "na_pratica": (
            "A pessoa é dona de fato, mas não de direito — não pode vender com segurança "
            "nem usar a terra como garantia em financiamento. É exatamente esse caso que a "
            "regularização fundiária resolve."
        ),
    },
    "area registrada (dominio)": {
        "termo": "Área Registrada (Domínio)",
        "explicacao": (
            "A terra tem documento (título) registrado em cartório no nome do dono. "
            "É a situação mais segura: dá para vender, herdar e usar como garantia sem risco."
        ),
        "na_pratica": "Cerca de 1 em cada 5 propriedades do Ceará está nessa situação.",
    },
    "posse a justo titulo": {
        "termo": "Posse a Justo Título",
        "explicacao": (
            "A pessoa tem algum papel que mostra como conseguiu a terra — um recibo, um "
            "contrato de compra e venda, um documento de herança — mas esse papel não foi "
            "registrado em cartório."
        ),
        "na_pratica": (
            "É melhor do que a simples ocupação, porque existe prova de origem, mas ainda "
            "não é o título definitivo."
        ),
    },
    "indefinido": {
        "termo": "Indefinido",
        "explicacao": (
            "O cadastro não informa qual é a situação jurídica da terra."
        ),
        "na_pratica": (
            "Não quer dizer que a terra seja irregular — quer dizer que essa informação "
            "não foi preenchida no levantamento."
        ),
    },
    "modulo fiscal": {
        "termo": "Módulo Fiscal",
        "explicacao": (
            "É uma medida de terra que muda de município para município. Ele representa a "
            "área mínima que uma família precisa para viver da terra naquele lugar. Onde a "
            "terra é mais fraca, o módulo é maior."
        ),
        "na_pratica": (
            "No Ceará varia entre 15 e 70 hectares, aproximadamente. Serve para classificar "
            "se uma propriedade é pequena, média ou grande."
        ),
    },
    "pequena propriedade < 1 mf": {
        "termo": "Pequena Propriedade < 1 MF",
        "explicacao": "Propriedade menor do que um módulo fiscal.",
        "na_pratica": (
            "É a grande maioria das terras cadastradas no Ceará (cerca de 84%). Costuma ser "
            "agricultura familiar."
        ),
    },
    "pequena propriedade": {
        "termo": "Pequena Propriedade",
        "explicacao": "Propriedade entre 1 e 4 módulos fiscais.",
        "na_pratica": "",
    },
    "media propriedade": {
        "termo": "Média Propriedade",
        "explicacao": "Propriedade entre 4 e 15 módulos fiscais.",
        "na_pratica": "",
    },
    "grande propriedade": {
        "termo": "Grande Propriedade",
        "explicacao": "Propriedade acima de 15 módulos fiscais.",
        "na_pratica": "",
    },
    "regularizacao fundiaria": {
        "termo": "Regularização Fundiária",
        "explicacao": (
            "É o processo de transformar a posse (uso sem documento) em propriedade com "
            "título registrado em cartório."
        ),
        "na_pratica": "No Ceará, quem cuida disso é o IDACE.",
    },
    "numero do incra": {
        "termo": "Número do INCRA",
        "explicacao": "Código de cadastro do imóvel rural no INCRA (o CCIR).",
        "na_pratica": "Cerca de 1 em cada 4 imóveis cadastrados não tem esse número preenchido.",
    },
    "numero do titulo": {
        "termo": "Número do Título",
        "explicacao": "Número do documento de titulação da terra.",
        "na_pratica": (
            "Quase metade dos registros não tem esse número — o que costuma indicar que a "
            "terra ainda não foi titulada."
        ),
    },
    "hectare": {
        "termo": "Hectare",
        "explicacao": "Unidade de medida de área.",
        "na_pratica": (
            "Um hectare é um quadrado de 100 metros por 100 metros — mais ou menos o tamanho "
            "de um campo de futebol e meio."
        ),
    },
}


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return texto.strip().lower()


def explicar_termo(termo: str) -> dict:
    chave = _normalizar(termo)
    if chave in GLOSSARIO:
        return dict(GLOSSARIO[chave])

    correspondencias = [v for k, v in GLOSSARIO.items() if chave in k or k in chave]
    if len(correspondencias) == 1:
        return dict(correspondencias[0])

    return {
        "erro": f"Não encontrei o termo '{termo}' no glossário.",
        "termos_disponiveis": listar_termos(),
    }


def listar_termos() -> list[str]:
    return [v["termo"] for v in GLOSSARIO.values()]
