"""Verifica que un draft generado sea internamente consistente antes de abrir CapCut.

Un draft con referencias rotas puede hacer que CapCut no abra el proyecto, asi que
conviene ejecutarlo tras generar: python tools/validar_draft.py <carpeta_del_draft>
"""
import json
import os
import sys


def validar(carpeta):
    ruta = os.path.join(carpeta, "draft_content.json")
    if not os.path.exists(ruta):
        return ["falta draft_content.json"]

    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)

    errores = []

    # indice de todos los materiales por id
    # pycapcut repite la entrada del material una vez por segmento que lo usa
    # (el clip principal sale 11 veces en un reel de 11 cortes). Es inofensivo:
    # 'FINAL v18' salio asi, se abrio, se edito y se exporto. Se avisa una sola
    # vez por id, no una por repeticion, que llenaba la pantalla de ruido.
    ids = {}
    repetidos = {}
    for clave, lista in d.get("materials", {}).items():
        if isinstance(lista, list):
            for m in lista:
                if isinstance(m, dict) and "id" in m:
                    if m["id"] in ids:
                        repetidos[m["id"]] = repetidos.get(m["id"], 1) + 1
                    ids[m["id"]] = clave
    for mid, veces in repetidos.items():
        errores.append("material %s repetido %d veces en %s (normal en pycapcut)"
                       % (mid[:8], veces, ids[mid]))

    total_esperado = 0
    for pista in d.get("tracks", []):
        tipo = pista.get("type")
        principal = tipo == "video" and pista.get("name") in (None, "", "video")
        cursor = None
        for i, s in enumerate(pista.get("segments", [])):
            if s.get("material_id") not in ids:
                errores.append("%s seg %d: material_id inexistente" % (tipo, i))
            for r in s.get("extra_material_refs") or []:
                # En los segmentos de TEXTO esto es normal y no es un problema:
                # pycapcut deja una referencia colgando en cada uno y CapCut la
                # resuelve sola al abrir el draft (verificado: 'FINAL v18' salio
                # con 93 colgando, se abrio, se edito y se exporto sin falla; al
                # reescribirlo CapCut quedo con 0 y su app_version 9.2.0).
                # Reportarlo hacia que un draft sano saliera con 22 "problemas".
                if r not in ids and tipo != "text":
                    errores.append("%s seg %d: extra_material_ref %s inexistente" % (tipo, i, r[:8]))

            tr = s.get("target_timerange") or {}
            if tr.get("duration", 0) <= 0:
                errores.append("%s seg %d: duracion no positiva" % (tipo, i))

            if tipo == "video":
                # Solo la pista PRINCIPAL debe ser continua. Las de encima
                # (b-roll, adornos) son superposiciones: tienen huecos por
                # definicion, y exigirles continuidad marcaba como rotos
                # proyectos sanos.
                if principal and cursor is not None and tr.get("start") != cursor:
                    errores.append("%s seg %d: empieza en %s pero se esperaba %s"
                                   % (tipo, i, tr.get("start"), cursor))
                cursor = tr.get("start", 0) + tr.get("duration", 0)

                sr = s.get("source_timerange") or {}
                mat = next((m for m in d["materials"]["videos"] if m["id"] == s["material_id"]), None)
                if mat and sr.get("start", 0) + sr.get("duration", 0) > mat.get("duration", 0) + 1000:
                    errores.append("%s seg %d: el corte excede la duracion del archivo fuente" % (tipo, i))

        if principal and cursor is not None:
            total_esperado = cursor

    if d.get("duration") != total_esperado:
        errores.append("duration=%s no coincide con el fin de la pista de video (%s)"
                       % (d.get("duration"), total_esperado))

    for m in d.get("materials", {}).get("videos", []):
        if not os.path.exists(m.get("path", "")):
            errores.append("archivo fuente no existe: %s" % m.get("path"))
            break

    if not os.path.exists(os.path.join(carpeta, "draft_meta_info.json")):
        errores.append("falta draft_meta_info.json")
    # draft_virtual_store.json y el resto de archivos (Resources/, key_value.json,
    # draft_cover.jpg...) los crea CAPCUT la primera vez que abre el proyecto.
    # Un draft recien generado tiene solo los dos JSON y abre perfecto: exigirlo
    # marcaba como roto a todo proyecto nuevo. Solo se reclama si el proyecto ya
    # paso por CapCut alguna vez y aun asi le falta.
    ya_abierto = os.path.exists(os.path.join(carpeta, "key_value.json"))
    if ya_abierto and not os.path.exists(
            os.path.join(carpeta, "draft_virtual_store.json")):
        errores.append("falta draft_virtual_store.json")

    vt = [t for t in d.get("tracks", []) if t.get("type") == "video"]
    tt = [t for t in d.get("tracks", []) if t.get("type") == "text"]
    print("  pistas: %d video (%d clips), %d texto (%d subtitulos)"
          % (len(vt), sum(len(t["segments"]) for t in vt),
             len(tt), sum(len(t["segments"]) for t in tt)))
    print("  duracion: %.2f s | materiales: %d" % (d.get("duration", 0) / 1e6, len(ids)))
    return errores


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("uso: python tools/validar_draft.py <carpeta_del_draft>")
    errs = validar(sys.argv[1])
    if errs:
        print("\n  %d PROBLEMA(S):" % len(errs))
        for e in errs[:20]:
            print("   - %s" % e)
        sys.exit(1)
    print("\n  Draft consistente.")
