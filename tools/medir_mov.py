# -*- coding: utf-8 -*-
"""Cuanto se mueve de verdad un reel: escala Y desplazamiento a la vez.

Medir cada cosa por separado ya fallo una vez (15-sep): en una escena con zoom y
paneo, el medidor de escala dijo "no se mueve" porque el corrimiento lo estorbaba,
y el de corrimiento dijo 0 porque el zoom lo estorbaba. Aqui se busca el par
(escala, corrimiento) que mejor empata los dos cuadros.

    python medir_mov.py <video.mp4> <t1> <t2> [...]
"""
import os
import subprocess
import sys
import tempfile

from PIL import Image

ANCHO, ALTO = 240, 426


def fotograma(video, t, destino):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", video,
                    "-frames:v", "1", "-vf", "scale=%d:%d" % (ANCHO, ALTO),
                    "-q:v", "2", destino], check=True, capture_output=True)
    return Image.open(destino).convert("L")


def dif(a, b):
    pa, pb = list(a.getdata()), list(b.getdata())
    return sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa)


def movimiento(a, b):
    """Devuelve (escala %, corrimiento en % del ancho) entre dos cuadros."""
    caja = (30, 50, ANCHO - 30, ALTO - 50)      # se ignoran los bordes y el subtitulo
    ref = a.crop(caja)
    mejor = (0.0, 0, 1e9)
    for mil in range(-100, 101, 5):             # escala de -10% a +10%
        s = 1.0 + mil / 1000.0
        nw, nh = int(ANCHO * s), int(ALTO * s)
        esc = b.resize((nw, nh)).crop(((nw - ANCHO) // 2, (nh - ALTO) // 2,
                                       (nw - ANCHO) // 2 + ANCHO,
                                       (nh - ALTO) // 2 + ALTO))
        for dx in range(-24, 25, 2):            # corrimiento lateral
            movido = esc.transform(esc.size, Image.AFFINE, (1, 0, dx, 0, 1, 0))
            d = dif(ref, movido.crop(caja))
            if d < mejor[2]:
                mejor = ((s - 1) * 100, dx, d)
    return mejor[0], mejor[1] / float(ANCHO) * 100


def main():
    video = sys.argv[1]
    tiempos = [float(t) for t in sys.argv[2:]]
    tmp = tempfile.mkdtemp()
    print("%-10s %10s %14s" % ("de -> a", "escala %", "corrimiento %"))
    for t1, t2 in zip(tiempos, tiempos[1:]):
        if t2 - t1 > 1.01:                      # solo pares consecutivos de 1 s
            continue
        a = fotograma(video, t1, os.path.join(tmp, "a.jpg"))
        b = fotograma(video, t2, os.path.join(tmp, "b.jpg"))
        e, c = movimiento(a, b)
        print("%4.1f -> %4.1f %9.1f %13.1f" % (t1, t2, e, c))


if __name__ == "__main__":
    main()
