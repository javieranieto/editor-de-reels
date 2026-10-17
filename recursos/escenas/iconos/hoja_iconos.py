"""Hoja de los íconos del banco en cada marca de recursos/marcas/, sobre tarjeta oscura, en dos momentos de su animación."""
import json, os
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw
AQ = os.path.dirname(os.path.abspath(__file__)); fuentes = json.load(open(os.path.join(AQ, "fuentes.json"), encoding="utf-8"))
nombres = list(fuentes); T = 180; cols = len(nombres)
_js = open(os.path.join(AQ, "iconos.js"), encoding="utf-8").read()
marcas = list(json.loads(_js[_js.index("=") + 1:].strip().rstrip(";")).keys())
filas = [(m, f) for m in marcas for f in (0.35, 0.8)]
hoja = Image.new("RGB", (cols * T, len(filas) * (T + 20)), (20, 24, 38))
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": T, "height": T})
    pg.goto("file:///" + os.path.join(AQ, "icono.html").replace("\\", "/")); pg.wait_for_timeout(300)
    pg.add_style_tag(content="body{background:#242f4a!important}")
    for r, (m, frac) in enumerate(filas):
        for i, n in enumerate(nombres):
            pg.evaluate("""([n,m,frac]) => { const d=window.ICONOS[m][n]; render((d.op-d.ip)*frac/d.fr, {icono:n, marca:m, tam:150}); }""", [n, m, frac])
            pg.screenshot(path="_t.png"); hoja.paste(Image.open("_t.png").convert("RGB"), (i * T, r * (T + 20)))
            if r == 0: ImageDraw.Draw(hoja).text((i * T + 6, T + 3), n, fill=(200, 210, 230))
    b.close()
os.remove("_t.png"); hoja.save(os.path.join(AQ, "hoja_iconos.jpg"), quality=88); print(hoja.size)
