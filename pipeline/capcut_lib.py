"""Generacion de drafts usando la libreria pycapcut (github.com/GuanYixuan/pyCapCut).

Es el port para CapCut internacional de pyJianYingDraft, con cientos de usuarios
verificando que sus drafts abren. Sustituye a nuestro escritor artesanal
(pipeline/capcut.py), que reproduce el formato pero CapCut 9.2 rechaza por algun
detalle no identificado.

Nota importante aprendida de esa comunidad: NO se toca root_meta_info.json.
CapCut descubre la carpeta nueva por si mismo al reiniciarse.
"""
import json
import os
import shutil

import pycapcut as cc

from . import cifras as mod_cifras
from . import frases as mod_frases
from . import letras as mod_letras

from . import zoom as zoom_mod
from .entorno import RAIZ, US, _capcut_abierto

# intensidades del zoom (ajustables)
ZOOM_SUAVE_HASTA = 1.05    # drift dentro del clip: 1.0 -> esto
ZOOM_PASO = 0.08           # cuanto se acerca cada corte en modo progresivo
ZOOM_TOPE = 1.20           # acercamiento maximo del progresivo
ZOOM_PUNCH = 1.14          # pico del punch automatico (modo 'punch')

# Animaciones propias de CapCut para dar movimiento real de camara. Se usan
# cuando un segmento del plan pide "mov". Antes eran el unico recurso porque
# se creia que los keyframes de escala no se aplicaban; resulto ser un bug de
# pycapcut (ver _kf_escala) y ya no hace falta recurrir a estas por eso.
ANIMACIONES = {
    "acercar": getattr(cc.IntroType, "轻微放大", None),    # acercamiento leve
    "acercar_fuerte": getattr(cc.IntroType, "放大", None),  # acercamiento marcado
    "dinamico": getattr(cc.IntroType, "动感放大", None),    # con inercia
    "entrar": getattr(cc.IntroType, "飞近", None),          # entra desde lejos
}

# Entrega: los reels se publican a 1080x1920. CapCut hace lo mismo al importar
# un 4K vertical (comprobado en los proyectos del usuario: fuente 2160x3840 ->
# canvas 1080x1920, escala 1.0). Dejar el canvas en 4K hace que el texto se vea
# diminuto, porque su tamano es absoluto y no relativo al lienzo.
LADO_MAX = 1920
TAM_CAPTION_PALABRA = 20.0   # a canvas de 1920 de alto
TAM_CAPTION_CLASICO = 10.0

# El tamano del texto se escala por el LADO MENOR del lienzo, no por el alto.
#
# Antes era `alto / 1920`, que en un reel vertical da 1.0 y esta aprobado,
# pero en el video horizontal de YouTube (1920x1080) da 0.5625: los
# subtitulos salian a poco mas de la mitad de tamano.
#
# En vertical las dos formulas dan EXACTAMENTE lo mismo, y no por casualidad:
# en 9:16 el ancho es alto*9/16, asi que ancho/1080 == alto/1920 para
# cualquier tamano de lienzo (1080x1920 -> 1.0, 720x1280 -> 0.667,
# 2160x3840 -> 2.0). Por eso los reels no se mueven ni un punto.
LADO_TEXTO = 1080.0
# En horizontal la escala se MIDIO, no se dedujo (2026-08-29, captura del
# primer video de YouTube): a escala 1.0 el caption salia como al 14% del alto
# y le tapaba la cara -o sea que un size de CapCut NO rinde los mismos pixeles
# en un lienzo ancho; rinde ~1.8x mas, proporcional al ancho-. La deduccion
# anterior (escalar por el lado menor) daba texto gigante, no chico como
# predecia el encargo: nadie lo habia visto en pantalla. 0.35 lo deja ~5% del
# alto, el subtitulo normal de YouTube. Se ajusta con --escala-texto.
ESCALA_TEXTO_HORIZONTAL = 0.35
# Y abajo, no bajo el centro: en un plano medio horizontal la cara ocupa el
# centro del cuadro. -0.72 centra el texto al 86% de la altura.
POS_CAPTION_HORIZONTAL = -0.72


def escala_texto(ancho, alto, lado=LADO_TEXTO):
    """Cuanto hay que agrandar el texto para este lienzo.

    Vertical: la formula validada por los reels (alto/1920, identica a
    min/1080 en 9:16). Horizontal: el factor medido de arriba.
    """
    if ancho > alto:
        return ESCALA_TEXTO_HORIZONTAL * alto / float(lado)
    return min(ancho, alto) / float(lado)


def canvas_entrega(ancho, alto, lado_max=LADO_MAX):
    """Reduce el lienzo al tamano de entrega manteniendo la proporcion."""
    mayor = max(ancho, alto)
    if mayor <= lado_max:
        return ancho, alto
    factor = lado_max / float(mayor)
    return (max(2, int(round(ancho * factor / 2)) * 2),
            max(2, int(round(alto * factor / 2)) * 2))


def construir(nombre, video, keeps, srt_path=None, carpeta_raiz=None):
    """Crea el draft con pycapcut. keeps = [(ini, fin)] en segundos del original."""
    raiz = carpeta_raiz or RAIZ
    if not os.path.isdir(raiz):
        raise RuntimeError("No encuentro la carpeta de proyectos de CapCut:\n  " + raiz)
    if _capcut_abierto():
        raise RuntimeError(
            "CapCut esta abierto. Cierralo por completo y vuelve a ejecutar.")
    carpeta_previa = os.path.join(raiz, nombre)
    if os.path.exists(carpeta_previa):
        # Una generacion que falla a media deja la carpeta creada pero sin
        # `draft_content.json`, y el siguiente intento moria con "ya existe"
        # -mandando a cambiar el nombre cuando lo que hacia falta era barrer
        # el cascaron-. Un proyecto de verdad SIEMPRE tiene ese archivo.
        if os.path.exists(os.path.join(carpeta_previa, "draft_content.json")):
            raise RuntimeError(
                "Ya existe un proyecto llamado '%s'. Elige otro nombre." % nombre)
        shutil.rmtree(carpeta_previa, ignore_errors=True)

    folder = cc.DraftFolder(raiz)
    script = folder.create_draft(nombre, video["width"], video["height"],
                                 fps=int(round(video["fps"])))
    script.add_track(cc.TrackType.video)

    cursor, n_seg = 0, 0
    for ini, fin in keeps:
        dur = int(round((fin - ini) * US))
        if dur <= 0:
            continue
        seg = cc.VideoSegment(
            video["path"],
            cc.trange(cursor, dur),
            source_timerange=cc.trange(int(round(ini * US)), dur),
        )
        script.add_segment(seg)
        cursor += dur
        n_seg += 1

    if n_seg == 0:
        raise RuntimeError("El plan de cortes quedo vacio: no hay nada que exportar.")

    n_subs = 0
    if srt_path and os.path.exists(srt_path):
        script.import_srt(srt_path, "subtitulos",
                          text_style=cc.TextStyle(size=7.0))
        n_subs = sum(1 for linea in open(srt_path, encoding="utf-8")
                     if "-->" in linea)

    script.save()
    return {"carpeta": os.path.join(raiz, nombre), "duracion_us": cursor,
            "segmentos": n_seg, "subtitulos": n_subs}


def construir_segmentos(nombre, segmentos, canvas, srt_path=None, carpeta_raiz=None,
                        palabras=None, captions="clasico", zoom="no",
                        palabras_por_clip=None, callouts=None, broll=None,
                        sfx=None, efectos=None, transiciones=None,
                        letras="resalte", cifra="pop", musica=None,
                        overlays=None, voz=None, frases=None,
                        escala_texto_forzada=None, caption_altura=None,
                        log=None):
    """Crea el draft desde una lista de trozos que pueden venir de VARIOS clips.

    segmentos : [{"path": ruta, "ini": seg, "fin": seg}] en orden de linea de tiempo
    canvas    : (ancho, alto, fps) tomados del primer clip
    palabras  : palabras con tiempos en la linea de tiempo FINAL (para captions)
    captions  : "clasico" (frases via SRT) | "palabra" (1-2 palabras, estilo reel)
    zoom      : "no" | "suave" (drift lento dentro de cada clip)
                | "progresivo" (se acerca un paso en cada corte; plano abierto al
                  cambiar de idea, detectado por la pausa larga en el original)
                | "punch" (envolvente asimetrica solo en las frases con enfasis,
                  elegidas por estructura del habla y limitadas en densidad)
    """
    raiz = carpeta_raiz or RAIZ
    if not os.path.isdir(raiz):
        raise RuntimeError("No encuentro la carpeta de proyectos de CapCut:\n  " + raiz)
    if _capcut_abierto():
        raise RuntimeError(
            "CapCut esta abierto. Cierralo por completo y vuelve a ejecutar.")
    carpeta_previa = os.path.join(raiz, nombre)
    if os.path.exists(carpeta_previa):
        # Una generacion que falla a media deja la carpeta creada pero sin
        # `draft_content.json`, y el siguiente intento moria con "ya existe"
        # -mandando a cambiar el nombre cuando lo que hacia falta era barrer
        # el cascaron-. Un proyecto de verdad SIEMPRE tiene ese archivo.
        if os.path.exists(os.path.join(carpeta_previa, "draft_content.json")):
            raise RuntimeError(
                "Ya existe un proyecto llamado '%s'. Elige otro nombre." % nombre)
        shutil.rmtree(carpeta_previa, ignore_errors=True)
    if not segmentos:
        raise RuntimeError("El plan de cortes quedo vacio: no hay nada que exportar.")

    ancho, alto, fps = canvas
    ancho, alto = canvas_entrega(ancho, alto)
    folder = cc.DraftFolder(raiz)
    script = folder.create_draft(nombre, ancho, alto, fps=int(round(fps)))
    script.add_track(cc.TrackType.video)

    trans = {}
    if transiciones:
        from . import efectos as mod_ef
        catalogo_tr = mod_ef.transiciones_disponibles()
        for t in transiciones:
            cfg = catalogo_tr.get(t.get("tipo"))
            if cfg:
                trans[int(t.get("corte", -1))] = (cfg, t.get("dur", cfg["dur"]))

    punches = {}
    if zoom == "punch":
        punches = zoom_mod.elegir_punches(segmentos, palabras_por_clip)

    # un material por archivo, reutilizado entre trozos del mismo clip
    materiales = {}
    cursor = 0
    escala = 1.0        # nivel actual del zoom progresivo
    anterior = None
    for idx, s in enumerate(segmentos):
        dur = int(round((s["fin"] - s["ini"]) * US))
        if dur <= 0:
            continue
        ruta = os.path.abspath(s["path"])
        if ruta not in materiales:
            materiales[ruta] = cc.VideoMaterial(ruta)
        # Lo que se pide del clip no puede pasar de lo que el clip dura. ffmpeg
        # ajusta el video a cuadros enteros, asi que un clip pedido de 8.21 s
        # sale de 8.20 y pycapcut lo rechaza con un ValueError EN CHINO que no
        # dice de que clip habla. Es el mismo caso que ya se arreglo para las
        # pistas de audio: se recorta a lo que hay.
        disponible = int(materiales[ruta].duration) - int(round(s["ini"] * US))
        if disponible <= 0:
            continue
        dur = min(dur, disponible)

        clip = None
        zoom_anim = None
        curva = None
        mov = None
        if s.get("zoom"):
            # zoom decidido en revision (plan.json): manda sobre el modo automatico.
            #   escalar        -> punch estatico
            #   [a, b]         -> entra en a y crece hasta b durante la frase
            #   {"punch": 1.15}-> envolvente asimetrica: entra rapido, sostiene,
            #                     suelta lento (se lee como intencion, no deriva)
            z = s["zoom"]
            if isinstance(z, dict):
                # ZOOM SECO: escala fija durante todo el corte, sin animacion.
                # Cada corte entra ya en su encuadre, como un cambio de camara.
                # La animacion queda opcional ("anim"): se lee como "efecto",
                # no como camara. Si se usa, los keyframes van con scale_x Y
                # scale_y (ver _kf_escala), nunca con uniform_scale.
                pico = float(z.get("punch", z.get("pico", 1.14)))
                # ANCLA: a que altura se queda quieta la imagen al escalar.
                # Centrada (0) el recorte se reparte arriba y abajo, y en un
                # primer plano lo de arriba es la frente. Con ancla=1 la imagen
                # baja lo justo para que el borde superior no se mueva y todo
                # el recorte se lo lleve la camisa, que no la mira nadie.
                # transform_y va en unidades de media pantalla, y al escalar s
                # la imagen sobresale (s-1)/2 por lado: bajar (s-1) unidades
                # deja el borde de arriba justo donde estaba.
                ancla = float(z.get("ancla", 0.0))
                # "x" / "y" explicitos mandan sobre el ancla: hacen falta al
                # recortar un video HORIZONTAL a lienzo vertical, donde la
                # escala ya no es "1 + un poco" sino ~3.2 y la cara no esta
                # en el centro del recorte.
                clip = cc.ClipSettings(scale_x=pico, scale_y=pico,
                                       transform_x=float(z.get("x", 0.0)),
                                       transform_y=float(z["y"]) if "y" in z
                                       else -ancla * (pico - 1.0))
                mov = z.get("mov")
                if z.get("anim"):
                    curva = zoom_mod.envolvente(
                        s["fin"] - s["ini"], base=float(z.get("base", 1.0)),
                        pico=pico, volver=bool(z.get("volver", True)))
            elif isinstance(z, (list, tuple)):
                zoom_anim = (float(z[0]), float(z[1]))
                clip = cc.ClipSettings(scale_x=zoom_anim[0], scale_y=zoom_anim[0])
            else:
                clip = cc.ClipSettings(scale_x=float(z), scale_y=float(z))
        elif zoom == "punch" and idx in punches:
            clip = cc.ClipSettings(scale_x=ZOOM_PUNCH, scale_y=ZOOM_PUNCH)
        elif zoom == "progresivo":
            # nueva idea (cambio de clip o pausa larga en el original) -> plano abierto
            if anterior and (s["path"] != anterior["path"]
                             or s["ini"] - anterior["fin"] > 1.2):
                escala = 1.0
            if escala > 1.001:
                clip = cc.ClipSettings(scale_x=round(escala, 3),
                                       scale_y=round(escala, 3))

        seg = cc.VideoSegment(
            materiales[ruta],
            cc.trange(cursor, dur),
            source_timerange=cc.trange(int(round(s["ini"] * US)), dur),
            clip_settings=clip,
            # En el reel grabado manda el audio del clip. En el de guion los
            # clips son stock y su audio estorba: el plan los marca mudos.
            volume=float(s.get("volumen", 1.0)),
        )

        # Movimiento nativo de CapCut: son sus propias animaciones, asi que se
        # renderizan seguro aunque los keyframes no se apliquen.
        if mov:
            anim = ANIMACIONES.get(mov if isinstance(mov, str) else "acercar")
            if anim is not None:
                seg.add_animation(anim, min(dur // 2, 900_000))

        if curva:
            for t_seg, valor in curva:
                _kf_escala(seg, min(int(round(t_seg * US)), dur), round(valor, 4))
        elif zoom_anim:
            _kf_escala(seg, 0, zoom_anim[0])
            _kf_escala(seg, dur, zoom_anim[1])
        elif zoom == "suave" and dur > 800_000 and not s.get("zoom"):
            # drift casi imperceptible dentro del clip (Ken Burns discreto)
            _kf_escala(seg, 0, 1.0)
            _kf_escala(seg, dur, ZOOM_SUAVE_HASTA)

        if idx in trans:
            cfg, dur_tr = trans[idx]
            seg.add_transition(cfg["obj"], duration=int(round(float(dur_tr) * US)))

        script.add_segment(seg)
        cursor += dur
        if zoom == "progresivo":
            escala = min(escala + ZOOM_PASO, ZOOM_TOPE)   # siguiente corte, un paso mas cerca
        anterior = s

    n_broll = _insertar_broll(script, broll, cursor, canvas)
    # la voz primero: queda debajo de todo y es la que manda
    n_voz = _insertar_musica(script, voz, cursor, pista="voz")
    n_musica = _insertar_musica(script, musica, cursor)
    n_sfx = _insertar_sfx(script, sfx, cursor)
    _avisar_overlays_tapados(overlays, broll, log)
    n_over = _insertar_overlays(script, overlays, cursor, log)
    n_efectos = _insertar_efectos(script, efectos, cursor)
    # `escala` sale del lienzo salvo que el plan la fije: en horizontal es lo
    # unico de este pipeline que no se ha podido MEDIR contra pantalla, asi
    # que se deja ajustable sin tocar codigo.
    escala = (float(escala_texto_forzada) if escala_texto_forzada
              else escala_texto(ancho, alto))
    receta = mod_letras.receta(letras)
    pos_caption = POS_CAPTION_HORIZONTAL if ancho > alto else None
    # El plan puede fijar la altura del caption, y hace falta cuando el cuadro
    # es una COMPOSICION: en un clip de demo de pantalla el documento va
    # arriba y la webcam abajo, asi que el 66% del CUADRO cae a media cara
    # -sobre la boca- en vez de sobre el pecho. Sin esto habria que mover la
    # constante global y se moverian los reels aprobados.
    if caption_altura is not None:
        pos_caption = float(caption_altura)
    n_datos = _callouts_datos(script, callouts, escala, cursor, receta,
                              cifra=cifra, canvas_ancho=canvas[0])
    # Las frases van ANTES que los captions a proposito: asi los captions
    # quedan en la pista de encima y se leen aunque una tarjeta caiga cerca.
    n_frases = _frases_clave(script, frases, escala, cursor, log=log)
    n_subs = 0
    if captions == "palabra" and palabras:
        n_subs = _captions_palabra(script, palabras, cursor, receta,
                                   escala_texto=escala,
                                   transform_y=pos_caption)
    elif srt_path and os.path.exists(srt_path):
        n_subs = _captions_srt(script, srt_path, receta, escala,
                               **({"transform_y": pos_caption}
                                  if pos_caption is not None else {}))

    script.save()
    carpeta = os.path.join(raiz, nombre)
    _igualar_font_size(carpeta)
    _resolver_efectos(carpeta)
    mod_letras.resolver(carpeta)
    return {"carpeta": carpeta, "duracion_us": cursor,
            "segmentos": len(segmentos), "subtitulos": n_subs, "datos": n_datos,
            "broll": n_broll, "sfx": n_sfx, "efectos": n_efectos,
            "musica": n_musica, "overlays": n_over, "voz": n_voz,
            "frases": n_frases}


def _kf_escala(seg, t_us, valor):
    """Keyframe de escala en los DOS ejes.

    NUNCA usar cc.KeyframeProperty.uniform_scale: pycapcut lo traduce a
    "KFTypeScaleX" y no escribe nunca la Y, asi que lo que sale no es un zoom
    sino un ESTIRON horizontal -- la cara se ensancha. Se comprobo el
    2026-08-24 generando el draft y leyendo el property_type antes de abrirlo.

    De ahi venia la regla dura 6 ("CapCut ignora los keyframes de video"): no
    los ignoraba, se le estaba pidiendo mal. Con los dos ejes se ven.
    """
    seg.add_keyframe(cc.KeyframeProperty.scale_x, t_us, valor)
    seg.add_keyframe(cc.KeyframeProperty.scale_y, t_us, valor)


def _insertar_efectos(script, lista, dur_total_us):
    """Pista de efectos visuales de CapCut, por resource_id.

    pycapcut trae el catalogo completo, asi que se escribe el MISMO efecto que
    el usuario eligio a mano, no una imitacion.

    OJO: hay que usar script.add_effect(), no add_segment() con un
    EffectSegment. add_segment no acepta ese tipo y deja el segmento apuntando
    a un material que no se escribe en materials.video_effects; CapCut abre el
    proyecto y tira la pista entera sin avisar. Sintoma: "no se ve nada".
    """
    if not lista:
        return 0
    from . import efectos as mod
    catalogo = mod.disponibles()
    puestos = 0
    for e in lista:
        cfg = catalogo.get(e.get("tipo"))
        if not cfg:
            continue
        ini_us = int(round(max(0.0, float(e.get("ini", 0))) * US))
        dur_us = int(round(float(e.get("dur", cfg["dur"])) * US))
        dur_us = min(dur_us, dur_total_us - ini_us)
        if dur_us < 100_000:
            continue
        if not puestos:
            script.add_track(cc.TrackType.effect, "efectos visuales")
        script.add_effect(cfg["tipo"], cc.trange(ini_us, dur_us),
                          "efectos visuales")
        puestos += 1
    return puestos


def _avisar_overlays_tapados(overlays, broll, log):
    """Avisa si un adorno cae donde el b-roll ocupa la pantalla.

    Paso de verdad: el circulo sobre una cifra coincidia con un b-roll a
    pantalla completa y solo le quedaban 0.5 s libres, justo cuando el trazo
    empieza a dibujarse. En pantalla no se vio NADA y el draft era correcto,
    asi que no habia nada que depurar. Es un choque de montaje, no un fallo.
    """
    if not overlays or not broll or log is None:
        return
    for o in overlays:
        a, b = float(o.get("ini", 0)), float(o.get("fin", 0))
        libre = b - a
        for x in broll:
            i, f = float(x.get("ini", 0)), float(x.get("fin", 0))
            libre -= max(0.0, min(b, f) - max(a, i))
        if libre < (b - a) * 0.6:
            log("  aviso: el adorno de %.1fs queda tapado por el b-roll "
                "(solo %.1fs a la vista)" % (a, max(0.0, libre)))


def _insertar_overlays(script, lista, dur_total_us, log=None):
    """Adornos animados encima del video: subrayados, circulos, destellos.

    Van en su propia pista por encima del A-roll y del b-roll, asi que se
    pueden mover y escalar a mano sin tocar nada mas.

    ⚠️ **Pero NO por encima de los captions**, como decia esta nota. Se midio
    en un draft generado (2026-09-06): la pista "adornos" es de VIDEO y sale
    con `render_index` 2, mientras que cualquier pista de TEXTO nace en
    15000 -es la base del tipo en pycapcut, no algo que se elija-. El texto
    gana siempre. Para subrayar una cifra da igual, porque el trazo tiene
    que verse sobre el numero y ahi lo que hay debajo es el A-roll; lo que
    NO se puede hacer por aqui es tapar un subtitulo.

    🔑 Y por eso esta pista sirve para algo que no son adornos: una segunda
    IMAGEN opaca. En los clips verticales de una demo de pantalla, la webcam
    entra aqui -llena la mitad de abajo y los captions siguen leyendose
    encima-. Ver "Los clips de una demo van en DOS piezas" en CLAUDE.md.

    Con `perfil`/`ancho`/`altura` se mide el CANAL ALFA del archivo y se
    descarta el que no lo tenga: un .mp4 opaco taparia el cuadro entero y
    pycapcut no expone modo de fusion. Con `escala`/`y` a pelo no se mide
    nada, que es justo lo que hace falta para la webcam.
    """
    if not lista:
        return 0

    # 🔑 Un overlay puede pedir su PROPIA pista con `"pista"`. Hace falta en
    # cuanto dos se SOLAPAN en el tiempo: la webcam de un clip de pantalla
    # dura todo el clip y la tarjeta de cierre cae dentro, asi que en una
    # sola pista pycapcut lo rechaza por segmentos encimados. El nombre
    # tambien le sirve a el para saber que esta agarrando en CapCut.
    pistas = []
    for o in lista:
        p = o.get("pista") or "adornos"
        if p not in pistas:
            pistas.append(p)
    for i, p in enumerate(pistas):
        script.add_track(cc.TrackType.video, p, relative_index=2 + i)

    n = 0
    for o in lista:
        ruta = o.get("archivo")
        if not ruta or not os.path.exists(ruta):
            continue
        ini = float(o.get("ini", 0))
        fin = min(float(o.get("fin", 0)), dur_total_us / US)
        dur = int(round((fin - ini) * US))
        if dur < 200_000:
            continue
        desde = int(round(float(o.get("desde", 0)) * US))

        # La escala NO se pide a ojo: se dice que fraccion del ancho debe
        # ocupar el trazo y `adornos` la calcula midiendo el archivo. Poner
        # "0.80" a mano dejo un circulo que el usuario tuvo que agrandar hasta
        # 1.778, porque cada .mov trae su trazo con distinto aire alrededor.
        escala, y = o.get("escala"), o.get("y")
        if o.get("perfil") or o.get("ancho") or o.get("altura"):
            from . import adornos as mod_ad
            puesto = mod_ad.colocar(ruta, ancho=o.get("ancho"),
                                    altura=o.get("altura"),
                                    perfil=o.get("perfil"))
            if not puesto:
                # sin alfa medible: mejor no ponerlo que tapar el video con un
                # rectangulo opaco
                if log:
                    log("  aviso: %s no tiene canal alfa medible; se omite"
                        % os.path.basename(ruta))
                continue
            escala = puesto["escala"] if escala is None else escala
            y = puesto["y"] if y is None else y

        clip = cc.ClipSettings(
            transform_y=float(y if y is not None else 0.0),
            transform_x=float(o.get("x", 0.0)),
            scale_x=float(escala if escala is not None else 1.0),
            scale_y=float(escala if escala is not None else 1.0),
            alpha=float(o.get("alpha", 1.0)))
        seg = cc.VideoSegment(cc.VideoMaterial(ruta),
                              cc.trange(int(round(ini * US)), dur),
                              source_timerange=cc.trange(desde, dur),
                              volume=0.0, clip_settings=clip)
        script.add_segment(seg, o.get("pista") or "adornos")
        n += 1
    return n


FADE_MUSICA_OUT = 1_500_000    # 1.5 s: cortar la musica en seco suena a error


def _insertar_musica(script, cfg, dur_total_us, pista="musica"):
    """Pista de musica de fondo, por debajo de todo.

    cfg = {"archivo", "desde", "volumen", "fade_in", "fade_out"}

    El volumen NO se inventa: se mide contra la voz (ver
    `musica.volumen_bajo_voz`). En el caso real la pista estaba 4 dB mas
    fuerte que el habla, asi que cualquier valor "razonable" de oido la habria
    dejado tapando al que habla.
    """
    if not cfg:
        return 0
    ruta = cfg.get("archivo")
    if not ruta or not os.path.exists(ruta):
        return 0
    desde_us = int(round(float(cfg.get("desde", 0)) * US))
    material = cc.AudioMaterial(ruta)
    # Lo que se pide del archivo no puede pasar de lo que el archivo tiene.
    # Pedirle 8.2 s a una voz de 7.05 s revienta con un ValueError EN CHINO que
    # no dice de que pista habla. Pasa siempre que el audio es mas corto que el
    # video: una voz en off sobre una imagen fija, o una musica corta que no se
    # repite. Mejor sonar hasta donde alcance -y avisarlo- que no generar nada.
    disponible = max(int(material.duration) - desde_us, 0)
    if disponible <= 0:
        return 0
    usar_us = min(dur_total_us, disponible)
    script.add_track(cc.TrackType.audio, pista)
    seg = cc.AudioSegment(material,
                          cc.trange(0, usar_us),
                          source_timerange=cc.trange(desde_us, usar_us),
                          volume=float(cfg.get("volumen", 0.10)))
    seg.add_fade(int(cfg.get("fade_in", 0)), int(cfg.get("fade_out",
                                                         FADE_MUSICA_OUT)))
    script.add_segment(seg, pista)
    return 1


def _insertar_sfx(script, lista, dur_total_us):
    """Pista de audio con los efectos, por debajo de la voz.

    Van bajos a proposito: un efecto que se OYE distrae; uno que se SIENTE
    subraya el corte sin que el espectador sepa por que.
    """
    if not lista:
        return 0

    # Los efectos se solapan a proposito (un whoosh que entra antes del corte
    # mientras suena el impacto), y una pista no admite segmentos encimados.
    # Se reparten en pistas paralelas, como en cualquier montaje de sonido.
    pistas = []          # [(nombre, fin_ocupado_en_us)]
    materiales = {}
    n = 0
    for e in sorted(lista, key=lambda x: float(x.get("ini", 0))):
        ruta = e.get("archivo")
        if not ruta or not os.path.exists(ruta):
            continue
        ini_us = int(round(max(0.0, float(e.get("ini", 0))) * US))
        if ini_us >= dur_total_us:
            continue
        dur_us = int(round(float(e["duracion"]) * US))
        dur_us = min(dur_us, dur_total_us - ini_us)
        if dur_us < 50_000:
            continue

        elegida = None
        for idx, (nombre, ocupado) in enumerate(pistas):
            if ini_us >= ocupado:
                elegida = idx
                break
        if elegida is None:
            nombre = "efectos" if not pistas else "efectos %d" % (len(pistas) + 1)
            script.add_track(cc.TrackType.audio, nombre)
            pistas.append([nombre, 0])
            elegida = len(pistas) - 1

        if ruta not in materiales:
            materiales[ruta] = cc.AudioMaterial(ruta)
        desde_us = int(round(float(e.get("desde", 0)) * US))
        seg = cc.AudioSegment(materiales[ruta], cc.trange(ini_us, dur_us),
                              source_timerange=cc.trange(desde_us, dur_us),
                              volume=float(e.get("volumen", 0.25)))
        script.add_segment(seg, pistas[elegida][0])
        pistas[elegida][1] = ini_us + dur_us
        n += 1
    return n


MARGEN_LLENADO = 1.04   # un pelo de mas: sin esto asoma el borde al redondear


def escala_para_llenar(w, h, canvas_w, canvas_h):
    """Cuanto hay que escalar un material para que CUBRA el lienzo.

    CapCut coloca el material ENCAJADO (letterbox), no recortado, asi que un
    clip apaisado en un lienzo vertical sale como una franja con dos barras
    negras enormes. A escala 1.0 se ve mal y no da ningun error.

    Se calcula, no se pide a ojo -misma leccion que `adornos.py`-: es la razon
    entre las dos proporciones, la que sea mayor que 1.
    """
    if not w or not h or not canvas_w or not canvas_h:
        return 1.0
    material, lienzo = float(w) / h, float(canvas_w) / canvas_h
    razon = max(material / lienzo, lienzo / material)
    return 1.0 if razon <= 1.001 else round(razon * MARGEN_LLENADO, 3)


def _insertar_broll(script, lista, dur_total_us, canvas=None):
    """Pista de superposicion con los clips de apoyo, en silencio.

    Van a pantalla completa y cortos: el reel es de una persona hablando, el
    b-roll ilustra un momento y devuelve la imagen. Nunca sobre la frase clave
    — tapar el golpe con stock lo debilita.

    🔴 "A pantalla completa" hay que CALCULARLO. Los 7 clips verticales del
    2026-09-05 reusaron stock apaisado del video largo y salieron los 7 con el
    clip metido en una franja: el usuario los agrando a mano a 3.3-3.5. Ahora
    lo hace `escala_para_llenar()`; sus valores medidos (3.472 y 3.305) salen
    a menos del 5%.
    """
    if not lista:
        return 0
    script.add_track(cc.TrackType.video, "broll", relative_index=1)
    n = 0
    ocupado = 0.0
    for b in sorted(lista, key=lambda x: float(x.get("ini", 0))):
        ruta = b.get("archivo")
        if not ruta or not os.path.exists(ruta):
            continue
        ini = float(b.get("ini", 0))
        fin = min(float(b.get("fin", 0)), dur_total_us / US)
        # Misma proteccion que ya tenian las cifras y las frases: una pista no
        # admite segmentos encimados y pycapcut lanza al toparse uno, tirando
        # la generacion ENTERA por unas decimas de solape. Se recorta.
        if ini < ocupado:
            ini = ocupado
        if fin - ini < 0.3:
            continue
        ocupado = fin
        dur = int(round((fin - ini) * US))
        if dur < 300_000:
            continue
        desde = int(round(float(b.get("desde", 0)) * US))
        # Un clip de stock mas corto de lo que se le pide revienta dentro de
        # pycapcut con un mensaje en chino que no dice cual fue. Aqui se dice el
        # archivo, lo que dura y lo que se le pidio, que es lo unico accionable.
        mat = cc.VideoMaterial(ruta)
        largo = getattr(mat, "duration", None)
        if largo and desde + dur > largo:
            raise RuntimeError(
                "El b-roll '%s' dura %.2f s y el plan le pide de %.2f a %.2f s. "
                "Baja su 'desde', acorta el tramo, o usa un clip mas largo."
                % (os.path.basename(ruta), largo / US, desde / US, (desde + dur) / US))
        escala = escala_para_llenar(getattr(mat, "width", None),
                                    getattr(mat, "height", None),
                                    (canvas or (None, None))[0],
                                    (canvas or (None, None))[1])
        seg = cc.VideoSegment(
            mat,
            cc.trange(int(round(ini * US)), dur),
            source_timerange=cc.trange(desde, dur),
            volume=0.0,                       # manda el audio de la persona
            clip_settings=cc.ClipSettings(scale_x=escala, scale_y=escala),
        )
        script.add_segment(seg, "broll")
        n += 1
    return n


TAM_CALLOUT = 30.0                 # a canvas de 1920 de alto
COLOR_CALLOUT = (1.0, 0.85, 0.15)  # ambar: se despega de los captions blancos
# transform_y: 0 = centro, +1 = borde superior. La fraccion de altura donde
# cae el texto es (0.5 - y/2), asi que 0.80 lo pone al 10% de arriba.
# Medido en los frames del usuario: franja vacia 0-14%, cabeza 15-49%.
# Con 0.42 el callout caia al 29%: sobre los ojos.
ALTURA_CALLOUT = 0.80              # franja vacia sobre la cabeza


def _callouts_datos(script, lista, escala_texto, dur_total_us, receta=None,
                    cifra="pop", canvas_ancho=1080):
    """Pista con las cifras del guion resaltadas en pantalla.

    En un reel cuyo argumento son los numeros, sacar la cifra grande justo
    cuando se dice pesa mas que cualquier b-roll generico. Como se ve cada una
    lo decide `pipeline/cifras.py`; aqui solo se coloca.
    """
    if not lista:
        return 0
    rc = mod_cifras.receta(cifra)
    fuente = (getattr(cc.FontType, rc["fuente"]) if rc["fuente"]
              else mod_letras.font_type(receta or mod_letras.receta("actual")))
    script.add_track(cc.TrackType.text, "datos")
    estilo = cc.TextStyle(size=rc["tam"] * escala_texto, bold=True, align=1,
                          color=COLOR_CALLOUT, alpha=rc["alpha"],
                          auto_wrapping=False)
    borde = (cc.TextBorder(color=(0.0, 0.0, 0.0), width=rc["borde"])
             if rc["borde"] > 0 else None)
    posicion = cc.ClipSettings(transform_y=rc["altura"])

    n = 0
    ocupado = 0.0
    for d in sorted(lista, key=lambda x: float(x.get("ini", 0))):
        texto = str(d.get("texto") or "").strip()
        ini = float(d.get("ini", 0))
        fin = min(float(d.get("fin", 0)), dur_total_us / US)
        # Una pista no admite segmentos encimados y pycapcut lanza al toparse
        # uno: un solape de 10 ms entre dos cifras tiraba la generacion entera.
        # Se recorta la anterior en vez de perder el proyecto.
        if ini < ocupado:
            ini = ocupado
        if not texto or fin - ini < 0.2:
            continue
        ocupado = fin
        dur = int(round((fin - ini) * US))
        # Una cifra larga NO se envuelve (`auto_wrapping=False`): se sale del
        # lienzo sin dar error. Se encoge lo justo para que quepa.
        enc = mod_cifras.escala_por_ancho(texto, rc, escala_texto, canvas_ancho)
        colocacion = (posicion if enc >= 0.999 else
                      cc.ClipSettings(transform_y=rc["altura"],
                                      scale_x=enc, scale_y=enc))
        seg = cc.TextSegment(texto, cc.trange(int(round(ini * US)), dur),
                             style=estilo, border=borde, clip_settings=colocacion,
                             font=fuente)
        mod_cifras.aplicar_animaciones(seg, rc, dur)
        script.add_segment(seg, "datos")
        n += 1
    return n


def _frases_clave(script, lista, escala_texto, dur_total_us, log=None):
    """Pista con la frase que carga cada bloque, en grande y rotando estilo.

    Es la segunda capa de texto: los captions palabra-por-palabra siguen abajo
    sin tocarse. Como se ve cada tarjeta lo decide `pipeline/frases.py`; aqui
    solo se coloca. Ver ese modulo para de donde salieron la altura y los seis
    tratamientos (se midieron de una edicion real, no se inventaron).
    """
    if not lista:
        return 0
    plan = mod_frases.planear(lista, log=log)
    if not plan:
        return 0
    script.add_track(cc.TrackType.text, "frases")

    n = 0
    ocupado = 0.0
    for f in plan:
        rc = mod_frases.receta(f["estilo"])
        ini = float(f.get("ini", 0))
        fin = min(float(f.get("fin", 0)), dur_total_us / US)
        # Misma proteccion que en los callouts: una pista no admite segmentos
        # encimados y pycapcut lanza al toparse uno. Se recorta en vez de
        # perder la generacion entera por 10 ms de solape.
        if ini < ocupado:
            ini = ocupado
        if fin - ini < 0.3:
            continue
        ocupado = fin
        dur = int(round((fin - ini) * US))

        estilo = cc.TextStyle(
            size=rc["tam"] * escala_texto, bold=True, align=1,
            color=rc["color"], alpha=1.0,
            auto_wrapping=True, max_line_width=mod_frases.MAX_ANCHO)
        borde = (cc.TextBorder(color=(0.0, 0.0, 0.0), width=rc["borde"])
                 if rc["borde"] > 0 else None)
        caja = cc.TextBackground(**rc["caja"]) if rc["caja"] else None
        altura = float(f.get("altura", mod_frases.ALTURA_FRASE))
        # `escala` se declara porque la altura aprobada (52%) salio de medir a
        # la editora sobre el encuadre 4K vertical del usuario. Un clip
        # RECORTADO de un video horizontal tiene otro encuadre -la cabeza
        # empieza al 21% y la cara ocupa mas cuadro-, y ahi la tarjeta pide ir
        # mas arriba y mas chica. Medido de su edicion del 2026-09-05:
        # altura 0.574, escala 0.80.
        esc_frase = float(f.get("escala", 1.0))

        seg = cc.TextSegment(
            mod_frases.texto_final(f["texto"], rc),
            cc.trange(int(round(ini * US)), dur),
            style=estilo, border=borde, background=caja,
            clip_settings=cc.ClipSettings(transform_y=altura,
                                          scale_x=esc_frase, scale_y=esc_frase),
            font=getattr(cc.FontType, rc["fuente"]) if rc["fuente"] else None)
        mod_frases.aplicar_animacion(seg, rc, dur)
        script.add_segment(seg, "frases")
        n += 1
    return n


def _resolver_efectos(carpeta):
    """Apunta cada efecto a la carpeta local de su recurso descargado.

    pycapcut deja el campo `path` con un marcador (##_material_placeholder_...).
    CapCut no lo resuelve: abre el proyecto, no encuentra el recurso y descarta
    la pista sin decir nada. El sintoma es "el efecto esta en la linea de
    tiempo pero no se ve".
    """
    from . import efectos as mod
    ruta = os.path.join(carpeta, "draft_content.json")
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)

    tocados = 0
    for e in d.get("materials", {}).get("video_effects") or []:
        rid = e.get("effect_id") or e.get("resource_id")
        local = mod.ruta_local(rid) if rid else None
        if local and str(e.get("path", "")).startswith("##"):
            e["path"] = local
            e["source_platform"] = 1
            tocados += 1
    if tocados:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)


def _igualar_font_size(carpeta):
    """pycapcut deja font_size fijo en 15.0 y CapCut se guia por ese campo.

    En todos los drafts reales font_size coincide con el tamano declarado en
    el contenido; si no, el texto sale con un tamano que nadie pidio.
    """
    ruta = os.path.join(carpeta, "draft_content.json")
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)
    tocados = 0
    for t in d.get("materials", {}).get("texts") or []:
        try:
            tam = json.loads(t["content"])["styles"][0]["size"]
        except Exception:
            continue
        if t.get("font_size") != tam:
            t["font_size"] = tam
            tocados += 1
    if tocados:
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)


# Donde cae la frase en un reel vertical. -0.22 la deja algo abajo del centro:
# por encima del 20% inferior, que en Instagram y TikTok se lo comen los botones
# y el copy, y por debajo del sujeto, que suele estar arriba.
POS_CAPTION_FRASE = -0.22


def _captions_srt(script, srt_path, receta, escala_texto=1.0,
                  transform_y=POS_CAPTION_FRASE):
    """Los bloques del SRT como texto CON el estilo de la receta.

    Antes esto era `script.import_srt(...)` pasandole solo el TAMANO, asi que
    todo caption "clasico" salia con la fuente por defecto de CapCut, delgada y
    sin contorno -mientras los captions de palabra si llevaban Anton, borde y
    color-. La misma receta tiene que valer para las dos vias: es el estilo del
    canal, no un detalle de la implementacion.
    """
    bloques = _leer_srt(srt_path)
    if not bloques:
        return 0
    script.add_track(cc.TrackType.text, "subtitulos")
    tam = receta["tam"] * escala_texto
    fuente = mod_letras.font_type(receta)
    borde = (cc.TextBorder(color=(0.0, 0.0, 0.0), width=receta["borde"])
             if receta["borde"] > 0 else None)
    posicion = cc.ClipSettings(transform_y=transform_y)
    # Una pista de texto de CapCut no admite dos bloques encima: revienta con
    # SegmentOverlap. Un SRT si puede traerlos -al extender cada tarjeta hasta
    # la siguiente para que no parpadee es facil pasarse unas centesimas-, asi
    # que se recorta el final contra el inicio del que sigue.
    ajustados = []
    for i, (ini, fin, texto) in enumerate(bloques):
        if i + 1 < len(bloques):
            fin = min(fin, bloques[i + 1][0] - 0.001)
        if fin > ini:
            ajustados.append((ini, fin, texto))
    bloques = ajustados
    for ini, fin, texto in bloques:
        dur = int(round((fin - ini) * US))
        if dur <= 0:
            continue
        seg = cc.TextSegment(
            texto, cc.trange(int(round(ini * US)), dur),
            style=cc.TextStyle(size=tam, bold=True, align=1,
                               color=receta["color"], auto_wrapping=True,
                               letter_spacing=receta["espaciado"]),
            border=borde, clip_settings=posicion, font=fuente)
        script.add_segment(seg, "subtitulos")
    return len(bloques)


def _leer_srt(ruta):
    """[(ini_seg, fin_seg, texto)] a partir de un archivo SRT."""
    def seg_de(t):
        t = t.strip().replace(",", ".")
        h, m, s = t.split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)

    bloques, ini, fin, lineas = [], None, None, []
    with open(ruta, encoding="utf-8") as f:
        for linea in list(f) + [""]:
            linea = linea.rstrip(chr(10)).rstrip(chr(13))
            if "-->" in linea:
                a, b = linea.split("-->")
                ini, fin, lineas = seg_de(a), seg_de(b), []
            elif linea.strip() == "":
                if ini is not None and lineas:
                    bloques.append((ini, fin, " ".join(lineas).strip()))
                ini, fin, lineas = None, None, []
            elif ini is not None:
                lineas.append(linea.strip())
    return bloques


def _captions_palabra(script, palabras, dur_total_us, receta=None,
                      escala_texto=1.0, max_palabras=1, max_chars=16,
                      transform_y=None):
    """Captions estilo reel: una palabra grande, centrada, con contorno negro.

    Una sola palabra por tarjeta se lee mejor que dos: con dos, la vista salta
    entre ellas y el ritmo del texto deja de coincidir con el del habla.

    Cada grupo permanece en pantalla hasta que empieza el siguiente (sin parpadeo).
    """
    script.add_track(cc.TrackType.text, "captions")

    # agrupar de a 1-2 palabras
    grupos, actual = [], []
    for w in palabras:
        if actual and (len(actual) >= max_palabras
                       or len(actual[0]["word"]) + len(w["word"]) + 1 > max_chars
                       or w["start"] - actual[-1]["end"] > 0.6):
            grupos.append(actual)
            actual = []
        actual.append(w)
    if actual:
        grupos.append(actual)

    receta = receta or mod_letras.receta("actual")
    tam = receta["tam"] * escala_texto
    fuente = mod_letras.font_type(receta)
    borde = (cc.TextBorder(color=(0.0, 0.0, 0.0), width=receta["borde"])
             if receta["borde"] > 0 else None)
    posicion = cc.ClipSettings(
        transform_y=-0.32 if transform_y is None else transform_y)  # tercio inferior

    def estilo_de(texto, previa=None):
        # las cifras se pintan aparte solo si el estilo lo pide: son las que
        # cargan el argumento y el ojo las busca
        color = receta["color"]
        if receta.get("color_dato") and mod_letras.es_dato(texto, previa):
            color = receta["color_dato"]
        return cc.TextStyle(size=tam, bold=True, align=1, color=color,
                            auto_wrapping=False,
                            letter_spacing=receta["espaciado"])

    n = 0
    previa = None            # la palabra anterior decide si un numero es dato
    for i, g in enumerate(grupos):
        texto = " ".join(w["word"] for w in g).strip()
        if not texto:
            continue
        ini = g[0]["start"]
        fin = g[-1]["end"]
        # extender hasta el siguiente grupo para que no parpadee
        if i + 1 < len(grupos):
            fin = min(grupos[i + 1][0]["start"], fin + 0.5)
        else:
            fin = min(dur_total_us / US, fin + 0.5)
        dur = int(round((fin - ini) * US))
        if dur <= 0:
            continue
        seg = cc.TextSegment(texto, cc.trange(int(round(ini * US)), dur),
                             style=estilo_de(texto, previa), border=borde,
                             clip_settings=posicion, font=fuente)
        script.add_segment(seg, "captions")
        previa = g[-1]["word"]
        n += 1
    return n
