"""Lee efectos visuales, transiciones y animaciones de un proyecto de CapCut.

Complementa a analizar_sonido.py. Sirve para aprender del usuario en vez de
adivinar: que efecto eligio, con que parametros, cuanto dura y donde cae
respecto a los cortes. Ademas dice si el recurso quedo descargado, que es lo
que permite reutilizarlo desde aqui.

Uso:
    python tools/analizar_visual.py "<nombre del proyecto en CapCut>"
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

RAIZ = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
US = 1_000_000


def cargar(nombre):
    ruta = os.path.join(RAIZ, nombre, "draft_content.json")
    if not os.path.exists(ruta):
        disponibles = sorted(d for d in os.listdir(RAIZ)
                             if os.path.isdir(os.path.join(RAIZ, d)))
        sys.exit("No encuentro '%s'.\nProyectos: %s" % (nombre, ", ".join(disponibles)))
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def pista_principal(d):
    for t in d.get("tracks", []):
        if t.get("type") == "video" and t.get("name") in (None, "", "video"):
            return t
    return None


def catalogo_inverso():
    """resource_id -> nombre legible en pycapcut, para poder replicarlo."""
    try:
        import pycapcut as cc
    except ImportError:
        return {}, {}
    efe, tra = {}, {}
    for n in dir(cc.VideoSceneEffectType):
        if n.startswith("_"):
            continue
        v = getattr(getattr(cc.VideoSceneEffectType, n), "value", None)
        rid = getattr(v, "resource_id", None)
        if rid:
            efe[str(rid)] = n
    for n in dir(cc.TransitionType):
        if n.startswith("_"):
            continue
        v = getattr(getattr(cc.TransitionType, n), "value", None)
        rid = getattr(v, "resource_id", None)
        if rid:
            tra[str(rid)] = n
    return efe, tra


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    nombre = sys.argv[1]
    d = cargar(nombre)
    cat_efe, cat_tra = catalogo_inverso()
    try:
        from pipeline import efectos as mod
    except Exception:
        mod = None

    principal = pista_principal(d)
    cortes = ([s["target_timerange"]["start"] / US for s in principal["segments"]]
              if principal else [])
    print("Proyecto: %s   (%.1f s, %d cortes)"
          % (nombre, d.get("duration", 0) / US, len(cortes)))

    # ---- efectos de escena
    efm = {e["id"]: e for e in (d.get("materials", {}).get("video_effects") or [])}
    hay = False
    for t in d.get("tracks", []):
        if t.get("type") != "effect":
            continue
        for s in t["segments"]:
            if not hay:
                print("\nEFECTOS VISUALES")
                hay = True
            m = efm.get(s.get("material_id"), {})
            ini = s["target_timerange"]["start"] / US
            dur = s["target_timerange"]["duration"] / US
            rid = str(m.get("effect_id") or m.get("resource_id") or "")
            clave = cat_efe.get(rid, "(no esta en pycapcut)")
            local = mod.ruta_local(rid) if (mod and rid) else None
            cerca = min(cortes, key=lambda c: abs(c - ini)) if cortes else None
            rel = ("%+.2fs del corte en %.2f" % (ini - cerca, cerca)) if cerca is not None else ""
            print("  %-22s en %6.2fs dura %.2fs  %s" % (m.get("name", "?")[:22], ini, dur, rel))
            print("       pycapcut: %-18s recurso descargado: %s"
                  % (clave, "si" if local else "NO"))
            for p in (m.get("adjust_params") or [])[:4]:
                print("       %-32s %.2f" % (p.get("name"), p.get("value", 0)))
    if not hay:
        print("\nEFECTOS VISUALES: ninguno")

    # ---- transiciones (viven en el segmento de video que las precede)
    trm = {t["id"]: t for t in (d.get("materials", {}).get("transitions") or [])}
    filas = []
    for t in d.get("tracks", []):
        if t.get("type") != "video":
            continue
        for i, s in enumerate(t["segments"]):
            for r in s.get("extra_material_refs") or []:
                if r in trm:
                    m = trm[r]
                    rid = str(m.get("resource_id") or m.get("effect_id") or "")
                    fin = (s["target_timerange"]["start"]
                           + s["target_timerange"]["duration"]) / US
                    filas.append((t.get("name") or "video", i, fin, m.get("name", "?"),
                                  m.get("duration", 0) / US, cat_tra.get(rid, "?")))
    print("\nTRANSICIONES: %s" % ("" if filas else "ninguna"))
    for pista, i, fin, nom, dur, clave in filas:
        print("  %-18s tras el corte %d (en %.2fs) dura %.2fs   pycapcut: %s"
              % (nom[:18], i, fin, dur, clave))

    # ---- animaciones de clip
    anm = {a["id"]: a for a in (d.get("materials", {}).get("material_animations") or [])}
    filas = []
    for t in d.get("tracks", []):
        if t.get("type") != "video":
            continue
        for i, s in enumerate(t["segments"]):
            for r in s.get("extra_material_refs") or []:
                a = anm.get(r)
                for an in (a or {}).get("animations") or []:
                    filas.append((t.get("name") or "video", i,
                                  s["target_timerange"]["start"] / US,
                                  an.get("name"), an.get("type"),
                                  an.get("duration", 0) / 1000))
    print("\nANIMACIONES DE CLIP: %s" % ("" if filas else "ninguna"))
    for pista, i, ini, nom, tipo, ms in filas:
        print("  %-18s clip %d de '%s' en %.2fs  (%s, %.0f ms)"
              % (str(nom)[:18], i, pista, ini, tipo, ms))

    print("\nPara replicar hace falta: el nombre en pycapcut y que el recurso"
          "\nesté descargado. Aplicar un efecto una vez a mano en CapCut lo descarga.")


if __name__ == "__main__":
    main()
