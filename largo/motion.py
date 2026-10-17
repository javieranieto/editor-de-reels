"""Paso 6 (opcional): los graficos animados del largo, con el banco de escenas y la marca.

Lee `escenas.json` (lo escribe Claude o quien edita) y captura cada pieza con
recursos/escenas/capturar.py. Todo TIEMPO se escribe como una FRASE del texto limpio, nunca
en segundos: asi el grafico cae en la voz aunque el corte cambie.

    python largo.py motion <proyecto> [nombre ...] [--revisar]

Formato de escenas.json:

    {"marca": "ejemplo",
     "piezas": [
      {"nombre": "L1_culpa", "tipo": "lateral",
       "desde": {"frase": "al principio te dije", "mas": -0.1},
       "hasta": {"frase": "ni tampoco tuya", "fin": true, "mas": 1.0},
       "T": {"etiqueta": "La pregunta", "titulo": "¿De quién es la culpa?",
             "filas": [{"txt": "De la agencia", "t": {"frase": "no es de la agencia"}, "ico": "mal"}]}},
      {"nombre": "P1_regla", "tipo": "panel", "desde": ..., "hasta": ..., "T": {"lineas": [...]}},
      {"nombre": "P2_tabla", "tipo": "escena", "html": "datos/tabla.html", "alfa": false, ...}
     ]}

- `tipo`: "lateral" (tarjeta a un lado, encima del que habla), "panel" (ocupa la pantalla)
  o "escena" (cualquier HTML del banco, con `html`). El nombre empieza con L si va encima del
  que habla y con P si ocupa la pantalla: asi lo acomoda `armar`.
- Un tiempo es `{"frase": "...", "fin": false, "mas": 0.0, "despues": <segundos>}`: el segundo
  donde empieza (o acaba, con fin) esa frase, mas un ajuste. Dentro de `T` la frase se busca
  despues del inicio de la pieza.
- Lo que cada plantilla acepta esta documentado al principio de su HTML. Toda plantilla trae
  datos de EJEMPLO: lo que no va se pasa vacio (`"filas": []`, `"pie": null`).
"""
import copy
import json
import os
import subprocess
import sys

from largo.comun import RAIZ, T as tiempo, escribir, leer, total_corte

BANCO = os.path.join(RAIZ, "recursos", "escenas")
HTML = {"lateral": "tarjetas/lateral.html", "panel": "tarjetas/panel.html"}


def resolver(x, tl, despues, total):
    """Cambia cada {"frase": ...} por su segundo en la linea de tiempo final."""
    if isinstance(x, dict) and "frase" in x and set(x) <= {"frase", "fin", "mas", "despues"}:
        if x["frase"] in ("FIN", "fin del video"):
            return round(total + x.get("mas", 0.0), 3)
        return round(tiempo(tl, x["frase"], x.get("despues", despues), fin=x.get("fin", False)) + x.get("mas", 0.0), 3)
    if isinstance(x, dict):
        return {k: resolver(v, tl, despues, total) for k, v in x.items()}
    if isinstance(x, list):
        return [resolver(v, tl, despues, total) for v in x]
    return x


def main(c, solo=None, revisar=False):
    tl = leer(c, "tl.json")
    total = total_corte(leer(c, "edl.json"))
    cfg = leer(c, "escenas.json")
    marca = cfg.get("marca", "ejemplo")
    vertical = leer(c, "proyecto.json")["lienzo"][1] > leer(c, "proyecto.json")["lienzo"][0]
    sal = os.path.join(c, "motion")
    os.makedirs(sal, exist_ok=True)
    malas = []
    for p in cfg["piezas"]:
        nombre = p["nombre"]
        if solo and not any(s in nombre for s in solo):
            continue
        try:
            ini = max(0.0, resolver(p["desde"], tl, 0.0, total))
            fin = min(resolver(p["hasta"], tl, ini, total), total)
            datos = resolver(copy.deepcopy(p.get("T", {})), tl, ini, total)
        except SystemExit as e:
            malas.append("%s: %s" % (nombre, str(e).splitlines()[0]))
            continue
        if revisar:
            print("%-18s %6.2f-%6.2f  ok" % (nombre, ini, fin))
            continue
        tipo = p.get("tipo", "escena")
        html = p.get("html") or HTML.get(tipo)
        if not html:
            raise SystemExit("%s: tipo %r sin html" % (nombre, tipo))
        if tipo == "lateral":
            for k, v in (("filas", []), ("pie", None), ("titulo", "")):
                datos.setdefault(k, v)
        if tipo == "panel":
            datos.setdefault("pie", None)
        if tipo in ("lateral", "panel"):
            datos.setdefault("t_in", ini)
            datos.setdefault("t_out", fin - 0.35)
        alfa = p.get("alfa", tipo in ("lateral", "panel"))
        dest = os.path.join(sal, nombre + (".mov" if alfa else ".mp4"))
        claves = [ini + 0.5, (ini + fin) / 2, fin - 0.5]
        args = [sys.executable, os.path.join(BANCO, "capturar.py"), os.path.join(BANCO, html), dest,
                "%.3f" % (fin - ini), "--desde", "%.3f" % ini, "--marca", marca,
                "--T", json.dumps(datos, ensure_ascii=False), "--claves", ",".join("%.2f" % k for k in claves)]
        if alfa:
            args.append("--alfa")
        if vertical:
            args.append("--vertical")
        if p.get("escena"):
            args += ["--escena", p["escena"]]
        r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                           env=dict(os.environ, PYTHONIOENCODING="utf-8"))
        if r.returncode:
            raise SystemExit("%s: %s" % (nombre, (r.stderr or r.stdout)[-800:]))
        escribir(sal, nombre + ".json", {"archivo": dest.replace("\\", "/"), "ini": round(ini, 3), "fin": round(fin, 3)})
        print("%-18s %6.2f-%6.2f  %s" % (nombre, ini, fin, os.path.basename(dest)))
    if malas:
        print("\nFRASES QUE NO EXISTEN en el texto limpio (corrige escenas.json):")
        for m in malas:
            print("  " + m)
        raise SystemExit(1)
    if not revisar:
        print("\nMIRA las hojas (motion/* - hoja.jpg) antes de armar: un texto encimado o un dato de\n"
              "ejemplo colado no lo caza ninguna medicion.")
