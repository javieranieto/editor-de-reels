"""Como aparecen en pantalla las cifras del guion (los callouts).

El detector de `datos.py` decide QUE numero merece pantalla. Esto decide COMO
se ve. Nacio porque el usuario aprobo los captions pero dijo de las cifras:
"no se ven tan mal, pero no tan muy feos, asi nada mas" -- son el argumento
del video y eran lo mas plano que habia.

Pidio que el numero saliera "por detras de mi", o "moviendose de un lado a
otro", o "un pop y luego que se remueva". Se probaron las tres y eligio el pop.

Las otras dos se borraron, pero dejaron dos cosas aprendidas que estan en las
reglas duras de CLAUDE.md: CapCut SI lee los keyframes en segmentos de texto
(aunque los ignore en los de video), y el recorte de fondo por `matting.flag`
NO funciona en un draft ajeno, porque la mascara la calcula su IA.

Queda `pop`, y `actual` como respaldo: es el unico que no necesita una fuente
ni una animacion descargada, asi que corre en cualquier computadora.
"""

ALTURA_CALLOUT = 0.80        # franja de pared vacia, sobre la cabeza
COLOR_AMBAR = (1.0, 0.76, 0.20)

ESTILOS = {
    "actual": {
        "descripcion": "como estaba: ambar, tamano 30, fijo arriba",
        "tam": 30.0, "altura": ALTURA_CALLOUT, "fuente": None,
        "alpha": 1.0, "borde": 40.0,
        "entrada": None, "salida": None,
    },
    "pop": {
        "descripcion": "entra con rebote y se va con un barrido; Anton grande",
        "tam": 44.0, "altura": ALTURA_CALLOUT, "fuente": "Anton",
        "alpha": 1.0, "borde": 52.0,
        # 0.35s de entrada: el callout dura 1.5-2s, mas seria medio callout
        # animandose. La salida se resta del final en `_callouts_datos`.
        "entrada": ("弹入", 350000), "salida": ("Wiping_Out", 400000),
    },
}


def receta(clave):
    """Receta del estilo. `clave` puede traer ajustes: {"estilo", "altura"}.

    La altura se deja ajustar porque ALTURA_CALLOUT da por hecha una franja de
    pared vacia sobre la cabeza, y eso depende de como haya grabado ese dia: en
    un primer plano cerrado la cabeza empieza al 5% y el callout le caeria en el
    pelo. Medirlo es `tools/encuadre.py <video> --cabeza`.
    """
    ajustes = {}
    if isinstance(clave, dict):
        ajustes = dict(clave)
        clave = ajustes.pop("estilo", "pop")
    if clave not in ESTILOS:
        raise SystemExit("Estilo de cifra desconocido: '%s'. Hay: %s"
                         % (clave, ", ".join(ESTILOS)))
    r = dict(ESTILOS[clave])
    for k, v in ajustes.items():
        if k in r:
            r[k] = v
    if r["fuente"]:
        from . import letras
        disp = letras.fuentes_disponibles()
        if r["fuente"] not in disp:
            raise SystemExit(
                "El estilo de cifra '%s' usa la fuente %s y no esta descargada.\n"
                "Aplicala una vez a mano en CapCut y vuelve a generar."
                % (clave, r["fuente"]))
    for campo in ("entrada", "salida"):
        if r[campo]:
            _verificar_animacion(clave, campo, r[campo][0])
    return r


def _verificar_animacion(clave, campo, nombre):
    """Falla con mensaje en vez de dibujar el texto sin animar."""
    import os

    import pycapcut as cc

    from . import letras
    grupo = cc.TextIntro if campo == "entrada" else cc.TextOutro
    if not hasattr(grupo, nombre):
        raise SystemExit("El estilo de cifra '%s' pide una animacion de %s que "
                         "no existe: %s" % (clave, campo, nombre))
    meta = getattr(grupo, nombre).value
    if not os.path.isdir(os.path.join(letras.CACHE_EFECTOS, str(meta.resource_id))):
        raise SystemExit(
            "El estilo de cifra '%s' usa la animacion de %s '%s' y no esta\n"
            "descargada en este CapCut. Aplicala una vez a mano a cualquier\n"
            "texto y vuelve a generar." % (clave, campo, nombre))


def aplicar_animaciones(segmento, receta_, dur_us):
    """Entrada y salida del callout. Devuelve cuantas puso."""
    import pycapcut as cc

    n = 0
    if receta_["entrada"]:
        nombre, dur = receta_["entrada"]
        segmento.add_animation(getattr(cc.TextIntro, nombre), min(dur, dur_us // 2))
        n += 1
    if receta_["salida"]:
        nombre, dur = receta_["salida"]
        segmento.add_animation(getattr(cc.TextOutro, nombre), min(dur, dur_us // 2))
        n += 1
    return n



# Cuantos caracteres caben de ancho en una cifra, MEDIDO: el usuario encogio a
# mano una cifra de 16 caracteres hasta escala 0.66 en un lienzo de 1080 con
# tam 44, y dejo intactas dos de 6 y 8 caracteres. 16 x 0.66 = 10.6, asi que a
# escala 1.0 caben ~11. Debajo de eso no se toca nada.
CHARS_CALLOUT = 11.0
ANCHO_BASE = 1080.0     # el lienzo donde se midio
TAM_BASE = 44.0         # y el tamano con el que se midio


def escala_por_ancho(texto, receta_, escala_texto=1.0, canvas_ancho=ANCHO_BASE):
    """Cuanto encoger la cifra para que QUEPA de ancho.

    Las cifras se escriben con `auto_wrapping=False` -una cifra partida en dos
    lineas no se lee-, asi que una larga simplemente se sale del lienzo y no da
    ningun error: se ve, y solo si alguien mira. Paso con los clips verticales
    del 2026-09-05.

    La capacidad no es un numero fijo: crece con el ancho del lienzo y baja con
    el tamano de letra, asi que en el video largo horizontal -lienzo de 1920 y
    `escala_texto` 0.35- caben ~56 caracteres y no se encoge nada.
    """
    n = len(str(texto or "").strip())
    if not n:
        return 1.0
    tam = float(receta_.get("tam") or TAM_BASE) * float(escala_texto or 1.0)
    if tam <= 0:
        return 1.0
    caben = CHARS_CALLOUT * (float(canvas_ancho) / ANCHO_BASE) * (TAM_BASE / tam)
    return 1.0 if n <= caben else round(caben / n, 3)
