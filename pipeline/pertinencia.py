"""Decide si un video de stock ILUSTRA la escena, o solo salio en la busqueda.

El buscador de stock nunca dice "no tengo": siempre devuelve algo. Medido
contra Pexels con las consultas de un guion historico:

    gallows dawn   -> "a pond with trees and water in the background"
    irish flag     -> "flag of france"
    old map mexico -> "close up of a ball shaped globe"
    cannon smoke   -> "smoke billowing from a chimney"

Las cuatro son resultados validos de la busqueda y ninguna ilustra la escena.
Conformarse con que la busqueda devuelva algo es lo que produce el video que se
ve automatico. Con las consultas cortas y literales de otro guion acerto 11 de 11:
el problema no es el proveedor, es que hay que mirar QUE devolvio.

La idea (umbral 0.6) viene de OpenReels, ver `IDEAS.md`. Aqui se puntua contra
el texto que el proveedor pone en el titulo, el slug o las etiquetas.
"""
import re

UMBRAL = 0.6

# Palabras de la consulta que no dicen de que es la imagen. Se descartan antes
# de puntuar: si no, "old library books" aprueba con solo traer "old".
VACIAS_EN = {
    "a", "an", "the", "of", "in", "on", "at", "with", "and", "or", "for",
    "to", "from", "by", "up", "close", "shot", "video", "footage", "scene",
    "background", "view",
}

MIN_RAIZ = 4        # letras que deben coincidir para dar dos palabras por iguales


def _palabras(texto):
    return [p for p in re.findall(r"[a-z0-9]+", (texto or "").lower()) if p]


def _misma(a, b):
    """Empareja singular con plural y familias cortas: player/players, war/wars."""
    if a == b:
        return True
    corta, larga = (a, b) if len(a) <= len(b) else (b, a)
    return len(corta) >= MIN_RAIZ and larga.startswith(corta)


def terminos(consulta):
    """Las palabras de la consulta que de verdad piden algo en pantalla."""
    return [p for p in _palabras(consulta) if p not in VACIAS_EN]


def puntuar(consulta, descripcion):
    """0.0 a 1.0: que parte de lo pedido aparece en lo que devolvio el stock."""
    pedidas = terminos(consulta)
    if not pedidas:
        return 0.0
    hay = _palabras(descripcion)
    aciertos = sum(1 for p in pedidas if any(_misma(p, h) for h in hay))
    return aciertos / float(len(pedidas))


def sirve(consulta, descripcion, umbral=UMBRAL):
    return puntuar(consulta, descripcion) >= umbral


def mejor(consulta, candidatos, umbral=UMBRAL):
    """El candidato que mejor ilustra la consulta, o None si ninguno llega.

    Devolver None es el punto de todo esto: vale mas una escena sin imagen
    -que se ve y se arregla- que una imagen que no viene al caso, que se cuela
    y solo la nota quien vea el reel publicado.
    """
    calificados = []
    for c in candidatos or []:
        p = puntuar(consulta, c.get("descripcion", ""))
        if p >= umbral:
            calificados.append((p, c))
    if not calificados:
        return None
    calificados.sort(key=lambda par: par[0], reverse=True)
    return calificados[0][1]
