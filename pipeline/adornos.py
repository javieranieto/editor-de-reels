"""Coloca adornos animados (.mov con alfa) midiendo su contenido real.

Nace de un error concreto: el circulo se puso a `escala 0.80` a ojo y el
usuario lo tuvo que agrandar a mano hasta **1.778**, mas del doble. El numero
"0.80" no significaba nada, porque **depende del archivo**: cada .mov tiene su
trazo dibujado en una parte distinta del cuadro, con aire alrededor.

Aqui no se pide una escala sino lo que de verdad importa: **que fraccion del
ancho de pantalla debe ocupar el trazo** y **a que altura debe quedar**. La
escala sale de medir el archivo.

Medido de una edicion manual del usuario:

    subrayado   38% del ancho, centrado al 23% de altura  (no lo toco)
    circulo    101% del ancho, centrado al 11% de altura  (lo agrando el)

El circulo va a ancho completo porque tiene que ENCERRAR la cifra, mientras el
subrayado solo la acompana por debajo. Por eso no comparten valor.
"""
import json
import os
import subprocess

import numpy as np

ANCHO_MUESTRA, ALTO_MUESTRA = 270, 480     # miniatura: basta para el recuadro
UMBRAL_ALFA = 20                           # por debajo es borde difuminado

# fraccion del ancho del lienzo que ocupa cada tipo de trazo, y a que altura
# va su centro. Los dos numeros salen de medir su edicion.
PERFILES = {
    "subrayado": {"ancho": 0.38, "altura": 0.23},
    "circulo": {"ancho": 1.00, "altura": 0.11},
}


def _cache_path():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "proyectos", "_adornos.json")


def medir(ruta, usar_cache=True):
    """Recuadro del trazo visible, en fracciones del cuadro.

    Devuelve {"x0","x1","y0","y1","ancho","alto","centro_y"} o None.

    Se toma la UNION de todos los fotogramas, no uno suelto: estos archivos
    dibujan el trazo progresivamente y un fotograma temprano mide de menos.
    """
    cache_file = _cache_path()
    cache = {}
    if usar_cache and os.path.exists(cache_file):
        try:
            with open(cache_file, encoding="utf-8") as f:
                cache = json.load(f)
        except Exception:
            cache = {}
    clave = os.path.abspath(ruta)
    if clave in cache:
        return cache[clave]

    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", ruta,
         "-vf", "scale=%d:%d,format=rgba,alphaextract,fps=2"
                % (ANCHO_MUESTRA, ALTO_MUESTRA),
         "-f", "rawvideo", "-pix_fmt", "gray", "-"],
        capture_output=True)
    n = ANCHO_MUESTRA * ALTO_MUESTRA
    a = np.frombuffer(r.stdout, dtype=np.uint8)
    if len(a) < n:
        return None            # sin canal alfa, o no se pudo leer
    fr = a[:len(a) // n * n].reshape(-1, ALTO_MUESTRA, ANCHO_MUESTRA)
    union = fr.max(axis=0)
    ys, xs = np.where(union > UMBRAL_ALFA)
    if not len(xs):
        return None
    info = {
        "x0": round(float(xs.min()) / ANCHO_MUESTRA, 4),
        "x1": round(float(xs.max()) / ANCHO_MUESTRA, 4),
        "y0": round(float(ys.min()) / ALTO_MUESTRA, 4),
        "y1": round(float(ys.max()) / ALTO_MUESTRA, 4),
    }
    info["ancho"] = round(info["x1"] - info["x0"], 4)
    info["alto"] = round(info["y1"] - info["y0"], 4)
    info["centro_y"] = round((info["y0"] + info["y1"]) / 2, 4)

    cache[clave] = info
    try:
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    except Exception:
        pass
    return info


def colocar(ruta, ancho=None, altura=None, perfil=None):
    """{"escala", "y"} para que el trazo ocupe `ancho` y quede a `altura`.

    ancho, altura : fracciones del lienzo (0-1). Si se da `perfil`, se toman
                    de PERFILES y se pueden sobrescribir sueltas.

    Devuelve None si el archivo no tiene alfa medible: mejor no colocarlo que
    poner un rectangulo opaco encima del video.
    """
    if perfil:
        base = PERFILES.get(perfil) or {}
        ancho = base.get("ancho") if ancho is None else ancho
        altura = base.get("altura") if altura is None else altura
    if ancho is None:
        ancho = 0.50
    if altura is None:
        altura = 0.25

    info = medir(ruta)
    if not info or info["ancho"] <= 0:
        return None

    escala = ancho / info["ancho"]
    # al escalar, el contenido se aleja del centro del cuadro en proporcion
    centro = 0.5 + (info["centro_y"] - 0.5) * escala
    # fraccion_final = centro - y/2   ->   y = 2*(centro - fraccion_final)
    y = 2.0 * (centro - altura)
    return {"escala": round(escala, 3), "y": round(y, 3)}
