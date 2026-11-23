"""Arte do post: fundo de madeira com luzinhas (como o logo do grupo), foto real do
produto num cartao claro, selo de desconto e preco em destaque.

Cada produto ganha um fundo diferente (luzes sorteadas pelo id do produto).
"""
import io
import random

import requests
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .comum import ASSETS, CONFIG, FONTES, reais

W, H = 1080, 1350
COR = {k: tuple(v) for k, v in CONFIG["marca"]["cores"].items()}
BRANCO = (255, 255, 255)


def fonte(nome, tam):
    return ImageFont.truetype(str(FONTES / f"{nome}.ttf"), tam)


def baixar_imagem(url):
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content)).convert("RGBA")


# ---------- fundo ----------

def fundo(semente):
    rnd = random.Random(semente)
    base = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(base)
    a, b = COR["fundo_escuro"], COR["fundo_madeira"]
    for y in range(H):
        t = abs(y / H - 0.45) * 1.6
        t = min(1, t)
        d.line([(0, y), (W, y)], fill=tuple(int(b[i] * (1 - t) + a[i] * t) for i in range(3)))
    # veios de madeira sutis
    veios = Image.new("L", (W, H), 0)
    dv = ImageDraw.Draw(veios)
    for _ in range(26):
        y0 = rnd.randint(0, H)
        pts = [(x, y0 + 14 * rnd.random() * ((x // 120) % 2 * 2 - 1)) for x in range(-40, W + 80, 120)]
        dv.line(pts, fill=rnd.randint(10, 22), width=rnd.randint(2, 6))
    veios = veios.filter(ImageFilter.GaussianBlur(3))
    base = Image.composite(Image.new("RGB", (W, H), COR["fundo_escuro"]), base, veios)
    # luzinhas (bokeh) - mais no topo, como o cordao de luz do logo
    luz = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dl = ImageDraw.Draw(luz)
    for _ in range(46):
        x, y = rnd.randint(-40, W + 40), int(abs(rnd.gauss(0, 0.28)) * H)
        r = rnd.randint(10, 48)
        dl.ellipse((x - r, y - r, x + r, y + r), fill=COR["luz"] + (rnd.randint(40, 120),))
    luz = luz.filter(ImageFilter.GaussianBlur(9))
    pontos = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    dp = ImageDraw.Draw(pontos)
    for _ in range(70):
        x, y = rnd.randint(0, W), int(abs(rnd.gauss(0, 0.2)) * H)
        r = rnd.randint(2, 5)
        dp.ellipse((x - r, y - r, x + r, y + r), fill=(255, 236, 190, 230))
    pontos = pontos.filter(ImageFilter.GaussianBlur(1.2))
    img = base.convert("RGBA")
    img.alpha_composite(luz)
    img.alpha_composite(pontos)
    # vinheta
    vin = Image.new("L", (W, H), 0)
    ImageDraw.Draw(vin).ellipse((-W * 0.3, -H * 0.2, W * 1.3, H * 1.2), fill=255)
    vin = vin.filter(ImageFilter.GaussianBlur(120))
    escuro = Image.new("RGBA", (W, H), COR["fundo_escuro"] + (255,))
    return Image.composite(img, escuro, vin)


# ---------- pecas ----------

def cabecalho(img):
    d = ImageDraw.Draw(img)
    logo = Image.open(ASSETS / "logo.png").convert("RGBA").resize((132, 132), Image.LANCZOS)
    aro = Image.new("RGBA", (146, 146), (0, 0, 0, 0))
    ImageDraw.Draw(aro).ellipse((0, 0, 145, 145), fill=COR["dourado"] + (255,))
    img.alpha_composite(aro, (52, 38))
    img.alpha_composite(logo, (59, 45))
    d.text((216, 44), "Os Achadinhos", font=fonte("Pacifico-Regular", 54), fill=COR["creme"])
    d.text((222, 112), "da Isanlly", font=fonte("Pacifico-Regular", 40), fill=COR["dourado"])
    selo = "ACHADINHO DO DIA"
    f = fonte("Poppins-Bold", 26)
    w = d.textlength(selo, font=f)
    x1 = W - 56
    d.rounded_rectangle((x1 - w - 48, 74, x1, 126), radius=26, fill=COR["turquesa"])
    d.text((x1 - w - 24, 81), selo, font=f, fill=BRANCO)


def aparar_branco(foto):
    """Corta as bordas brancas/transparentes da foto para o produto aparecer maior."""
    rgb = Image.new("RGB", foto.size, BRANCO)
    rgb.paste(foto, (0, 0), foto)
    cinza = rgb.convert("L").point(lambda v: 255 if v < 244 else 0)
    caixa = cinza.getbbox()
    if not caixa:
        return foto.copy()
    m = 12
    caixa = (max(0, caixa[0] - m), max(0, caixa[1] - m), min(foto.width, caixa[2] + m), min(foto.height, caixa[3] + m))
    return foto.crop(caixa)


def cartao_produto(img, foto, caixa, raio=46):
    x0, y0, x1, y1 = caixa
    sombra = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle((x0 + 6, y0 + 18, x1 + 6, y1 + 22), radius=raio, fill=(0, 0, 0, 150))
    img.alpha_composite(sombra.filter(ImageFilter.GaussianBlur(22)))
    cartao = Image.new("RGBA", (x1 - x0, y1 - y0), (0, 0, 0, 0))
    ImageDraw.Draw(cartao).rounded_rectangle((0, 0, x1 - x0 - 1, y1 - y0 - 1), radius=raio, fill=BRANCO + (255,))
    img.alpha_composite(cartao, (x0, y0))
    pad = 44
    fw, fh = x1 - x0 - 2 * pad, y1 - y0 - 2 * pad
    f = aparar_branco(foto)
    f.thumbnail((fw, fh), Image.LANCZOS)
    if f.width < fw * 0.6 and f.height < fh * 0.6:  # foto pequena: amplia um pouco
        esc = min(fw * 0.8 / f.width, fh * 0.8 / f.height)
        f = f.resize((int(f.width * esc), int(f.height * esc)), Image.LANCZOS)
    img.alpha_composite(f, (x0 + pad + (fw - f.width) // 2, y0 + pad + (fh - f.height) // 2))


def selo_desconto(img, desconto, centro, r=96):
    if not desconto:
        return
    cx, cy = centro
    camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(camada)
    d.ellipse((cx - r + 4, cy - r + 10, cx + r + 4, cy + r + 10), fill=(0, 0, 0, 110))
    camada = camada.filter(ImageFilter.GaussianBlur(10))
    d = ImageDraw.Draw(camada)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=COR["desconto"] + (255,))
    d.ellipse((cx - r + 9, cy - r + 9, cx + r - 9, cy + r - 9), outline=(255, 255, 255, 170), width=3)
    img.alpha_composite(camada)
    d = ImageDraw.Draw(img)
    d.text((cx, cy - 14), f"-{desconto}%", font=fonte("Poppins-ExtraBold", 56), fill=BRANCO, anchor="mm")
    d.text((cx, cy + 38), "OFF", font=fonte("Poppins-Bold", 28), fill=BRANCO, anchor="mm")


def quebrar(d, texto, f, largura, max_linhas):
    palavras, linhas, atual = texto.split(), [], ""
    for p in palavras:
        teste = f"{atual} {p}".strip()
        if d.textlength(teste, font=f) <= largura:
            atual = teste
        else:
            linhas.append(atual)
            atual = p
    linhas.append(atual)
    if len(linhas) > max_linhas:
        linhas = linhas[:max_linhas]
        while d.textlength(linhas[-1] + "…", font=f) > largura:
            linhas[-1] = linhas[-1].rsplit(" ", 1)[0]
        linhas[-1] += "…"
    return linhas


def bloco_preco(img, p, y):
    d = ImageDraw.Draw(img)
    if p.get("preco") is None:
        d.text((W // 2, y + 70), "CONFIRA O PREÇO NO LINK", font=fonte("Poppins-ExtraBold", 58),
               fill=COR["dourado"], anchor="mm")
        return
    if p.get("preco_original"):
        f_de = fonte("Poppins-Medium", 38)
        txt = f"De {reais(p['preco_original'])}"
        w = d.textlength(txt, font=f_de)
        d.text((76, y), txt, font=f_de, fill=COR["creme"] + (190,))
        x_valor = 76 + d.textlength("De ", font=f_de)
        d.line((x_valor, y + 27, 76 + w, y + 27), fill=COR["desconto"], width=4)
        y += 50
    inteiro, cent = f"{p['preco']:,.2f}".replace(",", ".").rsplit(".", 1)
    f_rs, f_val, f_cent = fonte("Poppins-Bold", 46), fonte("Poppins-ExtraBold", 124), fonte("Poppins-Bold", 52)
    x = 76
    d.text((x, y + 42), "R$", font=f_rs, fill=COR["dourado"])
    x += d.textlength("R$", font=f_rs) + 14
    d.text((x, y - 6), inteiro, font=f_val, fill=COR["dourado"])
    x += d.textlength(inteiro, font=f_val) + 6
    d.text((x, y + 18), f",{cent}", font=f_cent, fill=COR["dourado"])
    if p.get("frete_gratis"):
        f = fonte("Poppins-Bold", 26)
        txt = "FRETE GRÁTIS"
        w = d.textlength(txt, font=f)
        d.rounded_rectangle((W - 76 - w - 40, y + 60, W - 76, y + 112), radius=26, fill=COR["turquesa"])
        d.text((W - 76 - w - 20, y + 68), txt, font=f, fill=BRANCO)


def rodape(img, texto="Toque no link da mensagem"):
    d = ImageDraw.Draw(img)
    d.line((76, H - 92, W - 76, H - 92), fill=COR["dourado"] + (150,), width=2)
    f = fonte("Poppins-SemiBold", 28)
    d.text((76, H - 70), texto, font=f, fill=COR["creme"])
    d.text((W - 76, H - 70), CONFIG["marca"]["instagram_tiktok"], font=f, fill=COR["dourado"], anchor="ra")


# ---------- composicoes ----------

def arte_post(p, foto, nome_curto=None):
    """Imagem principal do post (1080x1350)."""
    img = fundo(p["ml_id"])
    cabecalho(img)
    cartao_produto(img, foto, (70, 196, W - 70, 880))
    selo_desconto(img, p.get("desconto"), (W - 128, 262))
    d = ImageDraw.Draw(img)
    f = fonte("Poppins-SemiBold", 44)
    y = 912
    for linha in quebrar(d, nome_curto or p["titulo"], f, W - 152, 2):
        d.text((76, y), linha, font=f, fill=COR["creme"])
        y += 58
    bloco_preco(img, p, 1052 if p.get("preco_original") else 1078)
    rodape(img, "Toque no link da mensagem")
    return img.convert("RGB")


def arte_slide(p, foto, indice, nome_curto=None):
    """Quadros do video: foto em destaque, sem preco (o preco aparece no final)."""
    img = fundo(f"{p['ml_id']}-{indice}")
    cabecalho(img)
    cartao_produto(img, foto, (70, 196, W - 70, 1040))
    selo_desconto(img, p.get("desconto"), (W - 128, 262))
    d = ImageDraw.Draw(img)
    f = fonte("Poppins-SemiBold", 42)
    y = 1080
    for linha in quebrar(d, nome_curto or p["titulo"], f, W - 152, 2):
        d.text((W // 2, y), linha, font=f, fill=COR["creme"], anchor="ma")
        y += 54
    rodape(img, "Oferta no link do grupo")
    return img.convert("RGB")
