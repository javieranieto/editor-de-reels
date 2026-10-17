"""Efectos de sonido: cuales usar y donde ponerlos.

Las reglas de aqui NO son teoria: salen de medir una edicion que un usuario hizo
a mano con los sonidos que a el le gustan. Antes se sintetizaban efectos con
ffmpeg y se colocaban por criterio propio, y rechazo las dos cosas: "no me
gustaron esos sonidos ni como los estas poniendo".

Lo que se aprendio de su edicion:

  - Cuatro sonidos y ya: riser, reveal, swish, pop. Los pone CADA QUIEN en
    recursos/sfx_usuario/ (ver su LEEME.md): los de la biblioteca de CapCut
    tienen licencia para usarse dentro de CapCut, no para redistribuirse, asi
    que el repo no los trae. Sin ellos el reel sale sin sonidos y se avisa.
  - **Volumen 1.0**, no 0.25. Los quiere audibles, no de fondo.
  - El **riser abre el video** (en 0.00 s), no anuncia el cierre.
  - El **reveal** aparece una sola vez: cuando entra la cifra estrella.
  - El **pop** marca los numeros que CARGAN la frase — "120" y "150" llevan uno
    cada uno, aunque en pantalla sean un solo callout. No marca el "ciento" de
    "por ciento" ni el "diez" de "de cada diez": esos no son el dato.
  - El **swish** va en los cortes, alrededor de -0.13 s del corte.
  - **Nunca dos sonidos a la vez.** El pop manda; el swish solo suena si ese
    corte no tiene ya otro efecto cerca.
  - Nada de "impacto" en los zooms: no usa ninguno.
"""
import os
import re

CARPETA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "recursos", "sfx_usuario")

# nombre interno -> archivo en recursos/sfx_usuario/. Vale .mp3, .wav o .m4a
# con ese nombre (riser.wav sirve igual que riser.mp3). Ver el LEEME.md de esa
# carpeta: los pone cada quien.
# Cada sonido dice tambien QUE PARTE de si mismo se usa. Es lo que mas se
# noto al comparar: un riser dura 4 s y lo que suena es el final; recortar el
# principio deja un segundo de casi nada. En su edicion tomo del 3.00 al 4.10.
#   parte "final"  -> la ventana termina donde termina el archivo
#   parte "inicio" -> arranca en 0
SONIDOS = {
    "riser":  {"archivo": "riser.mp3",  "parte": "final",  "dur": 1.10},
    "reveal": {"archivo": "reveal.mp3", "parte": "inicio", "dur": 1.33},
    "swish":  {"archivo": "swish.mp3",  "parte": "inicio", "dur": None},
    "pop":    {"archivo": "pop.mp3",    "parte": "inicio", "dur": None},
}

VOLUMEN = 1.0        # medido en su edicion: todos al 100%
ADELANTO_SWISH = 0.13   # el swish entra un poco antes del corte
SEPARACION = 0.5     # distancia minima entre dos efectos cualesquiera
# Cuanto swish aguanta, medido de una edicion aprobada: 6 swish en
# 36.97 s, o sea uno cada 6.2 s. Ojo con como salio ese 6: el pipeline los puso
# en los 10 cortes y CUATRO se cayeron solos al chocar con los pops de las
# cifras. Nunca se probo la regla a densidad plena. En un reel sin numeros no
# hay pops que los frenen y salen 12 en 35 s: *"se siente demasiado pesado"*.
# La densidad se limita al final, sobre los que sobreviven.
SEGUNDOS_POR_SWISH = 6.2
DUR_RISER = 1.2      # solo el arranque del riser, no los 4 s completos
DUR_REVEAL = 1.4

CIFRA = re.compile(r"\d")


EXTENSIONES = (".mp3", ".wav", ".m4a")


def disponibles(carpeta=None):
    """{tipo: {ruta, parte, dur}} de los sonidos que existan en disco.

    El que falte simplemente no suena: el repo no trae sonidos de usuario
    (ver recursos/sfx_usuario/LEEME.md) y quien llama avisa si no hay ninguno.
    """
    carpeta = carpeta or CARPETA
    salida = {}
    for tipo, cfg in SONIDOS.items():
        base = os.path.splitext(cfg["archivo"])[0]
        for ext in EXTENSIONES:
            ruta = os.path.join(carpeta, base + ext)
            if os.path.exists(ruta) and os.path.getsize(ruta) > 1000:
                salida[tipo] = dict(cfg, archivo=base + ext,
                                    ruta=os.path.abspath(ruta))
                break
    return salida


def donde_suena(ruta):
    """"inicio" o "final" segun donde este la energia del sonido.

    Sirve para configurar solo un sonido nuevo: un riser crece y revienta al
    final, un golpe suena de entrada. Recortar el extremo equivocado deja un
    trozo casi mudo — que fue justo lo que paso con el riser.
    """
    import subprocess

    def nivel(desde, dur):
        r = subprocess.run(
            ["ffmpeg", "-v", "info", "-ss", "%.3f" % desde, "-t", "%.3f" % dur,
             "-i", ruta, "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        for linea in (r.stderr or "").splitlines():
            if "mean_volume:" in linea:
                try:
                    return float(linea.split("mean_volume:")[1].split("dB")[0])
                except ValueError:
                    pass
        return -99.0

    import subprocess as sp
    total = sp.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                    "-of", "csv=p=0", ruta], capture_output=True, text=True).stdout.strip()
    total = float(total) if total else 0.0
    if total < 0.6:
        return "inicio"          # tan corto que se usa entero
    mitad = total / 2.0
    return "final" if nivel(mitad, mitad) > nivel(0, mitad) + 2.0 else "inicio"


def recorte(cfg, total, disponible):
    """(desde, duracion) del trozo a usar, quedandose con la parte que suena.

    Si el archivo es mas largo de lo que cabe, se elige el extremo segun
    `parte`: el final para los que van creciendo (riser), el principio para
    los que golpean de entrada.
    """
    dur = cfg.get("dur") or total
    dur = min(dur, total, disponible)
    dur = max(0.05, dur - 0.03)     # ffprobe reporta unos ms de mas
    desde = max(0.0, total - dur) if cfg.get("parte") == "final" else 0.0
    return round(desde, 3), round(dur, 3)


def planear(segmentos, callouts=None, duracion=None, palabras=None):
    """Efectos deducidos del montaje, con las reglas aprendidas del usuario.

    palabras : palabras en tiempo FINAL; sirven para poner un pop en cada
               numero dicho, que es como el los usa.
    """
    # Se arma por PRIORIDAD, no por tiempo: si un pop y el reveal caen en el
    # mismo instante debe quedar el reveal, aunque el pop empiece 10 ms antes.
    por_prioridad = []

    # 1. el riser abre el video
    por_prioridad.append({"ini": 0.0, "tipo": "riser", "dur": DUR_RISER})

    # 2. el reveal, una sola vez, en la primera cifra que aparece en pantalla
    orden = sorted(callouts or [], key=lambda c: float(c["ini"]))
    if orden:
        por_prioridad.append({"ini": max(0.0, float(orden[0]["ini"]) + 0.15),
                              "tipo": "reveal", "dur": DUR_REVEAL})

    # 3. un pop en cada numero que CARGA la frase
    lista = list(palabras or [])
    for i, w in enumerate(lista):
        if not (CIFRA.search(w["word"]) or _es_numero_escrito(w["word"])):
            continue
        previa = _limpiar(lista[i - 1]["word"]) if i else ""
        # "por ciento" y "de cada diez" traen numeros que no son el dato:
        # el usuario no los marca, marca la cifra que compara
        if previa in ("por", "cada"):
            continue
        por_prioridad.append({"ini": round(float(w["start"]), 3), "tipo": "pop"})

    # 4. swish en los cortes; se anota el peso del corte por si luego sobran
    cursor = 0.0
    for i, s in enumerate(segmentos):
        if i > 0:
            previo = segmentos[i - 1]["fin"] - segmentos[i - 1]["ini"]
            por_prioridad.append({"ini": round(max(0.0, cursor - ADELANTO_SWISH), 3),
                                  "tipo": "swish",
                                  "_peso": max(previo, s["fin"] - s["ini"])})
        cursor += s["fin"] - s["ini"]

    # 5. nunca dos a la vez
    limpio = []
    for e in por_prioridad:
        if any(abs(e["ini"] - x["ini"]) < SEPARACION for x in limpio):
            continue
        if duracion and e["ini"] >= duracion - 0.1:
            continue
        e["volumen"] = VOLUMEN
        limpio.append(e)
    limpio.sort(key=lambda e: e["ini"])

    # 6. y por ultimo se ralea el swish. Va DESPUES de las colisiones a
    # proposito: en un reel con cifras los pops ya se llevaron varios, y ahi no
    # hay nada que quitar. Solo se recorta lo que de verdad iba a sonar.
    limpio = _ralear_swish(limpio, duracion)
    for e in limpio:
        e.pop("_peso", None)
    return limpio


def _ralear_swish(eventos, duracion):
    """Deja como mucho un swish cada SEGUNDOS_POR_SWISH segundos.

    Sobreviven los cortes de mas peso: el que separa las dos escenas mas largas
    es el cambio de verdad, y el swish esta para marcar eso, no cada empalme.
    """
    swishes = [e for e in eventos if e["tipo"] == "swish"]
    if not duracion or not swishes:
        return eventos
    cupo = max(1, int(round(duracion / SEGUNDOS_POR_SWISH)))
    if len(swishes) <= cupo:
        return eventos
    fuertes = sorted(swishes, key=lambda e: (-e.get("_peso", 0.0), e["ini"]))[:cupo]
    se_quedan = set(id(e) for e in fuertes)
    return [e for e in eventos if e["tipo"] != "swish" or id(e) in se_quedan]


ESCRITOS = {"cero", "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho",
            "nueve", "diez", "once", "doce", "veinte", "treinta", "cuarenta",
            "cincuenta", "sesenta", "setenta", "ochenta", "noventa", "cien",
            "ciento", "mil"}


def _limpiar(palabra):
    return palabra.lower().strip(".,;:!?¿¡ ").strip()


def _es_numero_escrito(palabra):
    return _limpiar(palabra) in ESCRITOS
