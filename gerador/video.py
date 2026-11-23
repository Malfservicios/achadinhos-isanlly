"""Video de ~15 s com narracao, musica e legendas.

Cenas (cada uma comeca junto com a frase da narracao correspondente):
  1. Abertura   - logo, "ACHADINHO DO DIA" (gancho falado)
  2. Produto    - fotos com zoom suave, selo de desconto, beneficios (descricao falada)
  3. Preco      - preco antigo riscado e preco novo em destaque (preco falado)
  4. Chamada    - "toque no link", logo e @ (chamada falada)

Os quadros sao desenhados com Pillow e enviados direto ao FFmpeg.
"""
import math
import os
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from . import audio
from .arte import BRANCO, COR, H, W, aparar_branco, fonte, fundo, quebrar
from .comum import ASSETS, CONFIG, reais
from .textos import roteiro_narracao

FPS = 30
TRANS = 0.35  # duracao das transicoes entre cenas


def ffmpeg():
    return os.environ.get("FFMPEG") or shutil.which("ffmpeg")


# ---------- easing ----------

def _clamp(x):
    return max(0.0, min(1.0, x))


def ease_out(x):
    x = _clamp(x)
    return 1 - (1 - x) ** 3


def ease_back(x):
    x = _clamp(x)
    c = 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def _prog(t, ini, dur):
    return _clamp((t - ini) / dur)


# ---------- camadas (RGBA) ----------

def _texto(txt, f, cor, sombra=True):
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    x0, y0, x1, y1 = d.textbbox((0, 0), txt, font=f)
    pad = 12
    img = Image.new("RGBA", (x1 - x0 + 2 * pad, y1 - y0 + 2 * pad), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    if sombra:
        s = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(s).text((pad - x0 + 2, pad - y0 + 4), txt, font=f, fill=(0, 0, 0, 150))
        img.alpha_composite(s.filter(ImageFilter.GaussianBlur(5)))
    dd.text((pad - x0, pad - y0), txt, font=f, fill=cor)
    return img


def _pilula(txt, f, fundo_cor, cor=BRANCO, px=28, py=12):
    t = _texto(txt, f, cor, sombra=False)
    img = Image.new("RGBA", (t.width + 2 * px, t.height + 2 * py), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius=img.height // 2,
                                          fill=fundo_cor)
    img.alpha_composite(t, (px, py))
    return img


def _logo(d):
    esc = 3
    D = d * esc
    out = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, D - 1, D - 1), fill=COR["dourado"] + (255,))
    aro = int(D * 0.05)
    logo = Image.open(ASSETS / "logo.png").convert("RGBA").resize((D - 2 * aro, D - 2 * aro), Image.LANCZOS)
    out.alpha_composite(logo, (aro, aro))
    return out.resize((d, d), Image.LANCZOS)


def _selo(desconto, r=96):
    img = Image.new("RGBA", (2 * r + 40, 2 * r + 40), (0, 0, 0, 0))
    c = r + 20
    s = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(s).ellipse((c - r + 4, c - r + 10, c + r + 4, c + r + 10), fill=(0, 0, 0, 120))
    img.alpha_composite(s.filter(ImageFilter.GaussianBlur(9)))
    d = ImageDraw.Draw(img)
    d.ellipse((c - r, c - r, c + r, c + r), fill=COR["desconto"] + (255,))
    d.ellipse((c - r + 9, c - r + 9, c + r - 9, c + r - 9), outline=(255, 255, 255, 170), width=3)
    d.text((c, c - 14), f"-{desconto}%", font=fonte("Poppins-ExtraBold", 56), fill=BRANCO, anchor="mm")
    d.text((c, c + 38), "OFF", font=fonte("Poppins-Bold", 28), fill=BRANCO, anchor="mm")
    return img


def _cartao(w, h, raio=44):
    img = Image.new("RGBA", (w + 80, h + 80), (0, 0, 0, 0))
    s = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(s).rounded_rectangle((40, 58, 40 + w, 58 + h), radius=raio, fill=(0, 0, 0, 150))
    img.alpha_composite(s.filter(ImageFilter.GaussianBlur(20)))
    ImageDraw.Draw(img).rounded_rectangle((40, 40, 40 + w - 1, 40 + h - 1), radius=raio, fill=BRANCO + (255,))
    return img


def _mascara_arredondada(w, h, raio):
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, w - 1, h - 1), radius=raio, fill=255)
    return m


def _foto_no_quadro(foto, w, h, pad=40):
    """Foto aparada e centralizada num quadro branco w x h (RGB)."""
    f = aparar_branco(foto)
    f.thumbnail((w - 2 * pad, h - 2 * pad), Image.LANCZOS)
    if f.width < (w - 2 * pad) * 0.6 and f.height < (h - 2 * pad) * 0.6:
        e = min((w - 2 * pad) * 0.8 / f.width, (h - 2 * pad) * 0.8 / f.height)
        f = f.resize((int(f.width * e), int(f.height * e)), Image.LANCZOS)
    q = Image.new("RGBA", (w, h), BRANCO + (255,))
    q.alpha_composite(f, ((w - f.width) // 2, (h - f.height) // 2))
    return q.convert("RGB")


def _colar(base, camada, cx, cy, escala=1.0, alfa=1.0):
    """Cola a camada centrada em (cx, cy), com escala e opacidade."""
    if escala <= 0.01 or alfa <= 0.01:
        return
    c = camada
    if abs(escala - 1) > 0.005:
        c = c.resize((max(1, int(c.width * escala)), max(1, int(c.height * escala))), Image.BILINEAR)
    if alfa < 0.999:
        c = c.copy()
        c.putalpha(c.getchannel("A").point(lambda a: int(a * alfa)))
    base.alpha_composite(c, (int(cx - c.width / 2), int(cy - c.height / 2)))


# ---------- legendas ----------

def _blocos_legenda(texto, ini, fim, max_palavras=9):
    """Divide a fala em legendas curtas, cortando em pontuacao e sem deixar palavra sozinha."""
    palavras = texto.split()
    grupos, atual = [], []
    for p in palavras:
        atual.append(p)
        if len(atual) >= max_palavras or (p.endswith((".", "!", "?")) and len(atual) >= 3):
            grupos.append(atual)
            atual = []
    if atual:
        if grupos and len(atual) <= 2:
            grupos[-1] += atual
        else:
            grupos.append(atual)
    grupos = [" ".join(g) for g in grupos]
    total = sum(len(g) for g in grupos) or 1
    t, out = ini, []
    for g in grupos:
        d = (fim - ini) * len(g) / total
        out.append((t, t + d, g))
        t += d
    return out


def _camada_legenda(txt):
    f = fonte("Poppins-SemiBold", 40)
    d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    linhas = quebrar(d, txt, f, 880, 2)
    alt = 54 * len(linhas) + 28
    larg = int(max(d.textlength(l, font=f) for l in linhas)) + 56
    img = Image.new("RGBA", (larg, alt), (0, 0, 0, 0))
    dd = ImageDraw.Draw(img)
    dd.rounded_rectangle((0, 0, larg - 1, alt - 1), radius=22, fill=(20, 10, 4, 185))
    for i, l in enumerate(linhas):
        dd.text((larg // 2, 14 + i * 54), l, font=f, fill=BRANCO, anchor="ma")
    return img


# ---------- montagem ----------

class Video:
    def __init__(self, p, fotos, c, tempos):
        self.p, self.c = p, c
        self.t = tempos  # dict de cenas: inicio de cada uma e total
        self.bg = fundo(p["ml_id"]).convert("RGBA")
        self.rnd = random.Random(p["ml_id"])
        # cabecalho
        self.logo_peq = _logo(132)
        self.nome1 = _texto("Os Achadinhos", fonte("Pacifico-Regular", 54), COR["creme"])
        self.nome2 = _texto("da Isanlly", fonte("Pacifico-Regular", 40), COR["dourado"])
        self.pill = _pilula("ACHADINHO DO DIA", fonte("Poppins-Bold", 26), COR["turquesa"] + (255,))
        # abertura
        self.logo_grande = _logo(360)
        self.titulo1 = _texto("Achadinho", fonte("Pacifico-Regular", 128), COR["dourado"])
        self.titulo2 = _texto("DO DIA", fonte("Poppins-ExtraBold", 84), COR["creme"])
        # produto
        self.cw, self.ch = 900, 690
        self.cartao = _cartao(self.cw, self.ch)
        self.mascara = _mascara_arredondada(self.cw - 24, self.ch - 24, 34)
        self.fotos = [_foto_no_quadro(f, self.cw - 24, self.ch - 24) for f in fotos[:3]]
        self.selo = _selo(p["desconto"]) if p.get("desconto") else None
        nome = c.get("nome_curto") or p["titulo"]
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        self.nome_linhas = [_texto(l, fonte("Poppins-SemiBold", 44), COR["creme"])
                            for l in quebrar(d, nome, fonte("Poppins-SemiBold", 44), W - 160, 2)]
        self.beneficios = [_pilula("✓  " + b, fonte("Poppins-SemiBold", 30), (255, 255, 255, 34), COR["creme"])
                           for b in (c.get("beneficios") or [])[:3]]
        # preco
        self.foto_preco = _foto_no_quadro(fotos[0], 560, 440)
        self.cartao_preco = _cartao(580, 460, raio=36)
        self.masc_preco = _mascara_arredondada(560, 440, 28)
        if p.get("preco") is not None:
            self.de = _texto(f"De {reais(p['preco_original'])}", fonte("Poppins-Medium", 46), COR["creme"]) \
                if p.get("preco_original") else None
            self.por = _texto("POR APENAS", fonte("Poppins-Bold", 40), COR["creme"])
            inteiro, cent = f"{p['preco']:,.2f}".replace(",", ".").rsplit(".", 1)
            self.preco = self._camada_preco(inteiro, cent)
        else:
            self.de = None
            self.por = _texto("CONFIRA O PREÇO", fonte("Poppins-ExtraBold", 70), COR["dourado"])
            self.preco = _texto("NO LINK", fonte("Poppins-ExtraBold", 110), COR["dourado"])
        self.frete = _pilula("FRETE GRÁTIS", fonte("Poppins-Bold", 34), COR["turquesa"] + (255,)) \
            if p.get("frete_gratis") else None
        # chamada
        self.cta1 = _texto("Toque no link", fonte("Poppins-ExtraBold", 78), COR["creme"])
        self.cta2 = _texto("da mensagem", fonte("Poppins-ExtraBold", 78), COR["dourado"])
        self.arroba = _texto(CONFIG["marca"]["instagram_tiktok"], fonte("Poppins-SemiBold", 40), COR["creme"])
        # legendas
        self.legendas = []
        for ini, fim, txt in tempos.get("legendas", []):
            self.legendas.append((ini, fim, _camada_legenda(txt)))
        # brilhos
        self.brilhos = [(self.rnd.randint(40, W - 40), self.rnd.randint(30, H - 30), self.rnd.uniform(0, 6.28),
                         self.rnd.uniform(1.5, 3.5), self.rnd.randint(2, 5)) for _ in range(28)]

    def _camada_preco(self, inteiro, cent):
        f_rs, f_val, f_cent = fonte("Poppins-Bold", 56), fonte("Poppins-ExtraBold", 170), fonte("Poppins-Bold", 70)
        d = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        w = d.textlength("R$", font=f_rs) + 16 + d.textlength(inteiro, font=f_val) + 8 + d.textlength("," + cent, font=f_cent)
        img = Image.new("RGBA", (int(w) + 40, 230), (0, 0, 0, 0))
        s = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ds, dd = ImageDraw.Draw(s), ImageDraw.Draw(img)
        x = 20
        for txt, f, y in (("R$", f_rs, 92), (inteiro, f_val, 0), ("," + cent, f_cent, 34)):
            ds.text((x + 3, y + 6), txt, font=f, fill=(0, 0, 0, 160))
            dd.text((x, y), txt, font=f, fill=COR["dourado"])
            x += d.textlength(txt, font=f) + (16 if txt == "R$" else 8)
        sombra = s.filter(ImageFilter.GaussianBlur(6))
        sombra.alpha_composite(img)
        return sombra

    # --- cenas ---
    def _brilhar(self, img, t):
        d = ImageDraw.Draw(img)
        for x, y, fase, vel, r in self.brilhos:
            a = int(140 * (0.5 + 0.5 * math.sin(fase + t * vel)))
            d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 236, 190, a))

    def _cabecalho(self, img, t, entrada=1.0):
        a = ease_out(entrada)
        _colar(img, self.logo_peq, 52 + 73, 38 + 73 - (1 - a) * 40, 1, a)
        _colar(img, self.nome1, 216 + self.nome1.width / 2 - 12, 44 + self.nome1.height / 2 - 12 - (1 - a) * 40, 1, a)
        _colar(img, self.nome2, 222 + self.nome2.width / 2 - 12, 112 + self.nome2.height / 2 - 12 - (1 - a) * 40, 1, a)
        _colar(img, self.pill, W - 56 - self.pill.width / 2 + (1 - a) * 300, 100, 1, a)

    def cena_abertura(self, t, dur):
        img = self.bg.copy()
        self._brilhar(img, t)
        _colar(img, self.logo_grande, W / 2, 470, ease_back(_prog(t, 0.0, 0.55)) * (1 + 0.02 * math.sin(t * 3)))
        _colar(img, self.titulo1, W / 2, 780 + (1 - ease_out(_prog(t, 0.3, 0.5))) * 80, 1, _prog(t, 0.3, 0.4))
        _colar(img, self.titulo2, W / 2, 905, ease_back(_prog(t, 0.55, 0.45)))
        return img

    def cena_produto(self, t, dur):
        img = self.bg.copy()
        self._brilhar(img, t)
        self._cabecalho(img, t, _prog(t, 0, 0.5))
        # cartao entra subindo
        e = ease_out(_prog(t, 0.0, 0.55))
        cy = 200 + self.ch / 2 + (1 - e) * 220
        _colar(img, self.cartao, W / 2, cy + 0, 1, e)
        # fotos com zoom suave e troca com fusao
        n = len(self.fotos)
        seg = dur / n
        i = min(n - 1, int(t / seg))
        quadro = self._ken_burns(self.fotos[i], (t - i * seg) / seg)
        if i + 1 < n and t > (i + 1) * seg - 0.35:
            prox = self._ken_burns(self.fotos[i + 1], 0)
            quadro = Image.blend(quadro, prox, _clamp((t - ((i + 1) * seg - 0.35)) / 0.35))
        q = quadro.convert("RGBA")
        q.putalpha(self.mascara.point(lambda v: int(v * e)))
        img.alpha_composite(q, (int(W / 2 - q.width / 2), int(cy - q.height / 2)))
        if self.selo:
            pulso = 1 + 0.035 * math.sin(max(0, t - 0.9) * 5)
            _colar(img, self.selo, W - 140, 240, ease_back(_prog(t, 0.45, 0.45)) * pulso)
        # nome e beneficios
        y = 950
        for k, l in enumerate(self.nome_linhas):
            a = ease_out(_prog(t, 0.35 + 0.1 * k, 0.45))
            _colar(img, l, W / 2, y + (1 - a) * 30, 1, a)
            y += 56
        y += 34
        for k, b in enumerate(self.beneficios):
            a = ease_out(_prog(t, 1.0 + 0.7 * k, 0.45))
            if y + b.height / 2 > H - 175:
                break
            _colar(img, b, 70 + b.width / 2 - (1 - a) * 200, y, 1, a)
            y += b.height + 10
        return img

    def _ken_burns(self, foto, x):
        z = 1.0 + 0.07 * ease_out(_clamp(x))
        w, h = foto.size
        cw, ch = int(w / z), int(h / z)
        ox, oy = (w - cw) // 2, (h - ch) // 2
        return foto.crop((ox, oy, ox + cw, oy + ch)).resize((w, h), Image.BILINEAR)

    def cena_preco(self, t, dur):
        img = self.bg.copy()
        self._brilhar(img, t)
        self._cabecalho(img, t)
        _colar(img, self.cartao_preco, W / 2, 470, 0.9 + 0.1 * ease_out(_prog(t, 0, 0.4)))
        fz = self._ken_burns(self.foto_preco, t / max(dur, 0.1)).convert("RGBA")
        fz.putalpha(self.masc_preco)
        s = 0.9 + 0.1 * ease_out(_prog(t, 0, 0.4))
        _colar(img, fz, W / 2, 470, s)
        y = 790
        if self.de:
            a = ease_out(_prog(t, 0.1, 0.35))
            _colar(img, self.de, W / 2, y, 1, a)
            # risco animado
            r = ease_out(_prog(t, 0.45, 0.35))
            if r > 0:
                d = ImageDraw.Draw(img)
                x0 = W / 2 - self.de.width / 2 + 100
                x1 = x0 + (self.de.width - 124) * r
                d.line((x0, y + 4, x1, y + 4), fill=COR["desconto"], width=6)
            y += 80
        _colar(img, self.por, W / 2, y, 1, ease_out(_prog(t, 0.55, 0.3)))
        y += 135
        _colar(img, self.preco, W / 2, y, ease_back(_prog(t, 0.75, 0.5)) * (1 + 0.025 * math.sin(max(0, t - 1.3) * 4)))
        if self.selo:
            _colar(img, self.selo, W - 140, 300, ease_back(_prog(t, 1.0, 0.4)) * 0.95)
        if self.frete:
            _colar(img, self.frete, W / 2, y + 155, 1, ease_out(_prog(t, 1.2, 0.35)))
        return img

    def cena_chamada(self, t, dur):
        img = self.bg.copy()
        self._brilhar(img, t)
        _colar(img, self.logo_grande, W / 2, 380, 0.8 * ease_back(_prog(t, 0, 0.5)))
        _colar(img, self.cta1, W / 2, 700 + (1 - ease_out(_prog(t, 0.15, 0.4))) * 60, 1, _prog(t, 0.15, 0.3))
        _colar(img, self.cta2, W / 2, 800 + (1 - ease_out(_prog(t, 0.3, 0.4))) * 60, 1, _prog(t, 0.3, 0.3))
        # seta pulando
        a = _prog(t, 0.5, 0.3)
        if a > 0:
            d = ImageDraw.Draw(img)
            yy = 935 + 18 * abs(math.sin(t * 4.5))
            cor = COR["dourado"] + (int(255 * a),)
            d.polygon([(W / 2 - 46, yy), (W / 2 + 46, yy), (W / 2, yy + 56)], fill=cor)
        _colar(img, self.arroba, W / 2, 1075, 1, _prog(t, 0.6, 0.4))
        return img

    def quadro(self, t):
        cenas = self.t["cenas"]  # [(inicio, funcao)]
        idx = max(i for i, (ini, _) in enumerate(cenas) if t >= ini)
        ini, func = cenas[idx]
        fim = cenas[idx + 1][0] if idx + 1 < len(cenas) else self.t["total"]
        img = func(self, t - ini, fim - ini)
        # transicao: a cena anterior some por cima nos primeiros TRANS segundos
        if idx > 0 and t - ini < TRANS:
            ini_a, func_a = cenas[idx - 1]
            ant = func_a(self, t - ini_a, ini - ini_a)
            img = Image.blend(ant, img, ease_out((t - ini) / TRANS))
        for l0, l1, camada in self.legendas:
            if l0 <= t < l1:
                a = min(_prog(t, l0, 0.12), _clamp((l1 - t) / 0.12))
                _colar(img, camada, W / 2, H - 120 - camada.height / 2 + 40, 1, a)
                break
        return img


def _tempos(dur_blocos, alvo):
    """Decide quando cada cena/frase comeca."""
    g, d, p, c = (dur_blocos[k] for k in ("gancho", "descricao", "preco", "cta"))
    t_g = 0.45
    t_d = max(t_g + g + 0.25, 2.3)
    t_p = max(t_d + d + 0.35, t_d + 4.0, alvo - (p + 0.45 + c + 0.9))
    t_c = t_p + max(p + 0.45, 2.6)
    total = t_c + max(c + 0.9, 2.0)
    return {"gancho": t_g, "descricao": t_d, "preco": t_p, "cta": t_c, "total": total}


def gerar_video(p, fotos, c, destino):
    exe = ffmpeg()
    if not exe:
        print("  [video] ffmpeg nao encontrado; pulando video")
        return False
    cfg = CONFIG["video"]
    alvo = cfg.get("duracao_alvo", 15)
    roteiro = roteiro_narracao(p, c)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        blocos = audio.narrar_blocos(roteiro, tmp, exe) if cfg.get("narracao", True) else None
        if blocos:
            durs = {k: len(v) / audio.SR for k, v in blocos.items()}
        else:  # sem voz: tempos fixos
            durs = {"gancho": 1.2, "descricao": 4.5, "preco": 2.2, "cta": 1.4}
        tt = _tempos(durs, alvo)
        total = tt["total"]
        legendas = []
        if blocos and cfg.get("legendas", True):
            for k in ("gancho", "descricao", "preco", "cta"):
                legendas += _blocos_legenda(roteiro[k], tt[k], tt[k] + durs[k])
        tempos = {
            "cenas": [(0.0, Video.cena_abertura), (tt["descricao"] - 0.15, Video.cena_produto),
                      (tt["preco"] - 0.15, Video.cena_preco), (tt["cta"] - 0.15, Video.cena_chamada)],
            "total": total, "legendas": legendas,
        }
        v = Video(p, fotos, c, tempos)

        # 1) imagem -> video
        so_video = tmp / "video.mp4"
        cmd = [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
               "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
               "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(so_video)]
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        for i in range(int(total * FPS)):
            proc.stdin.write(v.quadro(i / FPS).convert("RGB").tobytes())
        proc.stdin.close()
        if proc.wait() != 0:
            print("  [video] ffmpeg falhou ao codificar")
            return False

        # 2) audio: narracao posicionada + musica com "ducking" sob a voz
        n = int(total * audio.SR)
        voz = np.zeros(n, dtype=np.float32)
        if blocos:
            for k, s in blocos.items():
                i0 = int(tt[k] * audio.SR)
                voz[i0:i0 + len(s)] += s[: max(0, n - i0)]
        voz_wav, mus_wav = tmp / "voz.wav", tmp / "musica.wav"
        audio.salvar_wav(voz_wav, voz * 0.95)
        entradas = ["-i", str(so_video), "-i", str(voz_wav)]
        if cfg.get("musica", True):
            audio.musica(p["ml_id"], total, mus_wav)
            entradas += ["-i", str(mus_wav)]
            filtro = ("[2:a]volume=0.42[m];[1:a]asplit=2[v1][v2];"
                      "[m][v1]sidechaincompress=threshold=0.015:ratio=7:attack=20:release=400[md];"
                      "[md][v2]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]")
        else:
            filtro = "[1:a]anull[a]"
        cmd = [exe, "-y", "-loglevel", "error", *entradas, "-filter_complex", filtro,
               "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
               "-movflags", "+faststart", str(destino)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  [video] ffmpeg falhou no audio: {r.stderr[-400:]}")
            return False
    return True
