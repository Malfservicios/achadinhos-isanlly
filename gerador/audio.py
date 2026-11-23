"""Audio do video: narracao (voz neural pt-BR) e musica de fundo propria.

A narracao e gerada por blocos (gancho, descricao, preco, chamada) para cada cena
do video comecar junto com a frase certa. A musica e sintetizada aqui mesmo,
diferente para cada produto, entao nao ha problema de direitos autorais.
"""
import asyncio
import random
import subprocess
import wave
from pathlib import Path

import numpy as np

from .comum import CONFIG

SR = 44100



# ---------- utilidades ----------

def _ler_wav(caminho):
    with wave.open(str(caminho)) as w:
        dados = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        if w.getnchannels() == 2:
            dados = dados.reshape(-1, 2).mean(axis=1)
    return dados


def salvar_wav(caminho, sinal):
    """sinal: array (n,) mono ou (n, 2) estereo, valores -1..1."""
    if sinal.ndim == 1:
        sinal = np.stack([sinal, sinal], axis=1)
    pcm = (np.clip(sinal, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


# ---------- narracao ----------

async def _tts(texto, destino, voz, velocidade):
    import edge_tts
    await edge_tts.Communicate(texto, voz, rate=velocidade).save(str(destino))


def narrar_blocos(blocos, pasta, ffmpeg):
    """Fala cada bloco do roteiro. Retorna {bloco: array mono} ou None se a voz falhar
    (sem internet, servico fora do ar...): o video sai so com musica."""
    cfg = CONFIG["video"]
    pasta = Path(pasta)
    saida = {}
    try:
        for nome, texto in blocos.items():
            mp3, wav = pasta / f"voz-{nome}.mp3", pasta / f"voz-{nome}.wav"
            asyncio.run(_tts(texto, mp3, cfg.get("voz", "pt-BR-ThalitaMultilingualNeural"),
                             cfg.get("velocidade_voz", "+0%")))
            subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", str(mp3), "-ac", "1", "-ar", str(SR), str(wav)],
                           check=True)
            s = _ler_wav(wav)
            ativo = np.where(np.abs(s) > 0.01)[0]  # corta silencio do inicio/fim
            if len(ativo):
                s = s[max(0, ativo[0] - 400): ativo[-1] + 2000]
            saida[nome] = s
    except Exception as e:  # noqa: BLE001
        print(f"  [voz] narracao indisponivel ({type(e).__name__}: {e})")
        return None
    pico = max(np.abs(s).max() for s in saida.values()) or 1
    return {k: (s / pico * 0.95).astype(np.float32) for k, s in saida.items()}


# ---------- musica ----------

NOTAS = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _freq(semitom_desde_la4):
    return 440.0 * 2 ** (semitom_desde_la4 / 12)


def musica(semente, duracao, destino):
    """Trilha leve e alegre (pop acustico/lo-fi), sintetizada. Cada produto tem tom/andamento proprios."""
    rnd = random.Random(semente)
    bpm = rnd.choice([96, 100, 104, 108])
    batida = 60 / bpm
    tom = rnd.choice([0, 2, 3, 5, 7, -2])  # transposicao
    # progressoes em graus (semitons a partir da tonica, acorde maior/menor)
    prog = rnd.choice([
        [(0, "M"), (7, "M"), (9, "m"), (5, "M")],    # I V vi IV
        [(0, "M"), (9, "m"), (5, "M"), (7, "M")],    # I vi IV V
        [(5, "M"), (7, "M"), (4, "m"), (9, "m")],    # IV V iii vi
    ])
    n = int(duracao * SR)
    t = np.arange(n) / SR
    saida = np.zeros((n, 2), dtype=np.float32)
    base = -9 + tom  # do (C4) relativo ao la4 + transposicao

    def nota(freq, inicio, dur, vol, decai=4.0, harm=(1.0, 0.35, 0.12), pan=0.0, ataque=0.005):
        i0, i1 = int(inicio * SR), min(n, int((inicio + dur) * SR))
        if i0 >= n or i1 <= i0:
            return
        tt = np.arange(i1 - i0) / SR
        onda = sum(a * np.sin(2 * np.pi * freq * (k + 1) * tt) for k, a in enumerate(harm))
        env = np.minimum(1, tt / ataque) * np.exp(-decai * tt)
        sinal = (onda * env * vol).astype(np.float32)
        saida[i0:i1, 0] += sinal * (1 - pan)
        saida[i0:i1, 1] += sinal * (1 + pan)

    compasso = 4 * batida
    padrao_arp = rnd.choice([[0, 1, 2, 1, 0, 2, 1, 2], [0, 2, 1, 2, 0, 2, 1, 0], [0, 1, 2, 3, 2, 1, 0, 1]])
    c = 0
    while c * compasso < duracao:
        grau, tipo = prog[c % len(prog)]
        terca = 4 if tipo == "M" else 3
        acorde = [base + grau, base + grau + terca, base + grau + 7, base + grau + 12]
        ini = c * compasso
        # pad suave (acorde inteiro, ataque lento)
        for s in acorde[:3]:
            nota(_freq(s), ini, compasso + 0.2, 0.045, decai=0.4, harm=(1, 0.2, 0.05), ataque=0.35)
        # baixo
        for b in (0, 2):
            nota(_freq(base + grau - 24), ini + b * batida, batida * 1.6, 0.22, decai=2.5, harm=(1, 0.5, 0.1))
        # arpejo dedilhado (colcheias)
        for k, idx in enumerate(padrao_arp):
            nota(_freq(acorde[idx] + 12), ini + k * batida / 2, batida, 0.07, decai=6,
                 harm=(1, 0.5, 0.25, 0.1), pan=0.25 if k % 2 else -0.25)
        # bumbo e chocalho
        for b in range(4):
            i0 = int((ini + b * batida) * SR)
            if i0 < n:
                tt = np.arange(min(int(0.18 * SR), n - i0)) / SR
                bumbo = np.sin(2 * np.pi * (50 + 70 * np.exp(-30 * tt)) * tt) * np.exp(-14 * tt) * 0.35
                saida[i0:i0 + len(tt)] += bumbo[:, None]
            j0 = int((ini + (b + 0.5) * batida) * SR)
            if j0 < n:
                m = min(int(0.06 * SR), n - j0)
                ruido = np.diff(np.random.default_rng(c * 8 + b).standard_normal(m + 1)) * 0.5
                saida[j0:j0 + m] += (ruido * np.exp(-60 * np.arange(m) / SR) * 0.05)[:, None]
        c += 1

    # fade in/out e normalizacao
    fade_in, fade_out = int(0.6 * SR), int(1.4 * SR)
    saida[:fade_in] *= np.linspace(0, 1, fade_in)[:, None]
    saida[-fade_out:] *= np.linspace(1, 0, fade_out)[:, None]
    saida /= max(0.01, np.abs(saida).max())
    salvar_wav(destino, saida * 0.85)
    return destino
