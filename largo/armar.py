"""Paso final: arma el video largo en CapCut con todo lo que este listo.

Lee el corte (`edl.json`) y, si existen, el stock (`stock_plan.json`), los graficos animados
(`motion/*.json`), el gancho visual (`gancho.json`) y la musica (`musica.json`). Lo que no
exista simplemente no entra: el largo sale igual, con menos capas.

    python largo.py armar <proyecto> [--nombre "Mi video"] [--subtitulos]

Ritmo: el plano se ALTERNA entre abierto y cerrado (zoom 1.15) en cada tramo de 0.9 s o mas.
En un video largo eso da movimiento sin la sensacion de «golpe» de un reel. Los graficos
tapan al stock (el stock se recorta donde choca), y cada grafico entra con un swish.
Los subtitulos van aparte en subtitulos.srt para subirlos a YouTube; quemarlos chocaria con
los graficos (--subtitulos los pone igual).
"""
import glob
import json
import os
import subprocess

from largo.comun import FR, escribir, leer, q, total_corte

ZOOM_CERRADO = 1.15


def _duracion(ruta):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", ruta],
                       capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def plan(c):
    from pipeline import nucleo
    proyecto = leer(c, "proyecto.json")
    SRC = proyecto["tomas"]
    E = leer(c, "edl.json")
    TOTAL = total_corte(E)

    segs, cerrado, acc, marcas = [], False, 0.0, [0.0]
    for t in E:
        acc += t["e"] - t["s"]
        marcas.append(q(acc))
    for i, (t, a, b) in enumerate(zip(E, marcas, marcas[1:])):
        if i > 0 and t["e"] - t["s"] >= 0.9:
            cerrado = not cerrado
        s = {"path": SRC[t["f"]], "ini": round(t["s"], 4), "fin": round(t["s"] + (b - a), 4)}
        if cerrado:
            s["zoom"] = {"punch": ZOOM_CERRADO, "ancla": 0.0}
        segs.append(s)
    # una pieza de menos de 2 cuadros hace que CapCut mueva la siguiente a otra pista al abrir
    corto = min(s["fin"] - s["ini"] for s in segs)
    if corto < 2 * FR - 1e-6:
        raise SystemExit("Quedo una pieza de %.3f s (menos de 2 cuadros). Revisa el corte." % corto)
    TL = marcas[-1]
    if abs(TL - TOTAL) > 0.05:
        raise SystemExit("La linea de tiempo (%.2f s) no dura lo que el corte (%.2f s)." % (TL, TOTAL))

    mov = []
    for p in sorted(glob.glob(os.path.join(c, "motion", "*.json"))):
        m = json.load(open(p, encoding="utf-8"))
        m["nombre"] = os.path.basename(p)[:-5]
        mov.append(m)
    # P* = panel que ocupa la pantalla (va en la pista del stock); L* = lateral encima del que habla
    paneles = [m for m in mov if m["nombre"].startswith("P")]
    laterales = [m for m in mov if m["nombre"].startswith("L")]
    tapa = [(m["ini"], m["fin"]) for m in mov]

    gv = leer(c, "gancho.json", falta={})
    if gv:
        tapa.append((0.0, gv["fin"]))

    broll, quitados = [], []
    for b in leer(c, "stock_plan.json", falta=[]):
        ini, fin = b["ini"], b["fin"]
        for a, z in tapa:
            if ini < z and a < fin:
                if a - ini >= 1.6:
                    fin = min(fin, a - 0.05)
                elif fin - z >= 1.6:
                    ini = max(ini, z + 0.05)
                else:
                    fin = ini
        if fin - ini >= 1.6:
            broll.append({"archivo": b["archivo"], "ini": ini, "fin": fin, "desde": 0.0, "stock": True})
        else:
            quitados.append(b["frase"])
    if gv:
        broll.append({"archivo": gv["archivo"], "ini": 0.0, "fin": gv["fin"], "desde": 0.0})
    for m in paneles:
        broll.append({"archivo": m["archivo"], "ini": m["ini"], "fin": min(m["fin"] - 0.02, TL), "desde": 0.0})
    for b in broll:
        b["ini"], b["fin"] = q(b["ini"]), min(q(b["fin"]), TL)
    broll.sort(key=lambda b: b["ini"])
    for x, y in zip(broll, broll[1:]):
        if y["ini"] < x["fin"] + FR:
            x["fin"] = round(y["ini"] - FR, 4)

    overlays = [{"archivo": m["archivo"], "pista": "graficas", "ini": q(m["ini"]),
                 "fin": min(q(m["fin"] - 0.02), TL), "escala": 1.0, "y": 0.0} for m in laterales]
    overlays.sort(key=lambda o: o["ini"])
    for o in overlays:   # una lateral no se queda encima de un panel que ya entro
        for m in paneles:
            if o["ini"] < m["ini"] < o["fin"]:
                o["fin"] = round(q(m["ini"]) - FR, 4)
    for x, y in zip(overlays, overlays[1:]):
        if y["ini"] < x["fin"] + FR:
            x["fin"] = round(y["ini"] - FR, 4)

    ev = [{"ini": round(m["ini"] - 0.05, 3), "tipo": "swish", "volumen": 0.6} for m in paneles]
    ev += [{"ini": round(m["ini"], 3), "tipo": "swish", "volumen": 0.4} for m in laterales]
    ev.sort(key=lambda e: e["ini"])
    limpio = []
    for e in ev:
        if not limpio or e["ini"] - limpio[-1]["ini"] >= 0.5:
            limpio.append(e)
    sfx = (nucleo._preparar_sfx({"sfx": limpio, "segmentos": segs}, TL, None, log=print) or []) if limpio else []
    for e in gv.get("sfx", []):
        dur = _duracion(e["archivo"])
        sfx.append(dict(e, tipo="gancho", desde=0.0, duracion=round(min(dur, e.get("max", 1.0)), 3)))
    sfx.sort(key=lambda e: e["ini"])

    musica = leer(c, "musica.json", falta=None)
    if musica:
        musica = dict(musica)
        if not os.path.isabs(musica["archivo"]):
            musica["archivo"] = os.path.join(c, musica["archivo"])
        if not os.path.exists(musica["archivo"]):
            raise SystemExit("musica.json apunta a un archivo que no existe: %s" % musica["archivo"])
        if "volumen" not in musica:
            # MEDIDO contra la voz del corte, con LUFS: en una charla las pausas hunden el
            # promedio de la voz y con el metodo de los reels la musica salia inaudible.
            from pipeline import musica as mu
            musica["volumen"] = mu.volumen_bajo_voz(musica["archivo"], os.path.join(c, "corte_audio.wav"),
                                                    metodo="lufs", log=print)
            print("  musica: volumen %.3f, medido contra la voz" % musica["volumen"])
        musica.setdefault("fade_in", 1_000_000)
    return {"segs": segs, "broll": broll, "overlays": overlays, "sfx": sfx, "musica": musica,
            "TL": TL, "lienzo": tuple(proyecto["lienzo"]), "quitados": quitados}


def main(c, nombre=None, subtitulos=False):
    from pipeline import capcut_lib as cl
    p = plan(c)
    nombre = nombre or os.path.basename(c.rstrip("/\\")) + " LARGO"
    stock_s = sum(b["fin"] - b["ini"] for b in p["broll"] if b.get("stock"))
    print("linea de tiempo %.1f s | stock %.1f s (%.0f%%) | graficos %d | sonidos %d | musica %s"
          % (p["TL"], stock_s, stock_s / p["TL"] * 100, len(p["overlays"]) + len([b for b in p["broll"] if not b.get("stock")]),
             len(p["sfx"]), "si" if p["musica"] else "no"))
    if p["quitados"]:
        print("  stock que no cupo junto a un grafico: %s" % ", ".join(p["quitados"]))
    for b in p["broll"]:
        b.pop("stock", None)
    w, h, fps = p["lienzo"]
    r = cl.construir_segmentos(nombre, p["segs"], (w, h, fps), zoom="no", broll=p["broll"], overlays=p["overlays"],
                               sfx=p["sfx"] or None, musica=p["musica"], captions="clasico",
                               srt_path=os.path.join(c, "subtitulos.srt") if subtitulos else None)
    escribir(c, "armado.json", {k: p[k] for k in ("segs", "broll", "overlays", "sfx")})
    from largo import aprender
    aprender.guardar_generado(c, nombre)   # para `largo.py aprender`: que cambio el usuario despues
    print("CREADO en CapCut: %r | %d piezas | %d encima | %d sonidos | %.1f s"
          % (nombre, r["segmentos"], r["broll"] + r["overlays"], r["sfx"], r["duracion_us"] / 1e6))
