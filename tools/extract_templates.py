"""Extrae las plantillas del formato de draft de CapCut desde drafts reales.

Se ejecuta cuando cambia la version de CapCut. Toma como molde un proyecto hecho con
la MISMA version instalada: un draft viejo se declara con otra 'new_version' y CapCut
se niega a abrir lo que generemos a partir de el.

Uso: python tools/extract_templates.py
"""
import glob
import json
import os
import re
import shutil
import sys

DRAFTS = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
APPS = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\Apps")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "pipeline", "templates")


def version_instalada():
    """Version de CapCut instalada, en el formato corto que usan los drafts (9.2.0)."""
    vers = []
    for d in os.listdir(APPS) if os.path.isdir(APPS) else []:
        m = re.match(r"^(\d+)\.(\d+)\.(\d+)\.(\d+)$", d)
        if m:
            vers.append(tuple(int(x) for x in m.groups()))
    if not vers:
        return None
    v = max(vers)
    return "%d.%d.%d" % v[:3]


def candidatos():
    """Todos los drafts reales, incluida la papelera interna de CapCut."""
    return (glob.glob(os.path.join(DRAFTS, "*", "draft_content.json"))
            + glob.glob(os.path.join(DRAFTS, ".recycle_bin", "*", "draft_content.json")))


def inventario(objetivo):
    """Drafts que coinciden con la version instalada, con su riqueza de segmentos."""
    filas = []
    for f in candidatos():
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        plat = (d.get("platform") or {}).get("app_version")
        if objetivo and plat != objetivo:
            continue
        conteo = {}
        for t in d.get("tracks", []):
            conteo[t.get("type")] = conteo.get(t.get("type"), 0) + len(t.get("segments", []))
        filas.append({"ruta": f, "carpeta": os.path.dirname(f), "draft": d,
                      "video": conteo.get("video", 0), "text": conteo.get("text", 0),
                      "plat": plat, "new_version": d.get("new_version")})
    return filas


def main():
    objetivo = version_instalada()
    print("CapCut instalado: %s" % (objetivo or "desconocido"))

    filas = inventario(objetivo)
    if not filas:
        sys.exit(
            "No encontre ningun proyecto hecho con CapCut %s.\n"
            "Abre CapCut, crea un proyecto con un video, cortalo en 2-3 trozos,\n"
            "anade un subtitulo, guardalo y vuelve a ejecutar este script." % objetivo)

    con_video = max(filas, key=lambda r: r["video"])
    con_texto = max(filas, key=lambda r: r["text"])
    if con_video["video"] < 2:
        sys.exit("Necesito un proyecto de la version %s con al menos 2 clips de video.\n"
                 "El mejor que encontre tiene %d." % (objetivo, con_video["video"]))

    print("molde de video: %s (%d clips, new_version %s)"
          % (os.path.basename(con_video["carpeta"]), con_video["video"], con_video["new_version"]))
    print("molde de texto: %s (%d subtitulos)"
          % (os.path.basename(con_texto["carpeta"]), con_texto["text"]))
    if con_texto["text"] == 0:
        print("  aviso: sin subtitulos de referencia; se generaran drafts sin pista de texto")

    os.makedirs(OUT, exist_ok=True)
    vd, td = con_video["draft"], con_texto["draft"]

    # --- esqueleto: ajustes globales del proyecto, sin materiales ni pistas
    skel = json.loads(json.dumps(vd))
    for k, v in skel["materials"].items():
        if isinstance(v, list):
            skel["materials"][k] = []
    skel["tracks"] = []
    for k in ("id", "name", "path", "duration", "create_time", "update_time",
              "cover", "static_cover_image_path", "retouch_cover"):
        if k in skel:
            actual = skel[k]
            skel[k] = "" if isinstance(actual, str) else (0 if isinstance(actual, int) else None)
    dump("skeleton.json", skel)

    vtrack = [t for t in vd["tracks"] if t["type"] == "video"][0]
    dump("video_track.json", dict(vtrack, segments=[]))
    dump("video_segment.json", vtrack["segments"][0])
    dump("video_material.json", vd["materials"]["videos"][0])

    for key in ("canvases", "speeds", "placeholder_infos", "sound_channel_mappings",
                "material_colors", "vocal_separations"):
        lst = vd["materials"].get(key) or []
        if lst:
            dump("aux_%s.json" % key, lst[0])

    if con_texto["text"]:
        ttrack = [t for t in td["tracks"] if t["type"] == "text"][0]
        dump("text_track.json", dict(ttrack, segments=[]))
        dump("text_segment.json", ttrack["segments"][0])
        dump("text_material.json", td["materials"]["texts"][0])
        anim = (td["materials"].get("material_animations") or [None])[0]
        if anim:
            dump("aux_material_animations.json", anim)

    # --- archivos sueltos que acompanan al draft
    base = con_video["carpeta"]
    for src, dst, vaciar in [
        ("draft_meta_info.json", "meta_info.json", True),
        ("draft_virtual_store.json", "virtual_store.json", False),
        ("attachment_pc_common.json", "attachment_pc_common.json", False),
        ("draft_agency_config.json", "draft_agency_config.json", False),
        ("performance_opt_info.json", "performance_opt_info.json", False),
        (os.path.join("Timelines", "project.json"), "timelines_project.json", False),
    ]:
        p = os.path.join(base, src)
        if not os.path.exists(p):
            print("  ! falta %s en el molde" % src)
            continue
        if vaciar:
            with open(p, encoding="utf-8") as fh:
                m = json.load(fh)
            for g in m.get("draft_materials", []):
                g["value"] = []
            m["draft_segment_extra_info"] = []
            dump(dst, m)
        else:
            shutil.copy2(p, os.path.join(OUT, dst))
            print("  + %s" % dst)

    print("\nPlantillas actualizadas en %s" % OUT)


def dump(name, obj):
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    print("  + %s" % name)


if __name__ == "__main__":
    main()
