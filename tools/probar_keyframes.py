"""Demuestra por que los keyframes de escala parecian no funcionar.

La regla dura 6 decia que CapCut ignora los keyframes en segmentos de VIDEO.
Es falso, y la causa real es un bug de pycapcut:

    scale_x       -> "KFTypeScaleX"
    scale_y       -> "KFTypeScaleY"
    uniform_scale -> "KFTypeScaleX"     <- y NUNCA escribe la Y

Al pedirle `uniform_scale`, pycapcut escribe solo el eje X. Eso no es un zoom:
es un ESTIRON horizontal que ensancha la cara. Comprobado el 2026-08-24
leyendo el `property_type` del draft recien generado, antes de abrirlo. La
pista salio del cookbook de cutcli (xuliang2024/cutcli-cookbook), que
documenta scale_x/scale_y y no menciona uniform_scale.

El proyecto pone el MISMO clip tres veces, rotulado:

    0-4 s   CONTROL             sin keyframes, la referencia
    4-8 s   UNIFORM SCALE       se estira de ancho (el bug)
    8-12 s  SCALE X + SCALE Y   se acerca de verdad

El control no es adorno: "se mueve" solo significa algo al lado de algo que
no se mueve.

Uso:  python tools/probar_keyframes.py [clip.mp4]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pycapcut as cc

from pipeline.entorno import consola_utf8, _capcut_abierto

RAIZ = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NOMBRE = "PRUEBA KEYFRAMES"
US = 1_000_000
DUR = 4 * US
HASTA = 2.2          # exagerado a proposito: aqui no se busca gusto, se busca ver


def clip_por_defecto():
    """Un clip con una cara: la deformacion del bug se ve en la cara.

    Busca el primer b-roll de stock ya descargado (proyectos/_broll/). Si no
    hay, se pasa uno a mano: python tools/probar_keyframes.py <clip.mp4>
    """
    import glob
    for p in sorted(glob.glob(os.path.join(BASE, "proyectos", "_broll", "*.mp4"))):
        if os.path.getsize(p) > 10000:
            return p
    return None


def armar(clip, log=print):
    if _capcut_abierto():
        raise SystemExit("CapCut esta abierto. Cierralo por completo y repite.")
    destino = os.path.join(RAIZ, NOMBRE)
    if os.path.exists(destino):
        import shutil
        shutil.rmtree(destino)

    folder = cc.DraftFolder(RAIZ)
    script = folder.create_draft(NOMBRE, 1080, 1920, fps=30)
    script.add_track(cc.TrackType.video)

    mat = cc.VideoMaterial(clip)
    largo = getattr(mat, "duration", 0)
    if largo < DUR:
        raise SystemExit("El clip dura %.1f s y hacen falta %d s."
                         % (largo / US, DUR // US))

    # --- 0: control, sin keyframes
    script.add_segment(cc.VideoSegment(
        mat, cc.trange(0, DUR), source_timerange=cc.trange(0, DUR), volume=0.0))

    # --- 1: el bug. Solo escribe el eje X, asi que estira en vez de acercar
    a = cc.VideoSegment(mat, cc.trange(DUR, DUR),
                        source_timerange=cc.trange(0, DUR), volume=0.0)
    a.add_keyframe(cc.KeyframeProperty.uniform_scale, 0, 1.0)
    a.add_keyframe(cc.KeyframeProperty.uniform_scale, DUR, HASTA)
    script.add_segment(a)

    # --- 2: los dos ejes. Esto si es un zoom
    b = cc.VideoSegment(mat, cc.trange(2 * DUR, DUR),
                        source_timerange=cc.trange(0, DUR), volume=0.0)
    for prop in (cc.KeyframeProperty.scale_x, cc.KeyframeProperty.scale_y):
        b.add_keyframe(prop, 0, 1.0)
        b.add_keyframe(prop, DUR, HASTA)
    script.add_segment(b)

    # rotulos, para saber cual se esta viendo
    script.add_track(cc.TrackType.text, "rotulos")
    estilo = cc.TextStyle(size=9.0, bold=True, align=1, color=(1.0, 1.0, 1.0),
                          auto_wrapping=False)
    borde = cc.TextBorder(color=(0.0, 0.0, 0.0), width=40.0)
    for i, texto in enumerate(("0) CONTROL\nno se mueve",
                               "1) UNIFORM SCALE\nse ESTIRA de ancho",
                               "2) SCALE X + SCALE Y\nse ACERCA de verdad")):
        script.add_segment(cc.TextSegment(
            texto, cc.trange(i * DUR, DUR), style=estilo, border=borde,
            clip_settings=cc.ClipSettings(transform_y=-0.78)), "rotulos")

    script.save()
    log("Proyecto '%s' con el clip %s" % (NOMBRE, os.path.basename(clip)))
    return os.path.join(RAIZ, NOMBRE)


def main():
    consola_utf8()
    clip = sys.argv[1] if len(sys.argv) > 1 else clip_por_defecto()
    if not clip or not os.path.exists(clip):
        sys.exit("No encuentro un clip para la prueba. Pasa uno:\n"
                 "  python tools/probar_keyframes.py <clip.mp4>")
    armar(clip)
    print("")
    print("AHORA: abre CapCut, entra a '%s' y dale play." % NOMBRE)
    print("  0) no se mueve: es la referencia.")
    print("  1) se ESTIRA a lo ancho y la cara se deforma: ese es el bug.")
    print("  2) se ACERCA sin deformarse: asi es como debe verse.")


if __name__ == "__main__":
    main()
