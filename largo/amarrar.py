"""Paso 4: los subtitulos y los tiempos de cada palabra EN LA LINEA DE TIEMPO FINAL.

Arma el audio del corte tal como va a sonar, lo vuelve a transcribir (en el corte ya no hay
desfase acumulado) y le amarra el TEXTO LIMPIO: el texto bien escrito, con su ortografia y
puntuacion, que es lo que se lee en pantalla. Asi el subtitulo dice lo que se dijo, y una
palabra que Whisper puso un poco antes de un corte ya no se pierde.

Si todavia no hay `texto_limpio.txt`, se escribe uno a partir de lo que dijo Whisper, un
renglon por tramo, para corregirlo (ortografia, cifras, nombres) y volver a correr.

    python largo.py amarrar <proyecto>

Escribe tl.json (cada palabra con su tiempo final), subtitulos.srt (para YouTube) y
corte_audio.wav.
"""
import difflib
import os

import numpy as np

from largo.comun import escribir, guardar_wav, leer, muestras, norm, q, total_corte


def audio_del_corte(c, E):
    """El audio del corte con las MISMAS duraciones que tendra la linea de tiempo (rejilla de cuadros)."""
    AUD = {k: muestras(os.path.join(c, "audio_%s.wav" % k)) for k in {t["f"] for t in E}}
    marcas, acc = [0.0], 0.0
    for t in E:
        acc += t["e"] - t["s"]
        marcas.append(q(acc))
    trozos = []
    for t, a, b in zip(E, marcas, marcas[1:]):
        i = int(round(t["s"] * 16000))
        trozos.append(AUD[t["f"]][i:i + int(round((b - a) * 16000))])
    return np.concatenate(trozos)


def amarrar(texto, W):
    """Tiempo de cada palabra del texto limpio, alineando contra lo que oyo Whisper."""
    A = [norm(x) for x in texto]
    B = [norm(w["w"]) for w in W]
    sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
    ini, fin, iguales = [None] * len(texto), [None] * len(texto), 0
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal" or (op == "replace" and (i2 - i1) == (j2 - j1)):
            for k in range(i2 - i1):
                ini[i1 + k], fin[i1 + k] = W[j1 + k]["s"], W[j1 + k]["e"]
                iguales += op == "equal"
    for i in range(len(texto)):   # las que Whisper no oyo se reparten entre sus vecinas
        if ini[i] is None:
            a = next((fin[k] for k in range(i - 1, -1, -1) if fin[k] is not None), 0.0)
            j = next((k for k in range(i + 1, len(texto)) if ini[k] is not None), None)
            b = ini[j] if j is not None else a + 0.4
            huecos = [k for k in range(i, j if j is not None else len(texto)) if ini[k] is None]
            paso = (b - a) / (len(huecos) + 1)
            for n_, k in enumerate(huecos, 1):
                ini[k], fin[k] = a + paso * (n_ - 0.5), a + paso * (n_ + 0.4)
    return A, ini, fin, iguales


ENLACE = {"tu", "tus", "el", "la", "los", "las", "de", "del", "que", "un", "una", "y", "o", "a", "en",
          "por", "para", "con", "mi", "su", "aqui", "lo", "le", "es"}


def srt(texto, A, ini, fin, total, max_renglon=42):
    cues, cur = [], []
    for i, p in enumerate(texto):
        if cur and len(" ".join(texto[k] for k in cur + [i])) > 2 * max_renglon - 6:
            cues.append(cur)
            cur = []
        cur.append(i)
        t = " ".join(texto[k] for k in cur)
        dur = fin[i] - ini[cur[0]]
        duro = p.endswith((".", "?", "!", "\"", "…"))
        suave = p.endswith((",", ";", ":"))
        if (duro and len(t) >= 14) or (suave and len(t) >= 40) or dur >= 5.5:
            cues.append(cur)
            cur = []
    if cur:
        cues.append(cur)
    for k in range(len(cues) - 1):   # no dejar «de», «el», «y» colgando al final de un subtitulo
        while len(cues[k]) > 2 and A[cues[k][-1]] in ENLACE and not texto[cues[k][-1]].endswith((".", ",", "?", "!", ":")):
            cues[k + 1].insert(0, cues[k].pop())

    def partir(t):
        if len(t) <= max_renglon:
            return t
        op = [(abs(len(t[:k]) - len(t[k + 1:])), t[:k] + "\n" + t[k + 1:]) for k in range(len(t))
              if t[k] == " " and len(t[:k]) <= max_renglon and len(t[k + 1:]) <= max_renglon]
        if not op:
            op = [(abs(len(t[:k]) - len(t[k + 1:])), t[:k] + "\n" + t[k + 1:]) for k in range(len(t)) if t[k] == " "]
        return min(op)[1] if op else t

    def ts(x):
        ms = int(round(x * 1000))
        return "%02d:%02d:%02d,%03d" % (ms // 3600000, ms // 60000 % 60, ms // 1000 % 60, ms % 1000)

    out, previo = [], 0.0
    for k, cu in enumerate(cues):
        a = ini[cu[0]]
        b = max(fin[cu[-1]] + 0.2, a + 1.0)
        if k + 1 < len(cues):
            b = min(b, ini[cues[k + 1][0]] - 0.03)
        b = min(b, total)
        if k > 0:
            a = max(a, previo + 0.01)
        previo = b
        out.append("%d\n%s --> %s\n%s\n" % (k + 1, ts(a), ts(b), partir(" ".join(texto[x] for x in cu))))
    return "\n".join(out)


def main(c, modelo="large-v3"):
    from pipeline.transcribe import transcribe
    E = leer(c, "edl.json")
    total = total_corte(E)
    wav = os.path.join(c, "corte_audio.wav")
    guardar_wav(wav, audio_del_corte(c, E))
    r = transcribe(wav, cache_path=os.path.join(c, "ver_corte.json"), model_size=modelo)
    W = [{"w": x["word"].strip(), "s": x["start"], "e": x["end"]} for x in r["words"] if x["word"].strip()]
    ruta_txt = os.path.join(c, "texto_limpio.txt")
    if not os.path.exists(ruta_txt):
        # primer borrador: lo que dijo Whisper EN EL CORTE, un renglon por tramo del guion
        escribir(c, "texto_limpio.txt", leer(c, "guion_armado.txt"))
        print("Escribi texto_limpio.txt con lo que dijo Whisper. Corrigelo (ortografia, cifras,\n"
              "nombres; no agregues ni quites palabras dichas) y vuelve a correr amarrar si cambias algo.")
    texto = leer(c, "texto_limpio.txt").split()
    A, ini, fin, iguales = amarrar(texto, W)
    escribir(c, "tl.json", [{"w": texto[i], "n": A[i], "s": round(ini[i], 3), "e": round(fin[i], 3)}
                            for i in range(len(texto))])
    s = srt(texto, A, ini, fin, total)
    escribir(c, "subtitulos.srt", s)
    pct = iguales / max(1, len(texto)) * 100
    print("corte: %.1f s | texto limpio: %d palabras, %d%% amarradas directo | %d subtitulos"
          % (total, len(texto), pct, s.count(" --> ")))
    if pct < 85:
        print("  aviso: menos del 85%% amarrado directo. Casi siempre es que el texto limpio no dice lo\n"
              "  mismo que el corte (un tramo quitado o agregado despues). Revisa antes de seguir.")
