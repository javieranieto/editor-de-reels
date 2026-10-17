"""Video LARGO (YouTube, horizontal): de una o varias tomas a un proyecto de CapCut armado.

Cada paso es un comando. Lo editorial (que frases van, el texto bien escrito, que stock va
donde) lo decide quien edita —o Claude— en tres archivos de texto; lo mecanico lo hace esto.
El metodo completo esta en largo/LEEME.md y en el skill `editar-largo`.

    python largo.py preparar <proyecto> --toma A=<video> [--toma R=<retomas>]
    python largo.py cortar   <proyecto>          # orden.json -> edl.json
    python largo.py revisar  <proyecto>          # escucha cada tramo y marca lo que no cuadra
    python largo.py amarrar  <proyecto>          # subtitulos y tiempos finales (texto_limpio.txt)
    python largo.py stock    <proyecto>          # stock.json -> clips + hoja de contactos
    python largo.py motion   <proyecto>          # escenas.json -> graficos animados con tu marca
    python largo.py armar    <proyecto> [--nombre N] [--subtitulos]
    python largo.py reels    <proyecto> [nombre ...]   # reels.json -> reels verticales en CapCut

<proyecto> es un nombre (vive en proyectos/<nombre>/) o una ruta a una carpeta.
CapCut tiene que estar CERRADO para `armar`.
"""
import argparse

from largo import comun


def main():
    ap = argparse.ArgumentParser(description="Video largo: de las tomas a CapCut, paso por paso.")
    sub = ap.add_subparsers(dest="paso", required=True)
    p = sub.add_parser("preparar", help="audio, transcripcion y version legible de cada toma")
    p.add_argument("proyecto")
    p.add_argument("--toma", action="append", default=[], metavar="LETRA=VIDEO",
                   help="A=toma principal; R=retomas (las que haya)")
    p.add_argument("--modelo", default="large-v3")
    p = sub.add_parser("cortar", help="de orden.json al corte medido en el audio")
    p.add_argument("proyecto")
    p = sub.add_parser("revisar", help="transcribe cada tramo suelto y marca diferencias")
    p.add_argument("proyecto")
    p.add_argument("etiquetas", nargs="*")
    p.add_argument("--modelo", default="large-v3")
    p = sub.add_parser("amarrar", help="tiempos finales de cada palabra y subtitulos")
    p.add_argument("proyecto")
    p.add_argument("--modelo", default="large-v3")
    p = sub.add_parser("stock", help="baja el stock de stock.json y hace la hoja de contactos")
    p.add_argument("proyecto")
    p = sub.add_parser("motion", help="captura los graficos de escenas.json con la marca")
    p.add_argument("proyecto")
    p.add_argument("piezas", nargs="*")
    p.add_argument("--revisar", action="store_true", help="solo comprueba que existan las frases")
    p = sub.add_parser("reels", help="reels verticales del largo (reels.json), estilo ventana")
    p.add_argument("proyecto")
    p.add_argument("nombres", nargs="*")
    p = sub.add_parser("armar", help="crea el proyecto en CapCut")
    p.add_argument("proyecto")
    p.add_argument("--nombre")
    p.add_argument("--subtitulos", action="store_true", help="quemar los subtitulos (por defecto van aparte)")
    a = ap.parse_args()
    c = comun.carpeta(a.proyecto)

    if a.paso == "preparar":
        from largo import preparar
        tomas = {}
        for t in a.toma:
            k, _, v = t.partition("=")
            if not v:
                raise SystemExit("--toma va como LETRA=VIDEO, por ejemplo --toma A=\"C:\\videos\\toma.mp4\"")
            tomas[k.strip().upper()] = v.strip().strip('"')
        preparar.main(c, tomas, a.modelo)
    elif a.paso == "cortar":
        from largo import cortar
        cortar.main(c)
    elif a.paso == "revisar":
        from largo import revisar
        revisar.main(c, a.etiquetas or None, a.modelo)
    elif a.paso == "amarrar":
        from largo import amarrar
        amarrar.main(c, a.modelo)
    elif a.paso == "stock":
        from largo import stock_largo
        stock_largo.main(c)
    elif a.paso == "motion":
        from largo import motion
        motion.main(c, a.piezas or None, a.revisar)
    elif a.paso == "reels":
        from largo import reels
        reels.main(c, a.nombres or None)
    elif a.paso == "armar":
        from largo import armar
        armar.main(c, a.nombre, a.subtitulos)


if __name__ == "__main__":
    main()
