"""Captura una ESCENA DE PANTALLA (HTML con una función render(t, T, escena)) cuadro por cuadro con Chromium y la
vuelve .mp4. Es el motor del banco de escenas: sombras, desenfoque y 3D reales, letra exacta, tiempos amarrados a la voz.
Uso:  python capturar.py <archivo.html> <salida.mp4> <segundos> --T '{"esc": 1.98, "uno": 4.22}' [--escena chats2]
      [--vertical] [--claves 0.5,2.6,4.8]   (las claves guardan una hoja de cuadros para MIRARLA antes de usarla)
      [--desde S] empieza en el segundo S de la escena (las claves también son absolutas)
      [--alfa]  fondo TRANSPARENTE -> .mov qtrle/argb (lo que CapCut acepta con alfa), para tarjetas encima del video.
                La escena debe poner <body class="alfa">.  La hoja de claves se pinta sobre gris para verla.
      [--marca ID]  la marca de recursos/marcas/<ID>.json (colores, letras, firma). Por defecto la que traiga T,
                o "ejemplo"."""
import argparse, json, os, subprocess, sys
from playwright.sync_api import sync_playwright
a = argparse.ArgumentParser(); a.add_argument("html"); a.add_argument("salida"); a.add_argument("segundos", type=float)
a.add_argument("--T", default="{}"); a.add_argument("--escena", default=""); a.add_argument("--vertical", action="store_true")
a.add_argument("--claves", default=""); a.add_argument("--fps", type=int, default=30); a.add_argument("--alfa", action="store_true")
a.add_argument("--marca", default="")
a.add_argument("--desde", type=float, default=0.0)   # el primer cuadro es el segundo «desde» de la escena (tiempos absolutos del video)
o = a.parse_args(); W, H = (1080, 1920) if o.vertical else (1920, 1080); T = json.loads(o.T)
DIR_MARCAS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "marcas")
MARCAS = {}
for f in sorted(os.listdir(DIR_MARCAS)):
    if f.endswith(".json"):
        m = json.load(open(os.path.join(DIR_MARCAS, f), encoding="utf-8")); MARCAS[m["id"]] = m
if o.marca: T["marca"] = o.marca
T.setdefault("marca", "ejemplo")
# los iconos se recolorean con las marcas que haya: si falta iconos.js o una marca es mas nueva, se rearma
ICONOS_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "iconos", "iconos.js")
if not os.path.exists(ICONOS_JS) or any(os.path.getmtime(os.path.join(DIR_MARCAS, f)) > os.path.getmtime(ICONOS_JS)
                                        for f in os.listdir(DIR_MARCAS) if f.endswith(".json")):
    subprocess.run([sys.executable, os.path.join(os.path.dirname(ICONOS_JS), "armar_iconos.py")], check=True)
if T["marca"] not in MARCAS:
    raise SystemExit("No existe la marca %r. Hay: %s (en recursos/marcas/)" % (T["marca"], ", ".join(MARCAS)))
n = int(round(o.segundos * o.fps))
cod = ["-c:v", "qtrle", "-pix_fmt", "argb"] if o.alfa else ["-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p"]
ff = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(o.fps), "-i", "-"] + cod + [o.salida],
                      stdin=subprocess.PIPE)
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": W, "height": H})
    pg.add_init_script("window.MARCAS = %s;" % json.dumps(MARCAS, ensure_ascii=False))
    pg.goto("file:///" + os.path.abspath(o.html).replace("\\", "/")); pg.wait_for_timeout(300)
    pinta = "([t,T,e]) => render(t,T,e)"
    for i in range(n):
        pg.evaluate(pinta, [o.desde + i / o.fps, T, o.escena]); ff.stdin.write(pg.screenshot(type="png", omit_background=o.alfa))
    if o.claves:
        from PIL import Image
        cs = [float(x) for x in o.claves.split(",")]; tw, th = (360, 640) if o.vertical else (640, 360)
        hoja = Image.new("RGB", ((tw + 10) * len(cs), th), (30, 30, 30))
        for j, c in enumerate(cs):
            pg.evaluate(pinta, [c, T, o.escena]); f = o.salida + ".clave.png"; pg.screenshot(path=f, omit_background=o.alfa)
            im = Image.open(f).convert("RGBA"); fondo = Image.new("RGBA", im.size, (120, 110, 105, 255)); fondo.alpha_composite(im)
            hoja.paste(fondo.convert("RGB").resize((tw, th)), (j * (tw + 10), 0)); os.remove(f)
        hoja.save(os.path.splitext(o.salida)[0] + " - hoja.jpg", quality=88)
    b.close()
ff.stdin.close(); ff.wait()
print("%s  %d cuadros (%.2f s)" % (o.salida, n, n / o.fps))
