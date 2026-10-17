"""Render de un video animado (animado/videos/<nombre>/escenas.js) cuadro por cuadro.

    python animado/render.py ejemplo-dato --fotos 0.3 1.2 2.8 --alfa   # capturas + hoja.png, para revisar
    python animado/render.py ejemplo-dato --alfa     # .mov con transparencia (qtrle/argb) para CapCut
    python animado/render.py <video>                 # MP4 final con musica y efectos (audio.json)
    python animado/render.py <video> --ver           # vista previa en vivo en el navegador

Rutas relativas a la raíz del repo. La salida va a proyectos/animado/<nombre>/ (fuera de git).
Chrome dibuja cada cuadro con frame(t), que es determinista: la vista previa y el render
son el mismo dibujo.

Necesita: playwright (pip install playwright) y un Chrome instalado (si no hay, usa el
Chromium de Playwright: python -m playwright install chromium), ffmpeg/ffprobe en el PATH
para el MP4 y el .mov, y Pillow para la hoja de capturas.
"""
import argparse, base64, functools, http.server, json, os, shutil, subprocess, sys, tempfile, threading, webbrowser

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)


class _Mudo(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def servidor():
    h = functools.partial(_Mudo, directory=AQUI)
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def ruta_repo(p):
    return p if os.path.isabs(p) else os.path.join(RAIZ, p)


def dur_medida(ruta):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", ruta],
                       capture_output=True, text=True)
    return float(r.stdout.strip())


def mezclar_audio(cfg, dur, salida):
    """Musica + efectos del audio.json, normalizado a LUFS. Devuelve la ruta del wav."""
    entradas, filtros, etiquetas = [], [], []
    m = cfg.get("musica")
    if m:
        if not os.path.exists(ruta_repo(m["archivo"])):
            sys.exit("No encuentro la musica: " + m["archivo"])
        entradas += ["-i", ruta_repo(m["archivo"])]
        d0, fo = m.get("desde", 0), m.get("fade_out", 1.5)
        filtros.append(f"[0:a]atrim={d0}:{d0 + dur},asetpts=PTS-STARTPTS,"
                       f"afade=t=out:st={dur - fo}:d={fo},volume={m.get('volumen', 0.55)}[m]")
    else:                                              # sin musica: una base muda marca la duracion
        entradas += ["-f", "lavfi", "-t", str(dur), "-i", "anullsrc=r=48000:cl=stereo"]
        filtros.append("[0:a]anull[m]")
    etiquetas.append("[m]")
    vol = cfg.get("volumen_efectos", 0.6)
    for i, e in enumerate(cfg.get("efectos", []), start=1):
        if not os.path.exists(ruta_repo(e["archivo"])):
            sys.exit("No encuentro el efecto: " + e["archivo"])
        entradas += ["-i", ruta_repo(e["archivo"])]
        rec = f"atrim=start={e['recorte']},asetpts=PTS-STARTPTS," if e.get("recorte") else ""
        ms = int(round(e["en"] * 1000))
        filtros.append(f"[{i}:a]{rec}adelay={ms}|{ms},volume={e.get('volumen', vol)}[s{i}]")
        etiquetas.append(f"[s{i}]")
    filtros.append("".join(etiquetas) + f"amix=inputs={len(etiquetas)}:normalize=0:duration=first,"
                   f"loudnorm=I={cfg.get('lufs', -14)}:TP=-1.5:LRA=11,aresample=48000[a]")
    r = subprocess.run(["ffmpeg", "-y", "-v", "error", *entradas, "-filter_complex", ";".join(filtros),
                        "-map", "[a]", "-t", str(dur), "-c:a", "pcm_s16le", salida])
    if r.returncode != 0:
        sys.exit("ffmpeg fallo al mezclar el audio")
    return salida


def hoja(fotos, destino):
    from PIL import Image
    ims = [Image.open(f).convert("RGBA") for f in fotos]
    w, h = 960, int(960 * ims[0].height / ims[0].width)
    filas = (len(ims) + 1) // 2
    out = Image.new("RGBA", (w * 2 + 8, filas * (h + 8)), (0, 0, 0, 255))
    for i, im in enumerate(ims):
        fondo = Image.new("RGBA", im.size, (255, 0, 255, 255))   # rosa = transparente, si hay alfa
        out.paste(Image.alpha_composite(fondo, im).resize((w, h)), ((i % 2) * (w + 8), (i // 2) * (h + 8)))
    out.convert("RGB").save(destino)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="nombre en animado/videos/ (o ruta a su carpeta)")
    ap.add_argument("--fotos", nargs="+", type=float, help="solo capturas en estos segundos")
    ap.add_argument("--alfa", action="store_true", help=".mov con fondo transparente, sin audio")
    ap.add_argument("--ver", action="store_true", help="abrir la vista previa en el navegador")
    ap.add_argument("--salida", help="archivo de salida; con --fotos, la CARPETA de las capturas (por defecto en proyectos/animado/<video>/)")
    ap.add_argument("--crf", type=int, default=24)
    a = ap.parse_args()

    carpeta = a.video if os.path.isdir(a.video) else os.path.join(AQUI, "videos", a.video)
    if not os.path.exists(os.path.join(carpeta, "escenas.js")):
        sys.exit(f"No hay escenas.js en {carpeta}")
    rel = os.path.relpath(carpeta, AQUI).replace("\\", "/")
    nombre = os.path.basename(os.path.normpath(carpeta))
    dest = os.path.join(RAIZ, "proyectos", "animado", nombre)

    s = servidor()
    url = f"http://127.0.0.1:{s.server_port}/pagina.html?v={rel}"
    if a.ver:
        print("Vista previa:", url, "(Ctrl+C para salir; &t=12 arranca en el segundo 12)")
        webbrowser.open(url)
        threading.Event().wait()

    if not a.fotos:
        for exe in ("ffmpeg", "ffprobe"):
            if not shutil.which(exe):
                sys.exit(f"No encuentro {exe} en el PATH (winget install Gyan.FFmpeg y reinicia la terminal)")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("Falta playwright: pip install playwright")
    with sync_playwright() as p:
        try:
            nav = p.chromium.launch(channel="chrome", headless=True)
        except Exception:
            try:                                       # sin Chrome instalado: el Chromium de Playwright
                nav = p.chromium.launch(headless=True)
            except Exception:
                sys.exit("No hay navegador para dibujar: instala Chrome o corre "
                         "'python -m playwright install chromium'")
        page = nav.new_page(viewport={"width": 1280, "height": 720})
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))
        page.goto(url + "&render=1" + ("&alfa=1" if a.alfa else ""))
        page.wait_for_function("window.READY === true || window.ERROR", timeout=60000)
        if page.evaluate("window.ERROR") or errores:
            sys.exit("Error en la pagina: " + (page.evaluate("window.ERROR") or errores[0]))
        cfg = page.evaluate("({dur: VIDEO.dur, fps: VIDEO.fps, salida: VIDEO.salida})")

        def png(t):
            url_png = page.evaluate(f"(frame({t}), cv.toDataURL('image/png'))")
            if errores:
                sys.exit(f"Error en la pagina en t={t}: " + errores[0])
            return base64.b64decode(url_png.split(",", 1)[1])

        if a.fotos:
            fuera = [t for t in a.fotos if t < 0 or t >= cfg["dur"]]
            if fuera:
                print(f"AVISO: {fuera} cae fuera del video (0-{cfg['dur']} s): se dibuja la ultima escena pasada de su final")
            fd = a.salida or os.path.join(dest, "fotos"); os.makedirs(fd, exist_ok=True)
            rutas = []
            for t in a.fotos:
                rutas.append(os.path.join(fd, f"t{t:06.2f}.png"))
                open(rutas[-1], "wb").write(png(t))
            hoja(rutas, os.path.join(fd, "hoja.png"))
            print("Capturas en", fd, "-> abrir hoja.png")
            return

        n = int(round(cfg["dur"] * cfg["fps"]))
        if a.alfa:
            salida = a.salida or os.path.join(dest, nombre + " (alfa).mov")
            os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
            cod = ["-c:v", "qtrle", "-pix_fmt", "argb"]
        else:
            salida = a.salida or os.path.join(dest, nombre + ".mp4")
            os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
            cod = ["-c:v", "libx264", "-preset", "slow", "-crf", str(a.crf), "-tune", "animation", "-pix_fmt", "yuv420p"]
        tmp = tempfile.mkdtemp(prefix="animado_")
        solo_video = os.path.join(tmp, "video" + (".mov" if a.alfa else ".mp4"))
        ff = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "image2pipe", "-framerate", str(cfg["fps"]),
                               "-i", "-", *cod, solo_video], stdin=subprocess.PIPE)
        for i in range(n):
            ff.stdin.write(png(i / cfg["fps"]))
            if i % (cfg["fps"] * 5) == 0:
                print(f"  cuadro {i}/{n}", flush=True)
        ff.stdin.close()
        if ff.wait() != 0:
            sys.exit("ffmpeg fallo al codificar")
        nav.close()

    audio = os.path.join(carpeta, "audio.json")
    if a.alfa or not os.path.exists(audio):
        shutil.move(solo_video, salida)          # move, no replace: el temporal puede estar en otro disco
    else:
        wav = mezclar_audio(json.load(open(audio, encoding="utf-8")), cfg["dur"], os.path.join(tmp, "mezcla.wav"))
        r = subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", solo_video, "-i", wav, "-map", "0:v", "-map", "1:a",
                            "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest", salida])
        if r.returncode != 0:
            sys.exit("ffmpeg fallo al unir audio y video")

    # se le pregunta al archivo, no al numero con el que se pidio
    d = dur_medida(salida)
    mb = os.path.getsize(salida) / 1e6
    print(f"listo: {salida}  ({d:.2f} s, {mb:.1f} MB)")
    if abs(d - cfg["dur"]) > 0.1:
        sys.exit(f"AVISO: dura {d:.2f} s y se pidieron {cfg['dur']} s")


if __name__ == "__main__":
    main()
