"""Paso 5 (opcional): video de stock anclado a la FRASE que ilustra.

Lee `stock.json` y baja cada clip de Pexels (y Pixabay si hay llave). Deja una HOJA DE
CONTACTOS (`hoja_stock.jpg`) con un cuadro de cada uno: se MIRA antes de usar ninguno,
porque un buscador de stock nunca dice «no tengo» y siempre contesta algo.

    python largo.py stock <proyecto>

Formato de stock.json:

    [{"frase": "el costo del escaneo", "despues": 0, "dur": 3.0,
      "consulta": "car engine diagnostic|mechanic laptop car"}]

La consulta va en INGLES (asi estan etiquetados los catalogos), corta y literal, con
alternativas separadas por `|`. ~20% del video con stock es referencia, no meta: ilustra y
tapa las costuras del corte. Nunca encima de una cifra ni de un momento en primer plano.
"""
import os
import subprocess

from largo.comun import T, escribir, leer


def main(c):
    from pipeline import stock as st
    tl = leer(c, "tl.json")
    pedido = leer(c, "stock.json")
    ancho, alto = leer(c, "proyecto.json")["lienzo"][:2]
    buscar = st.crear_buscador(c, orientacion="landscape" if ancho > alto else "portrait")
    plan = []
    for p in pedido:
        ini = round(T(tl, p["frase"], p.get("despues", 0.0)) + 0.15, 2)
        dur = float(p.get("dur", 3.0))
        ruta = buscar(p["consulta"], dur)
        if ruta:
            plan.append({"archivo": ruta, "ini": ini, "fin": round(ini + dur, 2), "desde": 0.0, "frase": p["frase"]})
    st.resumen(buscar.informe)
    escribir(c, "stock_plan.json", plan)
    if not plan:
        print("Ningun clip de stock. (Sin llave de Pexels en .secrets/pexels.yaml no se baja nada.)")
        return
    os.makedirs(os.path.join(c, "stock_frames"), exist_ok=True)
    frames = []
    for k, p in enumerate(plan):
        f = os.path.join(c, "stock_frames", "%02d.jpg" % k)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", "1", "-i", p["archivo"], "-frames:v", "1", "-vf",
                        "scale=480:270:force_original_aspect_ratio=decrease,pad=480:270:(ow-iw)/2:(oh-ih)/2,"
                        "drawtext=text='%02d':x=10:y=10:fontsize=36:fontcolor=yellow:box=1:boxcolor=black" % k, f])
        frames.append(f)
    cols = 4
    if len(frames) == 1:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", frames[0], os.path.join(c, "hoja_stock.jpg")])
    else:
        ins = sum([["-i", f] for f in frames], [])
        fc = "".join("[%d]" % i for i in range(len(frames))) + "xstack=inputs=%d:layout=%s:fill=black" % (
            len(frames), "|".join("%d_%d" % ((i % cols) * 480, (i // cols) * 270) for i in range(len(frames))))
        subprocess.run(["ffmpeg", "-v", "error", "-y"] + ins + ["-filter_complex", fc,
                                                                os.path.join(c, "hoja_stock.jpg")])
    for k, p in enumerate(plan):
        print("%02d %6.1f s  %-35s %s" % (k, p["ini"], p["frase"][:35], os.path.basename(p["archivo"])))
    print("\nMIRA hoja_stock.jpg antes de armar: un clip que no viene al caso se quita de stock.json.")
