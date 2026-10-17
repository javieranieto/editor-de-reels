"""Lo que comparten los pasos del video largo: la carpeta del proyecto, la forma de
comparar palabras y el volumen del audio de cada toma.

Un proyecto de video largo es una carpeta (por defecto `proyectos/<nombre>/`) con:

    proyecto.json        las tomas {"A": ruta, "R": ruta} y el lienzo  (lo escribe `preparar`)
    palabras_por_toma.json  cada palabra de cada toma con su tiempo     (lo escribe `preparar`)
    legible_<toma>.txt   la transcripcion con minutos, para leerla      (lo escribe `preparar`)
    orden.json           QUE frases van y en que orden                   (lo escribe Claude)
    texto_limpio.txt     el texto del corte bien escrito, para subtitulos (lo escribe Claude)
    stock.json           que video de stock va en que frase              (lo escribe Claude)

Todo lo demas lo generan los pasos. Las decisiones editoriales viven en esos tres
archivos de texto; el codigo no sabe de que trata el video.
"""
import io
import json
import os
import re
import sys
import unicodedata
import wave

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

if (sys.stdout.encoding or "").lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

FPS = 30
FR = 1 / FPS

# Whisper escribe numeros como cifras y el texto limpio a veces con letra: se comparan
# las dos formas como iguales.
NUM = {"1": "uno", "2": "dos", "3": "tres", "4": "cuatro", "5": "cinco", "6": "seis",
       "7": "siete", "8": "ocho", "9": "nueve", "10": "diez", "11": "once", "12": "doce",
       "15": "quince", "20": "veinte", "100": "cien", "1000": "mil"}


def norm(s):
    """Una palabra sin acentos, mayusculas ni signos, para comparar."""
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]", "", s)
    return NUM.get(s, s)


def carpeta(nombre_o_ruta):
    """La carpeta del proyecto: una ruta, o un nombre dentro de proyectos/."""
    if os.path.isdir(nombre_o_ruta):
        return os.path.abspath(nombre_o_ruta)
    return os.path.join(RAIZ, "proyectos", nombre_o_ruta)


_OBLIGATORIO = object()


def leer(c, archivo, falta=_OBLIGATORIO):
    """Lee un archivo del proyecto. Con `falta=` es opcional y devuelve eso si no existe."""
    ruta = os.path.join(c, archivo)
    if not os.path.exists(ruta):
        if falta is not _OBLIGATORIO:
            return falta
        raise SystemExit("Falta %s en %s. %s" % (archivo, c, AYUDA.get(archivo, "")))
    with open(ruta, encoding="utf-8") as f:
        return json.load(f) if archivo.endswith(".json") else f.read()


def escribir(c, archivo, datos):
    with open(os.path.join(c, archivo), "w", encoding="utf-8") as f:
        if archivo.endswith(".json"):
            json.dump(datos, f, ensure_ascii=False, indent=1)
        else:
            f.write(datos)


AYUDA = {
    "proyecto.json": "Corre primero: python largo.py preparar <proyecto> --toma A=<video>",
    "palabras_por_toma.json": "Corre primero: python largo.py preparar <proyecto> --toma A=<video>",
    "orden.json": "Escribelo (o pidele a Claude que lo escriba) leyendo legible_<toma>.txt. "
                  "Formato en largo/LEEME.md.",
    "edl.json": "Corre primero: python largo.py cortar <proyecto>",
    "tl.json": "Corre primero: python largo.py amarrar <proyecto>",
    "stock.json": "Escribelo (o pidele a Claude) con las frases que lleva stock. Formato en largo/LEEME.md.",
}


def palabras(c):
    """{toma: [{s, e, w, n}]} con la palabra ya normalizada."""
    p = leer(c, "palabras_por_toma.json")
    return {k: [dict(x, n=norm(x["w"])) for x in v] for k, v in p.items()}


def buscar(ws, frase, desde=0.0, donde=""):
    """Indice de la primera palabra de `frase` que empieza despues de `desde` segundos.

    Se busca SIEMPRE despues de un tiempo: una palabra comun («siete», «precio») sale
    muchas veces, y sin `desde` se agarra la primera aparicion, que casi nunca es la buena.
    """
    obj = [norm(x) for x in frase.split() if norm(x)]
    for i in range(len(ws) - len(obj) + 1):
        if ws[i]["s"] >= desde and all(ws[i + j]["n"] == obj[j] for j in range(len(obj))):
            return i
    raise SystemExit("NO ENCONTRE %r despues de %.1f s %s.\n  Revisa la frase contra "
                     "legible_*.txt: tiene que coincidir palabra por palabra con lo que dijo Whisper."
                     % (frase, desde, donde))


def niveles_db(ruta_wav):
    """Volumen en dB cada 10 ms de un WAV mono de 16 kHz."""
    import numpy as np
    w = wave.open(ruta_wav)
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    fr = 160
    n = len(x) // fr
    return 20 * np.log10(np.sqrt((x[:n * fr].reshape(n, fr) ** 2).mean(1)) + 1e-9)


def muestras(ruta_wav):
    import numpy as np
    w = wave.open(ruta_wav)
    return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)


def guardar_wav(ruta, datos, tasa=16000):
    w = wave.open(ruta, "wb")
    w.setnchannels(1)
    w.setsampwidth(2)
    w.setframerate(tasa)
    w.writeframes(datos.tobytes())
    w.close()


def q(x):
    """Redondea a la rejilla de cuadros: CapCut mueve de pista una pieza que no cae en ella."""
    return round(round(x / FR) * FR, 4)


def total_corte(edl):
    return round(sum(t["e"] - t["s"] for t in edl), 2)


def T(tl, frase, despues=0.0, fin=False):
    """Segundo de la linea de tiempo FINAL donde empieza (o acaba) una frase del texto limpio."""
    qq = [norm(x) for x in frase.split() if norm(x)]
    for i in range(len(tl) - len(qq) + 1):
        if tl[i]["s"] >= despues and all(tl[i + j]["n"] == qq[j] for j in range(len(qq))):
            return tl[i + len(qq) - 1]["e"] if fin else tl[i]["s"]
    raise SystemExit("NO ENCONTRE %r despues de %.1f s en el texto limpio (tl.json)." % (frase, despues))
