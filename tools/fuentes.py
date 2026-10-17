"""Baja varias fuentes de CapCut de un golpe, con un proyecto catalogo.

El problema: de las 348 fuentes del catalogo, en una computadora solo estan las
que alguna vez se usaron. Pedir una que no este no falla feo, pero tampoco se
ve: hay que ir a CapCut y aplicarla a mano, una por una.

La idea: CapCut DESCARGA SOLO los recursos que un proyecto necesita al abrirlo
-- asi funcionan las plantillas que comparte la gente. Entonces se arma un
proyecto con una tarjeta por fuente; al abrirlo, CapCut deberia bajarlas todas.

    python tools/fuentes.py                 # arma el proyecto catalogo
    python tools/fuentes.py --revisar       # mide cuales llegaron
    python tools/fuentes.py --lista         # que fuentes hay y cuales faltan

Si al revisar no llego ninguna, el proyecto igual sirve: cada tarjeta lleva el
NOMBRE de su fuente, asi que se pueden aplicar a mano en un solo lugar en vez
de andar buscandolas sueltas.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pycapcut as cc

from pipeline import letras
from pipeline.entorno import consola_utf8

RAIZ = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANTES = os.path.join(BASE, "proyectos", "_fuentes_antes.json")

NOMBRE_PROYECTO = "CATALOGO DE FUENTES"
DUR_TARJETA = 1.2          # segundos por fuente
US = 1_000_000

# Titulares utiles para un reel hablado: condensadas gruesas para el caption,
# un par de marcador para acentos. No estan todas las del catalogo a proposito:
# 20 caben en un proyecto corto y se revisan de una pasada.
CANDIDATAS = [
    "BebasNeue", "Core_Sans_D_77_Cn_Black", "West_West_Condensed",
    "Cako_Black", "Coda_Heavy", "HeadlineEN", "MADE_Awelier_Black",
    "Shiny_Black", "ChunkFive", "FugazOne", "Bungee_Regular",
    "Black_Ops_One_Regular", "CHONK", "FredokaOne_Regular", "Shrikhand",
    "PermanentMarker_Regular", "Markerist", "Marvin", "Eveleth",
    "Career_Mediumblack",
]


def _existe(nombre):
    return hasattr(cc.FontType, nombre)


def faltantes(nombres):
    """De la lista dada, las que el catalogo tiene y esta maquina no."""
    tengo = set(letras.fuentes_disponibles())
    return [n for n in nombres if _existe(n) and n not in tengo]


FONDO = os.path.join(BASE, "recursos", "negro_1080x1920.mp4")


def _fondo(segundos):
    """Un video negro sobre el que leer las fuentes.

    Hace falta por dos motivos: un draft sin pista de video deja la duracion
    en cero y CapCut no tiene que mostrar, y sobre negro las letras blancas se
    leen sin ruido. Se genera una sola vez.
    """
    if os.path.exists(FONDO):
        return FONDO
    import subprocess
    os.makedirs(os.path.dirname(FONDO), exist_ok=True)
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
         "-i", "color=c=black:s=1080x1920:r=30:d=%d" % max(int(segundos) + 2, 5),
         "-c:v", "libx264", "-pix_fmt", "yuv420p", FONDO],
        capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(FONDO):
        raise SystemExit("No pude generar el fondo negro con ffmpeg:\n%s" % r.stderr)
    return FONDO


def armar(nombres, nombre_proyecto=NOMBRE_PROYECTO, log=print):
    """Proyecto con una tarjeta por fuente. Devuelve la carpeta."""
    from pipeline.entorno import _capcut_abierto
    if _capcut_abierto():
        raise SystemExit("CapCut esta abierto. Cierralo por completo y repite.")

    if os.path.exists(os.path.join(RAIZ, nombre_proyecto)):
        import shutil
        shutil.rmtree(os.path.join(RAIZ, nombre_proyecto))

    total = len(nombres) * DUR_TARJETA
    fondo = _fondo(total)

    folder = cc.DraftFolder(RAIZ)
    script = folder.create_draft(nombre_proyecto, 1080, 1920, fps=30)
    script.add_track(cc.TrackType.video)
    mat = cc.VideoMaterial(fondo)
    script.add_segment(cc.VideoSegment(
        mat, cc.trange(0, int(round(total * US))),
        source_timerange=cc.trange(0, int(round(total * US)))))
    script.add_track(cc.TrackType.text, "catalogo")
    estilo = cc.TextStyle(size=18.0, bold=True, align=1,
                          color=(1.0, 1.0, 1.0), auto_wrapping=False)
    borde = cc.TextBorder(color=(0.0, 0.0, 0.0), width=40.0)

    for i, n in enumerate(nombres):
        ini = int(round(i * DUR_TARJETA * US))
        seg = cc.TextSegment(n.replace("_", " "),
                             cc.trange(ini, int(round(DUR_TARJETA * US))),
                             style=estilo, border=borde,
                             font=getattr(cc.FontType, n),
                             clip_settings=cc.ClipSettings(transform_y=0.0))
        script.add_segment(seg, "catalogo")

    script.save()
    carpeta = os.path.join(RAIZ, nombre_proyecto)
    letras.resolver(carpeta)
    log("Proyecto '%s' con %d fuentes." % (nombre_proyecto, len(nombres)))
    return carpeta


def instantanea():
    """Que fuentes hay descargadas ahora mismo."""
    return sorted(letras.fuentes_disponibles())


def guardar_instantanea():
    os.makedirs(os.path.dirname(ANTES), exist_ok=True)
    with open(ANTES, "w", encoding="utf-8") as f:
        json.dump(instantanea(), f, ensure_ascii=False, indent=1)


def revisar(log=print):
    """Compara contra la instantanea previa y reporta las nuevas."""
    if not os.path.exists(ANTES):
        log("No hay con que comparar todavia: corre primero")
        log("  python tools/fuentes.py")
        return []
    with open(ANTES, encoding="utf-8") as f:
        antes = set(json.load(f))
    ahora = set(instantanea())
    nuevas = sorted(ahora - antes)
    log("")
    log("Antes: %d fuentes.  Ahora: %d." % (len(antes), len(ahora)))
    if nuevas:
        log("")
        log("LLEGARON %d:" % len(nuevas))
        for n in nuevas:
            log("   %s" % n)
        log("")
        log("Ya se pueden usar. Para sumarlas a un estilo, dimelo y las pongo")
        log("en pipeline/letras.py.")
    else:
        log("")
        log("No llego ninguna. CapCut no las baja solo con abrir el proyecto.")
        log("Plan B, que igual es mucho mas rapido que buscarlas sueltas:")
        log("  abre '%s', y en cada tarjeta (dice el nombre" % NOMBRE_PROYECTO)
        log("  de la fuente) aplicasela desde el panel de texto. Guarda, cierra")
        log("  y vuelve a correr --revisar.")
    return nuevas


def main():
    consola_utf8()
    args = sys.argv[1:]
    if "--lista" in args:
        tengo = letras.fuentes_disponibles()
        print("")
        print("DESCARGADAS EN ESTA COMPUTADORA (%d):" % len(tengo))
        print("  " + ", ".join(sorted(tengo)))
        faltan = faltantes(CANDIDATAS)
        print("")
        print("CANDIDATAS DE TITULAR QUE FALTAN (%d):" % len(faltan))
        print("  " + ", ".join(faltan))
        print("")
        return
    if "--revisar" in args:
        revisar()
        print("")
        return

    faltan = faltantes(CANDIDATAS)
    if not faltan:
        print("")
        print("Ya tienes todas las candidatas. Nada que bajar.")
        print("")
        return

    print("")
    print("  BAJAR FUENTES DE CAPCUT")
    print("  " + "=" * 48)
    print("")
    print("  Faltan %d de las %d candidatas." % (len(faltan), len(CANDIDATAS)))
    guardar_instantanea()
    armar(faltan, log=lambda t: print("  " + t))
    print("")
    print("  QUE HACER AHORA:")
    print("   1. Abre CapCut y entra al proyecto '%s'." % NOMBRE_PROYECTO)
    print("   2. Deja que cargue del todo (si las baja, tarda un poco).")
    print("   3. Cierra CapCut.")
    print("   4. Corre:  python tools/fuentes.py --revisar")
    print("")


if __name__ == "__main__":
    main()
