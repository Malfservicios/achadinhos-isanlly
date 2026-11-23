"""Video curto (~9 s) com FFmpeg: fotos do produto com zoom suave e transicoes,
terminando na arte com o preco. Sem musica (evita problemas de direitos autorais).
"""
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .arte import H, W, arte_slide

FPS = 30


def ffmpeg():
    return os.environ.get("FFMPEG") or shutil.which("ffmpeg")


def gerar_video(p, fotos, arte_final, destino, nome_curto=None):
    exe = ffmpeg()
    if not exe:
        print("  [video] ffmpeg nao encontrado; pulando video")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        quadros = []
        for i, foto in enumerate(fotos[:3]):
            q = tmp / f"s{i}.jpg"
            arte_slide(p, foto, i, nome_curto).save(q, quality=94)
            quadros.append((q, 2.6))
        final = tmp / "final.jpg"
        arte_final.save(final, quality=94)
        quadros.append((final, 3.6))

        entradas, filtros = [], []
        for i, (q, dur) in enumerate(quadros):
            n = int(dur * FPS)
            entradas += ["-i", str(q)]  # 1 quadro; o zoompan gera os n quadros
            zoom = "min(zoom+0.0007,1.06)" if i < len(quadros) - 1 else "if(lte(on,8),1.12-0.015*on,1)"
            filtros.append(
                f"[{i}:v]scale={W * 2}:{H * 2},zoompan=z='{zoom}':d={n}:x='iw/2-(iw/zoom/2)'"
                f":y='ih/2-(ih/zoom/2)':s={W}x{H}:fps={FPS},setsar=1,format=yuv420p[v{i}]"
            )
        # encadeia com transicoes
        trans = ["fade", "slideleft", "smoothup"]
        atual, offset = "v0", 0.0
        for i in range(1, len(quadros)):
            offset += quadros[i - 1][1] - 0.4
            saida = f"x{i}"
            filtros.append(f"[{atual}][v{i}]xfade=transition={trans[(i - 1) % 3]}:duration=0.4:offset={offset:.2f}[{saida}]")
            atual = saida
        total = sum(d for _, d in quadros) - 0.4 * (len(quadros) - 1)
        cmd = [exe, "-y", "-loglevel", "error", *entradas,
               "-f", "lavfi", "-t", f"{total:.2f}", "-i", "anullsrc=r=44100:cl=stereo",
               "-filter_complex", ";".join(filtros), "-map", f"[{atual}]", "-map", f"{len(quadros)}:a",
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p",
               "-c:a", "aac", "-b:a", "64k", "-shortest", "-movflags", "+faststart", str(destino)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            print(f"  [video] ffmpeg falhou: {r.stderr[-400:]}")
            return False
    return True
