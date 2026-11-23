"""Gera os posts do dia.

Uso:
  python -m gerador.main auto                      # busca ofertas no Mercado Livre (API)
  python -m gerador.main links "URL | 199,90 | 349,90" "URL2"
      -> posts de links escolhidos a mao (meli.la ou link de produto);
         preco e preco antigo sao opcionais.
  python -m gerador.main conectar CODIGO REDIRECT_URI   # primeira conexao com o ML
"""
import re
import sys
from datetime import datetime, timedelta

from . import mercadolivre as ml
from .arte import arte_post, baixar_imagem
from .comum import CONFIG, DADOS, POSTS_DIR, agora, ler_json, salvar_json, slug
from .textos import criativo, montar_texto
from .video import gerar_video

POSTS_JSON = DADOS / "posts.json"
HISTORICO = DADOS / "historico.json"


def _num(txt):
    txt = (txt or "").strip().replace("R$", "").replace(" ", "")
    if not txt:
        return None
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    return float(txt)


# ---------- escolha dos produtos ----------

def buscar_ofertas(historico, quantidade):
    api = ml.ML()
    cfg = CONFIG["busca"]
    candidatos = []
    for cat, nome in cfg["categorias"].items():
        destaques = api.destaques(cat)[:12]
        print(f"[{nome}] {len(destaques)} mais vendidos")
        for pos, ent in enumerate(destaques):
            if ent.get("id") in historico:
                continue
            p = api.detalhe(ent)
            if not p or not p["fotos"] or p["ml_id"] in historico:
                continue
            p["categoria"] = nome
            # pontuacao: desconto pesa mais; estar no topo dos mais vendidos tambem conta
            p["_nota"] = p["desconto"] * 2 + max(0, 12 - pos) * 1.5 + (5 if p["frete_gratis"] else 0)
            if p["desconto"] >= cfg["desconto_minimo"] or pos < 3:
                candidatos.append(p)
    candidatos.sort(key=lambda p: p["_nota"], reverse=True)
    escolhidos, por_cat = [], {}
    for p in candidatos:  # no maximo 2 por categoria, para variar
        if por_cat.get(p["categoria"], 0) >= 2:
            continue
        por_cat[p["categoria"]] = por_cat.get(p["categoria"], 0) + 1
        escolhidos.append(p)
        if len(escolhidos) >= quantidade:
            break
    return escolhidos


def produtos_de_links(linhas):
    produtos = []
    for linha in linhas:
        for parte in re.split(r"[\n;]+", linha):
            campos = [c.strip() for c in parte.split("|")]
            if not campos[0]:
                continue
            url = campos[0]
            m = re.search(r"MLB-?(\d{6,})", url)
            p = None
            if m and ml.configurado() and "meli.la" not in url:
                api = ml.ML()
                p = api.item(f"MLB{m.group(1)}") or api.produto(f"MLB{m.group(1)}")
            if p is None:
                p = ml.ler_link(url)
            preco, original = (_num(campos[1]) if len(campos) > 1 else None), (_num(campos[2]) if len(campos) > 2 else None)
            if preco is not None:
                p["preco"] = preco
            if original is not None and p.get("preco") and original > p["preco"]:
                p["preco_original"] = original
                p["desconto"] = round((1 - p["preco"] / original) * 100)
            p.setdefault("categoria", "")
            produtos.append(p)
    return produtos


# ---------- geracao ----------

def gerar_post(p):
    ts = agora()
    pid = f"{ts:%Y%m%d-%H%M}-{slug(p['titulo'], 30)}"
    pasta = POSTS_DIR / pid
    pasta.mkdir(parents=True, exist_ok=True)
    print(f"→ {p['titulo'][:70]}")
    fotos = []
    for url in p["fotos"][:3]:
        try:
            fotos.append(baixar_imagem(url))
        except Exception as e:  # noqa: BLE001
            print(f"  [foto] {url}: {e}")
    if not fotos:
        print("  sem foto, pulando")
        return None
    c = criativo(p)
    arte = arte_post(p, fotos[0], c.get("nome_curto"))
    arte.save(pasta / "imagem.jpg", quality=90, optimize=True)
    tem_video = False
    if CONFIG["video"]["ativo"]:
        tem_video = gerar_video(p, fotos, arte, pasta / "video.mp4", c.get("nome_curto"))
    return {
        "id": pid, "criado_em": ts.isoformat(timespec="minutes"), "ml_id": p["ml_id"],
        "titulo": p["titulo"], "nome_curto": c.get("nome_curto"), "categoria": p.get("categoria", ""),
        "preco": p.get("preco"), "preco_original": p.get("preco_original"), "desconto": p.get("desconto", 0),
        "link": p["link"], "texto": montar_texto(p, c),
        "imagem": f"posts/{pid}/imagem.jpg", "video": f"posts/{pid}/video.mp4" if tem_video else None,
    }


def limpar_antigos(posts):
    limite = agora() - timedelta(days=CONFIG["busca"]["dias_guardar_midia"])
    manter = [p for p in posts if datetime.fromisoformat(p["criado_em"]) >= limite]
    ids = {p["id"] for p in manter}
    if POSTS_DIR.exists():
        for pasta in POSTS_DIR.iterdir():
            if pasta.is_dir() and pasta.name not in ids:
                for f in pasta.iterdir():
                    f.unlink()
                pasta.rmdir()
    return manter


def main(argv):
    modo = argv[0] if argv else "auto"
    if modo == "conectar":
        ml.trocar_codigo(argv[1], argv[2])
        print("Mercado Livre conectado ✔")
        return 0

    historico = ler_json(HISTORICO, {})
    limite_hist = (agora() - timedelta(days=CONFIG["busca"]["dias_sem_repetir"])).isoformat()
    historico = {k: v for k, v in historico.items() if v >= limite_hist}

    if modo == "links":
        produtos = produtos_de_links(argv[1:])
    else:
        if not ml.configurado():
            print("Mercado Livre ainda nao conectado: nada a buscar. Veja o LEIAME.")
            return 0
        produtos = buscar_ofertas(historico, CONFIG["busca"]["posts_por_execucao"])

    posts = ler_json(POSTS_JSON, [])
    novos = []
    for p in produtos:
        post = gerar_post(p)
        if post:
            novos.append(post)
            historico[p["ml_id"]] = agora().isoformat()
    # o mesmo produto gerado de novo substitui o post antigo
    repetidos = {n["ml_id"] for n in novos}
    posts = limpar_antigos(novos + [p for p in posts if p.get("ml_id") not in repetidos])
    salvar_json(POSTS_JSON, posts)
    salvar_json(HISTORICO, historico)
    print(f"\n{len(novos)} post(s) novo(s). Total no painel: {len(posts)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
