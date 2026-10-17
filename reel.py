"""Editor automatico de reels: corta silencios y muletillas, y arma el proyecto de CapCut.

Acepta un video, varios, o una carpeta con todos los clips del reel:
    python reel.py mi_video.mp4
    python reel.py clip1.mp4 clip2.mp4 clip3.mp4
    python reel.py C:\\videos\\reel_de_hoy\\
    python reel.py carpeta --perfil agresivo --mp4

El segundo tipo de reel no se graba: se escribe. Lo lee una voz sintetica y
cada escena se ilustra con stock:
    python reel.py --guion historia.txt --voz Rachel
    python reel.py --guion historia.txt --solo-plan   (revisar antes de armar)

Tambien hay interfaz grafica: doble clic en "Editor de Reels.bat".
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline import nucleo
from pipeline.cifras import ESTILOS as ESTILOS_CIFRA
from pipeline.letras import ESTILOS as ESTILOS_LETRA
from pipeline.plan import PERFILES


def resolver_voz(pedida):
    """Acepta el nombre de una voz publica o un id tal cual."""
    from pipeline import voz_off
    for nombre, vid in voz_off.VOCES_PUBLICAS:
        if pedida.lower() == nombre.lower():
            return vid, nombre
    return pedida, pedida


def reel_de_guion(args):
    """Guion escrito -> voz + stock -> proyecto de CapCut.

    El pegamento entre `guion.py` (que ya existia y nadie llamaba) y todo lo
    demas. Escribe el plan.json en la carpeta del proyecto, asi que se puede
    revisar y volver a generar con --desde-plan sin pagar el TTS otra vez: la
    sintesis se cachea por (texto, voz, modelo, velocidad).
    """
    from pipeline import guion as guion_mod
    from pipeline import nucleo, stock, voz_off

    if not os.path.exists(args.guion):
        raise RuntimeError("No encuentro el guion: %s" % args.guion)
    with open(args.guion, encoding="utf-8-sig") as f:
        texto = f.read().strip()
    if not texto:
        raise RuntimeError("El guion esta vacio: %s" % args.guion)

    aviso = voz_off.revisar_acentos(texto)
    if aviso:
        print("")
        print(aviso)
        print("")

    nombre = args.nombre or nucleo.nombre_por_defecto()
    carpeta = os.path.join(nucleo.TRABAJO, nombre)
    voz_id, voz_nombre = resolver_voz(args.voz)

    # se cuenta sobre el texto SIN anotaciones: las consultas no se locutan,
    # y contarlas daba una duracion estimada mas larga que la real
    palabras = len(guion_mod.extraer_consultas(texto)[0].split())
    print("Guion: %d palabras (~%d s) | voz: %s"
          % (palabras, round(palabras / 2.2), voz_nombre))

    umbral = args.umbral_stock if args.umbral_stock is not None else 0.6
    buscar = stock.crear_buscador(carpeta, umbral=umbral,
                                  usar_pixabay=not args.sin_pixabay)
    plan = guion_mod.guion_a_plan(texto, carpeta, voz_id, buscar=buscar)
    stock.resumen(buscar.informe)

    plan["creditos"] = buscar.informe["creditos"]
    plan_path = os.path.join(carpeta, "plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(plan, f, ensure_ascii=False, indent=1)
    print("Plan: %s" % plan_path)

    if args.solo_plan:
        print("")
        print("Revisa el plan y genera con:")
        print('  python reel.py --desde-plan "%s" --nombre "%s"'
              % (plan_path, nombre))
        return

    nucleo.editar_con_plan(
        plan_path, nombre, modelo=args.modelo, idioma=args.idioma,
        subtitulos=not args.sin_subtitulos,
        salida="mp4" if args.mp4 else "capcut",
        captions=args.captions, zoom=args.zoom, letras=args.letras,
        cifra=args.cifras)


def main():
    ap = argparse.ArgumentParser(
        description="Edita reels automaticamente y crea el draft de CapCut")
    ap.add_argument("videos", nargs="*",
                    help="video(s) a editar, o una carpeta con los clips")
    ap.add_argument("--guion", metavar="GUION_TXT",
                    help="reel de voz en off: archivo de texto con el guion")
    ap.add_argument("--voz", default="Rachel",
                    help="voz de ElevenLabs: nombre publico o id (--ver-voces)")
    ap.add_argument("--ver-voces", action="store_true",
                    help="lista las voces que se pueden usar")
    ap.add_argument("--umbral-stock", type=float,
                    help="que tan exigente es el filtro de imagenes (0 a 1, por defecto 0.6)")
    ap.add_argument("--sin-pixabay", action="store_true",
                    help="usar solo Pexels aunque haya clave de Pixabay")
    ap.add_argument("--desde-plan", metavar="PLAN_JSON",
                    help="genera desde un plan.json ya revisado (ignora el analisis)")
    ap.add_argument("--sin-tomas", action="store_true",
                    help="no detectar tomas repetidas ni falsos arranques")
    ap.add_argument("--captions", default="clasico", choices=["clasico", "palabra"],
                    help="estilo de subtitulos: frases (clasico) o 1-2 palabras (palabra)")
    ap.add_argument("--letras", default="resalte", choices=list(ESTILOS_LETRA),
                    help="estilo de los subtitulos (--ver-letras los lista)")
    ap.add_argument("--cifras", default="pop", choices=list(ESTILOS_CIFRA),
                    help="como aparecen las cifras en pantalla")
    ap.add_argument("--ver-letras", action="store_true",
                    help="lista los estilos de letra y las fuentes disponibles")
    ap.add_argument("--ver-frases", action="store_true",
                    help="lista los estilos de la frase clave y cuales estan listos")
    ap.add_argument("--zoom", default="no", choices=["no", "suave", "progresivo", "punch"],
                    help="suave: drift lento | progresivo: escalera por corte | "
                         "punch: empuje asimetrico solo en las frases con enfasis")
    ap.add_argument("--nombre", help="nombre del proyecto (por defecto: reel_<fecha>)")
    ap.add_argument("--perfil", default="dinamico", choices=list(PERFILES),
                    help="agresividad del corte (por defecto: dinamico). "
                         "'largo' es para video horizontal de YouTube: quita "
                         "muletillas y respeta el aire de una charla larga")
    ap.add_argument("--escala-texto", type=float, metavar="F",
                    help="agranda o encoge todo el texto (1.0 = el del lienzo)")
    ap.add_argument("--modelo", default="medium",
                    help="modelo whisper: tiny/base/small/medium/large-v3")
    ap.add_argument("--idioma", default="es", help="idioma hablado (por defecto: es)")
    ap.add_argument("--sin-subtitulos", action="store_true")
    ap.add_argument("--solo-plan", action="store_true",
                    help="muestra que cortaria, sin crear nada")
    ap.add_argument("--mp4", action="store_true",
                    help="renderiza un MP4 + SRT en vez del proyecto de CapCut")
    ap.add_argument("--max-hueco", type=float,
                    help="pausa maxima tolerada en segundos (sobrescribe el perfil)")
    args = ap.parse_args()

    if args.ver_letras:
        from pipeline import letras as _l
        disp = _l.fuentes_disponibles()
        print("")
        print("ESTILOS DE LETRA (--letras <nombre>)")
        print("")
        for k, v in _l.ESTILOS.items():
            falta = v["fuente"] and v["fuente"] not in disp
            print("  %-9s %s%s" % (k, v["descripcion"],
                                   "   [FALTA la fuente %s]" % v["fuente"] if falta else ""))
        print("")
        print("Fuentes descargadas en este CapCut (%d):" % len(disp))
        print("  " + ", ".join(sorted(disp)))
        print("")
        print("Para usar otra, agregala una vez a mano en CapCut y vuelve a generar.")
        print("")
        return

    if args.ver_frases:
        from pipeline import frases as _f
        disp = _f.disponibles()
        print("")
        print("ESTILOS DE LA FRASE CLAVE")
        print("")
        print('En el plan: "frases": [{"ini": 3.3, "fin": 6.1,')
        print('                        "texto": "NO FUNCIONABA",')
        print('                        "estilo": "bloque"}]')
        print("")
        print("Sin \"estilo\" se reparten solos y no se repite el anterior.")
        print("")
        for k in _f.ROTACION:
            ok, falta = disp[k]
            print("  %-11s %s" % (k, _f.ESTILOS[k]["descripcion"]))
            if not ok:
                print("  %-11s   [NO LISTO: falta %s]" % ("", falta))
        listos = [k for k, (o, _) in disp.items() if o]
        print("")
        print("Listos en esta computadora: %d de %d" % (len(listos), len(disp)))
        if len(listos) < len(disp):
            print("Lo que falta se descarga aplicandolo una vez a mano en CapCut.")
        print("")
        return

    if args.ver_voces:
        from pipeline import voz_off
        print("")
        print("VOCES PUBLICAS (--voz <nombre>)")
        for nombre, vid in voz_off.VOCES_PUBLICAS:
            print("  %-8s %s" % (nombre, vid))
        try:
            propias = voz_off.voces()
        except Exception as e:
            propias = []
            print("")
            print("No se pudieron listar las voces de la cuenta: %s" % e)
            print("Es normal si la clave solo tiene permiso de Text to Speech.")
            print("En ese caso pega el id de la voz directamente en --voz.")
        if propias:
            print("")
            print("VOCES DE LA CUENTA")
            for vid, nombre, idioma in propias:
                print("  %-24s %s %s" % (nombre, vid, idioma))
        print("")
        return

    if args.guion:
        try:
            reel_de_guion(args)
        except (RuntimeError, ValueError) as e:
            sys.exit("ERROR: %s" % e)
        return

    if args.desde_plan:
        try:
            nucleo.editar_con_plan(
                args.desde_plan,
                args.nombre or nucleo.nombre_por_defecto(),
                modelo=args.modelo, idioma=args.idioma,
                subtitulos=not args.sin_subtitulos,
                salida="mp4" if args.mp4 else "capcut",
                captions=args.captions, zoom=args.zoom, letras=args.letras,
                cifra=args.cifras, escala_texto=args.escala_texto)
        except (RuntimeError, ValueError) as e:
            sys.exit("ERROR: %s" % e)
        return

    if not args.videos:
        sys.exit("Indica videos, una carpeta, o --desde-plan plan.json")

    videos = []
    for v in args.videos:
        if os.path.isdir(v):
            encontrados = nucleo.listar_videos(v)
            if not encontrados:
                sys.exit("No hay videos en la carpeta: %s" % v)
            videos += encontrados
        elif os.path.exists(v):
            videos.append(v)
        else:
            sys.exit("No encuentro: %s" % v)

    print("Clips (%d):" % len(videos))
    for i, v in enumerate(videos, 1):
        print("  %d. %s" % (i, os.path.basename(v)))

    try:
        nucleo.editar(
            videos,
            args.nombre or nucleo.nombre_por_defecto(),
            perfil=args.perfil,
            modelo=args.modelo,
            idioma=args.idioma,
            subtitulos=not args.sin_subtitulos,
            salida="mp4" if args.mp4 else "capcut",
            solo_plan=args.solo_plan,
            max_hueco=args.max_hueco,
            quitar_tomas=not args.sin_tomas,
            captions=args.captions,
            letras=args.letras,
            cifra=args.cifras,
            escala_texto=args.escala_texto,
            zoom=args.zoom,
        )
    except (RuntimeError, ValueError) as e:
        sys.exit("ERROR: %s" % e)


if __name__ == "__main__":
    main()
