"""Reel de una frase: imagen fija, voz en off y el texto en tarjetas cortas.

El tercer tipo de reel: una frase partida en dos se lee sobre una imagen que
la ilustra. No hay guion que cortar ni video que analizar: la frase manda y
todo lo demas se acomoda a ella.

    python tools/reel_frase.py --imagen tablero.jpg --nombre "FRASE 01" \
        --frase "El foco no era el problema... | era el cableado viejo."

Con VARIAS imagenes cambia de escena en cada giro de la frase: una imagen por
parte, y el corte cae en la pausa entre una parte y la siguiente.

    python tools/reel_frase.py --imagen antes.jpg --imagen despues.jpg \
        --frase "Un apagador que chispea... | es un aviso, no una molestia." \
        --movimiento acercar --movimiento abrir

Asi tambien se cuenta una historia de varios capitulos en un solo reel: 5
imagenes y una frase de 5 partes.

Con la VOZ GRABADA de alguien en vez de la artificial:

    python tools/reel_frase.py --imagen e1.jpg ... --frase "..." --audio mi_voz.m4a

La grabacion se transcribe y se empareja palabra por palabra contra el guion:
el TEXTO de los subtitulos sale del guion (sin los errores de la transcripcion)
y los TIEMPOS salen de la voz, asi que los cortes caen en las pausas de quien
lee. Aguanta que cambie, salte o agregue palabras.

Deja un MP4 para revisar de inmediato Y el proyecto de CapCut para retocarlo.
La musica NO se pone: se elige de oido, y eso no se automatiza -ver la nota de
`catalogo_voces.py` sobre lo que una medicion no distingue.
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFont

from pipeline import letras as mod_letras
from pipeline import nucleo, voz_off
from pipeline import transcribe as mod_transcribe

W, H, FPS = 1080, 1920, 30
AIRE = 0.8            # la imagen abre antes de que la voz entre
COLA = 1.6            # y se queda un momento despues del remate
CIERRE = 2.0          # con --cierre ("Continuará…"): cuanto dura ese letrero al final
# La voz por defecto es una PUBLICA de ElevenLabs, que existe en cualquier
# cuenta. Para contar historias en espanol conviene elegir una de la cuenta
# (tools/catalogo_voces.py) y pasarla con --voz <id>.
VOZ_POR_DEFECTO = dict(voz_off.VOCES_PUBLICAS)["Rachel"]

# En v3 la estabilidad tiene tres valores y 0.0 es el CREATIVO: mas emocion y
# mas riesgo de que una toma salga rara. En un reel que cuenta una historia eso
# es lo que se quiere -lo pidio el usuario: "mas storytelling, mas emocion"-;
# el 0.5 "natural" del modulo esta pensado para leer, no para contar.
CREATIVO = 0.0

# Cuanto se mueve la camara, en RITMO POR SEGUNDO -no en recorrido total-.
#
# El recorrido se reparte entre todos los cuadros de la escena, asi que un
# recorrido fijo se diluye en cuanto la escena se alarga: el 24% de antes se
# sentia en una escena de 8 s y en una de 16 s iba a la mitad de velocidad.
# Medido en un reel de 5 capitulos: escenas de 9 a 16 s daban de 1.2 a 2.0 %
# por segundo, y el usuario lo reporto como "casi no se siente".
RITMO = 0.075           # 7.5% del encuadre por segundo
RECORRIDO_MIN = 0.15    # aunque la escena sea cortisima, que se note que vive
RECORRIDO_MAX = 0.65    # mas que esto pixela con una imagen de ~1250 px de ancho
QUIETO = 0.06           # "quieto" no es 1.00: deja un aire fijo, sin moverse

# 🔴 El zoom NUNCA arranca en 1.00, y no es estetico: el paneo solo puede correrse
# por lo que el zoom recorta -el margen es (1 - 1/zoom)-, asi que con zoom 1.00 el
# margen es CERO y no hay paneo posible. Con esta base siempre hay por donde
# moverse desde el primer cuadro.
BASE = 0.12

# sentido: +1 se acerca, -1 abre, 0 el zoom se queda quieto y solo se panea.
# pan: de donde a donde se corre, en fraccion del margen (0 izquierda, 1 derecha).
MOVIMIENTOS = {
    "acercar": (1, (0.62, 0.38), "se acerca y se corre; para lo intimo"),
    "abrir": (-1, (0.38, 0.62), "abre y se corre; para lo que se revela"),
    "lateral": (0, (0.04, 0.96), "recorre la imagen de lado a lado"),
    "quieto": (0, (0.5, 0.5), "sin movimiento"),
    "acercar-arriba": (1, (0.62, 0.38), "se acerca a la CARA: para tomas de cuerpo entero"),
    "abrir-arriba": (-1, (0.38, 0.62), "abre desde la CARA: para tomas de cuerpo entero"),
}

# 🔴 Hacia donde apunta el zoom en vertical (0 = arriba, 0.5 = centro). Los
# movimientos de siempre apuntan al CENTRO, y con un objeto centrado eso es lo
# correcto. Con una persona de cuerpo entero el centro es el CINTURON: en un
# reel de personaje tres escenas acababan -o empezaban- con la cara cortada y
# el encuadre en el pantalon ("se ve raro, ya no se le ve la cara"). Las
# variantes "-arriba" apuntan al tercio superior, donde van las caras; las de
# siempre no cambian, para no alterar lo ya aprobado.
FOCO_VERTICAL = {"acercar-arriba": 0.25, "abrir-arriba": 0.25}


def recorrido(dur):
    """Cuanto encuadre se recorre en una escena de `dur` segundos."""
    return min(max(RITMO * dur, RECORRIDO_MIN), RECORRIDO_MAX)

# Con dos escenas, los movimientos van EN CONTRA por defecto: la primera
# encierra y la segunda libera. El contraste hace el punto sin que se note.
PAR_POR_DEFECTO = ("acercar", "abrir")

# Hasta 3 palabras y 18 caracteres por tarjeta: una tarjeta corta se lee de un
# vistazo; una frase larga obliga a leer mientras la voz ya va en otra parte.
MAX_PALABRAS, MAX_CHARS = 3, 18
# Tope DURO: MAX_CHARS se puede pasar un poco para no dejar palabras sueltas, pero esto
# no. Una tarjeta de 3 palabras y 23 caracteres se salia de la pantalla por los dos
# lados en un reel real: antes que una tarjeta que no cabe, una palabra sola.
DURO_CHARS = 20

# Ninguna escena baja de esto: una imagen que aparece menos de un segundo se
# lee como un parpadeo, no como una escena.
MIN_ESCENA = 1.0


# Una pausa parte la tarjeta solo si es larga de verdad: quien lee pausado hace
# silencios de medio segundo A MITAD de frase, y cortar ahi dejaba "Y de |
# repente llegaba" (medido con una voz grabada real).
PAUSA_QUE_PARTE = 1.0
FIN_DE_ORACION = re.compile(r"[.?!…]+[\"”»')]*$")


def _tramos(palabras):
    """Los pedazos que una tarjeta NUNCA puede cruzar.

    Un punto cierra siempre. Una coma o una pausa de mas de medio segundo
    cortan tambien, pero solo si de cada lado quedan al menos dos palabras: si
    no, se produce justo la palabra suelta que se esta evitando.
    """
    oraciones, actual = [], []
    for w in palabras:
        actual.append(w)
        if FIN_DE_ORACION.search(w["word"]):
            oraciones.append(actual)
            actual = []
    if actual:
        oraciones.append(actual)
    tramos = []
    for o in oraciones:
        inicio = 0
        for i in range(len(o) - 1):
            corte_suave = (o[i]["word"].endswith(",")
                           or o[i + 1]["start"] - o[i]["end"] > PAUSA_QUE_PARTE)
            if corte_suave and i + 1 - inicio >= 2 and len(o) - (i + 1) >= 2:
                tramos.append(o[inicio:i + 1])
                inicio = i + 1
        tramos.append(o[inicio:])
    return tramos


# Palabras de enlace: una tarjeta que TERMINA en una de estas se lee trunca
# ("Y de | repente llegaba", "en el | mostrador"), porque la idea sigue en la
# siguiente. Se evitan al elegir donde partir.
ENLACE = {"y", "e", "o", "u", "de", "del", "a", "al", "el", "la", "los", "las",
          "lo", "le", "les", "un", "una", "unos", "unas", "en", "que", "qué",
          "por", "para", "con", "sin", "se", "su", "sus", "mi", "tu", "no", "es",
          "muy", "como", "cuando", "ya", "me", "te", "nos", "pero", "porque"}


def _costo_tarjeta(tarjeta, ultima):
    texto = " ".join(w["word"] for w in tarjeta)
    costo = 1.0                                   # menos tarjetas, mejor
    if len(tarjeta) == 1:
        costo += 5                                # la palabra suelta
    fin = re.sub(r"[^\w]", "", tarjeta[-1]["word"].lower())
    if not ultima and fin in ENLACE:
        costo += 3                                # termina a medias
    exceso = len(texto) - MAX_CHARS
    if exceso > 0:
        costo += 1 if exceso <= 3 else 4          # un poco larga se tolera
    return costo


def _equilibrar(tramo):
    """Un tramo en tarjetas de hasta MAX_PALABRAS, eligiendo DONDE partir.

    De todas las formas de dividirlo se queda con la mas barata: sin palabras
    sueltas, sin tarjetas que terminen en "de", "el", "y"..., y con las menos
    tarjetas posibles. Pasarse un poco de caracteres cuesta menos que cualquiera
    de esos dos defectos.
    """
    n = len(tramo)
    if n <= 1:
        return [tramo] if tramo else []
    mejor = [0.0] + [float("inf")] * n            # mejor[i]: costo de las i primeras
    desde = [0] * (n + 1)
    for i in range(1, n + 1):
        for largo in range(1, min(MAX_PALABRAS, i) + 1):
            if largo > 1 and len(" ".join(w["word"] for w in tramo[i - largo:i])) > DURO_CHARS:
                continue
            c = mejor[i - largo] + _costo_tarjeta(tramo[i - largo:i], i == n)
            if c < mejor[i]:
                mejor[i], desde[i] = c, i - largo
    tarjetas, i = [], n
    while i > 0:
        tarjetas.append(tramo[desde[i]:i])
        i = desde[i]
    return tarjetas[::-1]


def agrupar(palabras):
    """Las palabras en tarjetas cortas que respetan las frases.

    🔴 Antes se llenaba cada tarjeta hasta 3 palabras sin mirar la oracion, y
    en un reel real de 94 tarjetas 13 cruzaban un punto ("dias. Y la") y 12
    quedaban de una sola palabra ("trabajo.", "nada."). El veredicto: "la frase
    se entiende mas de que empieza, y luego punto, y luego una palabra... no
    me gusta que se corte asi de feo". Ahora una tarjeta no
    cruza un punto, se parte en comas y pausas cuando tiene sentido, y reparte
    las palabras parejo.
    """
    grupos = []
    for tramo in _tramos(palabras):
        grupos.extend(_equilibrar(tramo))
    return grupos

def punto_de_giro(palabras, n_palabras_parte1):
    """Donde cambia la escena: en medio del silencio del giro.

    La frase viene partida ("A... | B"), y esa barra es la bisagra:
    tension y resolucion. El corte de imagen cae en la PAUSA entre las dos, no
    sobre una palabra, para que la frase gire tambien en pantalla.
    """
    if n_palabras_parte1 <= 0 or n_palabras_parte1 >= len(palabras):
        return None
    fin_a = palabras[n_palabras_parte1 - 1]["end"]
    ini_b = palabras[n_palabras_parte1]["start"]
    return round((fin_a + ini_b) / 2.0, 2)


def tarjeta(destino, texto, fuente_ttf, tam=90, y_centro=1210):
    """El texto como PNG con contorno.

    y_centro = 1210 de 1920, o sea un 63% de la altura: por encima del 20%
    inferior, que en Instagram y TikTok se comen los botones y el copy, y por
    debajo del sujeto, que suele estar arriba.
    """
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fnt = ImageFont.truetype(fuente_ttf, tam)
    caja = d.textbbox((0, 0), texto, font=fnt)
    # Si aun asi no cabe (una palabra muy larga), se achica la letra hasta que entre. Se mide
    # CON el contorno; se centra SIN el, como siempre, para no mover las tarjetas que ya caben.
    while (caja[2] - caja[0]) + 20 > W - 80 and tam > 40:
        tam -= 4
        fnt = ImageFont.truetype(fuente_ttf, tam)
        caja = d.textbbox((0, 0), texto, font=fnt)
    d.text(((W - (caja[2] - caja[0])) / 2, y_centro - tam * 0.65), texto, font=fnt,
           fill=(255, 255, 255, 255), stroke_width=10, stroke_fill=(0, 0, 0, 235))
    img.save(destino)


def ruta_fuente(estilo="frase"):
    receta = mod_letras.receta(estilo)
    ruta = mod_letras.fuentes_disponibles().get(receta.get("fuente"))
    if not ruta:
        raise RuntimeError(
            "Falta la fuente %s en este CapCut. Agregala una vez a mano y "
            "vuelve a correr." % receta.get("fuente"))
    return ruta


def _zoompan(movimiento, dur):
    sentido, panx, _desc = MOVIMIENTOS[movimiento]
    r = recorrido(dur)
    if movimiento == "quieto":
        desde = hasta = 1.0 + QUIETO
    elif sentido > 0:
        desde, hasta = 1.0 + BASE, 1.0 + BASE + r
    elif sentido < 0:
        desde, hasta = 1.0 + BASE + r, 1.0 + BASE
    else:
        # solo paneo: el zoom se queda alto y quieto, y todo el movimiento es el
        # recorrido de lado. Con el zoom bajo no habria margen que recorrer.
        desde = hasta = 1.0 + BASE + r * 0.6
    n = max(int(dur * FPS), 1)
    z = "%.4f%+.6f*on" % (desde, (hasta - desde) / float(n))
    x = "(iw-iw/zoom)*(%.4f%+.6f*on)" % (panx[0], (panx[1] - panx[0]) / n)
    foco = FOCO_VERTICAL.get(movimiento)
    y = "ih/2-(ih/zoom/2)" if foco is None else "(ih-ih/zoom)*%.2f" % foco
    # se escala al doble antes del zoom: si no, el acercamiento pixela
    return ("scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,"
            "zoompan=z='%s':x='%s':y='%s':d=1:s=%dx%d:fps=%d"
            % (z, x, y, W, H, FPS))


def _entrada_imagen(ruta, dur):
    """Una imagen fija como entrada de ffmpeg, a los FPS del reel.

    🔴 El `-framerate` va ANTES del `-loop` y no es opcional: sin el, ffmpeg lee
    la imagen a 25 fps y zoompan saca los cuadros a 30, asi que cada escena dura
    5/6 de lo pedido y la ultima se estira para rellenar el reel.

    Medido en un reel de 5 capitulos: los cortes caian en
    10.5 / 18.5 / 26.5 / 37.5 s cuando el plan decia 12.5 / 22.3 / 32.2 / 44.6
    -exactamente 5/6-, o sea que el cambio de imagen dejaba de caer en la pausa
    de la frase, que es justo lo que este formato cuida.
    """
    return ["-framerate", str(FPS), "-loop", "1", "-t", "%.3f" % dur, "-i", ruta]


def _clip_base(img, movimiento, dur, salida):
    """El clip de una escena para el proyecto de CapCut, CON su movimiento.

    🔴 Lleva el mismo zoompan que el MP4, y no es un adorno. Antes estos clips
    eran imagenes fijas y el movimiento lo ponia CapCut con su zoom "suave":
    de 1.00 a 1.05 en toda la escena e identico en las cinco, o sea 0.3-0.5% por
    segundo. Medido sobre el proyecto: escala 0.0%, corrimiento 0.0%.

    El usuario lo vio y dijo "no se siente que se mueva nada, casi se sienten
    igual todas", y tenia razon: el MP4 se movia y el PROYECTO no -y el proyecto es de
    donde sale lo que se publica, porque ahi se le pone la musica.
    """
    return (["ffmpeg", "-v", "error", "-y"] + _entrada_imagen(img, dur)
            + ["-vf", _zoompan(movimiento, dur), "-r", str(FPS),
               "-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", salida])


def tira_de_letras(carpeta, bloques, dur):
    """Las tarjetas de texto, en UN solo video con transparencia.

    🔴 Antes cada tarjeta entraba a ffmpeg como una imagen aparte con -loop, y
    con un reel largo eso son mas de cien decodificadores abiertos a la vez: un
    reel de 23 escenas reviento con "get_buffer() failed" aunque la maquina
    tenia 34 GB libres. Pegadas en una tira, el
    montaje pasa de ~125 entradas a 3.
    """
    vacio = os.path.join(carpeta, "c_vacio.png")
    if not os.path.exists(vacio):
        Image.new("RGBA", (W, H), (0, 0, 0, 0)).save(vacio)
    lista, t = [], 0.0
    for i, b in enumerate(bloques):
        if b["ini"] > t + 0.01:
            lista.append((vacio, b["ini"] - t))
        lista.append((os.path.join(carpeta, "c%02d.png" % i), b["fin"] - b["ini"]))
        t = b["fin"]
    if dur > t + 0.01:
        lista.append((vacio, dur - t))
    txt = os.path.join(carpeta, "letras.txt")
    with open(txt, "w", encoding="utf-8") as f:
        for ruta, d in lista:
            f.write("file '%s'\nduration %.3f\n" % (ruta.replace("\\", "/"), max(d, 0.04)))
        f.write("file '%s'\n" % lista[-1][0].replace("\\", "/"))
    salida = os.path.join(carpeta, "letras.mov")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
                    "-i", txt, "-vsync", "cfr", "-r", str(FPS),
                    "-c:v", "qtrle", "-pix_fmt", "argb", salida],
                   check=True, capture_output=True)
    return salida


def montar(carpeta, clips, bloques, voz_mp3, dur, salida):
    """El MP4 final: los clips de escena pegados, las letras encima y la voz.

    `clips` son los mismos archivos que se le entregan a CapCut, asi que el
    movimiento se calcula UNA vez. Antes se hacia dos: una para este MP4 y otra
    para los clips del proyecto.
    """
    lista = os.path.join(carpeta, "escenas.txt")
    with open(lista, "w", encoding="utf-8") as f:
        for c in clips:
            f.write("file '%s'\n" % c.replace("\\", "/"))
    letras = tira_de_letras(carpeta, bloques, dur)
    filtro = ("[0:v][1:v]overlay=0:0:shortest=0[v1];"
              "[v1]fade=t=out:st=%.2f:d=0.5[vout];"
              # apad: el audio dura lo mismo que el video. Sin eso acababa con la voz y
              # la imagen seguia 3.6 s mas (cola + "Continuara..."); varios reproductores
              # de Windows cierran el video cuando se acaba el audio, y quien lo reviso
              # no llego a ver el cierre.
              "[2:a]adelay=%d|%d,loudnorm=I=-14:TP=-1.5:LRA=11,apad[aout]"
              % (dur - 0.5, int(AIRE * 1000), int(AIRE * 1000)))
    cmd = ["ffmpeg", "-v", "error", "-y",
           "-f", "concat", "-safe", "0", "-i", lista,
           "-i", letras, "-i", voz_mp3,
           "-filter_complex", filtro, "-map", "[vout]", "-map", "[aout]",
           "-t", str(dur), "-r", str(FPS),
           "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", salida]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode:
        raise RuntimeError("ffmpeg fallo:\n" + (r.stderr or "")[-800:])
    return os.path.getsize(salida)


def repartir_escenas(palabras, partes_frase, dur, log=print):
    """Cuanto dura cada escena: un corte por giro de la frase.

    Devuelve una duracion por parte de la frase. El corte cae en la PAUSA entre
    una parte y la siguiente -no sobre una palabra-, y ninguna escena baja de
    MIN_ESCENA: una imagen que aparece menos de un segundo es un parpadeo.
    """
    limites, acumulado = [0.0], 0
    for i, parte in enumerate(partes_frase[:-1]):
        acumulado += len(parte.split())
        corte = punto_de_giro(palabras, acumulado)
        faltan = len(partes_frase) - 1 - i          # escenas despues de esta
        minimo = limites[-1] + MIN_ESCENA
        maximo = dur - MIN_ESCENA * faltan
        if corte is None or not (minimo <= corte <= maximo):
            corte = limites[-1] + (dur - limites[-1]) / (faltan + 1)
            log("  aviso: el giro %d no cae donde deberia; reparto ese tramo"
                % (i + 1))
        limites.append(round(min(max(corte, minimo), maximo), 2))
    limites.append(dur)
    if len(limites) > 2:
        log("  cortes de escena en %s (las pausas de la frase)"
            % ", ".join("%.2f s" % t for t in limites[1:-1]))
    return [round(limites[i + 1] - limites[i], 2)
            for i in range(len(limites) - 1)]


# Una etiqueta de actuacion de v3 ([serio], [con calma]): se escribe para la voz
# artificial y no se dice. Con una voz grabada no significa nada.
ETIQUETA = re.compile(r"\[[^\]]*\]")

# Por debajo de esto la grabacion no es de este guion: con otro texto el
# emparejamiento siempre "encuentra" algo, y de ahi salen cortes inventados.
MIN_COINCIDENCIA = 0.6


def _norma(palabra):
    """Una palabra lista para comparar: sin mayusculas, acentos ni signos."""
    sin_acento = "".join(c for c in unicodedata.normalize("NFD", palabra.lower())
                         if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]+", "", sin_acento)


def alinear_guion(guion, dichas):
    """Los tiempos de una voz GRABADA, pegados palabra por palabra al guion.

    `guion` son las palabras del texto (texto.split()) y `dichas` las de la
    transcripcion, con sus tiempos. Devuelve UNA palabra por palabra del guion,
    con el texto del guion: asi los subtitulos no heredan los errores de la
    transcripcion ("don Veto") y el conteo con el que se cortan las escenas
    sigue siendo el del guion.

    Quien lee cambia palabras, se salta alguna o agrega otra. Lo que coincide
    toma su tiempo; lo cambiado reparte el tramo de lo que se dijo en su lugar;
    lo que no se dijo queda pegado entre sus vecinas. Si casi nada coincide,
    la grabacion es de otro texto y se detiene en vez de inventar cortes.
    """
    if not guion:
        return []
    a = [_norma(w) for w in guion]
    utiles = [d for d in dichas if _norma(d["word"])]
    b = [_norma(d["word"]) for d in utiles]
    if not utiles:
        raise RuntimeError("La grabacion no trae palabras: no se oye nada o no "
                           "es una voz.")
    tiempos = [None] * len(guion)
    iguales = 0
    comparador = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for op, i1, i2, j1, j2 in comparador.get_opcodes():
        if op == "equal":
            iguales += i2 - i1
            for k in range(i2 - i1):
                d = utiles[j1 + k]
                tiempos[i1 + k] = (d["start"], d["end"])
        elif op == "replace":
            ini, fin = utiles[j1]["start"], utiles[j2 - 1]["end"]
            paso = (fin - ini) / float(i2 - i1)
            for k in range(i2 - i1):
                tiempos[i1 + k] = (ini + paso * k, ini + paso * (k + 1))
        # "insert": dijo algo que no esta en el guion; su tiempo ya queda
        # entre las vecinas. "delete": se rellena abajo.
    contables = sum(1 for x in a if x)
    if contables and iguales < MIN_COINCIDENCIA * contables:
        raise RuntimeError(
            "La grabacion no se parece al guion: coinciden %d de %d palabras. "
            "O es de otro texto, o se leyo una version distinta de la que se paso "
            "en --frase." % (iguales, contables))

    # lo que no se dijo: repartido en el hueco entre sus vecinas
    i = 0
    while i < len(tiempos):
        if tiempos[i] is not None:
            i += 1
            continue
        j = i
        while j < len(tiempos) and tiempos[j] is None:
            j += 1
        if i > 0:
            antes = tiempos[i - 1][1]
        elif j < len(tiempos):
            antes = tiempos[j][0]
        else:
            antes = 0.0
        despues = max(tiempos[j][0] if j < len(tiempos) else antes, antes)
        paso = (despues - antes) / float(j - i)
        for k in range(j - i):
            tiempos[i + k] = (antes + paso * k, antes + paso * (k + 1))
        i = j

    salida, ultimo = [], 0.0
    for w, (ini, fin) in zip(guion, tiempos):
        ini = max(ini, ultimo)                   # nunca hacia atras
        fin = max(fin, ini)
        salida.append({"word": w, "start": round(ini, 3), "end": round(fin, 3)})
        ultimo = ini
    return salida


def duracion_audio(ruta):
    """Lo que dura el archivo, medido: no se hereda de nadie."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", ruta], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise RuntimeError("No pude medir la duracion de %s: %s"
                           % (ruta, (r.stderr or "sin salida").strip()[:200]))


# Cuanto por debajo de la voz tipica empieza una pausa. Medido con dos voces:
# la artificial deja 18 de 18 cortes en pausa con 4, 6, 8 o 10 dB; una grabada
# con el telefono 28 con 4, 27 con 6, 12 con 8 y 0 con 10. Con 6 funcionan las
# dos.
PAUSA_BAJO_LA_VOZ = 6


def umbral_desde_rms(niveles, resta=PAUSA_BAJO_LA_VOZ):
    """El umbral de silencio para UNA grabacion: su voz tipica menos `resta` dB."""
    validos = sorted(v for v in niveles if v > -200)
    if not validos:
        return -30.0
    return round(validos[len(validos) // 2] - resta, 1)


def silencios(ruta, umbral_db=None, minimo=0.2):
    """Los silencios que de verdad tiene el audio: [(inicio, fin), ...].

    🔴 El umbral es RELATIVO a la voz de cada grabacion, no un numero fijo.
    Estuvo en -30 dB fijo y con la primera grabacion real encontro
    CERO pausas: la voz artificial deja silencio digital entre frases, pero una
    grabacion de celular tiene ruido de cuarto y sus pausas quedan ~20 dB bajo
    la voz, no a -30. Con ese umbral la revision habria avisado en cada corte.
    Y 0.2 s de minimo para no tomar como pausa el hueco entre dos silabas.
    """
    if umbral_db is None:
        r = subprocess.run(["ffmpeg", "-hide_banner", "-i", ruta, "-af",
                            "astats=metadata=1:reset=15,ametadata=print:"
                            "key=lavfi.astats.Overall.RMS_level",
                            "-f", "null", "-"], capture_output=True, text=True)
        niveles = [float(x) for x in re.findall(r"RMS_level=(-?[\d.]+)", r.stderr)]
        umbral_db = umbral_desde_rms(niveles)
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", ruta, "-af",
                        "silencedetect=noise=%sdB:d=%s" % (umbral_db, minimo),
                        "-f", "null", "-"], capture_output=True, text=True)
    inicios = [float(x) for x in re.findall(r"silence_start: ([\d.]+)", r.stderr)]
    finales = [float(x) for x in re.findall(r"silence_end: ([\d.]+)", r.stderr)]
    return list(zip(inicios, finales))


def cortes_sobre_voz(cortes, huecos):
    """Que cortes de escena caen donde se esta hablando: [(n, segundo), ...].

    El corte tiene que caer en una pausa. Se revisa contra los silencios que se
    MIDEN en el audio, no contra los tiempos de ninguna transcripcion ni de la
    voz artificial.

    🔑 Por que es una revision y no una correccion: se intento pegar
    los cortes a los silencios porque, comparados contra los tiempos que
    reporta ElevenLabs, 15 de 18 parecian caer sobre la siguiente frase. Medido
    contra el AUDIO, los 18 ya estaban en silencio: los tiempos de ElevenLabs
    marcan cada palabra un poco ANTES de que se oiga. La alarma venia de la
    referencia, no del corte. Se corrige el dia que una grabacion real lo pida.
    """
    return [(n, c) for n, c in enumerate(cortes, 1)
            if not any(si <= c <= sf for si, sf in huecos)]


# Cuanto por debajo de la voz tipica tiene que estar el audio JUSTO en el corte
# para que cuente como pausa. Medido con una voz grabada real: los cortes entre
# palabras quedan de 18 a mas de 60 dB bajo la voz; uno a media frase, a 0.1 dB.
CORTE_BAJO_LA_VOZ = 12


def voz_tipica(ruta):
    """El nivel tipico (mediana del RMS, en dB) de la voz de una grabacion."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-i", ruta, "-af",
                        "astats=metadata=1:reset=15,ametadata=print:"
                        "key=lavfi.astats.Overall.RMS_level",
                        "-f", "null", "-"], capture_output=True, text=True)
    validos = sorted(v for v in (float(x) for x in re.findall(r"RMS_level=(-?[\d.]+)", r.stderr))
                     if v > -200)
    return validos[len(validos) // 2] if validos else -30.0


def nivel_en(ruta, t, ventana=0.08):
    """El RMS en dB de `ventana` segundos centrados en `t` (-200 si es silencio digital)."""
    r = subprocess.run(["ffmpeg", "-hide_banner", "-ss", "%.3f" % max(t - ventana / 2, 0),
                        "-t", "%.3f" % ventana, "-i", ruta, "-af", "astats=metadata=0",
                        "-f", "null", "-"], capture_output=True, text=True)
    v = re.findall(r"RMS level dB: (-?[\d.]+|-inf)", r.stderr)
    return float(v[-1]) if v and v[-1] != "-inf" else -200.0


def cortes_en_voz(ruta, cortes):
    """Los cortes que de verdad caen mientras se habla: [(n, segundo), ...].

    🔑 Dos pasadas. Primero, contra los silencios de 0.2 s o mas. Lo que
    no cae en uno se MIDE en el punto exacto del corte: si el audio esta
    CORTE_BAJO_LA_VOZ dB bajo la voz, es una pausa corta y no se avisa.
    Por que: hay quien lee con pausas de 0.1 s entre frases, mas cortas que el
    minimo de `silencios`, y el aviso salio en 5 de 16 cortes de los
    que 4 caian en silencio real. Una alarma que sale en cada episodio se
    aprende a ignorar.
    """
    candidatos = cortes_sobre_voz(cortes, silencios(ruta))
    if not candidatos:
        return []
    tope = voz_tipica(ruta) - CORTE_BAJO_LA_VOZ
    return [(n, c) for n, c in candidatos if nivel_en(ruta, c) > tope]


def recortar_bloques(bloques, limites):
    """Que ningun subtitulo se quede en pantalla despues del corte de escena.

    Un subtitulo dura hasta que empieza la siguiente palabra. Con pausas largas
    entre escenas eso dejaba la ultima frase de una escena encima de la imagen
    siguiente. Si su voz ya acabo antes del corte, se cierra
    en el corte. Quita la marca interna "voz_fin".
    """
    for b in bloques:
        voz_fin = b.pop("voz_fin", None)
        if voz_fin is None:
            continue
        for lim in limites:
            if b["ini"] < lim < b["fin"] and voz_fin <= lim + 0.05:
                b["fin"] = lim
                break
    return bloques


def acomodar_cortes(ruta, cortes, radio=0.25, paso=0.025):
    """Mueve al punto mas callado (a +-radio s) cada corte que cae sobre voz.

    🔑 Con voz grabada, los cortes se ubican con los tiempos de la
    transcripcion, que se desfasan 50-200 ms del audio real; en un reel real 4
    de 15 caian con la voz sonando (-1 a -8 dB) y el punto callado estaba a
    50-200 ms. No es la correccion a ciegas que se descarto (ver
    `cortes_sobre_voz`): aqui se MIDE el audio en cada
    candidato y solo se mueve lo que de verdad suena, sin cruzar a otro corte.
    """
    tope = voz_tipica(ruta) - CORTE_BAJO_LA_VOZ
    nuevos = []
    for i, c in enumerate(cortes):
        if nivel_en(ruta, c) <= tope:
            nuevos.append(c)
            continue
        antes = nuevos[-1] + MIN_ESCENA if nuevos else MIN_ESCENA
        despues = cortes[i + 1] - MIN_ESCENA if i + 1 < len(cortes) else float("inf")
        pasos = int(round(radio / paso))
        candidatos = [round(c + k * paso, 3) for k in range(-pasos, pasos + 1)]
        candidatos = [x for x in candidatos if antes <= x <= despues]
        mejor = min(candidatos, key=lambda x: nivel_en(ruta, x)) if candidatos else c
        nuevos.append(mejor if nivel_en(ruta, mejor) <= tope else c)
    return nuevos


def voz_grabada(audio, texto, carpeta, log=print):
    """La voz de una persona en vez de la artificial: {"palabras", "duracion"}."""
    if not os.path.exists(audio):
        raise RuntimeError("No encuentro la grabacion: %s" % audio)
    destino = os.path.join(carpeta, "voz.mp3")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", audio, "-vn",
                    "-c:a", "libmp3lame", "-q:a", "2", destino],
                   check=True, capture_output=True)
    # La cache lleva la HUELLA del audio: si se regraba con el mismo nombre de
    # proyecto, la ruta es la misma y sin huella volveria la transcripcion vieja.
    with open(destino, "rb") as f:
        huella = hashlib.sha1(f.read()).hexdigest()[:12]
    dichas = mod_transcribe.transcribe(
        destino, cache_path=os.path.join(carpeta, "transcripcion_%s.json" % huella))
    palabras = alinear_guion(texto.split(), dichas["words"])
    log("  voz grabada: %d palabras del guion alineadas con %d dichas"
        % (len(palabras), len(dichas["words"])))
    return {"palabras": palabras, "duracion": duracion_audio(destino)}


def estabilidad_para(modelo, tono=None):
    """La estabilidad que se le manda a ElevenLabs.

    🔴 Antes el tono "creativo" (0.0) se mandaba TAMBIEN al multilingue. En v3
    0.0 es el modo creativo; en el multilingue es el ajuste MAS variable que
    existe. Se oyo en una serie hecha con el multilingue -"varia mucho la
    emocion, a veces las palabras no se sienten"- y la causa era esa.
    Sin tono pedido: v3 va creativo y el multilingue con su 0.5 de siempre.
    """
    tonos = {"creativo": CREATIVO, "natural": 0.5, "robusto": 1.0}
    if tono:
        return tonos[tono]
    return CREATIVO if modelo == voz_off.MODELO_EXPRESIVO else voz_off.ESTABILIDAD


def hacer(imagenes, frase, nombre, movimientos=None, voz=VOZ_POR_DEFECTO,
          modelo=voz_off.MODELO_EXPRESIVO, estabilidad=CREATIVO, audio=None,
          cierre=None, log=print):
    """De una o dos imagenes y una frase, a un MP4 y a un proyecto de CapCut."""
    if isinstance(imagenes, str):
        imagenes = [imagenes]
    for img in imagenes:
        if not os.path.exists(img):
            raise RuntimeError("No encuentro la imagen: %s" % img)
    movimientos = list(movimientos or ())
    if not movimientos:
        movimientos = (["acercar"] if len(imagenes) == 1 else
                       [PAR_POR_DEFECTO[i % 2] for i in range(len(imagenes))])
    if len(movimientos) < len(imagenes):
        movimientos += [movimientos[-1]] * (len(imagenes) - len(movimientos))
    for m in movimientos:
        if m not in MOVIMIENTOS:
            raise RuntimeError("Movimiento desconocido: %s (hay: %s)"
                               % (m, ", ".join(MOVIMIENTOS)))

    # el | marca donde se parte la frase; la voz la lee entera
    if audio:
        frase = ETIQUETA.sub("", frase)
    partes_frase = [p.strip() for p in frase.split("|")]
    texto = " ".join(partes_frase)
    if len(imagenes) > 1 and len(partes_frase) != len(imagenes):
        raise RuntimeError(
            "Van %d imagenes y la frase trae %d partes separadas por '|'. "
            "Cada imagen necesita la suya: el corte de escena cae en la pausa "
            "entre una parte y la siguiente."
            % (len(imagenes), len(partes_frase)))
    aviso = voz_off.revisar_acentos(texto)
    if aviso:
        log(aviso)

    carpeta = os.path.join(nucleo.TRABAJO, "_" + nombre)
    os.makedirs(carpeta, exist_ok=True)
    # 🔴 Por defecto el EXPRESIVO (v3), no el multilingue. Con el multilingue la
    # voz recita -"se oye sin sabor, todo asi, sin intensidad", fue el
    # veredicto de los primeros reels-. Son historias; la voz tiene que
    # contar, no leer.
    if audio:
        hablado = voz_grabada(audio, texto, carpeta, log)
    else:
        hablado = voz_off.sintetizar(texto, voz, os.path.join(carpeta, "voz.mp3"),
                                     modelo=modelo, estabilidad=estabilidad,
                                     log=lambda *a: None)
    palabras = [{"word": p["word"], "start": round(p["start"] + AIRE, 3),
                 "end": round(p["end"] + AIRE, 3)} for p in hablado["palabras"]]
    # Con --cierre, el letrero entra casi en cuanto acaba la voz (0.6 s): antes eran 1.6 s
    # de nada y luego 2 s de letrero, y ese segundo de mas dejaba un episodio fuera de
    # los 90 s de Facebook.
    dur = round(hablado["duracion"] + AIRE + (0.6 + CIERRE if cierre else COLA), 2)

    fuente = ruta_fuente()
    grupos = agrupar(palabras)
    bloques = []
    for i, g in enumerate(grupos):
        t = " ".join(x["word"] for x in g).strip()
        ini = max(g[0]["start"] - 0.12, 0)
        fin = (grupos[i + 1][0]["start"] - 0.12 if i + 1 < len(grupos)
               else min(dur, g[-1]["end"] + 0.9))
        tarjeta(os.path.join(carpeta, "c%02d.png" % i), t, fuente)
        bloques.append({"ini": round(ini, 2), "fin": round(fin, 2), "texto": t,
                        "voz_fin": g[-1]["end"]})
    if cierre:
        # "Continuará…": un letrero sin voz sobre la ultima escena, en los
        # ultimos CIERRE segundos: que se sepa que es una serie sin decir "esa es
        # la parte 2" con la voz. Va a la altura de los subtitulos (ya no hay
        # ninguno): al centro le tapaba la cara al personaje.
        tarjeta(os.path.join(carpeta, "c%02d.png" % len(bloques)), cierre, fuente, tam=110)
        ini = max(bloques[-1]["fin"] if bloques else 0, dur - CIERRE)
        bloques.append({"ini": round(ini, 2), "fin": dur, "texto": cierre})

    if len(imagenes) > 1:
        duraciones = repartir_escenas(palabras, partes_frase, dur, log)
        if audio:
            # los cortes van corridos AIRE respecto al audio original
            cortes, t_acum = [], 0.0
            for d in duraciones[:-1]:
                t_acum += d
                cortes.append(round(t_acum - AIRE, 2))
            ruta_voz = os.path.join(carpeta, "voz.mp3")
            acomodados = acomodar_cortes(ruta_voz, cortes)
            movidos = sum(1 for x, y in zip(cortes, acomodados) if x != y)
            if movidos:
                limites = [0.0] + [round(c + AIRE, 2) for c in acomodados] + [dur]
                duraciones = [round(limites[i + 1] - limites[i], 2)
                              for i in range(len(limites) - 1)]
                log("  %d cortes movidos al punto callado mas cercano (medido)" % movidos)
                cortes = acomodados
            malos = cortes_en_voz(ruta_voz, cortes)
            if not malos:
                log("  los %d cortes caen en pausas de la grabacion (medido)"
                    % len(cortes))
            else:
                # una linea, no una por corte: con un guion repartido por tiempo
                # la mitad de los cortes cae a media frase y el aviso repetido se
                # vuelve paisaje.
                log("  aviso: %d de %d cortes caen mientras se habla (%s). Si el "
                    "guion se repartio por tiempo es lo esperado; si no, revisalos."
                    % (len(malos), len(cortes),
                       ", ".join("%d" % n for n, _ in malos[:8])
                       + (", ..." if len(malos) > 8 else "")))
        escenas = [(imagenes[i], movimientos[i], duraciones[i])
                   for i in range(len(imagenes))]
    else:
        escenas = [(imagenes[0], movimientos[0], dur)]
    limites, t_acum = [], 0.0
    for _, _, d in escenas[:-1]:
        t_acum += d
        limites.append(round(t_acum, 2))
    recortar_bloques(bloques, limites)

    # los clips primero: son los del proyecto de CapCut Y con los que se arma el MP4
    clips = []
    for i, (img, mov, d) in enumerate(escenas):
        base = os.path.join(carpeta, "base%d.mp4" % i)
        subprocess.run(_clip_base(img, mov, d, base), check=True, capture_output=True)
        clips.append(base)

    mp4 = os.path.join(carpeta, nombre + ".mp4")
    peso = montar(carpeta, clips, bloques, os.path.join(carpeta, "voz.mp3"), dur, mp4)
    log("  %-22s %.1f s | %d tarjetas | %d escena(s) | %s | %.1f MB"
        % (nombre, dur, len(bloques), len(escenas), "+".join(movimientos), peso / 1e6))

    # y el mismo reel como proyecto editable: los MISMOS clips del MP4
    segmentos = [{"path": c, "ini": 0.0, "fin": escenas[i][2], "volumen": 0.0}
                 for i, c in enumerate(clips)]
    # WAV y no MP3: el proyecto de CapCut toma la duracion del archivo, y de un MP3 de
    # bitrate variable la leyo 1.2 s CORTA (81.03 contra 82.23 reales): CapCut cortaba el
    # final de la voz -"apenas empezaba"- en un reel real. De un WAV no hay error.
    voz_aire = os.path.join(carpeta, "voz_con_aire.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(carpeta, "voz.mp3"),
                    "-af", "adelay=%d|%d" % (int(AIRE * 1000), int(AIRE * 1000)),
                    "-c:a", "pcm_s16le", voz_aire],
                   check=True, capture_output=True)
    plan = {"segmentos": segmentos,
            "voz": {"archivo": voz_aire, "volumen": 1.0, "fade_out": 0},
            "palabras": palabras, "bloques_texto": bloques, "letras": "frase",
            "resumen": {"tipo": "guion", "escenas": len(bloques),
                        "duracion_final": dur, "clips": len(segmentos)}}
    ruta_plan = os.path.join(carpeta, "plan.json")
    json.dump(plan, open(ruta_plan, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    # zoom="no": el movimiento ya viene en los clips. Pedirle ademas el suyo
    # encimaria dos zooms sobre la misma imagen.
    nucleo.editar_con_plan(ruta_plan, nombre, captions="clasico", zoom="no",
                           log=lambda *a: None)
    return {"mp4": mp4, "carpeta": carpeta, "duracion": dur, "tarjetas": len(bloques),
            "escenas": len(escenas)}


def main():
    ap = argparse.ArgumentParser(description="Reel de una frase sobre una imagen")
    ap.add_argument("--imagen", required=True, action="append",
                    help="la imagen; repetir para una segunda escena")
    ap.add_argument("--frase", required=True,
                    help="la frase; con | se marca donde se parte")
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--movimiento", action="append", choices=list(MOVIMIENTOS),
                    help="uno por escena; por defecto acercar+abrir")
    ap.add_argument("--voz", default="Rachel",
                    help="nombre de una voz publica (Rachel, Adam...) o el id de "
                         "una voz de tu cuenta (python tools/voz.py las lista)")
    ap.add_argument("--modelo", default="expresivo", choices=["expresivo", "multilingue"],
                    help="expresivo = eleven_v3 (por defecto, cuenta historias); "
                         "multilingue = eleven_multilingual_v2 (recita, mas estable)")
    ap.add_argument("--tono", choices=["creativo", "natural", "robusto"],
                    help="cuanta emocion se le permite a la voz: sin esto, v3 va "
                         "creativo (0.0) y el multilingue con su 0.5")
    ap.add_argument("--cierre",
                    help='un letrero sin voz al final, p. ej. "Continuará…"')
    ap.add_argument("--audio",
                    help="una voz GRABADA (mp3, wav, m4a...) en vez de la artificial: "
                         "los subtitulos salen del guion y los tiempos, de la grabacion")
    args = ap.parse_args()
    try:
        modelo = (voz_off.MODELO_EXPRESIVO if args.modelo == "expresivo"
                  else voz_off.MODELO)
        publicas = dict((n.lower(), v) for n, v in voz_off.VOCES_PUBLICAS)
        voz = publicas.get(args.voz.lower(), args.voz)
        r = hacer(args.imagen, args.frase, args.nombre, args.movimiento, voz,
                  modelo=modelo, estabilidad=estabilidad_para(modelo, args.tono),
                  audio=args.audio, cierre=args.cierre)
    except (RuntimeError, ValueError) as e:
        sys.exit("ERROR: %s" % e)
    print("")
    print("MP4:     %s" % r["mp4"])
    print("CapCut:  proyecto '%s' (falta ponerle musica)" % args.nombre)


if __name__ == "__main__":
    main()
