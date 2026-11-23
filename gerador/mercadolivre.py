"""Acesso a API oficial do Mercado Livre (OAuth) e leitura de links meli.la.

O refresh token do Mercado Livre so pode ser usado uma vez: a cada renovacao
recebemos um novo, que guardamos criptografado em dados/ml_token.enc
(chave = secret TOKEN_KEY). O primeiro vem do workflow "Conectar Mercado Livre".
"""
import base64
import hashlib
import html
import os
import re

import requests

from .comum import CONFIG, DADOS, link_afiliado

API = "https://api.mercadolibre.com"
TOKEN_ARQ = DADOS / "ml_token.enc"
UA_NAVEGADOR = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 Chrome/130 Mobile Safari/537.36"


class SemCredenciais(Exception):
    pass


# ---------- token ----------

def _fernet():
    from cryptography.fernet import Fernet
    chave = os.environ.get("TOKEN_KEY", "")
    if not chave:
        raise SemCredenciais("secret TOKEN_KEY nao configurado")
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(chave.encode()).digest()))


def salvar_refresh_token(token):
    TOKEN_ARQ.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_ARQ.write_bytes(_fernet().encrypt(token.encode()))


def _ler_refresh_token():
    if TOKEN_ARQ.exists():
        return _fernet().decrypt(TOKEN_ARQ.read_bytes()).decode()
    return os.environ.get("ML_REFRESH_TOKEN", "")


def _cliente():
    cid, segredo = os.environ.get("ML_CLIENT_ID", ""), os.environ.get("ML_CLIENT_SECRET", "")
    if not cid or not segredo:
        raise SemCredenciais("secrets ML_CLIENT_ID / ML_CLIENT_SECRET nao configurados")
    return cid, segredo


def trocar_codigo(codigo, redirect_uri):
    """Primeira conexao: troca o 'code' da autorizacao por tokens."""
    cid, segredo = _cliente()
    r = requests.post(f"{API}/oauth/token", timeout=30, data={
        "grant_type": "authorization_code", "client_id": cid, "client_secret": segredo,
        "code": codigo.strip(), "redirect_uri": redirect_uri,
    })
    r.raise_for_status()
    salvar_refresh_token(r.json()["refresh_token"])


def obter_access_token():
    cid, segredo = _cliente()
    refresh = _ler_refresh_token()
    if not refresh:
        raise SemCredenciais("Mercado Livre ainda nao conectado (rode o workflow 'Conectar Mercado Livre')")
    r = requests.post(f"{API}/oauth/token", timeout=30, data={
        "grant_type": "refresh_token", "client_id": cid, "client_secret": segredo,
        "refresh_token": refresh,
    })
    if r.status_code >= 400:
        raise SemCredenciais(f"falha ao renovar token do Mercado Livre: {r.status_code} {r.text[:200]}")
    dados = r.json()
    salvar_refresh_token(dados["refresh_token"])
    return dados["access_token"]


# ---------- API ----------

class ML:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {obter_access_token()}"

    def get(self, caminho, **params):
        r = self.s.get(f"{API}{caminho}", params=params, timeout=30)
        if r.status_code >= 400:
            print(f"  [ML] {caminho} -> {r.status_code}")
            return None
        return r.json()

    def destaques(self, categoria):
        d = self.get(f"/highlights/MLB/category/{categoria}") or {}
        return d.get("content", [])

    def produto(self, pid):
        """Catalogo (/products) -> dados normalizados."""
        p = self.get(f"/products/{pid}")
        if not p:
            return None
        bb = p.get("buy_box_winner") or {}
        preco, original = bb.get("price"), bb.get("original_price")
        if preco is None:
            itens = (self.get(f"/products/{pid}/items", limit=1) or {}).get("results") or []
            if itens:
                preco, original = itens[0].get("price"), itens[0].get("original_price")
                bb = itens[0]
        if preco is None:
            return None
        fotos = [f.get("url") for f in p.get("pictures", []) if f.get("url")]
        return _normalizar(
            id=pid, titulo=p.get("name", ""), preco=preco, original=original,
            permalink=p.get("permalink") or f"https://www.mercadolivre.com.br/p/{pid}",
            fotos=fotos, frete_gratis=(bb.get("shipping") or {}).get("free_shipping", False),
            atributos=[f"{a.get('name')}: {a.get('value_name')}" for a in p.get("attributes", [])[:12]
                       if a.get("value_name")],
        )

    def item(self, iid):
        i = self.get(f"/items/{iid}")
        if not i or i.get("price") is None:
            return None
        return _normalizar(
            id=iid, titulo=i.get("title", ""), preco=i.get("price"), original=i.get("original_price"),
            permalink=i.get("permalink", ""),
            fotos=[f.get("secure_url") or f.get("url") for f in i.get("pictures", [])],
            frete_gratis=(i.get("shipping") or {}).get("free_shipping", False),
            atributos=[f"{a.get('name')}: {a.get('value_name')}" for a in i.get("attributes", [])[:12]
                       if a.get("value_name")],
        )

    def detalhe(self, entrada):
        tipo, ident = entrada.get("type", "ITEM"), entrada.get("id")
        return self.produto(ident) if tipo == "PRODUCT" else self.item(ident)


def _foto_grande(url):
    # As fotos da API vem pequenas (-I/-O); a versao -F e a maior.
    return re.sub(r"-[A-Z]\.(jpg|webp|png)$", r"-F.\1", url or "")


def _normalizar(id, titulo, preco, original, permalink, fotos, frete_gratis, atributos):
    desconto = 0
    if original and original > preco:
        desconto = round((1 - preco / original) * 100)
    return {
        "ml_id": id, "titulo": titulo.strip(), "preco": float(preco),
        "preco_original": float(original) if original and original > preco else None,
        "desconto": desconto, "link": link_afiliado(permalink),
        "fotos": [_foto_grande(f) for f in fotos if f][:4],
        "frete_gratis": bool(frete_gratis), "atributos": atributos,
    }


# ---------- links manuais (meli.la) ----------

def ler_link(url):
    """Le titulo e foto da previa do link (os mesmos dados que o WhatsApp mostra)."""
    r = requests.get(url, headers={"User-Agent": "WhatsApp/2.24.1.0"}, timeout=30, allow_redirects=True)
    r.raise_for_status()
    meta = dict(re.findall(r'<meta property="og:([a-z:]+)" content="([^"]*)"', r.text))
    titulo = html.unescape(meta.get("title", "")).strip()
    foto = meta.get("image", "")
    if not titulo or not foto:
        raise ValueError(f"nao consegui ler a previa de {url}")
    m = re.search(r"(MLB-?\d{6,})", r.url + " " + url)
    return {
        "ml_id": (m.group(1).replace("-", "") if m else url.rsplit("/", 1)[-1]),
        "titulo": titulo, "preco": None, "preco_original": None, "desconto": 0,
        "link": link_afiliado(url), "fotos": [foto], "frete_gratis": False, "atributos": [],
    }


def configurado():
    return bool(os.environ.get("ML_CLIENT_ID") and os.environ.get("ML_CLIENT_SECRET")
                and (TOKEN_ARQ.exists() or os.environ.get("ML_REFRESH_TOKEN")))


__all__ = ["ML", "SemCredenciais", "ler_link", "trocar_codigo", "configurado", "CONFIG"]
