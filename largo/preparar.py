"""Paso 1: deja listo el proyecto para decidir el corte.

Por cada toma saca su audio (WAV mono 16 kHz, que es lo que miden los demas pasos),
la transcribe palabra por palabra y escribe una version LEGIBLE con minutos, que es la
que se lee para escribir `orden.json`.

    python largo.py preparar <proyecto> --toma A=<video principal> [--toma R=<retomas>]
"""
import json
import os
import subprocess

from largo.comun import escribir, leer


def _medir(video):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                        "stream=width,height,r_frame_rate", "-of", "json", video],
                       capture_output=True, text=True)
    s = json.loads(r.stdout or "{}").get("streams") or [{}]
    s = s[0]
    num, _, den = (s.get("r_frame_rate") or "30/1").partition("/")
    fps = round(float(num) / float(den or 1)) if float(den or 1) else 30
    return [int(s.get("width") or 1920), int(s.get("height") or 1080), fps or 30]


def _legible(ws, pausa=0.7, max_palabras=18):
    """Renglones de habla con su minuto: se corta en las pausas, que es donde se corta el video."""
    lineas, cur = [], []
    for k, w in enumerate(ws):
        if cur and (w["s"] - ws[k - 1]["e"] > pausa or len(cur) >= max_palabras):
            lineas.append(cur)
            cur = []
        cur.append(w)
    if cur:
        lineas.append(cur)
    out = []
    for ln in lineas:
        t = ln[0]["s"]
        out.append("[%02d:%04.1f | %7.2f] %s" % (int(t // 60), t % 60, t, " ".join(w["w"] for w in ln)))
    return "\n".join(out) + "\n"


def main(c, tomas, modelo="large-v3"):
    from pipeline.transcribe import transcribe
    os.makedirs(c, exist_ok=True)
    if not tomas:
        tomas = leer(c, "proyecto.json")["tomas"]
    for k, v in tomas.items():
        if not os.path.exists(v):
            raise SystemExit("No existe la toma %s: %s" % (k, v))
    primera = tomas.get("A") or next(iter(tomas.values()))
    proyecto = {"tomas": {k: os.path.abspath(v) for k, v in tomas.items()}, "lienzo": _medir(primera)}
    escribir(c, "proyecto.json", proyecto)

    palabras = {}
    for k, video in proyecto["tomas"].items():
        wav = os.path.join(c, "audio_%s.wav" % k)
        if not os.path.exists(wav):
            print("  audio de la toma %s..." % k)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vn", "-ac", "1", "-ar", "16000",
                            "-c:a", "pcm_s16le", wav], check=True)
        print("  transcribiendo la toma %s (%s)..." % (k, modelo))
        r = transcribe(wav, cache_path=os.path.join(c, "trans_%s.json" % k), model_size=modelo)
        ws = [{"s": round(x["start"], 2), "e": round(x["end"], 2), "w": x["word"].strip()}
              for x in r["words"] if x["word"].strip()]
        palabras[k] = ws
        escribir(c, "legible_%s.txt" % k, _legible(ws))
        dur = ws[-1]["e"] if ws else 0
        print("  toma %s: %d palabras, %d:%02d de habla -> legible_%s.txt" % (k, len(ws), dur // 60, dur % 60, k))
    escribir(c, "palabras_por_toma.json", palabras)
    print("\nListo. Ahora se escribe orden.json leyendo legible_*.txt (formato en largo/LEEME.md)\n"
          "y se corre: python largo.py cortar <proyecto>")
