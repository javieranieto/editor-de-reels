"""Saca frames del video para que Claude vea el encuadre y coloque bien las cosas.

Un caption o un callout mal puesto tapa la cara. Con frames reales se decide
dónde hay hueco en vez de adivinar. Claude puede leer las imagenes que esto
genera, asi que no hace falta que el usuario mande capturas.

Uso:
    python tools/encuadre.py <video>                  # 6 frames repartidos
    python tools/encuadre.py <video> 12.5 71.8 147.0  # frames en esos segundos
    python tools/encuadre.py --plan proyectos/<n>/plan_v5.json   # uno por corte
    python tools/encuadre.py <video> --cabeza          # cuanto zoom aguanta
"""
import json
import os
import subprocess
import sys

import numpy as np

SALIDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "proyectos", "_encuadre")
ANCHO = 540   # suficiente para juzgar composicion sin gastar de mas


def sacar(video, segundos, destino=SALIDA):
    os.makedirs(destino, exist_ok=True)
    hechos = []
    for i, t in enumerate(segundos):
        out = os.path.join(destino, "f%02d_%06.1fs.jpg" % (i, t))
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", "%.2f" % t, "-i", video,
             "-frames:v", "1", "-vf", "scale=%d:-2" % ANCHO, out],
            capture_output=True, timeout=180)
        if r.returncode == 0 and os.path.exists(out):
            hechos.append(out)
            print("  %6.1fs -> %s" % (t, os.path.basename(out)))
        else:
            print("  %6.1fs -> fallo" % t)
    return hechos


def desde_plan(ruta_plan):
    """Un frame por corte, tomado a la mitad de cada uno."""
    with open(ruta_plan, encoding="utf-8") as f:
        plan = json.load(f)
    segs = plan["segmentos"]
    video = segs[0]["path"]
    return video, [s["ini"] + (s["fin"] - s["ini"]) / 2 for s in segs]



# ------------------------------------------------------- cuanto zoom aguanta
# El zoom seco es una escala fija: a escala s se pierde (1 - 1/s)/2 de alto por
# arriba y por abajo. En un plano medio sobra pared y no se nota; en un primer
# plano cerrado la misma escala le come la frente al que habla. La escala que
# aguanta cada video NO se supone: se mide donde empieza la cabeza.
COLS = (0.30, 0.70)   # franja central: donde esta la cabeza, no los cuadros de la pared
OSCURO = 0.62         # fraccion del brillo de la pared por debajo de la cual ya no es pared


def _frames_gris(video, momentos, ancho=160):
    """Los frames pedidos en gris, como arrays (alto, ancho). Igual que adornos.py."""
    salida = []
    for t in momentos:
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-nostdin", "-ss", "%.2f" % t, "-i", video,
             "-frames:v", "1", "-vf", "scale=%d:-2,format=gray" % ancho,
             "-f", "rawvideo", "-"],
            capture_output=True, timeout=180)
        if r.returncode != 0 or not r.stdout:
            continue
        alto = len(r.stdout) // ancho
        if alto:
            salida.append(np.frombuffer(r.stdout[:alto * ancho], np.uint8)
                          .reshape(alto, ancho))
    return salida


def alto_cabeza(video, momentos):
    """Fraccion de altura donde empieza la cabeza (0 = borde de arriba).

    Devuelve None si no la encuentra, para no inventar un numero.
    """
    tops = []
    for g in _frames_gris(video, momentos):
        alto, ancho = g.shape
        franja = g[:, int(ancho * COLS[0]):int(ancho * COLS[1])]
        pared = np.percentile(franja, 90)      # el fondo es lo mas claro que hay
        umbral = pared * OSCURO
        # primera fila donde la franja central deja de ser pared
        filas = np.where(np.percentile(franja, 10, axis=1) < umbral)[0]
        if len(filas):
            tops.append(filas[0] / float(alto))
    if not tops:
        return None
    return float(np.median(tops))


# Cuanto del aire sobre la cabeza se deja comer. NO es un numero elegido: sale
# de un reel aprobado. Ahi la cabeza empezaba al 20.1% de la altura y se dio
# por bueno un pico de 1.36, que recorta el 13.2% por
# arriba: 0.132 / 0.201 = 0.66. O sea que acepta perder dos tercios del aire.
HOLGURA = 0.66


def zoom_que_aguanta(top, holgura=HOLGURA):
    """Escala maxima que no entra en la cabeza.

    A escala s se recorta (1 - 1/s)/2 por arriba. Se permite comerse `holgura`
    de lo que hay sobre la cabeza: recortar un poco de pelo es un primer plano
    normal, entrar en la frente no.
    """
    margen = top * holgura
    if margen <= 0:
        return 1.0
    return min(1.40, 1.0 / max(1e-6, 1.0 - 2.0 * margen))



def ancla_necesaria(top, escala, holgura=HOLGURA):
    """Cuanto hay que bajar la imagen para que el zoom no entre en la cabeza.

    Devuelve 0.0 si centrada ya cabe, 1.0 si hace falta anclar del todo al
    borde de arriba. Va al plan como {"zoom": {"punch": s, "ancla": a}}.
    """
    if escala <= 1.0:
        return 0.0
    recorte = (1.0 - 1.0 / escala) / 2.0     # lo que se come arriba, centrada
    permitido = max(0.0, top) * holgura
    if recorte <= permitido:
        return 0.0
    return min(1.0, max(0.0, 1.0 - permitido / recorte))


def recorte_abajo(escala, ancla):
    """Fraccion de la imagen que se pierde por abajo. Ahi estan sus manos."""
    if escala <= 1.0:
        return 0.0
    mitad = (1.0 - 1.0 / escala) / 2.0
    return mitad * (1.0 + ancla)


def informe_cabeza(video, momentos):
    top = alto_cabeza(video, momentos)
    print("")
    print("Cuanto zoom aguanta este encuadre:")
    if top is None:
        print("  no pude medir donde empieza la cabeza; no arriesgo un numero.")
        return
    smax = zoom_que_aguanta(top)
    print("  la cabeza empieza al %.1f%% de la altura" % (top * 100))
    print("  escala maxima sin entrar en la frente: %.2f" % smax)
    if smax < 1.12:
        print("  -> plano MUY cerrado: el zoom de 112-136% le corta la cara.")
        print("     usar escalas por debajo de %.2f o dejarlo todo abierto." % smax)
    elif smax < 1.25:
        print("  -> plano cerrado: cabe zoom leve, no el pico de 134-136%.")
    else:
        print("  -> plano con aire: la jerarquia de 112-136% entra sin problema.")
    if top < 0.15:
        print("  aviso: no hay pared vacia arriba, los callouts de datos taparian la cabeza.")


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)

    cabeza = "--cabeza" in args
    if cabeza:
        args = [a for a in args if a != "--cabeza"]

    if args[0] == "--plan":
        video, momentos = desde_plan(args[1])
    else:
        video = args[0]
        momentos = [float(x) for x in args[1:]]
        if not momentos:
            dur = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", video],
                capture_output=True, text=True).stdout.strip())
            momentos = [dur * f for f in (0.05, 0.2, 0.4, 0.6, 0.8, 0.95)]

    if not os.path.exists(video):
        sys.exit("No encuentro el video: %s" % video)
    print("Frames de %s:" % os.path.basename(video))
    hechos = sacar(video, momentos)
    print("\n%d frames en %s" % (len(hechos), SALIDA))
    print("Claude puede leerlos para decidir donde poner captions y callouts.")
    if cabeza:
        informe_cabeza(video, momentos)


if __name__ == "__main__":
    main()
