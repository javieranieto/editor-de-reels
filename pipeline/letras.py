"""Estilos de letra para los captions y los callouts.

Por que existe este modulo aparte: cambiar como se ven las letras toca cuatro
cosas a la vez (fuente, tamano, contorno, caja) y dos de ellas son RECURSOS
DESCARGABLES de CapCut, con la misma trampa que ya nos costo dias en los
efectos y en el zoom: pycapcut escribe una ruta inventada ("C:/Anton.ttf"),
CapCut no la encuentra, y en vez de avisar dibuja la fuente por defecto. El
sintoma es "le puse Anton y se ve igual".

Aqui se resuelven esas rutas contra la cache real de la maquina, y se declara
por adelantado que fuentes estan disponibles: pedir una que no este descargada
no falla en silencio, avisa.
"""
import json
import os

import pycapcut as cc

CACHE_EFECTOS = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Cache\effect")

# ---------------------------------------------------------------- recursos


def _archivo_en(resource_id, extensiones):
    """Primer archivo con esa extension dentro del recurso descargado."""
    base = os.path.join(CACHE_EFECTOS, str(resource_id))
    if not os.path.isdir(base):
        return None
    for raiz, _, archivos in os.walk(base):
        for a in sorted(archivos):
            if a.startswith("._"):        # basura de macOS dentro del paquete
                continue
            if a.lower().endswith(extensiones):
                return os.path.join(raiz, a).replace("\\", "/")
    return None


def fuentes_disponibles():
    """{nombre de FontType: ruta local} de las que SI estan descargadas."""
    salida = {}
    for nombre in dir(cc.FontType):
        if nombre.startswith("_"):
            continue
        meta = getattr(cc.FontType, nombre).value
        ruta = _archivo_en(meta.resource_id, (".ttf", ".otf", ".ttc"))
        if ruta:
            salida[nombre] = ruta
    return salida


def animaciones_disponibles():
    """Nombres de TextIntro cuyo recurso esta descargado en esta maquina."""
    salida = []
    for nombre in dir(cc.TextIntro):
        if nombre.startswith("_"):
            continue
        meta = getattr(cc.TextIntro, nombre).value
        if os.path.isdir(os.path.join(CACHE_EFECTOS, str(meta.resource_id))):
            salida.append(nombre)
    return salida


# ------------------------------------------------------------------ estilos
#
# Cada estilo es una receta completa. Los valores de gusto (tamano, grosor del
# contorno) estan aqui y no repartidos por el codigo, para poder comparar
# versiones cambiando una sola palabra en la linea de comando.

# Solo dos. De cinco versiones que vio eligio `resalte`; las otras se
# borraron porque tener opciones rechazadas a la vista solo estorba al elegir.
# `actual` se queda como respaldo: es el unico que NO necesita una fuente
# descargada, asi que funciona en cualquier computadora.
ESTILOS = {

    "frase": {
        "nombre": "Poppins Bold para frases",
        "descripcion": "frase completa, gruesa y con contorno; para reels de cita",
        "fuente": "Poppins_Bold", "tam": 13.0, "borde": 52.0,
        "color": (1.0, 1.0, 1.0), "color_dato": None,
        "espaciado": 0.0, "caja": None,
    },    "actual": {
        "nombre": "el de siempre",
        "descripcion": "fuente de CapCut, blanca con contorno negro",
        "fuente": None, "tam": 20.0, "borde": 40.0,
        "color": (1.0, 1.0, 1.0), "color_dato": None,
        "espaciado": 0.0, "caja": None,
    },
    "resalte": {
        "nombre": "Anton con cifras en ambar",
        "descripcion": "igual que Anton, pero numeros y porcentajes en ambar",
        "fuente": "Anton", "tam": 22.0, "borde": 48.0,
        "color": (1.0, 1.0, 1.0), "color_dato": (1.0, 0.76, 0.20),
        "espaciado": 0.02, "caja": None,
    },
}


def receta(clave):
    if clave not in ESTILOS:
        raise SystemExit("Estilo de letra desconocido: '%s'. Hay: %s"
                         % (clave, ", ".join(ESTILOS)))
    r = dict(ESTILOS[clave])
    if r.get("anim") and r["anim"] not in animaciones_disponibles():
        raise SystemExit(
            "El estilo '%s' usa la animacion de texto '%s' y no esta descargada\n"
            "en este CapCut. Aplicala una vez a mano a cualquier texto y vuelve\n"
            "a generar." % (clave, r["anim"]))
    if r["fuente"]:
        disponibles = fuentes_disponibles()
        if r["fuente"] not in disponibles:
            raise SystemExit(
                "El estilo '%s' usa la fuente %s y no esta descargada en este\n"
                "CapCut. Agregala una vez a mano a cualquier texto y vuelve a\n"
                "generar. Descargadas ahora: %s"
                % (clave, r["fuente"], ", ".join(sorted(disponibles))))
    return r


def font_type(receta_):
    return getattr(cc.FontType, receta_["fuente"]) if receta_["fuente"] else None


def es_dato(texto, previa=None):
    """Si la palabra carga una cifra: es lo unico que se pinta distinto.

    Cuenta tanto "44" como "tres", porque la transcripcion escribe unas con
    digito y otras con letra segun como suenen, y en pantalla las dos son el
    dato. Lo que NO cuenta es el numero que solo forma la unidad de medida:
    el "ciento" de "por ciento" y el "diez" de "de cada diez". Es la misma
    regla ya validada para los pops en `sonidos.planear()`, y por eso se
    reusa de ahi en vez de escribir otra lista.
    """
    from . import sonidos
    if previa is not None and sonidos._limpiar(previa) in ("por", "cada"):
        return False
    if any(ch.isdigit() for ch in texto) or "%" in texto:
        return True
    return sonidos._es_numero_escrito(texto)


# --------------------------------------------------- reparacion posterior


def resolver(carpeta):
    """Apunta fuentes y animaciones de texto a su recurso local descargado.

    Igual que `_resolver_efectos` para los efectos visuales: pycapcut deja
    marcadores y CapCut los descarta sin avisar. Devuelve (fuentes, animaciones).
    """
    ruta = os.path.join(carpeta, "draft_content.json")
    if not os.path.exists(ruta):
        return 0, 0
    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)

    fuentes = 0
    tocado = False
    for t in (d.get("materials") or {}).get("texts") or []:
        try:
            cont = json.loads(t.get("content") or "{}")
        except Exception:
            continue
        cambio = False
        for est in cont.get("styles") or []:
            fo = est.get("font") or {}
            rid = fo.get("id")
            if not rid:
                continue
            local = _archivo_en(rid, (".ttf", ".otf", ".ttc"))
            if not local:
                # Todavia no esta descargada. Se deja el identificador a nivel
                # material de todas formas: es lo que CapCut usa para reconocer
                # el recurso en la nube y bajarlo al abrir el proyecto. De eso
                # vive tools/fuentes.py.
                t["font_id"] = str(rid)
                t["font_resource_id"] = str(rid)
                tocado = True
                continue
            if fo.get("path") != local:
                fo["path"] = local
                cambio = True
            # los mismos datos hacen falta a nivel material: CapCut lee unos
            # para dibujar y otros para la interfaz, y si no coinciden muestra
            # el nombre de la fuente pero dibuja la de por defecto
            t["font_path"] = local
            t["font_id"] = str(rid)
            t["font_resource_id"] = str(rid)
            t["font_source_platform"] = 1
        if cambio:
            t["content"] = json.dumps(cont, ensure_ascii=False)
            fuentes += 1

    anims = 0
    for ma in (d.get("materials") or {}).get("material_animations") or []:
        for a in ma.get("animations") or []:
            rid = a.get("resource_id")
            if not rid or a.get("path"):
                continue
            base = os.path.join(CACHE_EFECTOS, str(rid))
            if os.path.isdir(base):
                a["path"] = base.replace("\\", "/")
                anims += 1

    if fuentes or anims or tocado:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    return fuentes, anims
