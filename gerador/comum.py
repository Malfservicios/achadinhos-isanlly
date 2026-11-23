"""Caminhos, configuracao e utilidades compartilhadas."""
import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

RAIZ = Path(__file__).resolve().parent.parent
ASSETS = RAIZ / "assets"
FONTES = ASSETS / "fonts"
# Tudo o que e gerado (posts, midia, historico, token) fica em DADOS.
# No GitHub Actions essa pasta e o branch "dados" (sem historico, nao cresce).
DADOS = RAIZ / "dados"
POSTS_DIR = DADOS / "posts"
FUSO_BR = timezone(timedelta(hours=-3))

with open(RAIZ / "config.json", encoding="utf-8") as f:
    CONFIG = json.load(f)


def agora():
    return datetime.now(FUSO_BR)


def ler_json(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def salvar_json(caminho, dados):
    Path(caminho).parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=1)


def slug(texto, limite=40):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:limite].strip("-") or "produto"


def reais(valor, centavos=True):
    """199.9 -> 'R$ 199,90'"""
    if valor is None:
        return ""
    s = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    if not centavos and s.endswith(",00"):
        s = s[:-3]
    return f"R$ {s}"


def link_afiliado(url):
    """Converte o link de um produto em link de afiliada (parametros matt_word/matt_tool).

    Links curtos meli.la ja sao de afiliada e voltam sem mudanca.
    """
    if not url:
        return url
    partes = urlsplit(url)
    if partes.netloc.endswith("meli.la"):
        return url
    af = CONFIG["afiliado"]
    query = f"matt_word={af['matt_word']}&matt_tool={af['matt_tool']}"
    return urlunsplit((partes.scheme or "https", partes.netloc, partes.path, query, ""))
