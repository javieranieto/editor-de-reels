"""Efectos visuales y transiciones de CapCut, y donde colocarlos.

Igual que con el sonido, las reglas salen de medir una edicion del usuario:
puso un **White Flash 2** en 0.00 s durante 1 s, junto con el riser. Un destello de apertura, no un adorno repartido por el video.

Dos cosas que costaron encontrar y que no se ven venir:

1. Hay que escribirlos con `script.add_effect()`, no con `add_segment()` y un
   `EffectSegment`: add_segment no acepta ese tipo y deja el material sin
   escribir.
2. Los efectos son **recursos que CapCut descarga**. Si el material del draft
   no apunta a la carpeta local del recurso, CapCut abre el proyecto, no lo
   resuelve y tira la pista **sin avisar**: se ve el efecto en la linea de
   tiempo y no pasa nada en pantalla. Por eso aqui solo se ofrecen los que el
   CapCut local ya tiene bajados.
"""
import os

CACHE_EFECTOS = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Cache\effect")

# Nombre interno -> nombre en el catalogo de pycapcut (que va en chino) y
# duracion tipica. Se anaden aqui segun el usuario los vaya validando.
CATALOGO = {
    # el suyo: destello blanco de apertura. Sus parametros coincidian con los
    # valores por defecto (velocidad 0.50, luminancia 1.00), asi que no se
    # fuerzan y CapCut usa los de fabrica.
    "flash_apertura": {"efecto": "闪白_II", "nombre": "White Flash 2", "dur": 1.0},
    # candidatos: solo se usaran si el usuario los estrena una vez en CapCut,
    # que es lo que hace que se descarguen
    "golpe": {"efecto": "Focus_Shake", "nombre": "Focus Shake", "dur": 0.7},
    "glitch": {"efecto": "RGB_Shake", "nombre": "RGB Shake", "dur": 0.6},
    "destello": {"efecto": "Flash_Light", "nombre": "Flash Light", "dur": 0.8},
}

# Transiciones. Van MUY contadas: lo que hace bueno este reel son los cortes
# secos, y una transicion en cada corte los arruinaria. Se reservan para el
# cambio de seccion, donde marcan que empieza otra idea.
TRANSICIONES = {
    "flash": {"tipo": "White_Flash", "nombre": "White Flash", "dur": 0.4},
    "flash_suave": {"tipo": "Lumin_Flash", "nombre": "Lumin Flash", "dur": 0.8},
    "zoom": {"tipo": "Snap_Zoom", "nombre": "Snap Zoom", "dur": 0.5},
}


def ruta_local(resource_id):
    """Carpeta del recurso descargado, o None si CapCut nunca lo bajo."""
    base = os.path.join(CACHE_EFECTOS, str(resource_id))
    if not os.path.isdir(base):
        return None
    for sub in sorted(os.listdir(base)):
        completo = os.path.join(base, sub)
        if os.path.isdir(completo):
            return completo.replace("\\", "/")
    return None


def _resource_id(tipo):
    return getattr(getattr(tipo, "value", None), "resource_id", None)


def disponibles(solo_descargados=True):
    """Efectos usables: en el catalogo de pycapcut Y descargados en el CapCut local."""
    import pycapcut as cc
    salida = {}
    for clave, cfg in CATALOGO.items():
        tipo = getattr(cc.VideoSceneEffectType, cfg["efecto"], None)
        if tipo is None:
            continue
        rid = _resource_id(tipo)
        ruta = ruta_local(rid) if rid else None
        if solo_descargados and not ruta:
            continue
        salida[clave] = dict(cfg, tipo=tipo, resource_id=rid, ruta=ruta)
    return salida


def sin_descargar():
    """[(clave, nombre)] del catalogo que el CapCut local aun no tiene bajados.

    Para usarlos basta con que el usuario los aplique una vez a mano en
    CapCut: eso los descarga y ya quedan disponibles para siempre.
    """
    import pycapcut as cc
    faltan = []
    for clave, cfg in CATALOGO.items():
        tipo = getattr(cc.VideoSceneEffectType, cfg["efecto"], None)
        if tipo is None:
            continue
        rid = _resource_id(tipo)
        if not (rid and ruta_local(rid)):
            faltan.append((clave, cfg["nombre"]))
    return faltan


def transiciones_disponibles():
    import pycapcut as cc
    salida = {}
    for clave, cfg in TRANSICIONES.items():
        tipo = getattr(cc.TransitionType, cfg["tipo"], None)
        if tipo is not None:
            salida[clave] = dict(cfg, obj=tipo)
    return salida


def planear(segmentos, duracion=None):
    """Efectos deducidos del montaje.

    Solo el destello de apertura, que es el unico que el usuario ha validado.
    Anadir mas cuando los apruebe: un efecto de mas se nota mucho mas que uno
    de menos.
    """
    if not segmentos or "flash_apertura" not in disponibles():
        return []
    return [{"ini": 0.0, "tipo": "flash_apertura",
             "dur": CATALOGO["flash_apertura"]["dur"]}]
