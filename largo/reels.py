"""Paso 7 (opcional): reels verticales sacados del LARGO, en el estilo VENTANA.

Cada reel es una pieza continua del largo (35-60 s) con un GANCHO al principio (una frase
fuerte de dentro de esa misma pieza), subtitulos palabra por palabra, una FRASE CLAVE grande
y, en el momento de la explicacion, la VENTANA: la persona se reduce a un hueco y la grafica
vive arriba (sigue hablando). Lo que el reel necesita se escribe en `reels.json`; los tiempos,
como siempre, son FRASES.

    python largo.py reels <proyecto> [nombre ...]      (CapCut cerrado)

Formato de reels.json:

    {"marca": "ejemplo", "cierre": "recursos/cta/mi_cierre.png",      (cierre opcional)
     "reels": [
      {"nombre": "R1 la culpa",
       "gancho": {"desde": "nadie se sento a decidir", "hasta": "ibas a hablar"},
       "cuerpo": [{"desde": "al principio te dije", "hasta": "que me escriba"}],
       "frase_clave": {"ancla": "a quien le ibas a hablar", "texto": "¿A quién le hablas?"},
       "ventana": {"desde": {"frase": "agarra el ultimo"}, "hasta": {"frase": "que me escriba", "fin": true},
                   "T": {"etiqueta": "Tu tarea", "titulo": "Tu último anuncio", "filas": [...]}}}]}

Reglas (medidas en reels aprobados):
- UNA pieza continua; el gancho se saca de DENTRO de esa pieza. Tres tramos distantes pegados
  no se entienden. 35-60 s: menos de ~25 es un gancho sin remate.
- La ventana nunca cae sobre el gancho ni sobre los ultimos 2 s (ahi va el cierre).
- La frase clave va fuera de la ventana y nunca en los ultimos 3 s.
"""
import copy
import json
import os
import subprocess
import sys

from largo.comun import FR, RAIZ, escribir, leer, norm, total_corte

W, H = 1080, 1920
VEN = [40, 840, 1040, 1620]          # el hueco de la ventana (x0, y0, x1, y1)
ZOOMS = (1.12, 1.25)                 # plano abierto / cerrado, alternando en cada corte de 0.9 s o mas
CAPTION_Y = -0.50                    # 75 % del alto: debajo de la barbilla
FRASE_Y = 0.76                       # 12 % del alto, sobre la cabeza
BANCO = os.path.join(RAIZ, "recursos", "escenas")


def cara(c, E, src):
    """Centro de la cara (x, y en 0-1) medido con YuNet en varios cuadros del corte.

    Si no se puede medir (sin opencv o sin cara clara) se dice y se usa el centro: un valor
    de reserva que viaja callado como si fuera medido es justo lo que no puede pasar.
    """
    cache = leer(c, "cara.json", falta=None)
    if cache:
        return cache["x"], cache["y"]
    try:
        import cv2
    except ImportError:
        print("  aviso: sin opencv-python no se mide la cara; encuadro al centro (pip install opencv-python)")
        return 0.5, 0.45
    modelo = os.path.join(RAIZ, "recursos", "modelos", "face_detection_yunet_2023mar.onnx")
    xs, ys = [], []
    for t in E[:: max(1, len(E) // 9)][:9]:
        cap = cv2.VideoCapture(src[t["f"]])
        cap.set(cv2.CAP_PROP_POS_MSEC, (t["s"] + t["e"]) / 2 * 1000)
        ok, img = cap.read()
        cap.release()
        if not ok:
            continue
        h, w = img.shape[:2]
        det = cv2.FaceDetectorYN.create(modelo, "", (w, h), 0.6, 0.3, 5000)
        _, caras = det.detect(img)
        if caras is not None and len(caras):
            x, y, cw, ch = max(caras, key=lambda f: f[2] * f[3])[:4]
            xs.append((x + cw / 2) / w)
            ys.append((y + ch / 2) / h)
    if len(xs) < 3:
        print("  aviso: no encontre la cara en suficientes cuadros (%d); encuadro al centro" % len(xs))
        return 0.5, 0.45
    xs.sort()
    ys.sort()
    x, y = round(float(xs[len(xs) // 2]), 3), round(float(ys[len(ys) // 2]), 3)
    escribir(c, "cara.json", {"x": x, "y": y, "cuadros": len(xs)})
    print("  cara medida en %d cuadros: x %.3f  y %.3f" % (len(xs), x, y))
    return x, y


class Largo:
    """El largo ya cortado: sus palabras (tl.json), sus cortes y sus piezas de origen."""

    def __init__(self, c):
        self.c = c
        self.E = leer(c, "edl.json")
        self.TL = leer(c, "tl.json")
        self.total = total_corte(self.E)
        self.src = leer(c, "proyecto.json")["tomas"]
        acc, self.cortes = 0.0, []
        for t in self.E:
            acc += t["e"] - t["s"]
            self.cortes.append(acc)
        ancho, alto = leer(c, "proyecto.json")["lienzo"][:2]
        from pipeline import capcut_lib as cl
        self.llenar = cl.escala_para_llenar(ancho, alto, W, H)
        self.cx, self.cy = cara(c, self.E, self.src)

    def buscar(self, frase, despues=0.0, fin=False):
        q = [norm(x) for x in frase.split() if norm(x)]
        for i in range(len(self.TL) - len(q) + 1):
            if self.TL[i]["s"] >= despues and all(self.TL[i + j]["n"] == q[j] for j in range(len(q))):
                return i, i + len(q) - 1
        raise SystemExit("NO ENCONTRE %r despues de %.1f s en el texto limpio." % (frase, despues))

    def tramo(self, desde, hasta, despues=0.0):
        """(t0, t1, ia, ib): un tramo del largo por frases, pegado a los cortes ya hechos."""
        ia, _ = self.buscar(desde, despues)
        _, ib = self.buscar(hasta, self.TL[ia]["s"])
        a, b = self.TL[ia]["s"], self.TL[ib]["e"]
        t0 = max(a - 0.12, self.TL[ia - 1]["e"] + 0.02 if ia else 0.0)
        t1 = min(b + 0.30, self.TL[ib + 1]["s"] - 0.03 if ib + 1 < len(self.TL) else self.total)
        c = [x for x in [0.0] + self.cortes if t0 - 0.2 <= x <= a + 0.02]
        if c:
            t0 = c[-1]
        c = [x for x in self.cortes if b - 0.02 <= x <= b + 0.8]   # hasta el fin del tramo del largo (por audio)
        if c:
            t1 = c[0]
        return t0, t1, ia, ib

    def piezas(self, t0, t1):
        out, base = [], 0.0
        for p in self.E:
            d = p["e"] - p["s"]
            a, b = max(t0, base), min(t1, base + d)
            if b - a > FR:
                out.append({"f": p["f"], "ini": p["s"] + a - base, "fin": p["s"] + b - base, "et": p["et"]})
            base += d
        return out

    def recortar(self, t0, t1):
        """Un pedacito de menos de 0.4 s de OTRO tramo en la orilla se deja fuera (se colaba la cola del vecino)."""
        while True:
            out = self.piezas(t0, t1)
            if not out:
                return t0, t1
            largo = max(out, key=lambda x: x["fin"] - x["ini"])["et"]
            if out[0]["et"] != largo and out[0]["fin"] - out[0]["ini"] < 0.4:
                t0 += out[0]["fin"] - out[0]["ini"]
                continue
            if out[-1]["et"] != largo and out[-1]["fin"] - out[-1]["ini"] < 0.4:
                t1 -= out[-1]["fin"] - out[-1]["ini"]
                continue
            return t0, t1

    def encuadre(self, z):
        S = self.llenar * z
        # y NEGATIVA = la imagen baja: aire arriba de la cabeza para la frase clave
        return {"punch": round(S, 4), "x": round(-2 * S * (self.cx - 0.5), 4),
                "y": round(-(z - 1.0) * 0.85 + 2 * z * (self.cy - 0.42), 4)}


def _limpiar(p):
    return p.strip("“”\"'.,;:").strip() or p


def plan_reel(L, r, stock):
    partes = []
    for k, tr in enumerate([r["gancho"]] + r["cuerpo"]):
        t0, t1, ia, ib = L.tramo(tr["desde"], tr["hasta"], tr.get("despues", 0.0))
        t0, t1 = L.recortar(t0, t1)
        pal = [{"word": w["w"], "start": w["s"] - t0, "end": w["e"] - t0}
               for w in L.TL[ia:ib + 1] if w["e"] > t0 + 0.02 and w["s"] < t1 - 0.02]
        partes.append((L.piezas(t0, t1), pal, t1 - t0, (t0, t1), k == 0))
    segs, palabras, broll, cursor, zi = [], [], [], 0.0, 0
    gancho_fin = partes[0][2]
    for pz, pal, d, rng, es_gancho in partes:
        for p in pz:
            if segs and p["fin"] - p["ini"] >= 0.9:
                zi ^= 1
            segs.append({"path": L.src[p["f"]], "ini": round(p["ini"], 3), "fin": round(p["fin"], 3),
                         "zoom": L.encuadre(ZOOMS[zi])})
        for w in pal:
            palabras.append({"word": _limpiar(w["word"]), "start": round(max(0.0, w["start"]) + cursor, 3),
                             "end": round(min(w["end"], d - 0.01) + cursor, 3)})
        if not es_gancho:   # el stock del largo que cae en este tramo (nunca en el gancho)
            for s in stock:
                a, b = max(s["ini"], rng[0]), min(s["fin"], rng[1])
                if b - a >= 1.4:
                    broll.append({"archivo": s["archivo"], "ini": round(a - rng[0] + cursor, 2),
                                  "fin": round(b - rng[0] + cursor, 2), "desde": round(s.get("desde", 0) + a - s["ini"], 2)})
        cursor += d
    total = round(cursor, 3)
    # palabras sin duracion (Whisper no las oyo): CapCut no las dibuja. Se reparte el hueco sin encimarlas.
    i = 0
    while i < len(palabras):
        if palabras[i]["end"] - palabras[i]["start"] >= 0.05:
            i += 1
            continue
        j = i
        while j + 1 < len(palabras) and palabras[j + 1]["end"] - palabras[j + 1]["start"] < 0.05:
            j += 1
        n_ = j - i + 1
        lo = palabras[i - 1]["end"] + 0.005 if i else max(0.0, palabras[i]["start"])
        hi = palabras[j + 1]["start"] - 0.005 if j + 1 < len(palabras) else total
        falta = 0.08 * n_ - (hi - lo)
        if falta > 0 and i:
            quita = min(falta, max(0.0, palabras[i - 1]["end"] - palabras[i - 1]["start"] - 0.08))
            palabras[i - 1]["end"] = round(palabras[i - 1]["end"] - quita, 3)
            lo -= quita
            falta -= quita
        if falta > 0 and j + 1 < len(palabras):
            sg = palabras[j + 1]
            quita = min(falta, max(0.0, sg["end"] - sg["start"] - 0.08))
            sg["start"] = round(sg["start"] + quita, 3)
            hi += quita
        paso = (hi - lo) / n_
        for k in range(n_):
            palabras[i + k]["start"] = round(lo + k * paso, 3)
            palabras[i + k]["end"] = round(lo + (k + 1) * paso - 0.003, 3)
        i = j + 1
    malas = [w["word"] for k, w in enumerate(palabras)
             if w["end"] - w["start"] < 0.05 or (k and w["start"] < palabras[k - 1]["end"] - 1e-6)]
    if malas:
        raise SystemExit("%s: palabras sin tiempo o encimadas: %s" % (r["nombre"], malas))
    frases = []
    if r.get("frase_clave"):
        ws = [norm(w["word"]) for w in palabras]
        q = [norm(x) for x in r["frase_clave"]["ancla"].split() if norm(x)]
        hits = [k for k in range(len(ws) - len(q) + 1) if ws[k:k + len(q)] == q]
        if not hits:
            raise SystemExit("%s: la frase clave %r no esta en el reel" % (r["nombre"], r["frase_clave"]["ancla"]))
        k = hits[-1]     # la ULTIMA: en el gancho repetido tambien aparece
        a, z = palabras[k]["start"], palabras[k + len(q) - 1]["end"]
        if a >= total - 3.0:
            raise SystemExit("%s: la frase clave cae en los ultimos 3 s (ahi va el cierre)" % r["nombre"])
        frases.append({"ini": round(a - 0.05, 2), "fin": round(min(total - 2.1, max(z + 0.6, a + 2.0)), 2),
                       "texto": r["frase_clave"]["texto"], "altura": FRASE_Y, "escala": 0.8, "estilo": "bloque"})
        c0 = 0.0     # durante la frase clave, zoom chico (al 125 % el pelo sube hasta la frase)
        for sg in segs:
            c1 = c0 + sg["fin"] - sg["ini"]
            if frases[0]["ini"] < c1 and c0 < frases[0]["fin"]:
                sg["zoom"] = L.encuadre(ZOOMS[0])
            c0 = c1
    return {"nombre": r["nombre"], "total": total, "gancho_fin": round(gancho_fin, 3), "segmentos": segs,
            "palabras": palabras, "broll": broll, "frases": frases}


def tiempo_reel(plan, frase, despues=-1.0, fin=False):
    p = plan["palabras"]
    n = [norm(w["word"]) for w in p]
    q = [norm(x) for x in frase.split() if norm(x)]
    for i in range(len(n) - len(q) + 1):
        if p[i]["start"] > despues and n[i:i + len(q)] == q:
            return p[i + len(q) - 1]["end"] if fin else p[i]["start"]
    raise SystemExit("%s: no encuentro %r despues de %.2f" % (plan["nombre"], frase, despues))


def resolver(x, plan, despues):
    if isinstance(x, dict) and "frase" in x and set(x) <= {"frase", "fin", "mas", "despues"}:
        return round(tiempo_reel(plan, x["frase"], x.get("despues", despues), x.get("fin", False)) + x.get("mas", 0.0), 3)
    if isinstance(x, dict):
        return {k: resolver(v, plan, despues) for k, v in x.items()}
    if isinstance(x, list):
        return [resolver(v, plan, despues) for v in x]
    return x


def ventana(c, plan, v, marca):
    t0 = max(resolver(v["desde"], plan, -1.0) - 0.2, plan["gancho_fin"] + 0.02)
    t1 = min(resolver(v["hasta"], plan, t0), plan["total"] - 2.1)
    datos = resolver(copy.deepcopy(v.get("T", {})), plan, t0 - 0.3)
    for k, d in (("filas", []), ("pie", None), ("titulo", "")):
        datos.setdefault(k, d)
    datos.update(t_in=t0, t_out=t1 + 0.5, ven=VEN)
    sal = os.path.join(c, "reels")
    dest = os.path.join(sal, plan["nombre"] + " - ventana.mov")
    args = [sys.executable, os.path.join(BANCO, "capturar.py"), os.path.join(BANCO, "tarjetas", "ventana.html"), dest,
            "%.3f" % (t1 - t0 + 0.5), "--vertical", "--alfa", "--desde", "%.3f" % t0, "--marca", marca,
            "--T", json.dumps(datos, ensure_ascii=False), "--claves", "%.2f,%.2f,%.2f" % (t0 + 0.6, (t0 + t1) / 2, t1 - 0.3)]
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    if r.returncode:
        raise SystemExit("%s ventana: %s" % (plan["nombre"], (r.stderr or r.stdout)[-800:]))
    return {"archivo": dest.replace("\\", "/"), "ini": round(t0, 3), "fin": round(t1 + 0.1, 3), "t0": t0, "t1": t1}


def armar(L, plan, mo, cierre):
    from pipeline import capcut_lib as cl, nucleo
    A, B = mo["t0"], mo["t1"]
    escala = max((VEN[2] - VEN[0]) / W, (VEN[3] - VEN[1]) / (W * 9 / 16))
    # en la ventana la CARA se ve grande: 1.55 veces el encaje y la cara al 45 % del alto del hueco
    esc2 = escala * 1.55
    fh, fw = 607.5 * esc2, 1080 * esc2
    cara_y = VEN[1] + 0.45 * (VEN[3] - VEN[1])
    cy = cara_y - (L.cy - 0.5) * fh
    cx = (VEN[0] + VEN[2]) / 2 - (L.cx - 0.5) * fw
    VZ = {"punch": round(esc2, 4), "x": round((cx - W / 2) / (W / 2), 4), "y": round((H / 2 - cy) / (H / 2), 4)}
    segs, cur = [], 0.0
    for s in plan["segmentos"]:
        dur = s["fin"] - s["ini"]
        trozos = [(cur, cur + dur)]
        for corte in (A, B):
            nuevos = []
            for a, b in trozos:
                nuevos += [(a, corte), (corte, b)] if a < corte < b else [(a, b)]
            trozos = nuevos
        for a, b in trozos:
            t = dict(s, ini=round(s["ini"] + (a - cur), 3), fin=round(s["ini"] + (b - cur), 3))
            if A <= a + 0.01 and b <= B + 0.01:
                t["zoom"] = VZ
            segs.append(t)
        cur += dur
    # CapCut redondea cada pieza al cuadro al abrir: un pedazo de menos de 2 cuadros mandaba la
    # pieza siguiente a OTRA pista (todo se recorria, audio doble). Se une a su vecina de la misma toma.
    i = 0
    while i < len(segs):
        sg = segs[i]
        if sg["fin"] - sg["ini"] < 2 * FR:
            sig = segs[i + 1] if i + 1 < len(segs) else None
            ant = segs[i - 1] if i else None
            if sig and sig["path"] == sg["path"] and abs(sig["ini"] - sg["fin"]) < 1e-3:
                sig["ini"] = sg["ini"]
                segs.pop(i)
                continue
            if ant and ant["path"] == sg["path"] and abs(ant["fin"] - sg["ini"]) < 1e-3:
                ant["fin"] = sg["fin"]
                segs.pop(i)
                continue
            sg["fin"] = round(sg["ini"] + 2 * FR, 4)
        i += 1
    c, qm = 0.0, [0.0]
    for sg in segs:
        c += sg["fin"] - sg["ini"]
        qm.append(round(c / FR) * FR)
    for sg, a0, b0 in zip(segs, qm, qm[1:]):
        sg["fin"] = round(sg["ini"] + (b0 - a0), 4)
    A, B = round(A / FR) * FR, round(B / FR) * FR
    total = round(sum(s["fin"] - s["ini"] for s in segs), 3)
    broll = [b for b in plan["broll"] if not (b["ini"] < B and A < b["fin"])]
    c0, ini_v, fin_v = 0.0, None, None
    for sg in segs:   # la grafica entra en el MISMO cuadro en que la persona se encoge
        if sg.get("zoom") is VZ:
            ini_v = c0 if ini_v is None else ini_v
            fin_v = c0 + sg["fin"] - sg["ini"]
        c0 += sg["fin"] - sg["ini"]
    if ini_v is None:
        raise SystemExit("%s: la ventana no cayo sobre ningun corte" % plan["nombre"])
    broll.append({"archivo": mo["archivo"], "ini": round(ini_v, 4), "fin": min(mo["fin"] - 0.02, total - 2.05),
                  "desde": round(max(0.0, ini_v - mo["ini"]), 4)})
    broll.sort(key=lambda b: b["ini"])
    for b in broll:
        b["ini"], b["fin"] = round(round(b["ini"] / FR) * FR, 4), round(round(b["fin"] / FR) * FR, 4)
    for x, y in zip(broll, broll[1:]):
        if y["ini"] < x["fin"] + FR:
            x["fin"] = round(y["ini"] - FR, 4)
    frases = []
    for f in plan["frases"]:   # fuera de la ventana: si apenas se encima, entra al cerrarse o se acorta
        if f["ini"] < B and A < f["fin"]:
            if f["fin"] - B >= 1.4:
                f = dict(f, ini=round(B + 0.05, 2))
            elif A - f["ini"] >= 1.2:
                f = dict(f, fin=round(A - 0.05, 2))
            else:
                print("  AVISO: la frase clave %r chocaba con la ventana y no cabia ni antes ni despues: "
                      "SE QUITO. Ancla la frase antes o mueve la ventana." % f["texto"])
                continue
        frases.append(f)
    ev = [{"ini": round(plan["gancho_fin"] - 0.13, 3), "tipo": "swish", "volumen": 0.6},
          {"ini": round(A - 0.05, 3), "tipo": "swish", "volumen": 0.6},
          {"ini": round(B - 0.1, 3), "tipo": "swish", "volumen": 0.35}]
    ev.sort(key=lambda e: e["ini"])
    limpio = []
    for e in ev:
        if not limpio or e["ini"] - limpio[-1]["ini"] >= 0.5:
            limpio.append(e)
    sfx = nucleo._preparar_sfx({"sfx": limpio, "segmentos": segs}, total, plan["palabras"], log=lambda *a: None) or []
    overlays = []
    if cierre:
        overlays.append({"archivo": cierre, "pista": "cierre", "ini": round(round((total - 2.0) / FR) * FR, 4),
                         "fin": total, "escala": 0.89, "y": 0.76})
    r = cl.construir_segmentos(plan["nombre"], segs, (W, H, 30), palabras=plan["palabras"], captions="palabra",
                               zoom="no", broll=broll, frases=frases, overlays=overlays or None, sfx=sfx or None,
                               letras="resalte", caption_altura=CAPTION_Y)
    print("CREADO %-26s %.1f s | ventana %.1f-%.1f | %d cortes | subtitulos %d | %d encima | %d sonidos | frase: %s"
          % (plan["nombre"], total, A, B, len(segs), r.get("subtitulos", 0), r["broll"] + r["overlays"], r["sfx"],
             ", ".join(f["texto"] for f in frases) or "-"))


def main(c, solo=None):
    cfg = leer(c, "reels.json")
    marca = cfg.get("marca", "ejemplo")
    cierre = cfg.get("cierre")
    if cierre and not os.path.isabs(cierre):
        cierre = os.path.join(RAIZ, cierre)
    if cierre and not os.path.exists(cierre):
        print("  aviso: no existe la tarjeta de cierre %s; los reels salen sin ella" % cierre)
        cierre = None
    L = Largo(c)
    stock = leer(c, "stock_plan.json", falta=[])
    os.makedirs(os.path.join(c, "reels"), exist_ok=True)
    for r in cfg["reels"]:
        if solo and not any(s in r["nombre"] for s in solo):
            continue
        plan = plan_reel(L, r, stock)
        print("%-26s %5.1f s | gancho %.1f s | %s" % (r["nombre"], plan["total"], plan["gancho_fin"],
                                                     " ".join(w["word"] for w in plan["palabras"])[:150]))
        if plan["total"] < 25:
            print("  aviso: menos de 25 s suele ser un gancho sin remate")
        escribir(os.path.join(c, "reels"), r["nombre"] + ".json", plan)
        if r.get("ventana"):
            mo = ventana(c, plan, r["ventana"], marca)
        else:
            raise SystemExit("%s: falta 'ventana' (por ahora cada reel lleva una)" % r["nombre"])
        armar(L, plan, mo, cierre)
    print("\nMIRA las hojas de las ventanas (reels/* - ventana - hoja.jpg) y abre cada reel en CapCut.")
