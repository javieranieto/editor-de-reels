"""Paso 3: revisa el corte TRAMO POR TRAMO antes de armar nada.

Transcribe el audio de cada tramo SUELTO (en piezas cortas Whisper no se desfasa; en una
toma de 14 minutos si) y lo compara con lo que el orden dice que debe decir. Marca las
palabras de mas (una repeticion, algo que se colo), las que faltan (una frase comida) y
los tramos que no coinciden. Un tramo marcado se arregla en orden.json y se vuelve a cortar.

    python largo.py revisar <proyecto> [etiqueta ...]
"""
import difflib
import hashlib
import os
import re

import numpy as np

from largo.comun import escribir, guardar_wav, leer, muestras, norm


def main(c, solo=None, modelo="large-v3"):
    from pipeline.transcribe import transcribe
    E = leer(c, "edl.json")
    G = leer(c, "guion_armado.txt").split("\n")
    AUD = {k: muestras(os.path.join(c, "audio_%s.wav" % k)) for k in {t["f"] for t in E}}
    orden = []
    for t in E:
        if not orden or orden[-1] != t["et"]:
            orden.append(t["et"])
    os.makedirs(os.path.join(c, "_revision"), exist_ok=True)
    malos, resumen = [], []
    for k, et in enumerate(orden):
        if solo and et not in solo:
            continue
        pz = [t for t in E if t["et"] == et]
        sil = np.zeros(int(0.25 * 16000), dtype=np.int16)   # un respiro entre piezas para que no se fundan
        # tambien un respiro AL PRINCIPIO: sin silencio antes, Whisper se salta la primera palabra
        # y la revision acusaba de «comida» una palabra que si estaba en el corte
        au = np.concatenate([sil] + sum([[AUD[t["f"]][int(t["s"] * 16000):int(t["e"] * 16000)], sil] for t in pz], []))
        # El nombre lleva la etiqueta (por numero, al quitar un tramo la cache se desfasaba) Y una
        # huella del audio: si el tramo cambia, se vuelve a escuchar. Con solo la etiqueta, la
        # cache devolvia la transcripcion del corte ANTERIOR y la revision mentia.
        huella = hashlib.md5(au.tobytes()).hexdigest()[:8]
        base = os.path.join(c, "_revision", "%s_%s" % (re.sub(r"[^a-z0-9]+", "_", norm(et) or "tramo_%d" % k), huella))
        guardar_wav(base + ".wav", au)
        r = transcribe(base + ".wav", cache_path=base + ".json", model_size=modelo)
        oido = " ".join(x["word"].strip() for x in r["words"])
        esperado = G[k] if k < len(G) else ""
        a = [norm(x) for x in esperado.split() if norm(x)]
        b = [norm(x) for x in oido.split() if norm(x)]
        ops = [(op, a[i1:i2], b[j1:j2]) for op, i1, i2, j1, j2 in
               difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if op != "equal"]
        marca = "OK " if not ops else "!! "
        print("%s%-22s %s" % (marca, et[:22], oido))
        for op, x, y in ops:
            print("      %-7s esperado: %s | se oye: %s" % (op, " ".join(x), " ".join(y)))
        if ops:
            malos.append(et)
        resumen.append({"etiqueta": et, "ok": not ops, "se_oye": oido})
    escribir(c, "revision.json", resumen)
    print("\n%d de %d tramos sin diferencias." % (len(resumen) - len(malos), len(resumen)))
    if malos:
        print("Revisar: %s\n  (Una diferencia de una letra suele ser Whisper; una palabra de mas o de menos, no.)"
              % ", ".join(malos))
