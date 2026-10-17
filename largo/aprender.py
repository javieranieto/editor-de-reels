"""Aprender tu estilo: compara el proyecto de CapCut que genero el editor con como lo dejaste.

Cuando `armar` o `reels` crean un proyecto, guardan una copia de como salio
(`capcut_generado/<nombre>.json`). Tu lo editas en CapCut como siempre. Despues:

    python largo.py aprender <proyecto> --capcut "<nombre del proyecto en CapCut>"

dice que cambiaste: piezas que quitaste o agregaste, si apretaste o soltaste los cortes, los
volumenes, el zoom, los textos que corregiste, capas que moviste y lo que agregaste tu
(textos, stickers, efectos). Lo deja en `aprendido/<nombre>.md`.

Lo que se repite en dos o tres videos ES tu estilo: Claude te pregunta si se vuelve regla y lo
escribe en `mi_estilo.md` (en la raiz del repo, solo en tu maquina), que el skill lee antes de
editar. Un cambio que hiciste una vez no es una regla; uno que haces siempre, si.
"""
import json
import os
import shutil

from largo.comun import escribir

US = 1_000_000
CAPCUT = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")


def guardar_generado(c, nombre):
    """Copia el draft recien creado, para poder compararlo despues."""
    src = os.path.join(CAPCUT, nombre, "draft_content.json")
    if os.path.exists(src):
        os.makedirs(os.path.join(c, "capcut_generado"), exist_ok=True)
        shutil.copy2(src, os.path.join(c, "capcut_generado", nombre + ".json"))


def _pistas(d):
    out = {}
    for k, t in enumerate(d.get("tracks", [])):
        clave = "%s:%s" % (t.get("type"), t.get("name") or "#%d" % k)
        out.setdefault(clave, []).extend(t.get("segments", []))
    return out


def _textos(d):
    out = {}
    for m in d.get("materials", {}).get("texts", []):
        try:
            txt = json.loads(m.get("content") or "{}").get("text", "")
        except ValueError:
            txt = m.get("content") or ""
        out[m["id"]] = txt
    return out


def _seg(s):
    tr, sr = s.get("target_timerange") or {}, s.get("source_timerange") or {}
    clip = s.get("clip") or {}
    return {"mat": s.get("material_id"), "t0": tr.get("start", 0) / US, "dur": tr.get("duration", 0) / US,
            "s0": (sr.get("start", 0) / US) if sr else None, "vol": s.get("volume"),
            "zoom": (clip.get("scale") or {}).get("x"), "visible": s.get("visible", True)}


def comparar(c, nombre):
    gen_ruta = os.path.join(c, "capcut_generado", nombre + ".json")
    act_ruta = os.path.join(CAPCUT, nombre, "draft_content.json")
    if not os.path.exists(gen_ruta):
        raise SystemExit("No tengo la copia de como lo genere (%s). Solo se puede comparar un proyecto "
                         "creado con `armar` o `reels` de esta version." % gen_ruta)
    if not os.path.exists(act_ruta):
        raise SystemExit("No encuentro el proyecto %r en CapCut." % nombre)
    G = json.load(open(gen_ruta, encoding="utf-8"))
    A = json.load(open(act_ruta, encoding="utf-8"))
    gp, ap = _pistas(G), _pistas(A)
    lineas = ["# Lo que cambiaste en «%s»" % nombre, "",
              "Duración: %.1f s generado → %.1f s ahora." % (G.get("duration", 0) / US, A.get("duration", 0) / US), ""]
    datos = {"nombre": nombre, "pistas": {}}
    for clave in sorted(set(gp) | set(ap)):
        g = [_seg(s) for s in gp.get(clave, [])]
        a = [_seg(s) for s in ap.get(clave, [])]
        if not g:
            lineas.append("- **Agregaste la pista %s** con %d piezas (lo que pusiste tú, no el editor)." % (clave, len(a)))
            datos["pistas"][clave] = {"agregada": len(a)}
            continue
        if not a:
            lineas.append("- **Quitaste toda la pista %s** (%d piezas)." % (clave, len(g)))
            datos["pistas"][clave] = {"quitada": len(g)}
            continue
        por_mat = {}
        for s in g:
            por_mat.setdefault(s["mat"], []).append(s)
        emparejadas, nuevas = [], []
        for s in a:
            cand = por_mat.get(s["mat"]) or []
            if cand:
                mejor = min(cand, key=lambda x: abs((x["s0"] or 0) - (s["s0"] or 0)) + abs(x["t0"] - s["t0"]))
                cand.remove(mejor)
                emparejadas.append((mejor, s))
            else:
                nuevas.append(s)
        quitadas = [s for v in por_mat.values() for s in v]
        dg, da = sum(s["dur"] for s in g), sum(s["dur"] for s in a)
        info = {"generadas": len(g), "ahora": len(a), "quitadas": len(quitadas), "nuevas": len(nuevas),
                "dur_generada": round(dg, 2), "dur_ahora": round(da, 2)}
        cambios = []
        if quitadas:
            cambios.append("quitaste %d de %d piezas" % (len(quitadas), len(g)))
        if nuevas:
            cambios.append("agregaste %d" % len(nuevas))
        recorte = [(b["dur"] - a_["dur"]) for a_, b in emparejadas if abs(b["dur"] - a_["dur"]) > 0.04]
        if recorte:
            media = sum(recorte) / len(recorte)
            info["ajuste_medio_s"] = round(media, 3)
            cambios.append("en %d piezas cambiaste la duración (%+.2f s en promedio: %s)" %
                           (len(recorte), media, "las ALARGASTE" if media > 0 else "las APRETASTE"))
        # relativo, no absoluto: la musica vive en 0.005-0.05, y bajarla a la mitad era invisible con un umbral de 0.01
        vol = [(a_["vol"], b["vol"]) for a_, b in emparejadas if a_["vol"] is not None and b["vol"] is not None
               and abs(a_["vol"] - b["vol"]) > 0.10 * max(a_["vol"], b["vol"], 1e-6)]
        if vol:
            info["volumen"] = {"antes": round(vol[0][0], 3), "ahora": round(vol[0][1], 3)}
            cambios.append("cambiaste el volumen (%.3f → %.3f%s)" % (vol[0][0], vol[0][1], ", y otros" if len(vol) > 1 else ""))
        zm = [(a_["zoom"], b["zoom"]) for a_, b in emparejadas if a_["zoom"] and b["zoom"] and abs(a_["zoom"] - b["zoom"]) > 0.01]
        if zm:
            info["zoom"] = len(zm)
            cambios.append("cambiaste el zoom en %d piezas (por ejemplo %.2f → %.2f)" % (len(zm), zm[0][0], zm[0][1]))
        movidas = [b["t0"] - a_["t0"] for a_, b in emparejadas if abs(b["t0"] - a_["t0"]) > 0.1]
        if movidas and not clave.startswith("video:video"):
            cambios.append("moviste %d piezas de lugar" % len(movidas))
        if abs(da - dg) > 0.1:
            cambios.append("la pista pasó de %.1f s a %.1f s" % (dg, da))
        datos["pistas"][clave] = info
        if cambios:
            lineas.append("- **%s**: %s." % (clave, "; ".join(cambios)))
    tg, ta = _textos(G), _textos(A)
    corregidos = [(tg[k], ta[k]) for k in tg if k in ta and tg[k] != ta[k]]
    if corregidos:
        lineas += ["", "**Textos que corregiste** (%d):" % len(corregidos)]
        lineas += ["- «%s» → «%s»" % (x[:60], y[:60]) for x, y in corregidos[:15]]
        datos["textos_corregidos"] = corregidos
    if len(lineas) <= 4:
        lineas.append("No encontré cambios: o no lo editaste, o lo guardaste con otro nombre.")
    lineas += ["", "Lo que se repita en dos o tres videos es tu estilo: pídele a Claude que lo escriba en "
               "`mi_estilo.md` para que el editor lo haga solo la próxima vez."]
    os.makedirs(os.path.join(c, "aprendido"), exist_ok=True)
    escribir(os.path.join(c, "aprendido"), nombre + ".md", "\n".join(lineas) + "\n")
    escribir(os.path.join(c, "aprendido"), nombre + ".json", datos)
    print("\n".join(lineas))
