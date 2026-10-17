"""Segunda fuente de stock, con el mismo formato de salida que `broll.py`.

Existe por una razon concreta: un solo proveedor siempre contesta algo, y ese
algo puede no venir al caso. Con dos catalogos distintos se puede comparar y
quedarse con el que de verdad ilustra la escena -o con ninguno.

Pixabay es gratis para uso comercial y no pide atribucion. El limite son 100
peticiones por minuto y piden cachear 24 horas lo que se recibe; aqui se cachea
el archivo descargado, que es lo que pesa.

Ventaja tecnica sobre Pexels: manda `tags`, o sea una descripcion de verdad, en
vez de tener que sacarla del slug de la url.
"""
import json
import os
import urllib.parse
import urllib.request

from . import llaves

API = "https://pixabay.com/api/videos/"
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# La clave vive en .secrets/pixabay.yaml (ver pipeline/llaves.py)
CLAVE = llaves.ruta("pixabay")
CACHE = os.path.join(BASE, "proyectos", "_broll")

CABECERAS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EditorReels/1.0",
    "Accept": "application/json",
}


def hay_clave(ruta=None):
    """Si no hay clave, este proveedor simplemente no participa: no es un error."""
    return llaves.hay("pixabay")


def leer_clave(ruta=None):
    """La clave de Pixabay, de .secrets/pixabay.yaml (campo api_key)."""
    clave, motivo = llaves.leer("pixabay")
    if clave is None:
        raise RuntimeError(
            "Falta la clave de Pixabay (%s).\n"
            "  Es gratis e inmediata en pixabay.com/api/docs (hay que tener\n"
            "  cuenta). Pegala en el campo api_key de:\n  %s" % (motivo, CLAVE))
    if " " in clave:
        raise RuntimeError("La clave de %s no parece valida" % CLAVE)
    return clave


def buscar(consulta, cantidad=5, dur_min=3, dur_max=25, clave=None,
           orientacion="portrait", **_):
    """Clips en la orientacion del proyecto, en el formato de `broll`."""
    clave = clave or leer_clave()
    url = "%s?%s" % (API, urllib.parse.urlencode({
        "key": clave, "q": consulta, "video_type": "all",
        "per_page": max(cantidad * 3, 10), "safesearch": "true"}))
    req = urllib.request.Request(url, headers=CABECERAS)
    with urllib.request.urlopen(req, timeout=30) as r:
        datos = json.load(r)

    salida = []
    for v in datos.get("hits", []):
        if not (dur_min <= v.get("duration", 0) <= dur_max):
            continue
        # el de mas calidad en la orientacion pedida; Pixabay no filtra por
        # orientacion, asi que hay que mirar las medidas de cada archivo
        vertical = orientacion != "landscape"
        archivos = [f for f in (v.get("videos") or {}).values()
                    if f.get("url") and f.get("height") and f.get("width")]
        encajan = [f for f in archivos
                   if (f["height"] >= f["width"] if vertical
                       else f["width"] >= f["height"])]
        archivos = encajan or archivos
        if not archivos:
            continue
        archivos.sort(key=lambda f: abs((f.get("height") or 0)
                                        - (1920 if vertical else 1080)))
        salida.append({
            "id": v["id"],
            "fuente": "pixabay",
            "duracion": v["duration"],
            "autor": v.get("user", ""),
            "pagina": v.get("pageURL", ""),
            # aqui si viene descripcion de verdad, no un slug
            "descripcion": v.get("tags", ""),
            "ancho": archivos[0].get("width"),
            "alto": archivos[0].get("height"),
            "descarga": archivos[0]["url"],
        })
        if len(salida) >= cantidad:
            break
    return salida


def descargar(video, destino=None):
    """Baja el archivo y devuelve la ruta local. Reutiliza lo ya descargado."""
    destino = destino or CACHE
    os.makedirs(destino, exist_ok=True)
    ruta = os.path.join(destino, "pixabay_%s.mp4" % video["id"])
    if os.path.exists(ruta) and os.path.getsize(ruta) > 10000:
        return ruta
    req = urllib.request.Request(video["descarga"], headers=CABECERAS)
    with urllib.request.urlopen(req, timeout=120) as r, open(ruta, "wb") as f:
        while True:
            trozo = r.read(262144)
            if not trozo:
                break
            f.write(trozo)
    return ruta
