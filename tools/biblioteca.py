"""Escanea los proyectos de CapCut y arma la biblioteca de efectos y transiciones.

Uso:
    python tools/biblioteca.py             # muestra lo que hay
    python tools/biblioteca.py --guardar   # lo deja en recursos/biblioteca.json
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline import biblioteca
from pipeline.entorno import consola_utf8


def main():
    consola_utf8()
    datos = biblioteca.escanear()
    for grupo in ("efectos", "transiciones", "voz"):
        items = datos.get(grupo) or {}
        print("\n%s (%d):" % (grupo.upper(), len(items)))
        for nombre, mat in sorted(items.items()):
            ok = "OK " if (grupo == "voz" or biblioteca.usable(mat)) else "recurso perdido"
            rid = mat.get("effect_id") or mat.get("resource_id")
            print("  %-3s %-30s %s" % (ok, nombre[:30], rid))

    if "--guardar" in sys.argv:
        ruta = biblioteca.guardar(datos)
        print("\nGuardada en %s" % ruta)
    else:
        print("\n(usa --guardar para escribirla en recursos/biblioteca.json)")


if __name__ == "__main__":
    main()
