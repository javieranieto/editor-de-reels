"""Deteccion de voz real con ffmpeg, para no cortar a media palabra.

Los tiempos de whisper son buenos pero no infalibles: a veces se le escapa la
ultima palabra de una frase, y un corte guiado solo por el transcript la parte
por la mitad. El audio no miente, asi que se mide donde hay voz de verdad y se
estiran los cortes hasta el final real del habla.

Solo se estira hacia el silencio que ibamos a tirar de todos modos: nunca se
invade la frase siguiente ni se reviven tomas descartadas.
"""
import json
import os
import re
import subprocess

INICIO = re.compile(r"silence_start:\s*(-?[\d.]+)")
FIN = re.compile(r"silence_end:\s*(-?[\d.]+)")

RUIDO_DB = -32      # por debajo de esto se considera silencio
MIN_SILENCIO = 0.2  # silencios mas cortos no cuentan como pausa


def intervalos_voz(path, duracion, ruido_db=RUIDO_DB, min_silencio=MIN_SILENCIO,
                   cache_path=None):
    """Tramos [(ini, fin)] donde hay voz, en segundos. Cachea en disco."""
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            guardado = json.load(f)
        if guardado.get("source") == os.path.abspath(path):
            return [tuple(x) for x in guardado["voz"]]

    salida = subprocess.run(
        # -vn es lo que hace esto rapido: sin el, ffmpeg decodifica todo el
        # video para analizar solo el audio (minutos en vez de segundos)
        ["ffmpeg", "-v", "info", "-vn", "-i", path, "-af",
         "silencedetect=noise=%ddB:d=%s" % (ruido_db, min_silencio),
         "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stderr or ""

    silencios, abierto = [], None
    for linea in salida.splitlines():
        m = INICIO.search(linea)
        if m:
            abierto = max(0.0, float(m.group(1)))
            continue
        m = FIN.search(linea)
        if m and abierto is not None:
            silencios.append((abierto, float(m.group(1))))
            abierto = None
    if abierto is not None:
        silencios.append((abierto, duracion))

    # la voz es el complemento de los silencios
    voz, cursor = [], 0.0
    for ini, fin in silencios:
        if ini > cursor:
            voz.append((round(cursor, 3), round(ini, 3)))
        cursor = max(cursor, fin)
    if cursor < duracion:
        voz.append((round(cursor, 3), round(duracion, 3)))

    if cache_path:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump({"source": os.path.abspath(path), "voz": voz}, f)
    return voz


MIN_TRAMO = 0.08    # tramos de voz mas cortos son ruido, no habla
AIRE = 0.05         # respiro que se deja a cada lado del habla
MARGEN = 0.6        # cuanto se puede estirar para rescatar habla cortada
RECORTE_MAX = 1.5   # cuanto silencio se puede recortar de una vez
MARGEN_FINAL = 0.03  # ffprobe reporta de mas: sin esto CapCut rechaza el draft
# Hasta donde se sigue un sonido que el transcript no cubre. Whisper solo
# escribe palabras: un ruido de demostracion, una risa o un suspiro no existen
# para el, y el corte se cierra encima. Paso en un reel que ensenaba un
# ruido ("lo tapamos con un ruido como este") y el ruido, 1.7 s, se quedaba
# fuera -- justo lo que el reel iba a ensenar. Si el tramo de voz
# que trae la ultima palabra SIGUE sonando, es la misma emision y se respeta.
SEGUIR_SONIDO = 2.5


def ajustar(keeps, voz, aire=AIRE, margen=MARGEN, recorte_max=RECORTE_MAX,
            duracion=None):
    """Pega cada corte al habla real: recorta el silencio y rescata lo cortado.

    Es lo que hace la diferencia entre un reel que se siente lento y uno
    fluido. Los tiempos del transcript dejan medio segundo de aire muerto a
    cada lado; aqui el corte se apoya en donde el audio dice que empieza y
    acaba la voz, dejando solo un respiro.

    keeps       : [(ini, fin)] del planificador, guiados por el transcript
    voz         : tramos con voz del audio
    aire        : respiro a cada lado (segundos)
    margen      : maximo que se estira para rescatar una silaba cortada
    recorte_max : maximo silencio que se recorta de un lado
    duracion    : cuanto dura el material, para no salirse de el

    🔴 `duracion` no es opcional en la practica. El aire se suma a los dos
    extremos, asi que un clip que EMPIEZA hablando sale con `ini = -0.05` y uno
    que ACABA hablando se pasa 50 ms del final. En un video largo no se nota
    -los bordes caen en silencio-, pero los siete clips verticales del
    2026-09-05 salieron los siete mal. No da error aqui: revienta despues, en
    pycapcut, con un ValueError en chino que no dice de que clip habla, o deja
    un draft que CapCut abre vacio.
    """
    if not voz:
        return keeps

    tramos = [(a, b) for a, b in voz if b - a >= MIN_TRAMO]
    if not tramos:
        return keeps

    ajustados = []
    for idx, (ini, fin) in enumerate(keeps):
        dentro = [(a, b) for a, b in tramos if b > ini and a < fin]
        if not dentro:
            ajustados.append((round(ini, 3), round(fin, 3)))
            continue

        primero, ultimo = dentro[0], dentro[-1]
        nuevo_ini, nuevo_fin = ini, fin

        # --- entrada
        if primero[0] > ini:
            # el corte abre en silencio: se recorta hasta justo antes de hablar
            nuevo_ini = min(primero[0] - aire, ini + recorte_max)
            nuevo_ini = max(nuevo_ini, ini)
        elif ini - primero[0] <= margen:
            # el corte entro con la palabra ya empezada: se rescata su arranque
            nuevo_ini = primero[0] - aire

        # --- salida
        if ultimo[1] < fin:
            # cola de silencio: se recorta y se deja solo el respiro
            nuevo_fin = max(ultimo[1] + aire, fin - recorte_max)
            nuevo_fin = min(nuevo_fin, fin)
        elif ultimo[1] - fin <= margen:
            # cortaba a media palabra: se rescata hasta el final del habla
            nuevo_fin = ultimo[1] + aire
        elif ultimo[1] - fin <= SEGUIR_SONIDO:
            # sigue sonando sin que el transcript lo diga: es un sonido que
            # whisper no escribe, no una frase nueva (entre frases hay silencio
            # y el tramo se habria cortado). Se respeta entero.
            nuevo_fin = ultimo[1] + aire

        # nunca pisar los cortes vecinos ni invertirse
        if idx > 0:
            nuevo_ini = max(nuevo_ini, keeps[idx - 1][1])
        if idx + 1 < len(keeps):
            nuevo_fin = min(nuevo_fin, keeps[idx + 1][0])
        # ni salirse del material: el aire de los extremos no tiene donde caer.
        # Al final se resta MARGEN_FINAL porque ffprobe reporta unos ms de mas
        # (regla dura 7) y CapCut rechaza el draft por pasarse.
        nuevo_ini = max(nuevo_ini, 0.0)
        if duracion:
            nuevo_fin = min(nuevo_fin, duracion - MARGEN_FINAL)
        if nuevo_fin - nuevo_ini < 0.2:
            nuevo_ini, nuevo_fin = ini, fin

        ajustados.append((round(nuevo_ini, 3), round(nuevo_fin, 3)))
    return ajustados


# --------------------------------------------------- salud del audio de origen
# Medido sobre grabaciones reales de telefono: las crudas pican en 0.0-0.2 dB,
# o sea SIN margen, con un rango dinamico de 10-15 LU. La unica con aire fue
# una que ya venia exportada (-3.9 dBTP, rango 3.6 LU).
#
# No hay recorte destructivo -- el "flat factor" es 0, la onda no esta achatada
# -- pero grabar pegado al techo no deja donde trabajar: cualquier proceso que
# suba el nivel distorsiona. El render ya lo evita con TP=-1.5, asi que esto no
# es un fallo del pipeline: es un aviso para la proxima grabacion, que es donde
# de verdad se arregla.
PICO_SEGURO = -1.0      # dBFS: por encima de esto ya no queda margen
RANGO_ANCHO = 9.0       # LU: mas que esto en un plano fijo es que pico y valle bailan


def salud_audio(path):
    """(pico_dBFS, LUFS, rango_LU) del audio, o None si no se puede medir."""
    import re
    try:
        r = subprocess.run(
            ["ffmpeg", "-nostdin", "-v", "info", "-i", path, "-vn",
             "-af", "loudnorm=print_format=json", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=600)
    except Exception:
        return None
    m = re.search(r"\{[^{}]*input_i[^{}]*\}", r.stderr, re.S)
    if not m:
        return None
    try:
        j = json.loads(m.group(0))
        return (float(j["input_tp"]), float(j["input_i"]), float(j["input_lra"]))
    except Exception:
        return None


def avisar_audio(path, log=print):
    """Una linea si la grabacion viene sin margen. Silencio si esta bien."""
    d = salud_audio(path)
    if not d:
        return
    pico, lufs, rango = d
    if pico >= PICO_SEGURO:
        log("  aviso: el audio pica en %+.1f dB, sin margen. Baja la ganancia "
            "un par de dB al grabar." % pico)
    elif rango >= RANGO_ANCHO:
        log("  aviso: rango dinamico de %.1f LU; el volumen sube y baja mucho." % rango)
