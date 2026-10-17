"""Voz sintetica para el reel de guion, con los tiempos de palabra exactos.

El segundo tipo de reel: no se graba nada. Se entrega un guion, lo lee una voz
y las imagenes salen de stock.

Lo que hace distinto a este flujo del de siempre: **no hay que transcribir**.
ElevenLabs devuelve, junto al audio, la alineacion CARACTER POR CARACTER del
texto que acaba de leer. Como el texto ya se conoce, los tiempos de palabra
salen exactos y deterministas, sin whisper y sin su deriva. `transcribe.py` no
interviene aqui.

    /v1/text-to-speech/{voz}/with-timestamps
      -> audio_base64 + alignment{characters, character_start_times_seconds,
                                  character_end_times_seconds}

La conversion de caracteres a palabras esta separada de la llamada de red a
proposito: es la pieza de la que depende todo lo demas (captions, cifras,
cortes de escena) y asi se puede probar sin gastar creditos ni tener clave.
"""
import base64
import json
import os
import re
import urllib.error
import urllib.request

from . import llaves

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# La clave vive en .secrets/elevenlabs.yaml (ver pipeline/llaves.py)
CLAVE = llaves.ruta("elevenlabs")

API = "https://api.elevenlabs.io/v1/text-to-speech/%s/with-timestamps"
MODELO = "eleven_multilingual_v2"     # el que habla espanol bien

# El modelo expresivo: lee con intencion en vez de recitar, y obedece
# etiquetas de emocion escritas en el propio texto -[serio], [con ironia]-.
# No es el de por defecto porque cambia como suena TODO lo ya aprobado.
MODELO_EXPRESIVO = "eleven_v3"

# En v3 la estabilidad solo admite tres valores, y son un gusto, no un ajuste
# fino: 0.0 creativo (mas emocion, mas riesgo), 0.5 natural, 1.0 robusto.
ESTABILIDAD = 0.5

# Un reel se lee mas despacio de lo que la gente cree; 0.9 suena a conversacion
# y no a locutor apurado. Es el unico valor de gusto de este modulo.
VELOCIDAD = 0.9


# Voces publicas de ElevenLabs, con id fijo. Sirven cuando la clave esta
# restringida a Text to Speech y no puede listar las de la cuenta. Con el
# modelo multilingue leen espanol; el acento no es nativo.
VOCES_PUBLICAS = [
    ("Adam", "pNInz6obpgDQGcFmaJgB"),
    ("Antoni", "ErXwobaYiN019PkySvjV"),
    ("Josh", "TxGEqnHWrfWFTfGW9XjX"),
    ("Rachel", "21m00Tcm4TlvDq8ikWAM"),
    ("Bella", "EXAVITQu4vr4xnSDxMaL"),
]


def leer_clave(ruta=None):
    """La clave de ElevenLabs, de .secrets/elevenlabs.yaml (api_key)."""
    clave, motivo = llaves.leer("elevenlabs")
    if clave is None:
        raise RuntimeError(
            "Falta la clave de ElevenLabs (%s).\n"
            "  Sacala en elevenlabs.io -> Developers -> API Keys y pegala en el\n"
            "  campo api_key de:\n  %s\n"
            "  El archivo lleva una linea: api_key: tu_llave" % (motivo, CLAVE))
    # un texto de relleno pasaria el filtro de "no vacio" y fallaria luego con
    # un 401 que no dice nada
    if " " in clave or clave.upper() == clave and "_" in clave:
        # no se imprime ni un pedazo: la consola acaba pegada en un chat
        raise RuntimeError(
            "Eso no parece una clave de ElevenLabs (%d caracteres, con espacios\n"
            "o todo en mayusculas). Revisa el campo api_key de:\n  %s"
            % (len(clave), CLAVE))
    return clave


# ------------------------------------------------- caracteres -> palabras


def palabras_desde_alineacion(caracteres, inicios, finales):
    """[{"word","start","end"}] a partir de la alineacion por caracter.

    Mismo formato que devuelve `transcribe.py`, para que todo lo que ya existe
    (captions, cifras, sonidos) funcione igual sin tocar nada.

    Una palabra empieza cuando empieza su primer caracter y termina cuando
    termina el ultimo. Los signos de puntuacion se pegan a la palabra anterior
    y no cuentan para su final: si contaran, la palabra parece durar hasta la
    coma y el caption se queda colgado despues de que la voz ya paso.
    """
    if not caracteres:
        return []
    n = min(len(caracteres), len(inicios), len(finales))
    palabras = []
    actual, ini, fin = "", None, None
    en_tag = False
    for i in range(n):
        c = caracteres[i]
        # Las etiquetas de emocion de v3 ([serio], [con ironia]) NO se locutan,
        # pero SI vienen en la alineacion, caracter por caracter y con tiempos.
        # Sin descartarlas aqui se convierten en palabras y salen impresas en
        # los subtitulos, con un tiempo en el que no se dice nada.
        if c == "[":
            en_tag = True
        if en_tag:
            if actual:
                palabras.append({"word": actual, "start": ini, "end": fin})
                actual, ini, fin = "", None, None
            if c == "]":
                en_tag = False
            continue
        if c.isspace():
            if actual:
                palabras.append({"word": actual, "start": ini, "end": fin})
                actual, ini, fin = "", None, None
            continue
        actual += c
        if ini is None:
            ini = float(inicios[i])
        # la puntuacion se queda en la palabra pero no estira su final
        if not _es_puntuacion(c):
            fin = float(finales[i])
        elif fin is None:
            fin = float(finales[i])
    if actual:
        palabras.append({"word": actual, "start": ini, "end": fin})
    return palabras


def _es_puntuacion(c):
    return c in ".,;:!?¿¡\"'()-—…«»"


# ------------------------------------------------------------- escenas


def escenas(guion, max_palabras=14, min_palabras=4):
    """Parte el guion en escenas, que es lo que decide cuantas imagenes hacen falta.

    Se corta por PUNTUACION FUERTE primero (punto, interrogacion, salto de
    linea) porque ahi es donde cambia la idea, y solo se parte una frase larga
    por comas si se pasa de `max_palabras`. Partir por numero de palabras a
    secas deja escenas que empiezan a media idea y luego piden una imagen que
    no ilustra nada.

    Devuelve [{"texto", "palabras"}].
    """
    bloques = [b.strip() for b in re.split(r"(?<=[.!?…])\s+|\n+", guion or "")
               if b.strip()]
    fuera = []
    for b in bloques:
        trozos = _partir_largo(b, max_palabras)
        fuera += trozos
    # una escena de dos palabras no da tiempo a ver nada: se pega a la anterior
    unidas = []
    for t in fuera:
        if unidas and len(t.split()) < min_palabras:
            unidas[-1] = unidas[-1] + " " + t
        else:
            unidas.append(t)
    return [{"texto": t, "palabras": len(t.split())} for t in unidas]


def _partir_largo(bloque, max_palabras):
    if len(bloque.split()) <= max_palabras:
        return [bloque]
    partes, actual = [], []
    for trozo in re.split(r"(?<=[,;:])\s+", bloque):
        actual.append(trozo)
        if len(" ".join(actual).split()) >= max_palabras:
            partes.append(" ".join(actual))
            actual = []
    if actual:
        partes.append(" ".join(actual))
    return partes


def tiempos_de_escenas(lista_escenas, palabras):
    """Le pone (ini, fin) a cada escena, contando palabras sobre la alineacion.

    Se cuenta por posicion y no por texto porque el TTS puede leer "44" como
    "cuarenta y cuatro": buscar la palabra en la alineacion falla, avanzar el
    indice no.
    """
    fuera, i = [], 0
    for e in lista_escenas:
        n = e["palabras"]
        trozo = palabras[i:i + n]
        if not trozo:
            break
        fuera.append({**e, "ini": round(trozo[0]["start"], 3),
                      "fin": round(trozo[-1]["end"], 3)})
        i += n
    return fuera


# ---------------------------------------------------------------- la voz


def revisar_acentos(texto, minimo_palabras=25):
    """Avisa si un guion en espanol parece venir sin tildes. "" si esta bien.

    En espanol la tilde ES la pronunciacion: el TTS lee "cambio" como el
    presente y "cambió" como el pasado, y suena mal sin que nada falle. Paso
    de verdad en la primera prueba: el guion se escribio sin acentos por
    costumbre del codigo y el usuario lo noto al oirlo.

    La regla de "sin acentos" del proyecto es para el CODIGO y los mensajes de
    consola, nunca para el texto que se va a locutar.
    """
    palabras = (texto or "").split()
    if len(palabras) < minimo_palabras:
        return ""
    if any(c in texto for c in "áéíóúÁÉÍÓÚñÑüü"):
        return ""
    return ("El guion no tiene ni una tilde en %d palabras. En espanol la tilde\n"
            "es la pronunciacion ('cambio' no suena como 'cambió'), asi que la\n"
            "voz va a leer mal sin que nada de error. Escribelo acentuado."
            % len(palabras))


def sintetizar(texto, voz_id, destino, clave=None, modelo=MODELO,
               velocidad=VELOCIDAD, estabilidad=ESTABILIDAD, log=print):
    """Genera el audio y devuelve {"archivo", "palabras", "duracion"}.

    Cachea por (texto, voz, modelo, velocidad, estabilidad): reintentar un plan
    no debe gastar creditos otra vez.
    """
    clave = clave or leer_clave()
    aviso = revisar_acentos(texto)
    if aviso and log:
        for linea in aviso.splitlines():
            log("  aviso: " + linea)
    firma = _firma(texto, voz_id, modelo, velocidad, estabilidad)
    cache = os.path.splitext(destino)[0] + ".json"
    if os.path.exists(destino) and os.path.exists(cache):
        with open(cache, encoding="utf-8") as f:
            guardado = json.load(f)
        if guardado.get("firma") == firma:
            log("  voz en cache (%d palabras)" % len(guardado["palabras"]))
            return {"archivo": destino, "palabras": guardado["palabras"],
                    "duracion": guardado["duracion"]}

    cuerpo = json.dumps({
        "text": texto,
        "model_id": modelo,
        "voice_settings": _ajustes(modelo, velocidad, estabilidad),
    }).encode("utf-8")
    pedido = urllib.request.Request(
        API % voz_id, data=cuerpo,
        headers={"xi-api-key": clave, "Content-Type": "application/json",
                 "Accept": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=120) as r:
            datos = json.load(r)
    except urllib.error.HTTPError as e:
        detalle = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError("ElevenLabs respondio %s:\n%s" % (e.code, detalle))

    os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
    with open(destino, "wb") as f:
        f.write(base64.b64decode(datos["audio_base64"]))

    al = datos.get("alignment") or datos.get("normalized_alignment") or {}
    palabras = palabras_desde_alineacion(
        al.get("characters") or [],
        al.get("character_start_times_seconds") or [],
        al.get("character_end_times_seconds") or [])
    duracion = round(palabras[-1]["end"], 3) if palabras else 0.0
    with open(cache, "w", encoding="utf-8") as f:
        json.dump({"firma": firma, "palabras": palabras,
                   "duracion": duracion}, f, ensure_ascii=False)
    log("  voz: %d palabras, %.1f s" % (len(palabras), duracion))
    return {"archivo": destino, "palabras": palabras, "duracion": duracion}


def _ajustes(modelo, velocidad, estabilidad):
    """Los ajustes de voz que acepta cada modelo.

    v3 no tiene `speed`: mandarselo no da error, simplemente no hace nada, que
    es peor -se cree que se pidio un ritmo y no se pidio-. El ritmo en v3 se
    dirige escribiendo, con la puntuacion y las etiquetas.
    """
    if modelo.startswith("eleven_v3"):
        return {"stability": estabilidad, "similarity_boost": 0.75}
    return {"stability": estabilidad, "similarity_boost": 0.75,
            "speed": velocidad}


def _firma(texto, voz_id, modelo, velocidad, estabilidad=ESTABILIDAD):
    import hashlib
    crudo = "|".join([texto, str(voz_id), str(modelo), str(velocidad)])
    # La estabilidad entra en la firma solo cuando NO es la de siempre: si
    # entrara siempre, cambiaria la firma de todo lo ya sintetizado y volver a
    # correr un plan viejo -con toda su voz ya pagada- volveria a cobrar.
    if estabilidad != ESTABILIDAD:
        crudo += "|est%s" % estabilidad
    return hashlib.sha1(crudo.encode("utf-8")).hexdigest()


def voces(clave=None):
    """Las voces disponibles en la cuenta: [(id, nombre, idiomas)]."""
    clave = clave or leer_clave()
    pedido = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": clave, "Accept": "application/json"})
    with urllib.request.urlopen(pedido, timeout=60) as r:
        datos = json.load(r)
    fuera = []
    for v in datos.get("voices") or []:
        etiquetas = v.get("labels") or {}
        fuera.append((v.get("voice_id"), v.get("name"),
                      etiquetas.get("language") or etiquetas.get("accent") or ""))
    return fuera
