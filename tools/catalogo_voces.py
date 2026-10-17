"""Muestrario de voces: la misma frase leida por todas, para elegir de oido.

Elegir voz mirando una lista de nombres no funciona -dos voces etiquetadas
igual ("narrador", "mexicano") no se parecen en nada al oirlas- y probar de una
en una gasta creditos y no deja rastro. Esto sintetiza la misma frase con cada voz,
las deja numeradas en `proyectos/_voces/` y escribe un indice.

    python tools/catalogo_voces.py              # las de espanol, modelo v2
    python tools/catalogo_voces.py --modelo eleven_v3
    python tools/catalogo_voces.py --idioma en  # otras
    python tools/catalogo_voces.py --frase "otra frase"

La carpeta empieza por `_` a proposito: `limpiar.py` conserva esas como cache
compartida y no se lleva por delante lo que costo creditos generar.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import unicodedata
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

NL_ARCHIVO = chr(10)

from pipeline import entorno, voz_off
from pipeline.nucleo import TRABAJO

DESTINO = os.path.join(TRABAJO, "_voces")

# La frase de prueba lleva a proposito una afirmacion y un remate: una voz
# puede sonar bien leyendo un dato y plana al rematar, que es donde se cae un
# reel. Y trae acentos, enes y una cifra.
FRASE = ("En 2019 cambiamos el tablero de una casa que se apagaba cada tarde. "
         "El problema nunca fue el foco: era un cable que ya no aguantaba.")

# Voces que NO entran al muestrario aunque esten en la cuenta: las CLONADAS de
# clientes. Estan en la cuenta porque se clonaron para su trabajo, y su voz es
# suya, no material para otros reels. El criterio es DE QUIEN ES la voz, no si
# esta clonada: la tuya propia si puede entrar.
#
# La lista NO vive en el codigo: lleva nombres de clientes y este archivo se
# comparte. Va en `voces_excluidas.txt` junto a este editor (git lo ignora),
# un nombre de voz por linea, tal cual sale en ElevenLabs. Hay un ejemplo en
# `voces_excluidas.ejemplo.txt`.
EXCLUIR_ARCHIVO = os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "voces_excluidas.txt")


def _excluidas():
    """Nombres (en minuscula) de las voces que no entran. Vacio si no hay lista."""
    if not os.path.exists(EXCLUIR_ARCHIVO):
        return set()
    with open(EXCLUIR_ARCHIVO, encoding="utf-8-sig") as f:
        return {l.strip().lower() for l in f
                if l.strip() and not l.lstrip().startswith("#")}


EXCLUIR = _excluidas()


def sin_acentos(t):
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


def nombre_archivo(i, nombre):
    limpio = re.sub(r"[^a-z0-9]+", "_", sin_acentos(nombre).lower()).strip("_")
    return "%02d_%s.mp3" % (i, limpio[:38])


def voces_de(idioma, clave):
    """Las voces de la cuenta en ese idioma, ya filtradas."""
    req = urllib.request.Request(
        "https://api.elevenlabs.io/v1/voices",
        headers={"xi-api-key": clave, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        datos = json.load(r)

    fuera = []
    for v in datos.get("voices") or []:
        et = v.get("labels") or {}
        idi = (et.get("language") or "").lower()
        texto = (v.get("name", "") + " " + json.dumps(et, ensure_ascii=False)).lower()
        if idioma == "es":
            entra = idi.startswith("es") or any(
                p in texto for p in ("spanish", "mexic", "latin", "castil", "peninsular"))
        else:
            entra = idi.startswith(idioma)
        if not entra or v.get("name", "").lower().strip() in EXCLUIR:
            continue
        fuera.append({
            "nombre": v.get("name", ""),
            "id": v.get("voice_id"),
            "genero": et.get("gender", ""),
            "acento": et.get("accent", ""),
            "uso": et.get("use_case") or et.get("description") or "",
        })
    return fuera


SILENCIO = 0.8      # entre una voz y la siguiente, para que no se peguen


def duracion_real(ruta):
    """Lo que dura el archivo, no lo que dijo el TTS.

    El mp3 no mide exactamente lo que la API reporta, y sobre 26 pistas esa
    diferencia se acumula: la primera version del indice decia 5:35 para un
    audio de 5:24, o sea que la ultima voz estaba anunciada 11 s despues de
    donde suena. Un indice que miente no se usa dos veces.
    """
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", ruta],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    try:
        return float((r.stdout or "0").strip())
    except ValueError:
        return 0.0


def unir(carpeta, destino, pistas):
    """Pega las pistas con silencio entre ellas. Devuelve donde empieza cada una."""
    silencio = os.path.join(carpeta, "_silencio.mp3")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "anullsrc=r=44100:cl=mono", "-t", str(SILENCIO),
         "-c:a", "libmp3lame", "-q:a", "9", silencio],
        check=True, capture_output=True)
    dur_silencio = duracion_real(silencio)

    marcas, t, renglones = {}, 0.0, []
    for i, (archivo, _v, _d) in enumerate(pistas):
        marcas[archivo] = t
        renglones.append("file '%s'" % archivo.replace("'", "'\''"))
        t += duracion_real(os.path.join(carpeta, archivo))
        if i < len(pistas) - 1:
            renglones.append("file '_silencio.mp3'")
            t += dur_silencio

    lista = os.path.join(carpeta, "_lista.txt")
    with open(lista, "w", encoding="utf-8") as f:
        f.write(NL_ARCHIVO.join(renglones))
    try:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0",
             "-i", lista, "-c", "copy", destino],
            check=True, capture_output=True)
    except Exception as e:
        print("  aviso: no se pudo unir en un solo audio (%s)" % str(e)[:70])
        return {}
    finally:
        for tmp in (lista, silencio):
            if os.path.exists(tmp):
                os.remove(tmp)
    # el total medido manda sobre el calculado
    marcas["__total__"] = duracion_real(destino)
    return marcas


# ---------------------------------------------------- draft de CapCut


ANCHO, ALTO, FPS = 1080, 1920, 30
FONDO = (17, 20, 26)
TINTA = (238, 240, 244)
APAGADO = (150, 158, 172)


def _fuente(tam):
    from PIL import ImageFont
    for f in ("segoeuib.ttf", "arialbd.ttf", "seguisb.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"),
                                                   "Fonts", f), tam)
        except Exception:
            continue
    return ImageFont.load_default()


def _centrar(dibujo, texto, fuente, y, color):
    caja = dibujo.textbbox((0, 0), texto, font=fuente)
    dibujo.text(((ANCHO - (caja[2] - caja[0])) / 2, y), texto, font=fuente, fill=color)
    return caja[3] - caja[1]


def tarjeta(destino, numero, nombre, acento, uso):
    """Un PNG vertical con el nombre de la voz. Es lo que se ve mientras suena."""
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    _centrar(d, "%02d" % numero, _fuente(150), 620, APAGADO)
    # el nombre puede ser largo: se parte en dos lineas por el guion
    partes = [t.strip() for t in nombre.split("-", 1)]
    y = 830
    y += _centrar(d, partes[0][:26], _fuente(84), y, TINTA) + 60
    if len(partes) > 1 and partes[1]:
        y += _centrar(d, partes[1][:34], _fuente(46), y, APAGADO) + 50
    pie = " · ".join(t for t in (acento, uso) if t)
    if pie:
        _centrar(d, pie[:44], _fuente(40), y + 20, APAGADO)
    img.save(destino)
    return destino


def clip_de_voz(carpeta, numero, v, mp3, duracion):
    """PNG + su mp3 -> un mp4 que CapCut puede poner en la linea de tiempo."""
    png = os.path.join(carpeta, "tarjeta_%02d.png" % numero)
    tarjeta(png, numero, v["nombre"], v.get("acento", ""), v.get("uso", ""))
    mp4 = os.path.join(carpeta, "clip_%02d.mp4" % numero)
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-loop", "1", "-framerate", str(FPS),
         "-i", png, "-i", mp3, "-t", "%.3f" % duracion,
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", str(FPS),
         "-c:a", "aac", "-b:a", "160k", "-shortest", mp4],
        check=True, capture_output=True)
    os.remove(png)
    return mp4


def draft_capcut(carpeta, pistas, nombre_proyecto, log=print):
    """Arma el muestrario como proyecto de CapCut: una tarjeta por voz."""
    from pipeline import capcut_lib
    segmentos = []
    for i, (archivo, v, _d) in enumerate(pistas, 1):
        mp3 = os.path.join(carpeta, archivo)
        dur = duracion_real(mp3)
        mp4 = clip_de_voz(carpeta, i, v, mp3, dur)
        # la duracion del mp4 se MIDE, no se hereda del mp3: ffmpeg ajusta el
        # video a frames enteros y queda unas milesimas mas corto. pycapcut lo
        # rechaza con un error en chino que no dice de que clip habla.
        fin = duracion_real(mp4) - 1.0 / FPS
        segmentos.append({"path": mp4, "ini": 0.0, "fin": round(max(fin, 0.5), 3)})
        log("  %2d/%d  %s" % (i, len(pistas), v["nombre"][:40]))
    res = capcut_lib.construir_segmentos(
        nombre_proyecto, segmentos, (ANCHO, ALTO, FPS), log=lambda *a: None)
    return res, sum(s["fin"] for s in segmentos)


def main():
    ap = argparse.ArgumentParser(description="Muestrario de voces de la cuenta")
    ap.add_argument("--idioma", default="es")
    ap.add_argument("--modelo", default=voz_off.MODELO)
    ap.add_argument("--frase", default=FRASE)
    ap.add_argument("--capcut", action="store_true",
                    help="ademas, arma el muestrario como proyecto de CapCut")
    ap.add_argument("--solo-listar", action="store_true",
                    help="dice cuales entrarian y cuanto costaria, sin gastar")
    args = ap.parse_args()

    entorno.consola_utf8()
    clave = voz_off.leer_clave()
    lista = voces_de(args.idioma, clave)
    if not lista:
        sys.exit("Ninguna voz en '%s'. Con otro idioma: --idioma en" % args.idioma)

    coste = len(lista) * len(args.frase)
    print("%d voces en '%s' | %d caracteres en total" % (len(lista), args.idioma, coste))
    if args.solo_listar:
        for i, v in enumerate(lista, 1):
            print("  %2d. %-28s %-16s %s" % (i, v["nombre"][:28], v["acento"], v["uso"]))
        return

    os.makedirs(DESTINO, exist_ok=True)
    filas = []
    for i, v in enumerate(lista, 1):
        archivo = nombre_archivo(i, v["nombre"])
        ruta = os.path.join(DESTINO, archivo)
        try:
            r = voz_off.sintetizar(args.frase, v["id"], ruta, clave=clave,
                                   modelo=args.modelo, log=lambda *a: None)
            filas.append((archivo, v, round(r["duracion"], 1), ""))
            print("  %2d/%d  %-28s %.1f s" % (i, len(lista), v["nombre"][:28], r["duracion"]))
        except Exception as e:
            filas.append((archivo, v, 0, str(e)[:60]))
            print("  %2d/%d  %-28s FALLA: %s" % (i, len(lista), v["nombre"][:28], str(e)[:60]))

    # Un solo audio corrido: 26 archivos sueltos no se comparan, se abandonan
    # al quinto. Con el minuto de cada una en el indice se salta a la que sea.
    corrido, marcas = os.path.join(DESTINO, "TODAS.mp3"), {}
    buenas = [(a, v, d) for a, v, d, e in filas if d]
    if buenas:
        marcas = unir(DESTINO, corrido, buenas)
        if marcas:
            total = marcas.pop("__total__", max(marcas.values()))
            print("")
            print("Todas seguidas: %s (%d:%02d)"
                  % (corrido, int(total) // 60, int(total) % 60))

    indice = os.path.join(DESTINO, "LEEME.md")
    with open(indice, "w", encoding="utf-8") as f:
        f.write("# Muestrario de voces (%s)\n\n" % args.idioma)
        f.write("Modelo: `%s` · la misma frase en todas, para comparar de oido.\n\n" % args.modelo)
        f.write("> %s\n\n" % args.frase)
        if marcas:
            f.write("**`TODAS.mp3`** las trae seguidas; la columna *minuto* "
                    "dice donde empieza cada una.\n\n")
        f.write("| # | Voz | Acento | Etiquetada para | Minuto | Archivo | ID |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        for archivo, v, dur, error in filas:
            m = marcas.get(archivo)
            minuto = "%d:%02d" % (int(m) // 60, int(m) % 60) if m is not None else "-"
            f.write("| %s | %s | %s | %s | **%s** | `%s` | `%s` |\n" % (
                archivo[:2], v["nombre"], v["acento"] or "-",
                v["uso"] or "-", minuto if dur else "FALLA: " + error,
                archivo, v["id"]))
    print("")
    print("Indice: %s" % indice)
    print("Audios: %s" % DESTINO)

    if args.capcut and buenas:
        print("")
        print("Armando el proyecto de CapCut...")
        proyecto = "voces %s" % args.idioma
        res, total = draft_capcut(DESTINO, buenas, proyecto)
        print("Proyecto '%s': %d clips, %d:%02d. Abre CapCut y ahi esta."
              % (proyecto, res["segmentos"], int(total) // 60, int(total) % 60))


if __name__ == "__main__":
    main()
