"""Busca y descarga b-roll de Pexels para superponerlo en el reel.

La licencia de Pexels permite uso comercial sin pedir credito, y prohibe
redistribuir su material como si fuera propio: aqui solo se inserta dentro del
video del usuario, que es un uso previsto.

Detalle que cuesta encontrar: la API responde 403 al agente por defecto de
Python, asi que hay que mandar un User-Agent normal.
"""
import json
import os
import re
import urllib.parse
import urllib.request

from . import llaves, pertinencia

API = "https://api.pexels.com/videos/search"
# La clave vive en .secrets/pexels.yaml (ver pipeline/llaves.py)
CLAVE = llaves.ruta("pexels")
CACHE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "proyectos", "_broll")

CABECERAS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) EditorReels/1.0",
    "Accept": "application/json",
}


def leer_clave(ruta=None):
    """La clave de Pexels, de .secrets/pexels.yaml (campo api_key)."""
    clave, motivo = llaves.leer("pexels")
    if clave is None:
        raise RuntimeError(
            "Falta la clave de Pexels (%s).\n"
            "  Sacala gratis en pexels.com/api y pegala en el campo api_key de:\n"
            "  %s\n"
            "  El archivo lleva una linea: api_key: tu_llave" % (motivo, CLAVE))
    if " " in clave:
        raise RuntimeError("La clave de %s no parece valida" % CLAVE)
    return clave


def descripcion_de(url):
    """De la url saca de que es: .../a-pond-with-trees-12345/ -> a pond with trees."""
    m = re.search(r"/video/([a-z0-9-]+?)-?\d*/?$", url or "")
    return m.group(1).replace("-", " ") if m else ""


def buscar(consulta, cantidad=5, orientacion="portrait", dur_min=3, dur_max=25,
           clave=None):
    """Clips que encajan en el lienzo del proyecto. Los mejores candidatos.

    `orientacion` es "portrait" (reel vertical, por defecto) o "landscape"
    (video largo de YouTube). No se elige a mano: sale del canvas del
    proyecto, que ya se calcula del primer clip -ver `stock.orientacion_de`-.
    Pedirle vertical al catalogo para un lienzo 1920x1080 devuelve material
    que habria que recortar, perdiendo la mitad de la imagen.
    """
    clave = clave or leer_clave()
    url = "%s?%s" % (API, urllib.parse.urlencode({
        "query": consulta, "per_page": max(cantidad * 3, 10),
        "orientation": orientacion, "size": "medium"}))
    req = urllib.request.Request(url, headers=dict(CABECERAS, Authorization=clave))
    with urllib.request.urlopen(req, timeout=30) as r:
        datos = json.load(r)

    salida = []
    for v in datos.get("videos", []):
        if not (dur_min <= v.get("duration", 0) <= dur_max):
            continue
        # el archivo de mayor calidad en la orientacion pedida, sin ser gigantesco
        vertical = orientacion != "landscape"
        archivos = [f for f in v.get("video_files", [])
                    if f.get("height") and f.get("width")
                    and (f["height"] >= f["width"] if vertical
                         else f["width"] >= f["height"])]
        if not archivos:
            archivos = v.get("video_files", [])
        # el lado que da la calidad es el alto en vertical y en horizontal
        # tambien, pero el objetivo cambia: 1920 de alto en un reel, 1080 en
        # un 1920x1080
        objetivo = 1920 if vertical else 1080
        archivos.sort(key=lambda f: abs((f.get("height") or 0) - objetivo))
        if not archivos:
            continue
        salida.append({
            "id": v["id"],
            "fuente": "pexels",
            "duracion": v["duration"],
            "autor": (v.get("user") or {}).get("name", ""),
            "pagina": v.get("url", ""),
            # de que es el video: Pexels no manda titulo, pero el slug de la
            # url es la descripcion que le puso quien lo subio
            "descripcion": descripcion_de(v.get("url", "")),
            "ancho": archivos[0].get("width"),
            "alto": archivos[0].get("height"),
            "descarga": archivos[0]["link"],
        })
        if len(salida) >= cantidad:
            break
    return salida


def descargar(video, destino=None):
    """Baja el archivo y devuelve la ruta local. Reutiliza lo ya descargado."""
    destino = destino or CACHE
    os.makedirs(destino, exist_ok=True)
    ruta = os.path.join(destino, "pexels_%s.mp4" % video["id"])
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


def conseguir(consulta, umbral=pertinencia.UMBRAL, **kwargs):
    """Busca y descarga el que ILUSTRA la consulta. None si ninguno lo hace.

    Antes se devolvia `resultados[0]`, o sea lo primero que Pexels contestara.
    Como la busqueda siempre contesta algo, eso metia un estanque donde el
    guion pedia una horca. Ahora se puntua y se prefiere no traer nada.
    """
    resultados = buscar(consulta, **kwargs)
    video = pertinencia.mejor(consulta, resultados, umbral)
    if not video:
        return None
    video["ruta"] = descargar(video)
    return video


def creditos(videos):
    """Lista de atribuciones.

    La licencia del contenido no exige credito, pero las guias de la API de
    Pexels si piden un enlace visible a Pexels donde se use. Poner
    "Videos: Pexels" en la descripcion del post cuesta cero y cierra el tema.
    """
    vistos, lineas = set(), []
    for v in videos:
        if v and v.get("autor") and v["id"] not in vistos:
            vistos.add(v["id"])
            lineas.append("%s — %s" % (v["autor"], v.get("pagina", "")))
    return lineas
