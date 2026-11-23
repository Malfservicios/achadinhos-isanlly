"""Recorta el logo circular de la captura del grupo de WhatsApp (uso unico)."""
import sys
from PIL import Image, ImageDraw
src, cx, cy, r = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
im = Image.open(src).convert("RGB").crop((cx - r, cy - r, cx + r, cy + r))
im = im.resize((512, 512), Image.LANCZOS)
mask = Image.new("L", (2048, 2048), 0)
ImageDraw.Draw(mask).ellipse((0, 0, 2047, 2047), fill=255)
mask = mask.resize((512, 512), Image.LANCZOS)
out = Image.new("RGBA", (512, 512)); out.paste(im, (0, 0), mask)
out.save("assets/logo.png")
for s in (192, 512):
    bg = Image.new("RGB", (s, s), (58, 34, 20)); bg.paste(out.resize((s, s), Image.LANCZOS), (0, 0), out.resize((s, s), Image.LANCZOS))
    bg.save(f"docs/icons/icon-{s}.png")
print("ok")
