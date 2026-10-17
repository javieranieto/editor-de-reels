"""Lo que hace falta saber de CapCut en esta computadora, y poco mas.

Antes esto vivia dentro de `capcut.py`, un escritor artesanal del formato de
draft que se abandono al adoptar pycapcut. Aquel modulo quedo 509 lineas de
codigo muerto del que solo se usaban estas cuatro cosas; se borro y se quedo
en el historial de git por si alguna vez hace falta consultar el formato.
"""
import os
import subprocess
import sys

RAIZ = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
US = 1_000_000          # CapCut mide el tiempo en microsegundos


def consola_utf8():
    """Deja que la consola imprima nombres con acentos sin reventar.

    La consola de Windows sigue en cp1252 y los nombres del pack de recursos
    traen acentos, algunos combinados (MUSICA con U+0301). Al imprimirlos, la
    herramienta muere con UnicodeEncodeError a media lista: paso de verdad con
    tools/musica.py --proponer, que dejo una candidata escrita y se cayo antes
    de las otras dos. No es cosmetico: corta la salida justo donde el usuario
    tenia que elegir.
    """
    for flujo in (sys.stdout, sys.stderr):
        try:
            flujo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass    # consola que no lo admite: mejor seguir que abortar


def _capcut_abierto():
    """True si CapCut esta corriendo.

    Generar con CapCut abierto pierde el proyecto: lo mantiene en memoria y
    reescribe su indice al cerrar. Es regla dura del proyecto y todo camino
    nuevo tiene que respetarla.
    """
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout.lower()
        return "capcut.exe" in out
    except Exception:
        return False


def _agrupar_subtitulos(words, max_chars=38, max_dur=2.2, max_gap=0.6):
    """Agrupa palabras en lineas de subtitulo legibles."""
    lineas, actual = [], []
    for w in words:
        if actual:
            texto = " ".join(x["word"] for x in actual)
            largo = len(texto) + 1 + len(w["word"]) > max_chars
            duracion = w["end"] - actual[0]["start"] > max_dur
            hueco = w["start"] - actual[-1]["end"] > max_gap
            if largo or duracion or hueco:
                lineas.append(actual)
                actual = []
        actual.append(w)
    if actual:
        lineas.append(actual)
    return lineas
