"""El segundo tipo de reel: de un guion escrito a un proyecto de CapCut.

No se graba nada. Se entrega el texto, lo lee una voz sintetica y cada escena
se ilustra con stock. La salida es un `plan.json` normal, asi que de ahi en
adelante **todo lo que ya existe funciona igual**: captions, cifras en
pantalla, musica pegada al beat, sonidos, efectos y exportar a la editora.

Ese fue el hallazgo al revisar las cinco herramientas parecidas (ver
`IDEAS.md`): el 70% ya estaba construido y lo que faltaba era la voz y elegir
la imagen. Y las cinco entregan un MP4 cerrado, que es justo lo que aqui no se
quiere.

Dos cosas robadas de ellas:

- **Verificar que el stock corresponda** a la escena, no conformarse con que la
  busqueda devuelva algo (OpenReels, umbral 0.6).
- **Partir cada escena en dos clips** cuando da tiempo: el plano fijo largo es
  lo que delata al video automatico (AutoShorts).
"""
import os
import re

from . import voz_off

# Una escena de menos de esto no da tiempo a leer la imagen; de mas, aburre.
ESCENA_MIN = 1.6
ESCENA_PARTIBLE = 4.0      # a partir de aqui se parte en dos clips distintos

# Palabras que no sirven para buscar imagenes: son las que unen la frase, no
# las que la ilustran.
VACIAS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al",
    "a", "en", "y", "o", "que", "con", "por", "para", "su", "sus", "mi", "mis",
    "lo", "le", "les", "se", "es", "son", "fue", "era", "ser", "estar", "esta",
    "este", "esto", "esa", "ese", "eso", "como", "mas", "pero", "si", "no",
    "ya", "muy", "todo", "toda", "todos", "todas", "hay", "he", "ha", "han",
    "me", "te", "nos", "tu", "yo", "cuando", "donde", "porque", "asi", "sin",
    "sobre", "entre", "hasta", "desde", "cada", "otro", "otra", "solo",
}


# Terminaciones de verbo conjugado. Ordenar por longitud premiaba justamente a
# los verbos, que en espanol son largos ("preguntaban", "cerraba") y no tienen
# imagen: el stock se indexa por cosa, no por accion conjugada.
VERBALES = ("aban", "ando", "iendo", "aron", "ieron", "abas", "aba", "ias",
            "amos", "emos", "imos", "aste", "iste", "eron", "aran", "eran",
            "enes", "ienes", "aria", "eria")


def consulta_de(texto, maximo=3):
    """Las palabras con las que buscar la imagen de una escena.

    Heuristica de respaldo. **Lo bueno es que las elija Claude al revisar**:
    saber que se ve en pantalla cuando alguien dice "el numero mas barato que
    tienes" es criterio, no conteo de letras. El plan admite `"consulta"` por
    escena y eso manda sobre esto.

    Buscar la frase entera devuelve cualquier cosa: los buscadores de stock
    indexan por concepto, no por oracion.
    """
    limpio = re.sub(r"[^\wáéíóúñü ]+", " ", (texto or "").lower())
    palabras = [p for p in limpio.split()
                if p not in VACIAS and len(p) > 3 and not p.isdigit()
                and not p.endswith(VERBALES)]
    palabras.sort(key=len, reverse=True)
    vistas, fuera = set(), []
    for p in palabras:
        if p[:5] not in vistas:
            vistas.add(p[:5])
            fuera.append(p)
        if len(fuera) >= maximo:
            break
    return " ".join(fuera)


# Anotacion de escena: [electrician at work]. Va DENTRO del texto, donde
# termina la escena que ilustra, y no se locuta.
MARCA = re.compile(r"[ \t]*\[([^\]\n]{2,60})\][ \t]*")


def extraer_consultas(texto):
    """Saca las anotaciones [consulta] del guion.

    Devuelve (texto_limpio, [(posicion_en_el_limpio, consulta)]). El texto
    limpio es el que se locuta: la anotacion nunca llega al TTS.

    Existe porque `consulta_de()` -el respaldo automatico- saca las palabras
    del propio guion, y los guiones estan en espanol mientras los catalogos de
    stock estan etiquetados en INGLES. Medido: un guion en espanol produjo 11
    consultas hechas con palabras del propio texto y ninguna encontro nada,
    con el mismo catalogo donde una consulta corta en ingles ("electrician at
    work") acierta a la primera. Traducir automaticamente seria adivinar;
    la consulta es criterio editorial y se escribe.
    """
    piezas, marcas, cursor = [], [], 0
    salto = chr(10)
    for m in MARCA.finditer(texto or ""):
        piezas.append(texto[cursor:m.start()])
        marcas.append((sum(len(t) for t in piezas), m.group(1).strip()))
        # la anotacion se come sus espacios, pero no puede pegar dos frases
        siguiente = texto[m.end():m.end() + 1]
        if piezas and piezas[-1][-1:] not in ("", salto) and siguiente not in ("", salto):
            piezas.append(" ")
        cursor = m.end()
    piezas.append(texto[cursor:])
    return "".join(piezas), marcas


def asignar_consultas(limpio, lista_escenas, marcas):
    """Le da a cada escena la consulta anotada dentro de ella, si la hay."""
    if not marcas:
        return lista_escenas
    cursor = 0
    for e in lista_escenas:
        i = limpio.find(e["texto"], cursor)
        if i < 0:
            i = cursor
        fin = i + len(e["texto"])
        for pos, consulta in marcas:
            if i <= pos <= fin + 1:
                e["consulta"] = consulta
                break
        cursor = fin
    return lista_escenas


def guion_a_plan(texto, carpeta, voz_id, clave_voz=None, buscar=None,
                 log=print):
    """Construye el plan completo. `buscar(consulta, segundos)` -> ruta o None.

    Se inyecta la busqueda en vez de llamarla aqui para poder armar el plan
    sin red (y probarlo), y para poder cambiar de fuente de stock sin tocar
    esta funcion.
    """
    os.makedirs(carpeta, exist_ok=True)
    texto, marcas = extraer_consultas(texto)
    audio = os.path.join(carpeta, "voz.mp3")
    hablado = voz_off.sintetizar(texto, voz_id, audio, clave=clave_voz, log=log)

    lista = asignar_consultas(texto, voz_off.escenas(texto), marcas)
    if marcas:
        log("  %d escena(s) con consulta anotada" % len(marcas))
    con_tiempo = voz_off.tiempos_de_escenas(lista, hablado["palabras"])
    log("  %d escenas en %.1f s" % (len(con_tiempo), hablado["duracion"]))

    segmentos, sin_imagen = [], 0
    for k, e in enumerate(con_tiempo):
        # Una escena dura hasta que EMPIEZA la siguiente, no hasta que termina
        # su ultima palabra: entre frase y frase la voz calla medio segundo, y
        # esas pausas suman. Medido en el primer reel real: 6.45 s perdidos en
        # 14 escenas, o sea que el video acababa casi 6 s antes que el audio y
        # la ultima frase -el remate- se quedaba sin imagen. La ultima escena
        # se estira hasta el final del audio por la misma razon.
        siguiente = (con_tiempo[k + 1]["ini"] if k + 1 < len(con_tiempo)
                     else hablado["duracion"])
        dur = max(siguiente, e["fin"]) - e["ini"]
        if dur < ESCENA_MIN:
            dur = ESCENA_MIN
        # la consulta del plan manda: es criterio, no conteo de letras
        consulta = e.get("consulta") or consulta_de(e["texto"])
        # partir la escena larga en dos clips: el plano fijo de 8 segundos es
        # lo que delata al video automatico
        trozos = 2 if dur >= ESCENA_PARTIBLE else 1
        for k in range(trozos):
            ruta = buscar(consulta, dur / trozos) if buscar else None
            if not ruta:
                sin_imagen += 1
                continue
            segmentos.append({
                "path": ruta,
                "ini": 0.0,
                "fin": round(dur / trozos, 3),
                "volumen": 0.0,      # el stock va mudo: manda la voz
                "escena": e["texto"][:60],
                "consulta": consulta,
            })
    if sin_imagen:
        log("  aviso: %d escena(s) sin imagen; se saltan" % sin_imagen)
    if not segmentos:
        raise RuntimeError(
            "Ninguna escena consiguio imagen.\n"
            "Lo mas probable: el guion esta en espanol y los catalogos de "
            "stock estan\netiquetados en INGLES, asi que las consultas "
            "automaticas no encuentran nada.\nAnota la consulta de cada "
            "escena en el propio guion, entre corchetes:\n\n"
            "  El tablero se calentaba cada tarde. [electrical panel]\n\n"
            "Tambien puede ser que la clave de stock falle, o que el guion sea "
            "tan\nabstracto que no haya nada que fotografiar.")

    return {
        "segmentos": segmentos,
        "voz": {"archivo": audio, "volumen": 1.0, "fade_out": 0},
        "palabras": hablado["palabras"],
        "escenas": con_tiempo,
        "resumen": {"tipo": "guion", "escenas": len(con_tiempo),
                    "duracion_final": hablado["duracion"],
                    "clips": len(segmentos)},
    }
