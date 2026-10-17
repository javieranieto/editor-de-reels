"""Baja de un golpe los efectos de apertura, con un proyecto catalogo.

Mismo truco que tools/fuentes.py usa con las fuentes: CapCut DESCARGA SOLO los
recursos que un proyecto necesita al abrirlo -- asi funcionan las plantillas
que comparte la gente. Se arma un proyecto con un efecto por tarjeta y, al
abrirlo, CapCut deberia bajarlos todos.

Hace falta porque de los cuatro efectos de pipeline/efectos.py en esta maquina
hay UNO descargado, y por eso la apertura sale siempre igual. Pedir uno que no
esta no da error: CapCut tira la pista sin avisar (regla dura 4).

    python tools/catalogo_efectos.py            # arma el proyecto catalogo
    python tools/catalogo_efectos.py --revisar  # mide cuales llegaron
    python tools/catalogo_efectos.py --lista    # que hay y que falta

Si no llega ninguno, el proyecto igual sirve de plan B: cada tarjeta lleva el
NOMBRE de su efecto, asi que se aplican a mano en un solo sitio en vez de
buscarlos sueltos por el panel de CapCut.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pycapcut as cc

from pipeline import efectos
from pipeline.entorno import consola_utf8

RAIZ = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANTES = os.path.join(BASE, "proyectos", "_efectos_antes.json")
FONDO = os.path.join(BASE, "recursos", "negro_1080x1920.mp4")

NOMBRE_PROYECTO = "CATALOGO DE EFECTOS"
DUR_TARJETA = 1.5          # segundos por efecto
US = 1_000_000

# Aperturas: destellos, sacudidas y glitches. Son los que sirven para el primer
# medio segundo del reel, que es lo unico donde el usuario acepta un efecto.
# Los tres primeros ya estan en pipeline/efectos.py esperando a existir aqui.
CANDIDATOS = [
    "Focus_Shake", "RGB_Shake", "Flash_Light", "Flash", "Glitch_Intro",
    "Neon_Flash", "Vintage_Flash", "Spin_Shake", "Pixel_Glitch",
    "Lightning_Twist",
]


def _tipo(nombre):
    return getattr(cc.VideoSceneEffectType, nombre, None)


def _descargado(nombre):
    t = _tipo(nombre)
    if t is None:
        return False
    rid = efectos._resource_id(t)
    return bool(rid) and efectos.ruta_local(rid) is not None


def instantanea():
    """Que efectos del catalogo estan descargados ahora mismo."""
    return sorted(n for n in CANDIDATOS if _descargado(n))


def faltantes():
    return [n for n in CANDIDATOS if _tipo(n) is not None and not _descargado(n)]


def _fondo(segundos):
    """Video negro sobre el que ver el efecto. Se genera una sola vez."""
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


def _sembrar_ids(carpeta, log=print):
    """Deja el resource_id a la vista para que CapCut sepa que bajar.

    pycapcut escribe `path` con un marcador ##_material_placeholder_... porque
    el recurso no esta en disco. Con las FUENTES se comprobo que CapCut si
    reconoce el recurso cuando el id esta escrito aunque el archivo no exista
    (letras.resolver lo hace a proposito), asi que aqui se hace lo mismo: se
    asegura effect_id/resource_id y se quita el marcador, que es basura de
    pycapcut y no una ruta.
    """
    ruta = os.path.join(carpeta, "draft_content.json")
    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)
    tocados = 0
    for e in d.get("materials", {}).get("video_effects") or []:
        rid = e.get("effect_id") or e.get("resource_id")
        if not rid:
            continue
        e["effect_id"] = str(rid)
        e["resource_id"] = str(rid)
        e["source_platform"] = 1
        # cadena vacia, NUNCA null ni el marcador: es lo que escribe
        # letras.resolver() para una fuente que todavia no esta descargada, y
        # es el unico precedente de recurso-sin-archivo que CapCut digiere.
        p = e.get("path")
        if p is None or str(p).startswith("##"):
            e["path"] = ""
        tocados += 1
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    log("  ids sembrados en %d efecto(s)" % tocados)
    return tocados


def armar(nombres=None, nombre_proyecto=NOMBRE_PROYECTO, log=print):
    """Proyecto con una tarjeta por efecto. Devuelve la carpeta."""
    from pipeline.entorno import _capcut_abierto
    if _capcut_abierto():
        raise SystemExit("CapCut esta abierto. Cierralo por completo y repite.")

    nombres = [n for n in (nombres or CANDIDATOS) if _tipo(n) is not None]
    if not nombres:
        raise SystemExit("Ninguno de los efectos pedidos existe en pycapcut.")

    destino = os.path.join(RAIZ, nombre_proyecto)
    if os.path.exists(destino):
        import shutil
        shutil.rmtree(destino)

    total = len(nombres) * DUR_TARJETA
    fondo = _fondo(total)

    folder = cc.DraftFolder(RAIZ)
    script = folder.create_draft(nombre_proyecto, 1080, 1920, fps=30)
    script.add_track(cc.TrackType.video)
    mat = cc.VideoMaterial(fondo)
    script.add_segment(cc.VideoSegment(
        mat, cc.trange(0, int(round(total * US))),
        source_timerange=cc.trange(0, int(round(total * US)))))

    # el nombre de cada efecto, para poder aplicarlos a mano si no se bajan
    script.add_track(cc.TrackType.text, "nombres")
    estilo = cc.TextStyle(size=12.0, bold=True, align=1,
                          color=(1.0, 1.0, 1.0), auto_wrapping=False)
    borde = cc.TextBorder(color=(0.0, 0.0, 0.0), width=40.0)

    # add_effect(), NUNCA add_segment() con un EffectSegment: regla dura 5
    script.add_track(cc.TrackType.effect, "efectos")
    for i, n in enumerate(nombres):
        ini = int(round(i * DUR_TARJETA * US))
        dur = int(round(DUR_TARJETA * US))
        script.add_effect(_tipo(n), cc.trange(ini, dur), "efectos")
        script.add_segment(cc.TextSegment(
            n.replace("_", " "), cc.trange(ini, dur), style=estilo, border=borde,
            clip_settings=cc.ClipSettings(transform_y=-0.75)), "nombres")

    script.save()
    carpeta = os.path.join(RAIZ, nombre_proyecto)
    _sembrar_ids(carpeta, log=log)
    log("Proyecto %s con %d efectos." % (nombre_proyecto, len(nombres)))
    return carpeta


def guardar_instantanea():
    os.makedirs(os.path.dirname(ANTES), exist_ok=True)
    with open(ANTES, "w", encoding="utf-8") as f:
        json.dump(instantanea(), f, ensure_ascii=False, indent=1)


def revisar(log=print):
    """Compara contra la instantanea previa y reporta los nuevos."""
    if not os.path.exists(ANTES):
        log("No hay con que comparar todavia: corre primero")
        log("  python tools/catalogo_efectos.py")
        return []
    with open(ANTES, encoding="utf-8") as f:
        antes = set(json.load(f))
    ahora = set(instantanea())
    nuevos = sorted(ahora - antes)
    log("")
    log("Antes: %d efectos.  Ahora: %d." % (len(antes), len(ahora)))
    if nuevos:
        log("")
        log("LLEGARON %d:" % len(nuevos))
        for n in nuevos:
            log("   %s" % n)
        log("")
        log("Ya se pueden usar de apertura. Dimelo y los meto en el catalogo")
        log("de pipeline/efectos.py para poder rotarlos.")
    else:
        log("")
        log("No llego ninguno: CapCut no los baja solo con abrir el proyecto.")
        log("Plan B, mucho mas rapido que buscarlos sueltos:")
        log("  abre el proyecto CATALOGO DE EFECTOS y en cada tarjeta (dice el")
        log("  nombre del efecto) aplicalo desde el panel de Efectos. Guarda,")
        log("  cierra y vuelve a correr --revisar.")
    return nuevos


def main():
    consola_utf8()
    args = sys.argv[1:]

    if "--lista" in args:
        print("Efectos de apertura del catalogo de pycapcut:")
        for n in CANDIDATOS:
            if _tipo(n) is None:
                print("   %-18s no existe en esta version de pycapcut" % n)
            else:
                print("   %-18s %s" % (n, "descargado" if _descargado(n) else "FALTA"))
        return

    if "--revisar" in args:
        revisar()
        return

    faltan = faltantes()
    print("Descargados ahora: %d de %d." % (len(instantanea()), len(CANDIDATOS)))
    if not faltan:
        print("No falta ninguno: no hace falta el catalogo.")
        return
    guardar_instantanea()
    armar(log=print)
    print("")
    print("AHORA:")
    print("  1. Abre CapCut y entra al proyecto CATALOGO DE EFECTOS.")
    print("  2. Deja que cargue del todo, dale play a la linea de tiempo.")
    print("  3. Cierra CapCut.")
    print("  4. python tools/catalogo_efectos.py --revisar")


if __name__ == "__main__":
    main()
