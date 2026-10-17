"""Restaura los proyectos que CapCut movio a su papelera interna (.recycle_bin).

CapCut, al arrancar, valida su indice de proyectos (root_meta_info.json). Si algo no
le cuadra puede reconstruirlo y mandar los proyectos existentes a .recycle_bin.
Este script los devuelve a su sitio y reconstruye el indice a partir de las entradas
que el propio CapCut escribio (formato garantizado valido).

Uso:  python tools/restaurar_capcut.py [--aplicar]
Sin --aplicar solo muestra lo que haria.
"""
import json
import os
import shutil
import subprocess
import sys

D = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
BIN = os.path.join(D, ".recycle_bin")
IDX = os.path.join(D, "root_meta_info.json")


def capcut_abierto():
    try:
        out = subprocess.run(["tasklist"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout.lower()
        return "capcut.exe" in out
    except Exception:
        return False


def limpiar_ruta(p):
    """Quita el tramo .recycle_bin de una ruta y normaliza separadores."""
    return p.replace("/.recycle_bin", "").replace("\\.recycle_bin", "").replace("\\", "/")


def main():
    aplicar = "--aplicar" in sys.argv

    if not os.path.isdir(BIN):
        sys.exit("No hay papelera interna: nada que restaurar.")
    if aplicar and capcut_abierto():
        sys.exit("CapCut esta abierto. Cierralo antes de restaurar.")

    rec_idx = os.path.join(BIN, "root_meta_info.json")
    if not os.path.exists(rec_idx):
        sys.exit("Falta %s: no puedo saber que proyectos restaurar." % rec_idx)

    with open(rec_idx, encoding="utf-8") as f:
        rec = json.load(f)
    entradas = rec.get("all_draft_store") or []

    # Solo se restaura lo que tiene entrada en el indice de la papelera.
    # Una carpeta sin entrada fue borrada a proposito por el usuario: se respeta.
    restaurables, faltantes = [], []
    for e in entradas:
        nombre = e.get("draft_name")
        if os.path.isdir(os.path.join(BIN, nombre)):
            restaurables.append(e)
        else:
            faltantes.append(nombre)

    carpetas = {d for d in os.listdir(BIN) if os.path.isdir(os.path.join(BIN, d))}
    intocadas = sorted(carpetas - {e["draft_name"] for e in restaurables})

    print("A restaurar: %d proyectos" % len(restaurables))
    print("Se quedan en la papelera (los borraste tu): %s" % (", ".join(intocadas) or "ninguno"))
    if faltantes:
        print("Con entrada pero sin carpeta (se ignoran): %s" % ", ".join(faltantes))

    if not aplicar:
        print("\nSimulacion. Ejecuta con --aplicar para hacerlo de verdad.")
        return

    if os.path.exists(IDX):
        shutil.copy2(IDX, IDX + ".roto")
        print("\nIndice actual guardado como root_meta_info.json.roto")

    movidos = 0
    for e in restaurables:
        origen = os.path.join(BIN, e["draft_name"])
        destino = os.path.join(D, e["draft_name"])
        if os.path.exists(destino):
            print("  saltado (ya existe en destino): %s" % e["draft_name"])
            continue
        shutil.move(origen, destino)
        movidos += 1

    # Reescribir las rutas para que apunten fuera de la papelera
    for e in restaurables:
        for k in ("draft_fold_path", "draft_json_file", "draft_cover"):
            if e.get(k):
                e[k] = limpiar_ruta(e[k])
        e["draft_root_path"] = D
        e["tm_draft_removed"] = 0

    nuevo = {
        "all_draft_store": restaurables,
        "draft_ids": rec.get("draft_ids", 0),
        "root_path": D.replace("\\", "/"),
    }
    with open(IDX, "w", encoding="utf-8") as f:
        json.dump(nuevo, f, ensure_ascii=False)

    # La papelera queda sin entradas activas
    rec["all_draft_store"] = []
    with open(rec_idx, "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)

    print("\n%d carpetas devueltas a su sitio." % movidos)
    print("Indice reconstruido con %d proyectos." % len(restaurables))
    print("Abre CapCut y revisa que esten todos.")


if __name__ == "__main__":
    main()
