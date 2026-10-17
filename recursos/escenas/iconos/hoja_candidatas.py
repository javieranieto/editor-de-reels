"""Dibuja todas las candidatas (un cuadro a 60% de su animación) en una hoja numerada, para ELEGIR mirándolas."""
import json, os, glob
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw
AQ = os.path.dirname(os.path.abspath(__file__)); LOT = open(os.path.join(AQ, "..", "base", "lottie.min.js"), encoding="utf-8").read()
fs = sorted(glob.glob(os.path.join(AQ, "candidatas", "*.json"))); fs = [f for f in fs if not f.endswith("fuentes.json")]
T = 220; cols = 8; hoja = Image.new("RGB", (cols * T, ((len(fs) + cols - 1) // cols) * (T + 24)), (250, 250, 250))
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page(viewport={"width": T, "height": T})
    pg.set_content("<html><body style='margin:0;background:#fff'><div id=c style='width:%dpx;height:%dpx'></div><script>%s</script></body></html>" % (T, T, LOT))
    for i, f in enumerate(fs):
        data = json.load(open(f, encoding="utf-8"))
        pg.evaluate("""(d) => { const c=document.getElementById('c'); c.innerHTML=''; if(window.A) window.A.destroy();
            window.A = lottie.loadAnimation({container:c, renderer:'svg', loop:false, autoplay:false, animationData:d});
            window.A.goToAndStop(Math.floor((d.op-d.ip)*0.6), true); }""", data)
        pg.wait_for_timeout(60); pg.screenshot(path="_t.png")
        x, y = (i % cols) * T, (i // cols) * (T + 24)
        hoja.paste(Image.open("_t.png").convert("RGB"), (x, y))
        ImageDraw.Draw(hoja).text((x + 6, y + T + 4), os.path.basename(f)[:-5], fill=(0, 0, 0))
    b.close()
os.remove("_t.png"); hoja.save(os.path.join(AQ, "hoja_candidatas.jpg"), quality=85); print(hoja.size)
