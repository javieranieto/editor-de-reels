"""Orquestador del flujo completo: uno o varios clips -> proyecto CapCut o MP4.

Es el corazon compartido por la linea de comandos (reel.py) y la interfaz
grafica (interfaz.pyw). Recibe una funcion `log` para reportar progreso.
"""
import glob
import json
import os
import time

from . import biblioteca, efectos, sonidos, tomas, voz
from .entorno import _agrupar_subtitulos
from .plan import PERFILES, planear
from .probe import probe
from .transcribe import transcribe

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRABAJO = os.path.join(BASE, "proyectos")

EXTENSIONES = (".mp4", ".mov", ".mkv", ".avi", ".m4v")


def listar_videos(carpeta):
    """Videos de una carpeta en orden alfabetico (= orden de grabacion en camaras)."""
    encontrados = []
    for ext in EXTENSIONES:
        encontrados += glob.glob(os.path.join(carpeta, "*" + ext))
        encontrados += glob.glob(os.path.join(carpeta, "*" + ext.upper()))
    return sorted(set(encontrados), key=lambda p: os.path.basename(p).lower())


def _mmss(s):
    return "%d:%05.2f" % (int(s // 60), s % 60)


def _dur_humana(seg):
    if seg < 60:
        return "%.1f s" % seg
    return "%d min %d s" % (int(seg // 60), int(seg % 60))


def editar(videos, nombre, perfil="dinamico", modelo="medium", idioma="es",
           subtitulos=True, salida="capcut", solo_plan=False, max_hueco=None,
           quitar_tomas=True, captions="clasico", zoom="no", letras="resalte",
           cifra="pop", escala_texto=None, log=print):
    """Procesa los clips en orden y entrega el resultado.

    videos : lista de rutas en el orden en que van en la linea de tiempo
    salida : "capcut" (proyecto listo) o "mp4" (video renderizado + SRT)
    Devuelve un dict con estadisticas y rutas de lo generado.
    """
    if not videos:
        raise ValueError("No hay videos que procesar")
    if perfil not in PERFILES:
        raise ValueError("Perfil desconocido: %s" % perfil)

    t_inicio = time.time()
    t_transcripcion = 0.0

    trabajo = os.path.join(TRABAJO, nombre)
    os.makedirs(trabajo, exist_ok=True)

    segmentos = []        # [{"path", "ini", "fin"}] en tiempo del clip original
    palabras_finales = [] # palabras con tiempos en la linea de tiempo FINAL
    cursor = 0.0
    dur_total = 0.0
    canvas = None
    muletillas = 0
    guion = []            # transcripcion anotada para revision humana (o de Claude)
    por_clip = {}         # palabras por archivo, para elegir enfasis del zoom

    for n, ruta in enumerate(videos, 1):
        log("[%d/%d] %s" % (n, len(videos), os.path.basename(ruta)))
        v = probe(ruta)
        if not v["has_audio"]:
            log("  sin audio: se conserva entero, sin cortes")
            segmentos.append({"path": ruta, "ini": 0.0, "fin": v["duration"]})
            cursor += v["duration"]
            dur_total += v["duration"]
            continue
        try:
            voz.avisar_audio(ruta, log)
        except Exception:
            pass    # un aviso nunca debe impedir que se arme el reel
        if canvas is None:
            canvas = (v["width"], v["height"], v["fps"])
        elif (v["width"], v["height"]) != canvas[:2]:
            log("  aviso: resolucion %dx%d distinta al primer clip (%dx%d)"
                % (v["width"], v["height"], canvas[0], canvas[1]))

        cache = os.path.join(trabajo, "cache_%02d_%s.json"
                             % (n, os.path.splitext(os.path.basename(ruta))[0]))
        t0 = time.time()
        tr = transcribe(ruta, cache_path=cache, model_size=modelo, language=idioma)
        t_transcripcion += time.time() - t0

        palabras = tr["words"]
        rangos = []
        if quitar_tomas:
            rangos, reporte = tomas.detectar(palabras)
            for linea in reporte:
                log("  " + linea)
            if rangos:
                palabras = tomas.filtrar_palabras(palabras, rangos)

        por_clip[ruta] = tr["words"]
        extra = {"max_gap": max_hueco} if max_hueco else {}
        keeps, stats = planear(palabras, v["duration"], perfil=perfil, **extra)

        # el transcript a veces se come la ultima palabra de una frase; el audio
        # no miente, asi que se estiran los cortes hasta el final real del habla
        try:
            tramos = voz.intervalos_voz(
                ruta, v["duration"],
                cache_path=os.path.join(trabajo, "voz_%02d.json" % n))
            antes = list(keeps)
            keeps = voz.ajustar(keeps, tramos, duracion=v["duration"])
            rescatados = sum(1 for a, b in zip(antes, keeps) if abs(a[1] - b[1]) > 0.05)
            if rescatados:
                log("  %d corte(s) estirados al final real de la voz" % rescatados)
        except Exception as e:
            log("  aviso: no se pudo medir la voz (%s); sigo con el transcript"
                % str(e)[:60])
        # `len(segmentos)` es el numero que le tocara al primer keep de este
        # clip: mas abajo se anaden en el mismo orden, uno por keep.
        guion += _guion_clip(os.path.basename(ruta), tr["words"], rangos, keeps,
                             base=len(segmentos))
        muletillas += stats.get("muletillas_eliminadas", 0)
        dur_total += v["duration"]

        log("  %s -> %s  (%d trozos, %d muletillas fuera)"
            % (_mmss(stats["duracion_original"]), _mmss(stats["duracion_final"]),
               stats["cortes"], stats.get("muletillas_eliminadas", 0)))

        for ini, fin in keeps:
            palabras_finales += palabras_del_tramo(palabras, ini, fin, cursor)
            segmentos.append({"path": ruta, "ini": ini, "fin": fin})
            cursor += fin - ini

    if canvas is None:
        canvas = (1080, 1920, 30.0)

    dur_final = cursor
    resumen = {
        "clips": len(videos),
        "duracion_original": round(dur_total, 2),
        "duracion_final": round(dur_final, 2),
        "ahorro_seg": round(dur_total - dur_final, 2),
        "ahorro_pct": round(100 * (dur_total - dur_final) / dur_total, 1) if dur_total else 0,
        "trozos": len(segmentos),
        "muletillas_eliminadas": muletillas,
    }
    log("TOTAL: %s -> %s  (ahorro %s, %.1f%%)"
        % (_mmss(dur_total), _mmss(dur_final),
           _mmss(resumen["ahorro_seg"]), resumen["ahorro_pct"]))

    with open(os.path.join(trabajo, "plan.json"), "w", encoding="utf-8") as f:
        json.dump({"segmentos": segmentos, "resumen": resumen}, f,
                  ensure_ascii=False, indent=1)

    with open(os.path.join(trabajo, "guion.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(_cabecera_guion(nombre) + guion
                          + _resumen_segmentos(segmentos, por_clip)))
    log("guion.txt: transcripcion anotada y numerada por segmento")

    # Aqui las palabras salen de transcribir los clips: no hay ningun `plan`
    # del que sacar `bloques_texto`, eso es cosa de `editar_con_plan`. Este
    # bloque llego copiado de alla y `plan` no existe en esta funcion, asi que
    # CUALQUIER corrida moria con NameError justo despues de escribir
    # guion.txt -incluida `--solo-plan`-. Se reconoce porque la carpeta del
    # proyecto queda con plan.json y guion.txt pero SIN subtitulos.srt.
    srt_path = os.path.join(trabajo, "subtitulos.srt")
    n_srt = _escribir_srt(srt_path, palabras_finales)
    log("subtitulos.srt: %d lineas" % n_srt)

    resultado = {"resumen": resumen, "trabajo": trabajo, "srt": srt_path}

    def _cerrar():
        total = time.time() - t_inicio
        resumen["tiempo_seg"] = round(total, 1)
        log("Tiempo de trabajo: %s (transcripcion: %s)"
            % (_dur_humana(total), _dur_humana(t_transcripcion)))

    if solo_plan:
        log("Modo solo-plan: no se creo nada mas. Revisa plan.json")
        _cerrar()
        return resultado

    if salida == "mp4":
        from .render import renderizar_segmentos
        destino = os.path.join(trabajo, nombre + ".mp4")
        log("Renderizando MP4 (volumen normalizado a -14 LUFS)...")
        peso = renderizar_segmentos(segmentos, destino)
        log("%s (%.1f MB)" % (destino, peso / 1e6))
        resultado["mp4"] = destino
        _cerrar()
        return resultado

    from . import capcut_lib
    log("Creando el proyecto de CapCut...")
    res = capcut_lib.construir_segmentos(
        nombre, segmentos, canvas,
        srt_path=srt_path if subtitulos else None,
        palabras=palabras_finales if subtitulos else None,
        captions=captions, zoom=zoom, palabras_por_clip=por_clip,
        letras=letras, cifra=cifra, escala_texto_forzada=escala_texto)
    log("Proyecto '%s': %d clips, %d subtitulos" % (nombre, res["segmentos"], res["subtitulos"]))
    log("Abre CapCut y buscalo en tu lista de proyectos.")
    resultado["capcut"] = res["carpeta"]
    _cerrar()
    return resultado


def _resolver_broll(lista, canvas, carpeta, log=print):
    """Deja cada b-roll con su `archivo`. Los que vienen por `consulta` se buscan.

    En el plan se puede escribir el b-roll de dos maneras:

        {"ini": 120, "fin": 123, "archivo": "C:/.../clip.mp4"}   <- como siempre
        {"ini": 120, "fin": 123, "consulta": "phone repair shop"} <- se busca

    La orientacion NO se pide: sale del lienzo del proyecto. Un reel vertical
    y un video horizontal de YouTube necesitan material distinto, y pedirle
    vertical al catalogo para un 1920x1080 devuelve clips que habria que
    recortar por la mitad.

    Una escena sin imagen se queda sin ella y se dice: preferir eso a una
    imagen que no viene al caso es la regla que ya rige en `pertinencia`.
    """
    if not lista:
        return lista
    pendientes = [b for b in lista if not b.get("archivo") and b.get("consulta")]
    if not pendientes:
        return lista

    from . import stock
    orientacion = stock.orientacion_de(canvas)
    log("  b-roll: %d consulta(s) a buscar en %s" % (len(pendientes), orientacion))
    buscar = stock.crear_buscador(carpeta, orientacion=orientacion, log=log)
    salida = []
    for b in lista:
        if b.get("archivo") or not b.get("consulta"):
            salida.append(b)
            continue
        ruta = buscar(b["consulta"], float(b.get("fin", 0)) - float(b.get("ini", 0)))
        if ruta:
            salida.append(dict(b, archivo=ruta))
    stock.resumen(buscar.informe, log=log)
    return salida


def _lista(plan, clave, por_defecto):
    """El valor del plan si es una lista; False significa "ninguno"."""
    v = plan.get(clave)
    if isinstance(v, list):
        return v
    return [] if v is False else (por_defecto or [])


def _preparar_musica(plan, duracion_us, log=print):
    """Deja lista la musica de fondo del plan, midiendo su volumen.

    En el plan: {"musica": {"archivo": ..., "desde": 0, "debajo": 18}}

    El volumen se MIDE contra la voz en vez de fijarse a ojo. En el caso real
    la pista estaba 4 dB mas fuerte que el habla, asi que un valor "razonable"
    la habria dejado encima del que habla.
    """
    cfg = plan.get("musica")
    if not cfg or not cfg.get("archivo"):
        return None
    ruta = cfg["archivo"]
    if not os.path.exists(ruta):
        log("  musica: no encuentro %s" % os.path.basename(ruta))
        return None

    from . import musica as mod_mus
    salida = dict(cfg)
    if not cfg.get("volumen"):
        # Contra la VOZ, y en un reel de guion la voz no esta en los segmentos:
        # esos van mudos a proposito y muchos ni traen pista de audio. Medir
        # contra el primer clip devolvia None y el volumen caia al 0.10 por
        # defecto haciendose pasar por medido -la musica salia al triple de lo
        # calculado-. En un reel grabado a camara el primer segmento SI trae la
        # voz dentro, y por eso el fallo no habia mordido hasta ahora.
        voz = (plan.get("voz") or {}).get("archivo")
        if not (voz and os.path.exists(voz)):
            voz = (plan.get("segmentos") or [{}])[0].get("path")
        if voz and os.path.exists(voz):
            # `lufs` cuando hay voz en off: son frases separadas por silencios y
            # el promedio simple los cuenta, hundiendo el nivel de la voz.
            metodo = "lufs" if (plan.get("voz") or {}).get("archivo") else "medio"
            salida["volumen"] = mod_mus.volumen_bajo_voz(
                ruta, voz, debajo=float(cfg.get("debajo",
                                                mod_mus.DEBAJO_DE_LA_VOZ)),
                metodo=metodo, log=log)
        else:
            log("  aviso: no hay con que comparar la musica; volumen 0.10 "
                "por defecto, NO medido")
            salida["volumen"] = 0.10
    log("  musica: %s (volumen %.3f)"
        % (os.path.basename(ruta)[:44], salida["volumen"]))
    return salida


def _preparar_sfx(plan, duracion, palabras=None, log=print):
    """Efectos de sonido del plan, o deducidos del montaje si no vienen dados."""
    if plan.get("sfx") is False:
        return None
    rutas = sonidos.disponibles()
    if not rutas:
        log("  aviso: no hay sonidos en recursos/sfx_usuario/ (riser, reveal, "
            "swish, pop); sigo sin sonido. Ver el LEEME.md de esa carpeta")
        return None

    eventos = plan.get("sfx")
    if not isinstance(eventos, list):
        eventos = sonidos.planear(plan["segmentos"], plan.get("datos"),
                                  duracion, palabras)

    # Un sonido se puede quitar sin tener que escribir la lista entera a mano.
    # Nacio del riser: abre bien un reel, pero en los clips cortos "se oye muy
    # feo, se usa de vez en cuando pero no abusar". Quitarlo era reescribir
    # los 12 eventos; ahora es una linea.
    fuera = plan.get("sfx_sin")
    if fuera:
        fuera = set(fuera if isinstance(fuera, (list, tuple, set)) else [fuera])
        eventos = [e for e in eventos if e.get("tipo") not in fuera]

    import subprocess
    duraciones = {}
    for tipo, cfg in rutas.items():
        try:
            duraciones[tipo] = float(subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "csv=p=0", cfg["ruta"]],
                capture_output=True, text=True).stdout.strip())
        except Exception:
            duraciones[tipo] = 0.5

    listos = []
    for e in eventos:
        tipo = e.get("tipo")
        if tipo not in rutas:
            continue
        cfg = rutas[tipo]
        desde, dur = sonidos.recorte(cfg, duraciones[tipo],
                                     max(0.1, duracion - e["ini"]))
        listos.append(dict(e, archivo=cfg["ruta"], desde=desde, duracion=dur))
    return listos


def palabras_del_tramo(palabras, ini, fin, base):
    """Palabras de un tramo, con sus tiempos llevados a la linea de tiempo final.

    Una palabra que EMPIEZA dentro del corte se dijo dentro del corte, y entra
    entera. Para la que viene arrastrando del corte anterior sigue valiendo la
    regla de la mitad: exigir que quepa entera dejaba fuera las de los bordes y
    los subtitulos salian incompletos.

    La mitad NO basta en el borde de SALIDA, y eso costo dos frases visibles
    en un video largo. Whisper estira el final de la ultima palabra antes de
    una pausa hasta el siguiente sonido: la ultima palabra del gancho media
    16.71-17.43 y el corte caia en 16.84 -donde el habla real YA habia
    terminado, medido con `voz.intervalos_voz`-, asi que solo quedaba dentro el
    18% y la palabra se caia del subtitulo. Se oye y no se lee. Salio en el
    gancho y en el remate, que son justo las dos frases que mas importan.

    Un limite contiguo -los que reparte `tools/planos.py`- cae siempre en el
    punto medio de un silencio entre dos palabras, asi que ninguna palabra lo
    cruza y esto no puede duplicar nada.
    """
    salida = []
    for w in palabras:
        a, b = max(w["start"], ini), min(w["end"], fin)
        dentro = b - a
        dur = w["end"] - w["start"]
        if dentro <= 0:
            continue
        if not (ini <= w["start"] < fin) and dur > 0 and dentro < dur * 0.5:
            continue
        salida.append({"start": base + (a - ini), "end": base + (b - ini),
                       "word": w["word"]})
    return salida


def _marca_segmentos(nums):
    """#5 para uno, #15-16 cuando la frase cruza el corte entre dos."""
    if not nums:
        return "--"
    if len(nums) == 1:
        return "#%d" % nums[0]
    return "#%d-%d" % (nums[0], nums[-1])


def _guion_clip(nombre_clip, words, rangos_tomas, keeps, base=0):
    """Transcripcion anotada de un clip: que quedo, con QUE NUMERO, y que salio.

    El numero es el del segmento en plan.json (`base` es cuantos segmentos
    lleva la linea de tiempo antes de este clip). Sin el hay que cruzar
    tiempos a mano para decir "quita el 15 y el 28", que es justo la decision
    que esta revision existe para tomar.

    La etiqueta MENTIA en las frases largas. Se marcaba FUERA cuando ninguno
    de los DOS EXTREMOS caia dentro de un tramo conservado, asi que un bloque
    de 88 s que en realidad se conserva casi entero salia como
    "FUERA silencio" -el corte solo le habia recortado las puntas-. Ahora se
    mide cuanto de la frase se conserva de verdad, sumando el solape con cada
    tramo, y se dice el porcentaje.
    """
    lineas = ["", "=== %s ===" % nombre_clip]
    for frase in tomas._frases(words):
        ini, fin = frase[0]["start"], frase[-1]["end"]
        dur = max(fin - ini, 1e-6)
        texto = " ".join(w["word"] for w in frase)
        en_toma = any(ri - 0.05 <= ini and fin <= rf + 0.05 for ri, rf in rangos_tomas)

        # cuanto de la frase sobrevive, y en que segmento(s) queda
        dentro, nums = 0.0, []
        for j, (ki, kf) in enumerate(keeps):
            solape = min(fin, kf) - max(ini, ki)
            if solape > 0:
                dentro += solape
                nums.append(base + j)
        pct = 100.0 * dentro / dur

        if en_toma:
            marca, estado = "--", "FUERA toma repetida"
        elif not nums or dentro < 0.05:
            marca, estado = "--", "FUERA silencio"
        else:
            marca = _marca_segmentos(nums)
            estado = "entera" if pct >= 99.5 else "%.0f%% dentro" % pct

        linea = "[%7.2f-%7.2f] %-8s %-19s %s" % (ini, fin, marca, estado, texto)
        # repeticiones quitadas DENTRO de esta frase (tomas sin pausa)
        for ri, rf in rangos_tomas:
            if ri < fin and rf > ini and not (ri - 0.05 <= ini and fin <= rf + 0.05):
                linea += "   << se quito toma repetida interna %.1f-%.1fs" % (ri, rf)
        lineas.append(linea)
    return lineas


def _cabecera_guion(nombre):
    """Como se lee este archivo. Sin esto, la columna nueva no dice nada."""
    return [
        "GUION ANOTADO — %s" % nombre,
        "",
        "Columnas:  [inicio-fin en el video ORIGINAL]  segmento  cuanto se conserva  texto",
        "",
        "  #5       la frase vive en el segmento 5 de plan.json",
        "  #15-16   la frase cruza dos segmentos: ahi cae un corte",
        "  --       de esa frase no se conserva nada",
        "",
        "Para quitar un bloque entero, borra ese segmento de plan.json y regenera:",
        '  python reel.py --desde-plan "<plan.json>" --nombre "<nombre>"',
        "",
        "Los tiempos de aqui son los del ORIGINAL, no los del video ya cortado.",
        "Una frase larga puede repartirse entre dos segmentos; la verdad de que",
        "se conserva esta en plan.json.",
    ]


def _resumen_segmentos(segmentos, palabras_por_clip, ancho=96):
    """Indice por numero de segmento: es la lista sobre la que se decide.

    El guion anotado va por frases y un bloque de 4 minutos son decenas de
    lineas; para decidir que se va hace falta ver los 38 segmentos de un
    vistazo, con su duracion, que es lo que dice cuanto se ahorra al quitarlo.
    """
    lineas = ["", "", "=" * 78,
              "RESUMEN POR SEGMENTO   (el numero es el indice en plan.json)",
              "=" * 78,
              "  #    empieza      dura   de que habla"]
    for i, s in enumerate(segmentos):
        ws = palabras_por_clip.get(s["path"]) or []
        texto = " ".join(w["word"] for w in ws
                         if s["ini"] <= (w["start"] + w["end"]) / 2.0 <= s["fin"])
        if len(texto) > ancho:
            texto = texto[:ancho - 3].rsplit(" ", 1)[0] + "..."
        lineas.append("%3d  %9s  %7s   %s"
                      % (i, _mmss(s["ini"]), _dur_corta(s["fin"] - s["ini"]), texto))
    total = sum(s["fin"] - s["ini"] for s in segmentos)
    lineas += ["", "%d segmentos, %s en total." % (len(segmentos), _dur_humana(total))]
    return lineas


def _dur_corta(seg):
    """Duracion compacta para una tabla: 4.0s / 2m30s."""
    if seg < 60:
        return "%.1fs" % seg
    return "%dm%02ds" % (int(seg // 60), int(round(seg % 60)))


def editar_con_plan(plan_path, nombre, modelo="medium", idioma="es",
                    subtitulos=True, salida="capcut", captions="clasico",
                    letras="resalte", cifra="pop", escala_texto=None,
                    zoom="no", log=print):
    """Genera el resultado desde un plan.json ya revisado/editado a mano.

    Permite el flujo con revision: primero `--solo-plan`, alguien (humano o
    Claude) ajusta los segmentos del plan.json, y esto lo convierte en
    proyecto sin volver a analizar nada.
    """
    t_inicio = time.time()
    with open(plan_path, encoding="utf-8") as f:
        plan = json.load(f)
    segmentos = plan["segmentos"]
    if not segmentos:
        raise ValueError("El plan no tiene segmentos")

    trabajo = os.path.join(TRABAJO, nombre)
    os.makedirs(trabajo, exist_ok=True)
    carpeta_plan = os.path.dirname(os.path.abspath(plan_path))

    # El plan de un guion (voz en off + stock) ya trae las palabras con sus
    # tiempos exactos, sacados de la alineacion del TTS. Ahi NO hay que
    # transcribir: los clips de stock van mudos, asi que whisper devolveria
    # nada -o peor, inventaria- y `voz.ajustar` pegaria los cortes a un habla
    # que no existe. Ver `guion.py` y `voz_off.py`.
    de_guion = bool(plan.get("palabras") and (plan.get("voz") or {}).get("archivo"))

    # transcripciones: reutiliza las caches que quedaron junto al plan
    palabras_por_clip = {}
    tramos_voz = {}
    canvas = None
    for ruta in dict.fromkeys(s["path"] for s in segmentos):
        v = probe(ruta)
        if canvas is None:
            canvas = (v["width"], v["height"], v["fps"])
        if de_guion:
            tramos_voz[ruta] = []
            palabras_por_clip[ruta] = []
            continue
        try:
            tramos_voz[ruta] = voz.intervalos_voz(
                ruta, v["duration"],
                cache_path=os.path.join(trabajo, "voz_%s.json"
                                        % os.path.splitext(os.path.basename(ruta))[0]))
        except Exception:
            tramos_voz[ruta] = []
        base = os.path.splitext(os.path.basename(ruta))[0]
        candidatas = glob.glob(os.path.join(carpeta_plan, "cache_*_%s.json" % base))
        cache = candidatas[0] if candidatas else os.path.join(
            trabajo, "cache_00_%s.json" % base)
        tr = transcribe(ruta, cache_path=cache, model_size=modelo, language=idioma)
        palabras_por_clip[ruta] = tr["words"]

    # `voz.ajustar` pega los cortes al habla real y esta pensado para reels,
    # donde los cortes caen en SILENCIOS. En un corte narrativo el limite cae
    # a media emision, y SEGUIR_SONIDO lo estira tragandose palabras que se
    # habian quitado a proposito: en el primer video largo un corte pedido en
    # 76.10 salio en 78.17, con la frase siguiente -que se habia quitado-
    # cortada en el aire, y otro arranco a media palabra. Un plan de corte
    # narrativo declara
    # "pegar_voz": false y sus tiempos mandan tal cual.
    if not de_guion and plan.get("pegar_voz", True):
        # el plan revisado trae tiempos a mano o de una corrida vieja: se pegan
        # igualmente al habla real para que el ritmo no se sienta lento
        ajustados = []
        for ruta in dict.fromkeys(s["path"] for s in segmentos):
            del_clip = [s for s in segmentos if s["path"] == ruta]
            keeps = voz.ajustar([(s["ini"], s["fin"]) for s in del_clip],
                                tramos_voz.get(ruta) or [],
                                duracion=probe(ruta)["duration"])
            for s, (a, b) in zip(del_clip, keeps):
                ajustados.append((segmentos.index(s), dict(s, ini=a, fin=b)))
        for i, s in ajustados:
            segmentos[i] = s

    if de_guion:
        # los tiempos ya son los de la voz: los subtitulos salen de ella, no de
        # recortar palabras por clip (los clips no tienen ninguna)
        palabras_finales = plan["palabras"]
        cursor = sum(s["fin"] - s["ini"] for s in segmentos)
    else:
        palabras_finales, cursor = [], 0.0
        for s in segmentos:
            # Un segmento puede declarar `"captions": false` y entonces NO
            # lleva subtitulo quemado. Hace falta cuando lo que se ve en
            # pantalla ES texto que hay que leer: en una demo de pantalla
            # compartida el caption cae al 86% de la altura y ahi vive el
            # documento; medido sobre un fotograma real, tapaba una linea
            # entera del informe -justo el detalle que estaba narrando-. Se
            # dejan en las partes a camara, donde no tapan nada.
            if s.get("captions") is not False:
                palabras_finales += palabras_del_tramo(
                    palabras_por_clip.get(s["path"], []), s["ini"], s["fin"], cursor)
            cursor += s["fin"] - s["ini"]

    # El plan puede traer los bloques de texto ya decididos
    # (`bloques_texto: [{ini, fin, texto}]`). Entonces mandan esos y el
    # agrupador no opina: hay formatos donde el corte de la frase ES el
    # contenido -las columnas "Parte 1 / Parte 2" de un guion de frases- y
    # dejarlo al algoritmo lo parte por donde no toca.
    bloques = plan.get("bloques_texto")
    srt_path = os.path.join(trabajo, "subtitulos.srt")
    if bloques:
        n_srt = _escribir_srt_bloques(srt_path, bloques)
        palabras_finales = None
    else:
        n_srt = _escribir_srt(srt_path, palabras_finales)
    log("subtitulos.srt: %d lineas%s | duracion final %s"
        % (n_srt, " (del plan)" if bloques else "", _mmss(cursor)))

    if salida == "mp4":
        from .render import renderizar_segmentos
        destino = os.path.join(trabajo, nombre + ".mp4")
        log("Renderizando MP4...")
        # en el reel de guion la pista que manda es la voz en off; el stock va
        # mudo a proposito
        voz_path = (plan.get("voz") or {}).get("archivo") if de_guion else None
        if voz_path and not os.path.isabs(voz_path):
            voz_path = os.path.join(carpeta_plan, os.path.basename(voz_path))
        peso = renderizar_segmentos(segmentos, destino, voz_path=voz_path)
        log("%s (%.1f MB)" % (destino, peso / 1e6))
        log("Tiempo de trabajo: %s" % _dur_humana(time.time() - t_inicio))
        return {"mp4": destino, "trabajo": trabajo}

    from . import capcut_lib
    log("Creando el proyecto de CapCut...")
    res = capcut_lib.construir_segmentos(
        nombre, segmentos, canvas, srt_path=srt_path if subtitulos else None,
        caption_altura=plan.get("caption_altura"),
        palabras=palabras_finales if subtitulos else None,
        captions=captions, zoom=zoom, palabras_por_clip=palabras_por_clip,
        callouts=plan.get("datos"),
        broll=_resolver_broll(plan.get("broll"), canvas, trabajo, log),
        # Un reel de guion -imagen fija, voz reflexiva- NO lleva el flash de
        # apertura ni los golpes de sonido: esos existen para el reel hablado a
        # camara, donde marcan el arranque y los cortes. Aqui no hay cortes que
        # marcar y el efecto se siente pegado encima. Si el plan los declara,
        # mandan ellos.
        sfx=(_preparar_sfx(plan, cursor, palabras_finales, log)
             if (plan.get("sfx") or not de_guion) else None),
        efectos=[e for e in _lista(
            plan, "efectos", [] if de_guion else efectos.planear(segmentos, cursor))
                 if e.get("tipo")],
        transiciones=[t for t in _lista(plan, "transiciones", []) if t.get("tipo")],
        letras=plan.get("letras") or letras,
        cifra=plan.get("cifra") or cifra,
        musica=_preparar_musica(plan, cursor, log),
        voz=({"volumen": 1.0, "fade_out": 0, **plan["voz"]}
             if plan.get("voz", {}).get("archivo") else None),
        overlays=_lista(plan, "overlays", []) or None,
        # la frase clave en grande: cual merece pantalla es criterio, asi que
        # solo sale si el plan la escribe (ver pipeline/frases.py)
        frases=_lista(plan, "frases", []) or None,
        escala_texto_forzada=plan.get("escala_texto") or escala_texto, log=log)

    # lo que pycapcut no conoce (efectos nuevos de CapCut) se inyecta desde la
    # biblioteca aprendida de los proyectos del usuario
    pedidos_ef = [e for e in _lista(plan, "efectos", []) if e.get("nombre")]
    pedidas_tr = [t for t in _lista(plan, "transiciones", []) if t.get("nombre")]
    puestos = biblioteca.inyectar(
        res["carpeta"], efectos=pedidos_ef, transiciones=pedidas_tr)
    if puestos["efectos"] or puestos["transiciones"]:
        log("  biblioteca: %d efecto(s), %d transicion(es)"
            % (puestos["efectos"], puestos["transiciones"]))
    # 🔴 Un recurso que ya no esta descargado se descartaba EN SILENCIO
    # (`if not usable(): continue`), y el clip salia sin el efecto sin que
    # nada lo relacionara. Paso con `Colors Off`: su carpeta de cache solo
    # tenia la version `_tmp`, o sea que la descarga nunca
    # termino. Se arregla abriendolo una vez en CapCut, pero primero hay
    # que ENTERARSE. Es la misma familia que las reglas duras 4 y 9.
    for pedidos, clave, que in ((pedidos_ef, "efectos", "efectos"),
                                (pedidas_tr, "transiciones", "transiciones")):
        faltan = len(pedidos) - puestos[clave]
        if faltan > 0:
            bib = biblioteca.cargar()
            sin = [p["nombre"] for p in pedidos
                   if not biblioteca.usable(bib.get(clave, {})
                                            .get(p["nombre"]) or {})]
            log("  aviso: %d de los %s del plan NO entraron -no estan "
                "descargados en esta computadora-: %s"
                % (faltan, que, ", ".join(sin) or "?"))
            log("         se arregla aplicandolos una vez en CapCut y "
                "corriendo 'python tools/biblioteca.py --guardar'")
    log("Proyecto '%s': %d clips, %d subtitulos%s%s"
        % (nombre, res["segmentos"], res["subtitulos"],
           ", %d cifras" % res["datos"] if res.get("datos") else "",
           ", %d b-roll" % res["broll"] if res.get("broll") else "")
        + (", %d frases" % res["frases"] if res.get("frases") else "")
        + (", %d efectos" % res["sfx"] if res.get("sfx") else "")
        + (", %d visuales" % res["efectos"] if res.get("efectos") else ""))
    log("Tiempo de trabajo: %s" % _dur_humana(time.time() - t_inicio))
    return {"capcut": res["carpeta"], "trabajo": trabajo}


def _escribir_srt_bloques(destino, bloques):
    """SRT a partir de bloques ya decididos: [{"ini", "fin", "texto"}]."""
    def ts(seg):
        ms = int(round(seg * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return "%02d:%02d:%02d,%03d" % (h, m, s, ms)

    puestos = 0
    with open(destino, "w", encoding="utf-8") as f:
        for b in bloques:
            texto = (b.get("texto") or "").strip()
            if not texto:
                continue
            puestos += 1
            f.write("%d\n%s --> %s\n%s\n\n"
                    % (puestos, ts(b["ini"]), ts(b["fin"]), texto))
    return puestos


def _escribir_srt(ruta, palabras):
    """Palabras ya en tiempo final -> lineas SRT agrupadas y legibles."""
    def ts(seg):
        ms = int(round(seg * 1000))
        h, ms = divmod(ms, 3_600_000)
        m, ms = divmod(ms, 60_000)
        s, ms = divmod(ms, 1000)
        return "%02d:%02d:%02d,%03d" % (h, m, s, ms)

    lineas = _agrupar_subtitulos(palabras) if palabras else []
    with open(ruta, "w", encoding="utf-8") as f:
        n = 0
        for linea in lineas:
            texto = " ".join(w["word"] for w in linea).strip()
            if not texto:
                continue
            n += 1
            f.write("%d\n%s --> %s\n%s\n\n"
                    % (n, ts(linea[0]["start"]), ts(linea[-1]["end"]), texto))
    return n


def nombre_por_defecto():
    return time.strftime("reel_%Y%m%d_%H%M")
