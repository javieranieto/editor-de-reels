# -*- coding: utf-8 -*-
"""Da planos a un video largo: parte los bloques fijos y reparte el zoom seco.

El problema de un video largo hablado a camara no son los cortes: es que
catorce minutos de plano identico delatan al video automatico. Aqui se
arregla sin tocar una sola palabra del audio.

**Un bloque largo se parte donde el hablante RESPIRA**, no cada X segundos.
Los trozos quedan contiguos, asi que no hay corte que oir: lo unico que
cambia es el tamano de plano, y cambia donde cambia la idea. Verificado en el
primer video: 50 tramos de audio antes y despues, los mismos 840.866 s.

**La mayoria de los planos van ABIERTOS.** Si todo esta acercado nada
destaca; el acercamiento tiene que significar algo. Cuales significan algo es
criterio, y por eso NO lo decide esta herramienta: se declara en el plan.

    "momentos": [{"seg": 1174.28, "zoom": 1.30, "nota": "la cifra que sostiene todo"}]

`seg` es el segundo del ORIGINAL (no el de la linea de tiempo), asi que la
decision sobrevive a que se renumeren los cortes. Lo que no cae en ningun
momento declarado alterna solo entre abierto y un escalon intermedio.

    python tools/planos.py "<proyecto>"

Trabaja sobre `plan_base.json` -que crea la primera vez copiando `plan.json`-
y escribe `plan.json`. Asi se puede correr las veces que haga falta sin que
cada corrida vuelva a partir lo ya partido.
"""
import argparse
import glob
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.entorno import consola_utf8

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

LARGO = 22.0        # a partir de aqui un plano fijo se nota
TROZO = 17.0        # duracion buscada de cada sub-plano
MEDIO = 1.12        # el escalon intermedio: ni abierto ni golpe
BORDE = 6.0         # no partir tan cerca del principio o del final del bloque
SEPARACION = 8.0    # ni dos cortes casi juntos


def respiraciones(words, a, b):
    """Los huecos entre palabras dentro de (a, b), de mayor a menor.

    En un hablante sin pausas el mayor puede ser de 0.2 s, y aun asi es el
    mejor sitio: es donde toma aire.
    """
    dentro = [w for w in words if a <= w["start"] <= b]
    huecos = [(w["start"] - p["end"], (p["end"] + w["start"]) / 2.0)
              for p, w in zip(dentro, dentro[1:])]
    return sorted(huecos, reverse=True)


def partir(s, words, largo=LARGO, trozo=TROZO):
    """Un segmento largo -> varios CONTIGUOS, cortando donde respira."""
    dur = s["fin"] - s["ini"]
    if dur <= largo:
        return [dict(s)]
    cuantos = max(2, int(round(dur / trozo)))
    cortes = []
    for _, centro in respiraciones(words, s["ini"], s["fin"]):
        if centro - s["ini"] < BORDE or s["fin"] - centro < BORDE:
            continue
        if any(abs(centro - c) < SEPARACION for c in cortes):
            continue
        cortes.append(centro)
        if len(cortes) >= cuantos - 1:
            break
    trozos, prev = [], s["ini"]
    for c in sorted(cortes) + [s["fin"]]:
        trozos.append(dict(s, ini=round(prev, 3), fin=round(c, 3)))
        prev = c
    return trozos


def repartir_zoom(segs, momentos, medio=MEDIO):
    """Escala de cada plano: la declarada si la hay, si no alterna."""
    puestos = 0
    for i, s in enumerate(segs):
        s.pop("zoom", None)
        escala = None
        for m in momentos:
            if s["ini"] <= float(m["seg"]) <= s["fin"]:
                escala = float(m.get("zoom", 1.25))
                puestos += 1
                break
        if escala is None:
            # nunca dos acercamientos seguidos: el escalon se percibe por
            # contraste con el plano abierto de al lado
            previo = (segs[i - 1].get("zoom") or {}).get("punch", 1.0) if i else 1.0
            escala = medio if (i % 3 == 1 and previo <= 1.001) else 1.0
        if escala > 1.001:
            # ancla arriba: lo que se recorta es la camisa, no la frente
            s["zoom"] = {"punch": escala, "ancla": 0.5}
    return puestos


def palabras_de(carpeta):
    hallados = sorted(glob.glob(os.path.join(carpeta, "cache_*.json")))
    if not hallados:
        raise SystemExit("No hay transcripcion cacheada en %s" % carpeta)
    with io.open(hallados[0], encoding="utf-8") as f:
        return json.load(f)["words"]


def main():
    consola_utf8()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("proyecto")
    ap.add_argument("--largo", type=float, default=LARGO,
                    help="a partir de cuantos segundos se parte un plano")
    ap.add_argument("--trozo", type=float, default=TROZO,
                    help="duracion buscada de cada sub-plano")
    args = ap.parse_args()

    carpeta = args.proyecto
    if not os.path.isdir(carpeta):
        carpeta = os.path.join(RAIZ, "proyectos", args.proyecto)
    if not os.path.isdir(carpeta):
        raise SystemExit("No encuentro el proyecto: %s" % args.proyecto)

    base = os.path.join(carpeta, "plan_base.json")
    if not os.path.exists(base):
        import shutil
        shutil.copy2(os.path.join(carpeta, "plan.json"), base)
        print("plan_base.json: copia del corte aprobado (de aqui se parte siempre)")
    with io.open(base, encoding="utf-8") as f:
        plan = json.load(f)

    words = palabras_de(carpeta)
    antes = plan["segmentos"]
    segs = []
    for s in antes:
        segs += partir(s, words, args.largo, args.trozo)

    momentos = plan.get("momentos") or []
    puestos = repartir_zoom(segs, momentos)

    # el audio NO puede haber cambiado: es la comprobacion que importa
    def fundir(lista):
        out = []
        for a, b in sorted((round(x["ini"], 3), round(x["fin"], 3)) for x in lista):
            if out and a - out[-1][1] < 0.005:
                out[-1][1] = max(out[-1][1], b)
            else:
                out.append([a, b])
        return out
    if fundir(antes) != fundir(segs):
        raise SystemExit("ERROR: al partir se movio el audio. No se escribio nada.")

    plan["segmentos"] = segs
    with io.open(os.path.join(carpeta, "plan.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(plan, ensure_ascii=False, indent=1))

    niveles = {}
    for s in segs:
        k = round((s.get("zoom") or {}).get("punch", 1.0), 2)
        niveles[k] = niveles.get(k, 0) + 1
    total = sum(s["fin"] - s["ini"] for s in segs)
    print("%d planos (antes %d) | %d:%05.2f | audio intacto"
          % (len(segs), len(antes), total // 60, total % 60))
    print("escalas: %s" % dict(sorted(niveles.items())))
    print("abiertos: %d%%   momentos declarados aplicados: %d de %d"
          % (round(100.0 * niveles.get(1.0, 0) / len(segs)), puestos, len(momentos)))
    if len(momentos) and puestos < len(momentos):
        print("  aviso: algun momento cae fuera del corte y no se aplico")


if __name__ == "__main__":
    main()
