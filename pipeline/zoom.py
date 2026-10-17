"""Movimiento de camara: punch-ins, envolventes y drift.

Ideas tomadas de OpenShorts (github.com/mutonby/openshorts, punch_in.py), que
las valido sobre un corpus de 20 clips:

  1. ENVOLVENTE ASIMETRICA. Entra rapido, sostiene, suelta lento. Una rampa
     lineal se lee como deriva mecanica; la asimetrica se lee como un operador
     humano moviendo la camara a proposito.
  2. DENSIDAD. Mas de ~3 punches por minuto se siente como tic, y dos seguidos
     se leen como glitch. Ellos midieron 8.4/min con umbrales flojos y lo
     llamaron "not a push on the beat, it is a twitch".
  3. TOPE DE ~15%. Mas alla empieza a cortar cabeza en plano medio y a mostrar
     el reescalado.

Mejora propia: ellos disparan con picos del envolvente de audio, y su propio
codigo anota que el transcript seria mejor fuente ("punch on the hook word, not
on the loudest syllable"). Nosotros SI tenemos timestamps por palabra, asi que
el modo automatico dispara sobre estructura del habla: la frase que sigue a una
pausa larga (el hablante tomo aire antes de decirla) y las que traen cifras.
"""
import re

# --- envolvente ------------------------------------------------------------

SUBIDA = 0.28      # segundos de entrada (rapida)
BAJADA = 0.60      # segundos de salida (lenta)
MUESTRAS = 4       # puntos intermedios por tramo curvo
PICO_MAX = 1.30    # tope duro de seguridad


def _suavizar(t):
    """Smoothstep en [0,1]: las rampas lineales se ven mecanicas."""
    t = min(max(t, 0.0), 1.0)
    return t * t * (3.0 - 2.0 * t)


def envolvente(dur, base=1.0, pico=1.14, volver=True):
    """Puntos (segundo, escala) de un punch asimetrico dentro de un segmento.

    dur    : duracion del segmento en segundos
    base   : escala de reposo
    pico   : escala maxima del empuje
    volver : si True suelta de vuelta a `base` antes de terminar; si False se
             queda arriba (util cuando el corte siguiente continua la idea)
    """
    pico = min(float(pico), PICO_MAX)
    if dur <= 0 or pico <= base:
        return [(0.0, base)]

    subida = min(SUBIDA, dur * 0.25)
    bajada = min(BAJADA, dur * 0.30) if volver else 0.0
    sostiene = max(0.0, dur - subida - bajada)

    puntos = [(0.0, base)]
    for i in range(1, MUESTRAS + 1):
        t = i / (MUESTRAS + 1)
        puntos.append((t * subida, base + (pico - base) * _suavizar(t)))
    puntos.append((subida, pico))

    if sostiene > 0:
        puntos.append((subida + sostiene, pico))
    if bajada > 0:
        for i in range(1, MUESTRAS + 1):
            t = i / (MUESTRAS + 1)
            puntos.append((subida + sostiene + t * bajada,
                           pico - (pico - base) * _suavizar(t)))
        puntos.append((dur, base))

    # sin duplicados de tiempo y en orden (CapCut ignora keyframes repetidos)
    limpio = []
    for t, v in puntos:
        t = min(max(t, 0.0), dur)
        if limpio and abs(t - limpio[-1][0]) < 0.01:
            limpio[-1] = (t, v)
        else:
            limpio.append((t, v))
    return limpio


# --- eleccion automatica de enfasis ---------------------------------------

MIN_HUECO = 12.0        # segundos entre punches: dos seguidos se leen como glitch
POR_MINUTO_MAX = 3.0    # techo de densidad medido por OpenShorts sobre 20 clips
PAUSA_DRAMATICA = 0.9
CIFRA = re.compile(r"\d")


def elegir_punches(segmentos, palabras_por_clip=None, min_hueco=MIN_HUECO,
                   por_minuto_max=POR_MINUTO_MAX):
    """Indices de segmentos que merecen punch, por estructura del habla.

    Puntua cada segmento y se queda con los mejores respetando dos limites:
    la distancia minima entre punches y el techo de densidad por minuto.
    Devuelve un dict {indice: puntaje} con los elegidos.
    """
    palabras_por_clip = palabras_por_clip or {}
    candidatos = []
    cursor = 0.0
    posicion = []          # posicion en la linea de tiempo final de cada segmento

    anterior = None
    for i, s in enumerate(segmentos):
        dur = s["fin"] - s["ini"]
        posicion.append(cursor)
        cursor += dur

        puntaje = 0.0
        # el hablante hizo una pausa antes de esta frase: viene algo importante
        if anterior and s["path"] == anterior["path"]:
            hueco = s["ini"] - anterior["fin"]
            if hueco > PAUSA_DRAMATICA:
                puntaje += min(hueco, 4.0)
        # cifras y porcentajes: casi siempre son el dato que carga la frase
        texto = " ".join(
            w["word"] for w in palabras_por_clip.get(s["path"], [])
            if s["ini"] <= w["start"] and w["end"] <= s["fin"])
        if CIFRA.search(texto):
            puntaje += 2.5
        # frases muy cortas no dan tiempo a que el empuje se lea
        if dur < 1.2:
            puntaje -= 3.0

        if puntaje > 0:
            candidatos.append((puntaje, i))
        anterior = s

    tope = max(1, int(cursor / 60.0 * por_minuto_max)) if cursor > 0 else 1
    elegidos = {}
    for puntaje, i in sorted(candidatos, reverse=True):
        if len(elegidos) >= tope:
            break
        if all(abs(posicion[i] - posicion[j]) >= min_hueco for j in elegidos):
            elegidos[i] = round(puntaje, 2)
    return elegidos
