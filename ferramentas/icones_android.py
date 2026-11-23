"""Gera os icones do app Android a partir de assets/logo.png."""
from pathlib import Path
from PIL import Image, ImageDraw

RES = Path("android/app/src/main/res")
OURO = (242, 186, 72, 255)
logo = Image.open("assets/logo.png").convert("RGBA")


def circulo_com_aro(d):
    """Logo redondo com aro dourado, d x d pixels."""
    esc = 4
    D = d * esc
    out = Image.new("RGBA", (D, D), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, D - 1, D - 1), fill=OURO)
    aro = int(D * 0.05)
    out.alpha_composite(logo.resize((D - 2 * aro, D - 2 * aro), Image.LANCZOS), (aro, aro))
    return out.resize((d, d), Image.LANCZOS)


dens = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
for nome, f in dens.items():
    pasta = RES / f"mipmap-{nome}"
    pasta.mkdir(parents=True, exist_ok=True)
    circulo_com_aro(int(48 * f)).save(pasta / "ic_launcher.png")
    lado = int(108 * f)
    fg = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    c = circulo_com_aro(int(72 * f))
    fg.alpha_composite(c, ((lado - c.width) // 2, (lado - c.height) // 2))
    fg.save(pasta / "ic_launcher_foreground.png")
(RES / "drawable-nodpi").mkdir(parents=True, exist_ok=True)
circulo_com_aro(512).save(RES / "drawable-nodpi" / "splash.png")
print("ok")
