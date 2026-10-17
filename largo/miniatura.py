"""Paso opcional: miniaturas de YouTube con un cuadro REAL del video y la marca.

Busca en el corte los cuadros donde la cara se ve bien (detector YuNet: cara grande, de
frente, nitida), deja una hoja con los candidatos y compone las miniaturas que pidas en
`miniatura.json`, con los colores y la letra de tu marca. No necesita Magnific: la cara sale
de un fotograma real, que es lo que da confianza. (Con Magnific se puede ademas recortar el
fondo; eso es aparte.)

    python largo.py miniatura <proyecto>              # candidatos -> miniatura/candidatos.jpg
    python largo.py miniatura <proyecto> --componer    # miniatura.json -> miniatura/A.png, B.png...

Formato de miniatura.json:

    {"marca": "ejemplo", "cuadro": 3,
     "opciones": [{"nombre": "A", "texto": "¿A quién NO\\nle hablas?", "sub": "tu último anuncio"},
                  {"nombre": "B", "texto": "Nadie lo\\ndecidió", "sub": null}]}

Reglas: todo lo legible en el 85 % de arriba (YouTube tapa la esquina de abajo con la duracion);
pocas palabras, enormes; se revisa en chico (`- vista 320.png`), que es como la ve casi todo el mundo.
"""
import json
import os
import subprocess

from largo.comun import RAIZ, escribir, leer

ANCHO, ALTO = 1280, 720


def _cuadro(src, t, ruta):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % t, "-i", src, "-frames:v", "1", ruta], check=True)


def candidatos(c, n=8):
    import cv2
    E = leer(c, "edl.json")
    src = leer(c, "proyecto.json")["tomas"]
    modelo = os.path.join(RAIZ, "recursos", "modelos", "face_detection_yunet_2023mar.onnx")
    sal = os.path.join(c, "miniatura")
    os.makedirs(sal, exist_ok=True)
    puntos = []
    for t in E:
        for f in (0.3, 0.6):
            ts = t["s"] + (t["e"] - t["s"]) * f
            cap = cv2.VideoCapture(src[t["f"]])
            cap.set(cv2.CAP_PROP_POS_MSEC, ts * 1000)
            ok, img = cap.read()
            cap.release()
            if not ok:
                continue
            h, w = img.shape[:2]
            det = cv2.FaceDetectorYN.create(modelo, "", (w, h), 0.7, 0.3, 5000)
            _, caras = det.detect(img)
            if caras is None or not len(caras):
                continue
            x, y, cw, ch = [int(v) for v in max(caras, key=lambda q: q[2] * q[3])[:4]]
            gris = cv2.cvtColor(img[max(0, y):y + ch, max(0, x):x + cw], cv2.COLOR_BGR2GRAY)
            nitidez = float(cv2.Laplacian(gris, cv2.CV_64F).var()) if gris.size else 0.0
            confianza = float(max(caras, key=lambda q: q[2] * q[3])[-1])
            puntos.append({"toma": t["f"], "t": round(ts, 2), "score": round(nitidez * confianza * (cw * ch) / (w * h), 3)})
    puntos.sort(key=lambda p: -p["score"])
    elegidos, ultimos = [], []
    for p in puntos:   # que no sean el mismo instante
        if all(abs(p["t"] - u) > 3 for u in ultimos):
            elegidos.append(p)
            ultimos.append(p["t"])
        if len(elegidos) >= n:
            break
    from PIL import Image, ImageDraw
    hoja = Image.new("RGB", (4 * 480, ((len(elegidos) + 3) // 4) * 290), (25, 25, 25))
    for k, p in enumerate(elegidos):
        ruta = os.path.join(sal, "cuadro_%d.png" % k)
        _cuadro(src[p["toma"]], p["t"], ruta)
        p["archivo"] = ruta
        im = Image.open(ruta).convert("RGB").resize((480, 270))
        hoja.paste(im, ((k % 4) * 480, (k // 4) * 290))
        ImageDraw.Draw(hoja).text(((k % 4) * 480 + 8, (k // 4) * 290 + 272), "%d  ·  %.1f s" % (k, p["t"]), fill=(230, 230, 230))
    hoja.save(os.path.join(sal, "candidatos.jpg"), quality=88)
    escribir(sal, "candidatos.json", elegidos)
    print("%d cuadros candidatos -> miniatura/candidatos.jpg. MIRALA y pon el numero en miniatura.json (\"cuadro\")."
          % len(elegidos))


def _hex(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _fuente(nombre, tam):
    from PIL import ImageFont
    for archivo in ("%s-Bold.ttf" % nombre.replace(" ", ""), "Poppins-Bold.ttf"):
        r = os.path.join(RAIZ, "recursos", "fuentes", archivo)
        if os.path.exists(r):
            return ImageFont.truetype(r, tam)
    return ImageFont.load_default()


def componer(c):
    from PIL import Image, ImageDraw, ImageFilter
    cfg = leer(c, "miniatura.json")
    cands = leer(os.path.join(c, "miniatura"), "candidatos.json")
    m = json.load(open(os.path.join(RAIZ, "recursos", "marcas", cfg.get("marca", "ejemplo") + ".json"), encoding="utf-8"))
    col = m["colores"]
    base = Image.open(cands[cfg.get("cuadro", 0)]["archivo"]).convert("RGB")
    # la cara a la DERECHA (al 70 % del ancho) y un poco mas cerca: el texto vive a la izquierda y
    # no puede tocar la cabeza. Se usa el centro de cara MEDIDO (cara.json) si existe.
    caraj = leer(c, "cara.json", falta={"x": 0.5, "y": 0.45})
    w, h = base.size
    zoom = 1.3
    esc = ALTO * zoom / h
    base = base.resize((int(w * esc), int(h * esc)))
    fx, fy = caraj["x"] * base.width, caraj["y"] * base.height
    x0 = int(min(max(0, fx - 0.70 * ANCHO), base.width - ANCHO))
    y0 = int(min(max(0, fy - 0.42 * ALTO), base.height - ALTO))
    base = base.crop((x0, y0, x0 + ANCHO, y0 + ALTO))
    for op in cfg["opciones"]:
        im = base.copy()
        # degradado de la marca de izquierda a derecha, para que el texto se lea sobre cualquier fondo
        capa = Image.new("RGBA", (ANCHO, ALTO))
        dc = ImageDraw.Draw(capa)
        r, g, b = _hex(col["fondo2"]) if col["fondo2"].startswith("#") else (20, 28, 48)
        for x in range(ANCHO):
            a = int(245 * max(0.0, 1 - x / (ANCHO * 0.62)) ** 0.8)
            dc.line([(x, 0), (x, ALTO)], fill=(r, g, b, a))
        im = Image.alpha_composite(im.convert("RGBA"), capa)
        d = ImageDraw.Draw(im)
        tam = 118
        lineas = op["texto"].split("\n")
        f = _fuente(m["letras"].get("titulos", "Poppins"), tam)
        while max(d.textlength(ln, font=f) for ln in lineas) > ANCHO * 0.50 and tam > 60:
            tam -= 6
            f = _fuente(m["letras"].get("titulos", "Poppins"), tam)
        y = 70
        acento = _hex(col["acento"])
        for k, ln in enumerate(lineas):
            d.text((60, y), ln, font=f, fill=acento if k == len(lineas) - 1 else _hex(col["texto"]),
                   stroke_width=3, stroke_fill=(0, 0, 0))
            y += int(tam * 1.08)
        if op.get("sub"):
            fs = _fuente(m["letras"].get("cuerpo", "Poppins"), 44)
            d.text((62, y + 14), op["sub"], font=fs, fill=_hex(col["texto"]), stroke_width=2, stroke_fill=(0, 0, 0))
            y += 70
        if y > ALTO * 0.85:
            print("  AVISO %s: el texto baja del 85 %% del alto; ahi YouTube pone la duracion" % op["nombre"])
        sal = os.path.join(c, "miniatura", "%s.png" % op["nombre"])
        im.convert("RGB").save(sal)
        im.convert("RGB").resize((320, 180), Image.LANCZOS).save(sal[:-4] + " - vista 320.png")
        print("miniatura %s -> %s (y la vista en chico)" % (op["nombre"], sal))
