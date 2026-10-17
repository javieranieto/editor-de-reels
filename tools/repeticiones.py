# -*- coding: utf-8 -*-
"""Arranques falsos DENTRO de un bloque, que `tomas.py` no puede ver.

`tomas.detectar()` compara frases VECINAS, y una frase es lo que hay entre dos
pausas de 0.7 s. En un video largo hablado sin respirar eso falla: un bloque
de 148 s con una sola pausa de 0.25 s es, para el, "una frase", y no hay
vecina con la que comparar.

Aqui se busca lo otro: una secuencia de palabras que se repite casi igual unos
segundos despues. Es la firma de "empece a decir algo, me trabe, y lo volvi a
empezar". La regla del usuario es quedarse con la SEGUNDA, que suele ser la
buena.

    python tools/repeticiones.py "<proyecto>"              # sobre el original
    python tools/repeticiones.py "<proyecto>" --plan       # lo que aun queda
                                                           # despues de cortar

No corrige nada: propone. Que se quita es criterio, y hay repeticiones que son
a proposito -"se cambio el contacto, se cambio el apagador" es una
enumeracion, no un tropiezo-.
"""
import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import tomas
from pipeline.entorno import consola_utf8

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

VENTANA = 6        # palabras que tienen que coincidir para llamarlo repeticion
CERCA = 25.0       # segundos: mas lejos que esto ya no es un tropiezo
PARECIDO = 0.82


def palabras_de(carpeta):
    hallados = sorted(glob.glob(os.path.join(carpeta, "cache_*.json")))
    if not hallados:
        raise SystemExit("No hay transcripcion cacheada en %s" % carpeta)
    with open(hallados[0], encoding="utf-8") as f:
        return json.load(f)["words"]


def palabras_del_plan(carpeta, words):
    """Las palabras que SOBREVIVEN al plan, ya en la linea de tiempo final."""
    ruta = os.path.join(carpeta, "plan.json")
    if not os.path.exists(ruta):
        raise SystemExit("No hay plan.json en %s" % carpeta)
    with open(ruta, encoding="utf-8") as f:
        segmentos = json.load(f)["segmentos"]
    salida, cursor = [], 0.0
    for s in segmentos:
        for w in words:
            if s["ini"] <= (w["start"] + w["end"]) / 2.0 <= s["fin"]:
                salida.append({"word": w["word"],
                               "start": cursor + w["start"] - s["ini"]})
        cursor += s["fin"] - s["ini"]
    return salida


def buscar(words, ventana=VENTANA, cerca=CERCA, parecido=PARECIDO):
    """[(tiempo, tiempo_de_la_repeticion, texto)] de cada arranque falso."""
    norm = [tomas._norm(w["word"]) for w in words]
    crudos = []
    for i in range(len(words) - ventana):
        if any(not x for x in norm[i:i + ventana]):
            continue
        for j in range(i + ventana, len(words) - ventana):
            if words[j]["start"] - words[i]["start"] > cerca:
                break
            if tomas._similitud(norm[i:i + ventana],
                                norm[j:j + ventana]) >= parecido:
                crudos.append((words[i]["start"], words[j]["start"],
                               " ".join(w["word"] for w in words[i:j + ventana])))
                break
    # una repeticion dispara varias ventanas seguidas: se queda la primera
    salida, ultimo = [], -99.0
    for h in sorted(crudos):
        if h[0] - ultimo > 4.0:
            salida.append(h)
            ultimo = h[0]
    return salida


def main():
    consola_utf8()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("proyecto", help="carpeta en proyectos/ o ruta completa")
    ap.add_argument("--plan", action="store_true",
                    help="mirar lo que queda DESPUES de aplicar plan.json")
    ap.add_argument("--parecido", type=float, default=PARECIDO)
    args = ap.parse_args()

    carpeta = args.proyecto
    if not os.path.isdir(carpeta):
        carpeta = os.path.join(BASE, "proyectos", args.proyecto)
    if not os.path.isdir(carpeta):
        raise SystemExit("No encuentro el proyecto: %s" % args.proyecto)

    words = palabras_de(carpeta)
    total = len(words)
    if args.plan:
        words = palabras_del_plan(carpeta, words)
        print("Sobre el CORTE: %d palabras de %d" % (len(words), total))
    else:
        print("Sobre el ORIGINAL: %d palabras" % total)

    hallados = buscar(words, parecido=args.parecido)
    print("")
    if not hallados:
        print("Sin arranques falsos.")
        return
    print("%d posible(s) arranque(s) falso(s):" % len(hallados))
    print("")
    for ini, repe, texto in hallados:
        print("  %7.1f s  (se vuelve a empezar en %.1f s)" % (ini, repe))
        print("            %s" % texto[:150])
        print("")
    print("La regla del usuario: quedarse con la SEGUNDA, que suele ser la buena.")
    print("Ojo: una enumeracion se parece a una repeticion y NO se toca.")


if __name__ == "__main__":
    main()
