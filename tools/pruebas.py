"""Pruebas del proyecto. Sin dependencias: python tools/pruebas.py

Cubre la logica que decide QUE se corta y COMO se mueve la camara, que es
donde un error se ve en el video final. Los casos con audio real usan las
transcripciones cacheadas en proyectos/ si existen; si no, se saltan.
"""
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import plan, tomas, zoom
from pipeline import voz as voz_mod
from pipeline.transcribe import fusionar_fragmentos

FALLOS = []
SALTADAS = 0


def ok(caso, condicion):
    print(("  OK    " if condicion else "  FALLA ") + caso)
    if not condicion:
        FALLOS.append(caso)


def saltar(caso, motivo):
    global SALTADAS
    SALTADAS += 1
    print("  ...    %s (%s)" % (caso, motivo))


def palabras(inicio, frase, dur=0.3, hueco=0.08):
    """Construye palabras sinteticas con tiempos regulares."""
    salida, t = [], inicio
    for p in frase.split():
        salida.append({"start": round(t, 2), "end": round(t + dur, 2), "word": p})
        t += dur + hueco
    return salida, t


# Tus reels aprobados, para las pruebas con audio real. No van a git: son tus
# proyectos. Se declaran en proyectos/_pruebas.json:
#
#   {"enfasis_retorico": "<proyecto con un 'espere y espere y espere'>",
#    "densidad": ["<proyecto>", "<proyecto>"],
#    "huellas": {"<proyecto>|dinamico": "<16 hex>", ...}}
#
# Las huellas se toman ANTES de tocar el pipeline, con:
#   python tools/pruebas.py --huellas "<proyecto>" "<proyecto>"
# Sin ese archivo, esas pruebas se SALTAN y lo dicen: "Todo en orden (N
# saltadas)" no es lo mismo que "Todo en orden". Se cuentan los OK.
REFERENCIAS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "proyectos", "_pruebas.json")


def referencias():
    if not os.path.exists(REFERENCIAS):
        return {}
    with open(REFERENCIAS, encoding="utf-8") as f:
        return json.load(f)


def cache(proyecto):
    hallados = glob.glob(os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "proyectos", proyecto, "cache_*.json"))
    if not hallados:
        return None
    with open(hallados[0], encoding="utf-8") as f:
        return json.load(f)


def region_repetida(tr, raiz, cerca=1.5, margen=3):
    """Palabras alrededor de una raiz que se repite seguida (enfasis retorico).

    Devuelve [] si no la encuentra, para que el caso se salte en vez de fallar
    por una ventana de tiempo que ya no corresponde al audio cacheado.
    """
    if not tr:
        return []
    ws = tr.get("words") or []
    hits = [i for i, w in enumerate(ws) if raiz in w["word"].lower()]
    for a, b in zip(hits, hits[1:]):
        if ws[b]["start"] - ws[a]["start"] <= cerca:
            return ws[max(0, a - margen):min(len(ws), b + margen + 1)]
    return []


# --------------------------------------------------------------- fragmentos
def pruebas_fragmentos():
    print("\n[fusion de fragmentos de palabra]")

    def w(t, a, b, p=0.9):
        return {"crudo": t, "start": a, "end": b, "prob": p}

    r = fusionar_fragmentos([w(" vendio", 5.2, 5.9), w(" 44", 5.96, 6.4),
                             w("%", 6.4, 6.6), w(" mas.", 6.7, 7.2)])
    ok("'44' + '%' se unen en un solo caption",
       [x["word"] for x in r] == ["vendio", "44%", "mas."])
    ok("el final se extiende al fragmento pegado", abs(r[1]["end"] - 6.6) < 1e-9)

    r = fusionar_fragmentos([w(" publicidad", 142.4, 143.2), w(".", 145.9, 146.0)])
    ok("un fragmento lejano NO infla la duracion de la palabra",
       r[0]["end"] == 143.2 and r[0]["word"] == "publicidad.")

    r = fusionar_fragmentos([w(" ich", 0, 0.3), w(" habe", 0.3, 0.6)])
    ok("palabras normales no se pegan entre si",
       [x["word"] for x in r] == ["ich", "habe"])
    ok("lista vacia no revienta", fusionar_fragmentos([]) == [])
    ok("primer token sin espacio no revienta",
       len(fusionar_fragmentos([w("solo", 0, 0.3)])) == 1)


# -------------------------------------------------------------------- tomas
def pruebas_tomas():
    print("\n[tomas repetidas y falsos arranques]")
    a, t = palabras(0.0, "hola bienvenidos al canal de electricidad")
    b, t = palabras(t + 1.2, "hola bienvenidos al canal de electricidad y hoy veremos contactos")
    ok("frase repetida tras una pausa: se quita la primera",
       len(tomas.detectar(a + b)[0]) == 1)

    a, t = palabras(0.0, "y entonces fui")
    b, t = palabras(t + 1.0, "y entonces fuimos al parque con los ninos")
    ok("falso arranque truncado", len(tomas.detectar(a + b)[0]) == 1)

    a, t = palabras(0.0, "hoy hablaremos de la tierra fisica")
    b, t = palabras(t + 1.0, "tambien veremos el calibre del cable")
    ok("frases distintas NO se tocan", len(tomas.detectar(a + b)[0]) == 0)

    a, t = palabras(0.0, "muy bien muy bien vamos a empezar la revision de hoy")
    ok("enfasis corto repetido NO se corta", len(tomas.detectar(a)[0]) == 0)

    a, t = palabras(0.0, "este torneo sera el sabado")
    b, t = palabras(t + 1.0, "este torneo sera el sabado a las diez")
    c, t = palabras(t + 1.0, "este torneo sera el sabado a las diez de la manana")
    ok("tres intentos: sobreviven solo los ultimos",
       len(tomas.detectar(a + b + c)[0]) == 2)

    # la ultima toma NO siempre es la buena: si quedo trunca fue un reinicio
    # que el hablante abandono, y vale la anterior completa
    a, t = palabras(0.0, "y ese es el cable mas viejo que tienes que cambiar")
    b, t = palabras(t + 1.0, "y ese")
    c, t = palabras(t + 1.0, "y ese es el")
    rangos, _ = tomas.detectar(a + b + c)
    sobrevive = " ".join(w["word"] for w in
                         tomas.filtrar_palabras(a + b + c, rangos))
    ok("arranque abandonado al final: se queda la toma completa",
       sobrevive == "y ese es el cable mas viejo que tienes que cambiar")

    a, t = palabras(0.0, "con un cable nuevo en cocina "
                         "con un cable nuevo en cocina con un cable nuevo de")
    rangos, _ = tomas.detectar(a)
    sobrevive = " ".join(w["word"] for w in tomas.filtrar_palabras(a, rangos))
    ok("cadena que termina trunca: se queda la ultima COMPLETA",
       sobrevive == "con un cable nuevo en cocina")

    a, t = palabras(0.0, "practica todos los dias sin falta")
    b, t = palabras(t + 45.0, "practica todos los dias")
    ok("una repeticion mucho despues NO se toma por abandono",
       len(tomas.detectar(a + b)[0]) == 0)

    # La region se busca POR CONTENIDO, no por segundos: el mismo reel existe
    # en version cruda y ya cortada, y una ventana fija se queda mirando otra
    # parte del audio. Cuando eso pasa la prueba no falla: se salta callada.
    proy = referencias().get("enfasis_retorico")
    tr = cache(proy) if proy else None
    reg = region_repetida(tr, "esper") if tr else []
    if reg:
        ok("audio real: 'espere y espere y espere' retorico queda intacto",
           len(tomas.detectar(reg)[0]) == 0)
    else:
        saltar("audio real: enfasis retorico",
               "declara 'enfasis_retorico' en proyectos/_pruebas.json")


# --------------------------------------------------------------------- plan
def pruebas_plan():
    print("\n[plan de cortes]")
    ws, t = palabras(0.5, "hola esto es una prueba")
    ws2, t = palabras(t + 3.0, "segunda frase despues de una pausa larga")
    keeps, stats = plan.planear(ws + ws2, t + 1.0, perfil="dinamico")
    ok("corta la pausa larga entre frases", len(keeps) == 2)
    ok("reporta ahorro positivo", stats["ahorro_seg"] > 2.0)
    ok("los trozos van en orden y no se solapan",
       all(b[0] >= a[1] for a, b in zip(keeps, keeps[1:])))

    ws, t = palabras(0.0, "una frase entera sin pausas dignas de corte")
    keeps, _ = plan.planear(ws, t + 0.2, perfil="conservador")
    ok("perfil conservador deja la frase de una pieza", len(keeps) == 1)

    keeps, stats = plan.planear([], 10.0)
    ok("sin transcripcion no corta nada", keeps == [(0.0, 10.0)])


# --------------------------------------------------------------------- zoom
def pruebas_zoom():
    print("\n[movimiento de camara]")
    pts = zoom.envolvente(3.0, 1.0, 1.14)
    ok("arranca y termina en la base",
       abs(pts[0][1] - 1.0) < 1e-9 and abs(pts[-1][1] - 1.0) < 1e-9)
    ok("alcanza el pico pedido", abs(max(v for _, v in pts) - 1.14) < 1e-9)
    ok("los tiempos son crecientes", all(b[0] >= a[0] for a, b in zip(pts, pts[1:])))
    ok("entra mas rapido de lo que sale (asimetrica)",
       pts[5][0] < 3.0 - pts[-6][0])
    ok("respeta el tope de seguridad",
       max(v for _, v in zoom.envolvente(3.0, 1.0, 5.0)) <= zoom.PICO_MAX)
    ok("duracion cero no revienta", len(zoom.envolvente(0, 1.0, 1.14)) == 1)
    ok("pico menor que la base se ignora",
       len(zoom.envolvente(3.0, 1.1, 1.05)) == 1)
    corta = zoom.envolvente(0.9, 1.0, 1.14)
    ok("frase corta: la envolvente se comprime sin salirse",
       corta[-1][0] <= 0.9 + 1e-9)

    print("\n[densidad de punches]")
    for proyecto in referencias().get("densidad", []):
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "proyectos", proyecto, "plan.json")
        tr = cache(proyecto)
        if not (os.path.exists(base) and tr):
            saltar("densidad en %s" % proyecto, "sin plan o cache")
            continue
        with open(base, encoding="utf-8") as f:
            segs = json.load(f)["segmentos"]
        elegidos = zoom.elegir_punches(segs, {segs[0]["path"]: tr["words"]})
        dur = sum(s["fin"] - s["ini"] for s in segs)
        por_min = len(elegidos) / (dur / 60.0)
        ok("%s: %.1f punches/min (tope %.0f)" % (proyecto, por_min, zoom.POR_MINUTO_MAX),
           por_min <= zoom.POR_MINUTO_MAX)
    if not referencias().get("densidad"):
        saltar("densidad de punches en audio real",
               "declara 'densidad' en proyectos/_pruebas.json")

    segs = [{"path": "x", "ini": i * 3.0, "fin": i * 3.0 + 2.5} for i in range(4)]
    ok("sin senales de enfasis no inventa punches",
       len(zoom.elegir_punches(segs)) == 0)


def pruebas_encuadre():
    """El techo de zoom: a escala s se recorta (1 - 1/s)/2 por arriba."""
    print("")
    print("[cuanto zoom aguanta el encuadre]")
    sys.path.insert(0, os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))
    import encuadre

    # calibrado: en el reel de referencia la cabeza esta al 20.1% y se aprobo
    # el pico 1.36
    ok("reproduce el pico aprobado de calibracion (20.1% -> 1.36)",
       abs(encuadre.zoom_que_aguanta(0.201) - 1.36) < 0.02)
    ok("un primer plano NO admite el pico de 1.36",
       encuadre.zoom_que_aguanta(0.092) < 1.20)
    ok("cabeza pegada al borde: no se puede acercar nada",
       encuadre.zoom_que_aguanta(0.0) == 1.0)
    ok("nunca propone mas de 1.40 por muy abierto que este",
       encuadre.zoom_que_aguanta(0.9) <= 1.40)
    ok("mas aire arriba nunca da menos zoom",
       encuadre.zoom_que_aguanta(0.05) <= encuadre.zoom_que_aguanta(0.15))
    # el numero exacto del caso real: cabeza al 9.2% -> 1.10
    ok("y el techo medido en un primer plano (9.2% -> 1.14)",
       abs(encuadre.zoom_que_aguanta(0.092) - 1.14) < 0.01)

    print("")
    print("[ancla del zoom]")
    # con aire de sobra no hace falta bajar la imagen
    ok("si centrada ya cabe, no se ancla",
       encuadre.ancla_necesaria(0.20, 1.10) == 0.0)
    # primer plano cerrado: hay que anclar para no entrar en la frente
    a = encuadre.ancla_necesaria(0.053, 1.14)
    ok("en un plano muy cerrado si se ancla", 0.0 < a < 1.0)
    ok("anclada, lo que se come arriba cabe en el aire disponible",
       (1 - 1 / 1.14) / 2 * (1 - a) <= 0.053 * encuadre.HOLGURA + 1e-9)
    ok("cuanto mas cerrado, mas ancla",
       encuadre.ancla_necesaria(0.03, 1.14) > encuadre.ancla_necesaria(0.08, 1.14))
    ok("nunca pasa de 1.0", encuadre.ancla_necesaria(0.0, 1.30) <= 1.0)
    ok("sin zoom no hay nada que anclar",
       encuadre.ancla_necesaria(0.05, 1.0) == 0.0)
    # lo que se pierde por abajo son sus manos: hay que poder mirarlo
    ok("anclar mueve el recorte hacia abajo",
       encuadre.recorte_abajo(1.14, a) > encuadre.recorte_abajo(1.14, 0.0))
    ok("centrada, arriba y abajo pierden lo mismo",
       abs(encuadre.recorte_abajo(1.14, 0.0) - (1 - 1 / 1.14) / 2) < 1e-9)

    print("")
    print("[altura del callout]")
    from pipeline import cifras
    ok("por defecto va en la pared de arriba",
       cifras.receta("pop")["altura"] == cifras.ALTURA_CALLOUT)
    r = cifras.receta({"estilo": "pop", "altura": -0.05})
    ok("el plan puede bajarlo si no hay pared", r["altura"] == -0.05)
    ok("y no le cambia nada mas", r["tam"] == cifras.ESTILOS["pop"]["tam"])


    print("")
    print("[keyframes de escala]")
    # pycapcut traduce uniform_scale a KFTypeScaleX y no escribe la Y: lo que
    # sale es un estiron horizontal, no un zoom. De ahi venia la regla dura 6.
    import pycapcut as _cc
    from pipeline import capcut_lib as _cl

    class _SegFalso(object):
        def __init__(self):
            self.props = []

        def add_keyframe(self, prop, t, v):
            self.props.append(getattr(prop, "value", prop))

    seg = _SegFalso()
    _cl._kf_escala(seg, 0, 1.0)
    ok("escribe los DOS ejes, no solo la X",
       seg.props == ["KFTypeScaleX", "KFTypeScaleY"])
    ok("y no usa uniform_scale", "UNIFORM_SCALE" not in seg.props)
    ok("uniform_scale sigue siendo la trampa que era",
       getattr(_cc.KeyframeProperty.uniform_scale, "value", None) == "UNIFORM_SCALE")


def pruebas_sonidos():
    """Cuanto swish aguanta: la densidad que aprobo, no uno por corte."""
    print("")
    print("[densidad de swish]")
    from pipeline import sonidos

    def montaje(n, dur_corte):
        return [{"ini": i * 10.0, "fin": i * 10.0 + dur_corte} for i in range(n)]

    # 13 cortes en 35.5 s sin una sola cifra: nada frena a los swish. Es el caso
    # que sonaba pesado -- 12 swish, uno cada 3 s.
    segs = montaje(13, 2.73)
    dur = sum(s["fin"] - s["ini"] for s in segs)
    ev = sonidos.planear(segs, None, dur, None)
    sw = [e for e in ev if e["tipo"] == "swish"]
    ok("un reel sin cifras no se llena de swish",
       len(sw) <= round(dur / sonidos.SEGUNDOS_POR_SWISH))
    ok("pero no se queda sin ninguno", len(sw) >= 1)

    seps = [b["ini"] - a["ini"] for a, b in zip(sw, sw[1:])]
    ok("y no quedan dos pegados", all(x > sonidos.SEPARACION for x in seps))

    # con pocos cortes no hay nada que ralear: se quedan todos
    segs = montaje(4, 8.0)
    dur = sum(s["fin"] - s["ini"] for s in segs)
    ev = sonidos.planear(segs, None, dur, None)
    ok("un montaje holgado conserva todos sus swish",
       len([e for e in ev if e["tipo"] == "swish"]) == 3)

    ok("el swish sigue entrando antes del corte, no encima",
       sonidos.ADELANTO_SWISH > 0)

    # no se toca lo demas
    ev = sonidos.planear(montaje(13, 2.73), None, 35.5, None)
    ok("el riser sigue abriendo en 0.00",
       any(e["tipo"] == "riser" and e["ini"] == 0.0 for e in ev))
    ok("no se cuela ninguna clave interna en la salida",
       all(not k.startswith("_") for e in ev for k in e))


def pruebas_voz():
    print("\n[ajuste de cortes al habla real]")
    # el transcript decia que la frase acababa en 10.0, pero el audio sigue a 10.6
    voz = [(2.0, 10.6), (14.0, 25.0)]
    r = voz_mod.ajustar([(2.0, 10.0), (14.0, 17.0)], voz)
    ok("estira el final hasta donde acaba la voz", r[0][1] > 10.5)
    ok("NO persigue habla que sigue mucho mas alla (corte a proposito)",
       r[1][1] == 17.0)

    r = voz_mod.ajustar([(2.0, 10.0), (10.4, 12.0)], [(2.0, 11.5), (10.4, 12.0)])
    ok("nunca invade el corte siguiente", r[0][1] <= 10.4)

    r = voz_mod.ajustar([(5.0, 8.0)], [(4.6, 8.6)])
    ok("tambien rescata el arranque de la frase", r[0][0] < 5.0)
    r = voz_mod.ajustar([(5.0, 8.0)], [(4.9, 8.4)])
    ok("el rescate deja aire, no pega la silaba al borde", r[0][0] < 4.9)
    r = voz_mod.ajustar([(5.0, 8.0)], [(3.0, 8.4)])
    ok("no rescata si la voz empezo mucho antes (corte a proposito)",
       r[0][0] == 5.0)

    # lo nuevo y lo que mas se nota: recortar el silencio muerto
    r = voz_mod.ajustar([(10.0, 20.0)], [(10.8, 18.9)])
    ok("recorta el silencio de entrada", 10.7 < r[0][0] < 10.8)
    ok("recorta el silencio de salida", 18.9 < r[0][1] < 19.0)
    r = voz_mod.ajustar([(10.0, 20.0)], [(10.8, 18.9), (10.9, 10.92)])
    ok("ignora micro-ruidos que no son habla", 10.7 < r[0][0] < 10.8)
    r = voz_mod.ajustar([(0.0, 30.0)], [(20.0, 21.0)])
    ok("el recorte tiene tope (no salta de golpe al habla lejana)",
       r[0][0] <= 1.6 and r[0][1] >= 28.4)

    # Un CLIP empieza y acaba hablando, asi que el aire de los extremos no
    # tiene donde caer: sale ini=-0.05 y fin 50 ms mas alla del archivo. Aqui
    # no da error; revienta despues en pycapcut con un ValueError en chino, o
    # deja un draft que no abre. Salio en una tanda de 7 clips verticales,
    # en los 7.
    r = voz_mod.ajustar([(0.0, 20.5)], [(0.0, 20.5)], duracion=20.5)
    ok("un clip que empieza hablando no arranca en negativo", r[0][0] >= 0.0)
    ok("ni acaba mas alla del material", r[0][1] <= 20.5)
    ok("y deja el margen de ffprobe (regla dura 7)", r[0][1] <= 20.5 - 0.029)
    sin_tope = voz_mod.ajustar([(0.0, 20.5)], [(0.0, 20.5)])
    ok("sin `duracion` se sale: por eso el llamador la pasa siempre",
       sin_tope[0][0] < 0 or sin_tope[0][1] > 20.5)

    r = voz_mod.ajustar([(5.0, 8.0)], [(0.0, 30.0)])
    ok("un corte dentro de habla larga queda intacto por ambos lados",
       r[0] == (5.0, 8.0))

    ok("sin datos de voz devuelve los cortes intactos",
       voz_mod.ajustar([(1.0, 2.0)], []) == [(1.0, 2.0)])
    ok("un corte fuera de todo tramo de voz no cambia",
       voz_mod.ajustar([(50.0, 51.0)], [(2.0, 10.0)]) == [(50.0, 51.0)])


    print("")
    print("[sonidos que el transcript no escribe]")
    # whisper solo escribe palabras: un ruido de demostracion no existe para el
    # y el corte se cerraba encima. "lo tapamos con un ruido como este" + ruido.
    tramos = [(16.85, 21.89)]
    ini, fin = voz_mod.ajustar([(16.80, 20.22)], tramos)[0]
    ok("si sigue sonando, el corte lo respeta", fin >= 21.89)
    ok("y no se pasa de largo", fin <= 21.89 + voz_mod.AIRE + 1e-9)

    # pero una frase NUEVA si esta separada por silencio: son dos tramos, y el
    # segundo no se absorbe
    tramos = [(16.85, 20.10), (23.00, 26.00)]
    ini, fin = voz_mod.ajustar([(16.80, 20.22)], tramos)[0]
    ok("una frase aparte no se absorbe", fin < 21.0)

    # y lo lejano sigue fuera de alcance
    tramos = [(16.85, 25.00)]
    ini, fin = voz_mod.ajustar([(16.80, 20.22)], tramos)[0]
    ok("seguir el sonido tiene tope",
       fin <= 20.22 + voz_mod.SEGUIR_SONIDO + voz_mod.AIRE + 1e-9)


    print("")
    print("[salud del audio de origen]")
    # medido sobre grabaciones reales: las crudas pican en 0.0-0.2 dB (sin
    # margen) y una ya exportada estaba en -3.9 dBTP
    guardado = voz_mod.salud_audio
    try:
        salida = []
        voz_mod.salud_audio = lambda p: (0.08, -16.3, 12.8)      # cruda de telefono
        voz_mod.avisar_audio("x", salida.append)
        ok("avisa cuando pica sin margen",
           any("sin margen" in l for l in salida))

        salida = []
        voz_mod.salud_audio = lambda p: (-3.94, -21.76, 3.60)    # ya exportada, sana
        voz_mod.avisar_audio("x", salida.append)
        ok("y calla con una grabacion sana", salida == [])

        salida = []
        voz_mod.salud_audio = lambda p: (-6.0, -20.0, 14.0)      # con aire pero irregular
        voz_mod.avisar_audio("x", salida.append)
        ok("avisa del rango dinamico ancho aunque haya margen",
           any("rango" in l for l in salida))

        salida = []
        voz_mod.salud_audio = lambda p: None                      # no se pudo medir
        voz_mod.avisar_audio("x", salida.append)
        ok("si no puede medir, no inventa un aviso", salida == [])
    finally:
        voz_mod.salud_audio = guardado


def pruebas_exportar():
    """Que el paquete para la editora no deje recursos fuera.

    Dos veces se mando un proyecto al que le faltaba algo y no se noto hasta
    que ella lo abrio, porque CapCut descarta la pista sin avisar: la fuente
    descargada y las animaciones de texto de los callouts.
    """
    from tools.exportar import medios_de, recursos_que_necesita, CACHE
    cache = CACHE.replace(chr(92), "/")
    draft = {"materials": {
        "videos": [{"path": "C:/clips/uno.mp4"}],
        "audios": [{"path": "C:/sfx/riser.mp3"}],
        "video_effects": [{"path": cache + "/effect/111/aaa", "name": "White Flash"}],
        "transitions": [{"path": cache + "/effect/222/bbb", "name": "Holographic Scan"}],
        "material_animations": [{"animations": [
            {"name": "Wiping Out", "path": cache + "/effect/333"}]}],
        "texts": [{
            "font_path": cache + "/effect/444/Anton-Regular.ttf",
            "content": json.dumps({"styles": [{"font": {
                "path": cache + "/effect/444/Anton-Regular.ttf"}}]}),
        }],
    }}
    u = medios_de(draft)
    ok("los clips y sonidos entran como medios",
       "C:/clips/uno.mp4" in u["medios"] and "C:/sfx/riser.mp3" in u["medios"])
    ok("la fuente DESCARGADA viaja como archivo",
       any(x.endswith("Anton-Regular.ttf") for x in u["medios"]))
    ok("las animaciones de texto entran en la cache a remapear",
       any(x.endswith("/effect/333") for x in u["cache"]))
    ok("los efectos y transiciones entran en la cache a remapear",
       len([x for x in u["cache"] if "/effect/111/" in x or "/effect/222/" in x]) == 2)

    import shutil
    import tempfile
    from tools.exportar import _copiar_proyecto, ESENCIALES
    origen = tempfile.mkdtemp()
    for n in ESENCIALES:
        io_open = open(os.path.join(origen, n), "w", encoding="utf-8")
        io_open.write("{}")
        io_open.close()
    # lo que CapCut deja al abrir un draft: copias con las rutas del origen
    os.makedirs(os.path.join(origen, "Timelines", "abc"))
    open(os.path.join(origen, "Timelines", "abc", "t.json"), "w").write("x")
    open(os.path.join(origen, "draft_content.json.bak"), "w").write("x")
    open(os.path.join(origen, "template-2.tmp"), "w").write("x")
    destino = os.path.join(tempfile.mkdtemp(), "p")
    _copiar_proyecto(origen, destino)
    quedaron = sorted(os.listdir(destino))
    ok("solo viaja lo que define el proyecto",
       quedaron == sorted(ESENCIALES))
    ok("no viajan las copias que deja CapCut al abrirlo",
       not os.path.exists(os.path.join(destino, "Timelines"))
       and not os.path.exists(os.path.join(destino, "draft_content.json.bak"))
       and not os.path.exists(os.path.join(destino, "template-2.tmp")))
    shutil.rmtree(origen, ignore_errors=True)

    aviso = "".join(recursos_que_necesita(draft))
    ok("se avisa por nombre de lo que ella necesita tener",
       "White Flash" in aviso and "Holographic Scan" in aviso
       and "Wiping Out" in aviso)
    ok("las animaciones con nombre interno llevan traduccion",
       "salida por barrido" in aviso)


    print("")
    print("[recursos que requieren CapCut Pro]")
    import exportar as _exp
    ok("sabe que White Flash es gratis", _exp._es_vip("White Flash") is False)
    ok("y que Focus Shake es de Pro", _exp._es_vip("Focus Shake") is True)
    ok("un nombre que no existe no revienta ni miente",
       _exp._es_vip("Efecto Que No Existe") is False)

    draft = {"materials": {"transitions": [{"name": "Snap Zoom"}],
                           "video_effects": [{"name": "White Flash"}]}}
    lineas = chr(10).join(_exp.recursos_que_necesita(draft))
    ok("marca el que necesita Pro", "requiere CapCut Pro" in lineas)
    ok("y avisa de que no basta con descargarlo",
       "no es cuestion de descargarlos" in lineas)
    ok("el gratis no se marca",
       "White Flash   [requiere" not in lineas)

    solo_gratis = {"materials": {"transitions": [{"name": "White Flash"}]}}
    ok("sin nada de Pro no aparece el aviso",
       "requiere CapCut Pro" not in chr(10).join(_exp.recursos_que_necesita(solo_gratis)))


    print("")
    print("[importar un draft de otra computadora]")
    import importar as _imp

    # rutas_del_draft miraba una lista fija de claves. Un pack de titulos
    # comprado traia 26 rutas en hsl/common_mask/color_curves que se quedaban
    # sin tocar, y CapCut descarta lo que no resuelve sin avisar.
    d = {"materials": {
        "videos": [{"path": "C:/otro/clip.mp4"}],
        "hsl": [{"path": "C:/otro/x/hsl"}],
        "common_mask": [{"path": "C:/otro/x/mask"}],
        "color_curves": [{"path": "C:/otro/x/curva"}],
        "canvases": [{"sin_ruta": 1}],
        "texts": [{"path": "##_material_placeholder_1"}],
        "algo_nuevo_de_capcut": [{"path": "C:/otro/x/nuevo"}],
    }}
    claves = sorted(c for c, _ in _imp.rutas_del_draft(d))
    ok("mira todas las claves con ruta, no una lista fija",
       claves == ["algo_nuevo_de_capcut", "color_curves", "common_mask", "hsl", "videos"])
    ok("y no se inventa rutas donde no las hay", "canvases" not in claves)
    ok("el marcador ## no cuenta como ruta", "texts" not in claves)

    # las fuentes de un pack vienen en su propia carpeta, no en la cache
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        sub = os.path.join(tmp, "Fuentes Premium")
        os.makedirs(sub)
        destino = os.path.join(sub, "Prueba-Bold.ttf")
        with open(destino, "wb") as f:
            f.write(b"x")
        idx = _imp._indice_fuentes([tmp])
        ok("encuentra el .ttf suelto del pack", idx.get("prueba-bold.ttf") == destino)
        draft = {"materials": {"texts": [
            {"font_path": "C:/OtroUsuario/Cache/effect/1/2/Prueba-Bold.ttf"}]}}
        _imp._reescribir_fuentes(draft, "C:/fake/Font", idx)
        ok("y reapunta la fuente rota a ese archivo",
           draft["materials"]["texts"][0]["font_path"].endswith("Prueba-Bold.ttf")
           and "OtroUsuario" not in draft["materials"]["texts"][0]["font_path"])


def pruebas_voz_off():
    """La alineacion por caracter de ElevenLabs -> palabras con tiempos.

    Es la pieza de la que cuelga todo el reel de guion: captions, cifras y
    cortes de escena salen de aqui. Se prueba sin clave y sin gastar creditos.
    """
    from pipeline import voz_off as vo

    def alinear(texto, paso=0.1):
        chars = list(texto)
        return (chars, [i * paso for i in range(len(chars))],
                [(i + 1) * paso for i in range(len(chars))])

    p = vo.palabras_desde_alineacion(*alinear("Hola, mundo raro"))
    ok("separa las palabras por los espacios",
       [w["word"] for w in p] == ["Hola,", "mundo", "raro"])
    ok("la puntuacion se queda pegada a su palabra", p[0]["word"] == "Hola,")
    ok("pero la puntuacion NO estira el final de la palabra",
       abs(p[0]["end"] - 0.4) < 1e-9)
    ok("la palabra empieza cuando empieza su primer caracter",
       abs(p[1]["start"] - 0.6) < 1e-9)
    ok("una alineacion vacia no revienta",
       vo.palabras_desde_alineacion([], [], []) == [])

    # Las etiquetas de emocion de v3 no se locutan pero SI vuelven en la
    # alineacion: sin filtrarlas salen impresas como palabra en los subtitulos.
    p3 = vo.palabras_desde_alineacion(*alinear("[serio] Se ve bien."))
    ok("la etiqueta de emocion no se cuela como palabra",
       [w["word"] for w in p3] == ["Se", "ve", "bien."])
    ok("y la primera palabra real conserva su tiempo",
       abs(p3[0]["start"] - 0.8) < 1e-9)
    p3b = vo.palabras_desde_alineacion(*alinear("Ya. [con ironia] Claro."))
    ok("una etiqueta de dos palabras tampoco parte nada",
       [w["word"] for w in p3b] == ["Ya.", "Claro."])
    ok("v3 no manda speed en los ajustes de voz",
       "speed" not in vo._ajustes("eleven_v3", 0.9, 0.5))
    ok("pero el modelo de siempre si lo manda",
       vo._ajustes(vo.MODELO, 0.9, 0.5).get("speed") == 0.9)
    ok("la firma de cache no cambia con la estabilidad de siempre",
       vo._firma("t", "v", "m", 0.9) == vo._firma("t", "v", "m", 0.9, vo.ESTABILIDAD))
    ok("pero si cambia con otra estabilidad",
       vo._firma("t", "v", "m", 0.9) != vo._firma("t", "v", "m", 0.9, 0.0))
    ok("aguanta que las listas vengan de distinto largo",
       len(vo.palabras_desde_alineacion(list("abc def"), [0, 1], [1, 2])) >= 1)

    largo = ("La semana pasada una clienta nos llamo porque el tablero se "
             "calentaba y no cambio nada con poner focos nuevos lo que cambio "
             "todo fue revisar cada uno de los cables de la cocina y del patio")
    ok("avisa si un guion largo viene sin una sola tilde",
       bool(vo.revisar_acentos(largo)))
    ok("no avisa si el guion trae tildes",
       not vo.revisar_acentos(largo.replace("cambio", "cambió")))
    ok("no avisa en un texto corto, donde puede no tocar ninguna",
       not vo.revisar_acentos("Hola mundo"))

    g = "Una idea. Otra idea distinta que es bastante mas larga que la primera."
    esc = vo.escenas(g)
    ok("corta por punto, no por numero de palabras",
       esc[0]["texto"] == "Una idea.")
    ok("una escena muy corta se pega a la siguiente",
       all(e["palabras"] >= 4 or i == 0 for i, e in enumerate(esc)))

    palabras = [{"word": "x", "start": i * 0.5, "end": i * 0.5 + 0.4}
                for i in range(20)]
    conts = vo.tiempos_de_escenas([{"texto": "a", "palabras": 3},
                                   {"texto": "b", "palabras": 5}], palabras)
    ok("la escena hereda el inicio de su primera palabra",
       abs(conts[0]["ini"] - 0.0) < 1e-9)
    ok("y el final de su ultima", abs(conts[0]["fin"] - 1.4) < 1e-9)
    ok("la segunda escena arranca donde termina la primera",
       abs(conts[1]["ini"] - 1.5) < 1e-9)


def pruebas_pertinencia():
    """Que el filtro de stock rechace lo que NO ilustra la escena.

    Los pares son reales: se midieron contra Pexels el 2026-08-25 con las
    consultas de dos guiones, uno historico y uno de ajedrez.
    """
    print("\npertinencia del stock")
    from pipeline import pertinencia as P

    # lo que la busqueda devolvio y NO viene al caso
    malos = [
        ("gallows dawn", "a pond with trees and water in the background"),
        ("irish flag", "flag of france"),
        ("old map mexico", "close up of a ball shaped globe"),
        ("cannon smoke", "smoke billowing from a chimney in the sky"),
        ("immigrants ship", "tranquil sunset view from ship deck"),
    ]
    for consulta, desc in malos:
        ok("rechaza '%s' -> %s" % (consulta, desc),
           not P.sirve(consulta, desc))

    buenos = [
        ("soldiers marching", "soldiers marching while holding gun"),
        ("chess player thinking", "two chess players thinking"),
        ("chess board", "chess pieces on board"),
        ("hand moving chess piece", "hand moving a chess piece on the board"),
    ]
    for consulta, desc in buenos:
        ok("acepta '%s' -> %s" % (consulta, desc), P.sirve(consulta, desc))

    ok("empareja plural con singular",
       P.puntuar("chess player", "two chess players thinking") == 1.0)
    ok("no empareja por prefijo corto",       # war / warehouse
       P.puntuar("war soldiers", "warehouse workers") < 0.6)
    ok("una consulta solo de palabras vacias no aprueba nada",
       P.puntuar("a close up of the", "anything at all") == 0.0)

    candidatos = [
        {"descripcion": "flag of france"},
        {"descripcion": "irish flag waving in the wind"},
    ]
    elegido = P.mejor("irish flag", candidatos)
    ok("elige el candidato que mejor ilustra, no el primero",
       elegido is not None and elegido["descripcion"].startswith("irish"))
    ok("devuelve None si ninguno llega al umbral",
       P.mejor("gallows dawn", [{"descripcion": "a quiet pond"}]) is None)

    from pipeline import broll
    ok("saca la descripcion del slug de Pexels",
       broll.descripcion_de(
           "https://www.pexels.com/video/chess-pieces-on-board-855456/")
       == "chess pieces on board")
    ok("y aguanta una url vacia", broll.descripcion_de("") == "")


def pruebas_plan_de_guion():
    """El plan de un guion se distingue del de un video hablado.

    De eso depende que `editar_con_plan` no mande los clips de stock -que son
    mudos- a whisper, y que los subtitulos salgan de la alineacion del TTS.
    """
    print("\nplan de guion vs plan de video")

    def es_de_guion(plan):
        return bool(plan.get("palabras") and (plan.get("voz") or {}).get("archivo"))

    ok("un plan de video hablado no se toma por guion",
       not es_de_guion({"resumen": {}, "segmentos": [{"path": "a.mp4"}]}))
    ok("un plan de guion si",
       es_de_guion({"palabras": [{"word": "hola"}],
                    "voz": {"archivo": "voz.mp3"}}))
    ok("no basta con traer palabras: sin voz no es guion",
       not es_de_guion({"palabras": [{"word": "hola"}]}))


def pruebas_guion_cubre_el_audio():
    """El video tiene que durar lo que dura la voz.

    Una escena vale hasta que EMPIEZA la siguiente, no hasta su ultima
    palabra: entre frase y frase la voz calla. En el primer reel real esas
    pausas sumaban 6.45 s en 14 escenas y el video acababa antes que el audio,
    con la ultima frase -el remate- sin imagen.
    """
    print("\nel guion cubre todo el audio")
    import tempfile
    from pipeline import guion as G
    from pipeline import voz_off

    # tres frases con medio segundo de silencio entre ellas
    pal, t = [], 0.0
    for frase in ("uno dos tres cuatro.", "cinco seis siete ocho.",
                  "nueve diez once doce."):
        for w in frase.split():
            pal.append({"word": w, "start": round(t, 2), "end": round(t + 0.3, 2)})
            t += 0.35
        t += 0.5
    duracion = round(t, 2)

    real = voz_off.sintetizar
    voz_off.sintetizar = lambda *a, **k: {"palabras": pal, "duracion": duracion}
    try:
        carpeta = tempfile.mkdtemp()
        plan = G.guion_a_plan(
            "uno dos tres cuatro. cinco seis siete ocho. nueve diez once doce.",
            carpeta, "voz-falsa", buscar=lambda q, s=None: __file__,
            log=lambda *a: None)
    finally:
        voz_off.sintetizar = real

    video = sum(x["fin"] - x["ini"] for x in plan["segmentos"])
    ok("el video cubre el audio completo", video >= duracion - 0.05)
    ok("y no se pasa de largo", video <= duracion + 2.0)


def pruebas_frases():
    """La segunda capa de texto: rotacion de estilos y colocacion.

    Lo que se cuida aqui es justo el motivo por el que existe el modulo: que
    dos tarjetas seguidas NO salgan con el mismo tratamiento. Si eso se rompe
    vuelve la monotonia y el sintoma no se ve leyendo el codigo, solo mirando
    el reel entero.
    """
    print("\n== frases (la capa de frase clave) ==")
    from pipeline import frases

    lista = [{"ini": i * 3.0, "fin": i * 3.0 + 2.0, "texto": "FRASE %d" % i}
             for i in range(8)]
    plan_ = frases.planear(lista)
    ok("reparte estilo a todas", len(plan_) == 8
       and all(f.get("estilo") for f in plan_))
    seguidas = [(a["estilo"], b["estilo"]) for a, b in zip(plan_, plan_[1:])
                if a["estilo"] == b["estilo"]]
    ok("nunca repite el tratamiento anterior", not seguidas)
    ok("usa mas de un estilo", len({f["estilo"] for f in plan_}) > 1)

    # el estilo escrito a mano manda sobre la rotacion: es criterio editorial
    fijo = frases.planear([{"ini": 0, "fin": 2, "texto": "A", "estilo": "badge"},
                           {"ini": 3, "fin": 5, "texto": "B"}])
    ok("respeta el estilo escrito en el plan", fijo[0]["estilo"] == "badge")
    ok("y el siguiente no lo repite", fijo[1]["estilo"] != "badge")

    ok("ordena por tiempo aunque el plan venga desordenado",
       [f["texto"] for f in frases.planear(
           [{"ini": 9, "fin": 10, "texto": "tarde"},
            {"ini": 1, "fin": 2, "texto": "pronto"}])] == ["pronto", "tarde"])
    ok("descarta las frases vacias",
       frases.planear([{"ini": 0, "fin": 2, "texto": "   "}]) == [])
    ok("sin frases no hay capa", frases.planear([]) == [])

    # Solo los estilos en mayusculas transforman el texto. Se comprueba porque
    # la fuente manuscrita en mayusculas se lee peor y por eso va sin ellas.
    r_bloque = frases.ESTILOS["bloque"]
    r_marca = frases.ESTILOS["marcador"]
    ok("el bloque va en mayusculas",
       frases.texto_final("se acabo", r_bloque) == "SE ACABO")
    ok("la manuscrita respeta como se escribio",
       frases.texto_final("se acabo", r_marca) == "se acabo")

    # Dos lineas es lo normal (las tarjetas de la editora casi todas lo son);
    # tres es lo que hay que cazar, porque sube hasta la boca.
    r_bloque_ = frases.ESTILOS["bloque"]
    ok("una palabra corta cabe en una linea",
       frases.lineas("Basta", r_bloque_) == 1)
    ok("una frase normal cae en dos",
       frases.lineas("No funcionaba", r_bloque_) == 2)
    ok("una frase larga se detecta como tres o mas",
       frases.lineas("Cuenta los dias que ha estado prendida", r_bloque_) >= 3)
    ok("el salto ocurre entre palabras, no a mitad",
       frases.lineas("aaaa bbbb", {"chars_linea": 9}) == 1
       and frases.lineas("aaaa bbbbbb", {"chars_linea": 9}) == 2)
    ok("una frase vacia no ocupa ninguna", frases.lineas("", r_bloque_) == 0)

    avisos = []
    frases.planear([{"ini": 0, "fin": 3,
                     "texto": "Cuenta los dias que ha estado prendida",
                     "estilo": "bloque"}], log=avisos.append)
    ok("avisa de la frase que no cabe en dos lineas",
       any("lineas" in a for a in avisos))

    # La altura no es un numero elegido: se midio al 52% de la altura en la
    # edicion de la editora. Lo que importa es que caiga DEBAJO de la zona de
    # cabeza (0.49) y ENCIMA de los captions (0.66).
    frac = 0.5 - frases.ALTURA_FRASE / 2
    ok("la frase cae bajo la cabeza y sobre los captions",
       0.49 < frac < 0.66)

    # Un estilo inventado tiene que fallar CON MENSAJE, no dibujar cualquier
    # cosa: es la misma trampa de los recursos descargables de CapCut.
    try:
        frases.receta("no-existe")
        ok("un estilo desconocido falla con mensaje", False)
    except SystemExit as e:
        ok("un estilo desconocido falla con mensaje", "no-existe" in str(e))

    faltan = [k for k, (o, _) in frases.disponibles().items() if not o]
    if faltan:
        saltar("todos los estilos tienen sus recursos",
               "faltan por descargar: %s" % ", ".join(faltan))
    else:
        ok("todos los estilos tienen sus recursos descargados", True)


# ------------------------------------------------------ video largo horizontal
def pruebas_video_largo():
    """El perfil de video largo y lo que cambia por ser horizontal.

    Lo que se vigila aqui no es solo que lo nuevo funcione: cada cosa que se
    toco (escala del texto, orientacion del stock) lleva su caso en las DOS
    orientaciones a proposito, porque el riesgo real era romper los reels.
    """
    print("")
    print("VIDEO LARGO HORIZONTAL")
    from pipeline import capcut_lib, nucleo, stock

    # -- La escala del texto no se mueve en vertical y deja de encogerse en
    #    horizontal. En 9:16 la formula vieja (alto/1920) y la nueva
    #    (lado_menor/1080) son la MISMA por construccion, no por casualidad.
    for ancho, alto in [(1080, 1920), (720, 1280), (2160, 3840), (900, 1600)]:
        ok("texto igual que antes en %dx%d" % (ancho, alto),
           abs(capcut_lib.escala_texto(ancho, alto) - alto / 1920.0) < 1e-9)
    # La primera version de esta prueba pedia 1.0 ("no sale a la mitad").
    # El usuario lo VIO: a 1.0 el caption tapaba la cara -un size de CapCut
    # rinde mas pixeles en un lienzo ancho-. El factor es medido, no deducido.
    ok("en horizontal el texto usa el factor medido en pantalla",
       abs(capcut_lib.escala_texto(1920, 1080)
           - capcut_lib.ESCALA_TEXTO_HORIZONTAL) < 1e-9)
    ok("y el caption baja al 86% de la altura, lejos de la cara",
       capcut_lib.POS_CAPTION_HORIZONTAL == -0.72)

    # -- La orientacion del stock sale del lienzo, no de una opcion a mano
    ok("un lienzo vertical pide portrait",
       stock.orientacion_de((1080, 1920, 30)) == "portrait")
    ok("un lienzo horizontal pide landscape",
       stock.orientacion_de((1920, 1080, 30)) == "landscape")
    ok("un lienzo cuadrado no se toma por horizontal",
       stock.orientacion_de((1080, 1080, 30)) == "portrait")

    # -- El perfil nuevo existe y NO se cuela entre los de reel
    ok("hay un perfil para video largo", "largo" in plan.PERFILES)
    ok("los perfiles de reel siguen siendo tres", len(plan.PERFILES_REEL) == 3)
    ok("el perfil largo no entra en los de reel",
       "largo" not in plan.PERFILES_REEL)
    ok("el perfil largo si quita muletillas",
       plan.PERFILES["largo"]["quitar_hesitaciones"])
    ok("y no se come palabras reales como el agresivo",
       not plan.PERFILES["largo"]["relleno_agresivo"])

    # -- guion.txt: el numero de segmento, y una etiqueta que no miente.
    #    Este caso reproduce el fallo real: una frase larga cuyos DOS extremos
    #    caen fuera del tramo conservado pero que se conserva casi entera. Se
    #    marcaba "FUERA silencio" -en el video de YouTube, 88 s dados por
    #    descartados que en realidad se quedaban-.
    ws, _ = palabras(103.9, " ".join(["palabra"] * 60), dur=1.0, hueco=0.4)
    fin = ws[-1]["end"]
    keeps = [(ws[0]["start"] + 0.2, fin - 0.2)]      # solo se recortan las puntas
    cuerpo = [l for l in nucleo._guion_clip("v.mp4", ws, [], keeps, base=5)
              if l.startswith("[")]
    ok("una frase larga recortada solo en las puntas NO se marca fuera",
       bool(cuerpo) and "FUERA" not in cuerpo[0])
    ok("y dice en que segmento de plan.json vive",
       bool(cuerpo) and "#5" in cuerpo[0])

    # lo que de verdad se descarta: ni un solape
    cuerpo = [l for l in nucleo._guion_clip("v.mp4", ws, [], [(fin + 10, fin + 20)],
                                            base=0) if l.startswith("[")]
    ok("lo que no se conserva si se marca fuera",
       bool(cuerpo) and "FUERA silencio" in cuerpo[0])

    # una frase a caballo entre dos segmentos: ahi cae un corte
    cuerpo = [l for l in nucleo._guion_clip(
        "v.mp4", ws, [], [(ws[0]["start"], 120.0), (130.0, fin)], base=15)
        if l.startswith("[")]
    ok("una frase que cruza el corte nombra los dos segmentos",
       bool(cuerpo) and "#15-16" in cuerpo[0])
    ok("y no dice que se conserve entera",
       bool(cuerpo) and "entera" not in cuerpo[0])

    # -- El indice por segmento, que es la lista sobre la que se decide
    segs = [{"path": "v.mp4", "ini": 0.0, "fin": 4.0},
            {"path": "v.mp4", "ini": 10.0, "fin": 240.0}]
    idx = chr(10).join(nucleo._resumen_segmentos(segs, {"v.mp4": ws}))
    ok("el indice numera desde 0", (chr(10) + "  0  ") in idx)
    ok("el indice dice cuanto dura el bloque largo", "3m50s" in idx)

    # -- B-roll por consulta: lo que ya trae archivo no pasa por el buscador
    yaestan = [{"ini": 1, "fin": 3, "archivo": "x.mp4"}]
    ok("un b-roll que ya trae archivo se deja igual",
       nucleo._resolver_broll(yaestan, (1080, 1920, 30), ".") is yaestan)
    ok("sin b-roll no hay nada que resolver",
       nucleo._resolver_broll(None, (1920, 1080, 30), ".") is None)


def huella(proyecto, perfil):
    """Huella del corte que da `perfil` sobre la transcripcion cacheada, o None."""
    import hashlib
    tr = cache(proyecto)
    if not tr or not tr.get("words"):
        return None
    ws = tr["words"]
    keeps, _ = plan.planear(ws, max(w["end"] for w in ws) + 5, perfil=perfil)
    return hashlib.sha256(json.dumps(keeps, sort_keys=True).encode()).hexdigest()[:16]


def imprimir_huellas(proyectos):
    """Las huellas de hoy, listas para pegar en proyectos/_pruebas.json."""
    salida = {}
    for proy in proyectos:
        for perfil in plan.PERFILES_REEL:
            sha = huella(proy, perfil)
            if sha is None:
                print("sin transcripcion cacheada: %s" % proy)
                break
            salida["%s|%s" % (proy, perfil)] = sha
    print(json.dumps({"huellas": salida}, ensure_ascii=False, indent=1))


def pruebas_reels_intactos():
    """Los reels aprobados no se mueven ni un corte.

    La huella se tomo ANTES de tocar el pipeline, sobre las transcripciones
    cacheadas en proyectos/. Es la unica forma de saber que un cambio pensado
    para el video largo no toco lo que ya estaba aprobado.
    """
    print("")
    print("LOS REELS APROBADOS NO SE MUEVEN")
    ESPERADO = referencias().get("huellas") or {}
    comprobados, movidos = 0, []
    for clave in sorted(ESPERADO):
        proy, perfil = clave.split("|")
        sha = huella(proy, perfil)
        if sha is None:
            continue
        comprobados += 1
        if sha != ESPERADO[clave]:
            movidos.append(clave)
    if not comprobados:
        return saltar("los perfiles de reel dan lo mismo",
                      "sin huellas en proyectos/_pruebas.json")
    ok("%d cortes de reel identicos a antes del cambio%s"
       % (comprobados, "" if not movidos else " (movidos: %s)" % ", ".join(movidos)),
       not movidos)


# ------------------------------------------------- palabras de cada tramo
def pruebas_palabras_del_tramo():
    print("\n[que palabras entran en cada corte]")
    from pipeline.nucleo import palabras_del_tramo

    def w(t, a, b):
        return {"word": t, "start": a, "end": b}

    # Whisper estira el final de la ultima palabra antes de una pausa hasta el
    # siguiente sonido. La ultima palabra se dijo entera antes de 16.84
    # -medido con el nivel del audio- y su `end` de 17.43 es relleno: con la
    # regla de la mitad solo quedaba dentro el 18% y la palabra se caia del
    # subtitulo. Se oye y no se lee, y no da ningun error. En un video largo
    # salio en el gancho y en el remate.
    ws = [w("hasta", 16.05, 16.23), w("te", 16.23, 16.43),
          w("lo", 16.43, 16.71), w("instalamos.", 16.71, 17.43)]
    r = palabras_del_tramo(ws, 8.43, 16.84, 0.0)
    ok("la palabra que EMPIEZA dentro del corte no se cae del subtitulo",
       [x["word"] for x in r][-1] == "instalamos.")

    # La que viene arrastrando del corte anterior sigue con la regla de la
    # mitad: si apenas asoma, es del tramo de antes y aqui no se repite.
    r = palabras_del_tramo(ws, 16.65, 17.50, 0.0)
    ok("la que solo asoma por el borde de entrada no entra",
       "lo" not in [x["word"] for x in r])
    r = palabras_del_tramo(ws, 16.50, 17.50, 0.0)
    ok("pero si entra mas de la mitad, si", "lo" in [x["word"] for x in r])

    # Un limite contiguo -los que reparte tools/planos.py- NO cae dentro de una
    # palabra: `respiraciones()` devuelve el punto medio del silencio entre dos.
    # Por eso incluir la que empieza dentro no puede duplicar nada. Aqui el
    # silencio va de 16.23 a 16.43 y el corte cae en medio, como en el pipeline.
    partido = [w("hasta", 16.05, 16.23), w("lo", 16.43, 16.71),
               w("instalamos.", 16.71, 17.43)]
    a = palabras_del_tramo(partido, 8.43, 16.33, 0.0)
    b = palabras_del_tramo(partido, 16.33, 17.50, 0.0)
    ok("un corte en el silencio no duplica ni pierde ninguna palabra",
       [x["word"] for x in a] + [x["word"] for x in b]
       == [x["word"] for x in partido])

    ok("los tiempos se llevan a la linea de tiempo final",
       abs(palabras_del_tramo(ws, 16.0, 17.5, 100.0)[0]["start"] - 100.05) < 1e-6)


def pruebas_captions_por_segmento():
    print("\n[un segmento puede ir SIN caption quemado]")
    from pipeline.nucleo import palabras_del_tramo

    def w(t, a, b):
        return {"word": t, "start": a, "end": b}

    # En una demo de pantalla compartida casi todo el metraje es el
    # documento: el caption cae al 86% de la altura y ahi vive el documento
    # que el video existe para mostrar. Medido sobre un fotograma real, tapaba
    # una linea entera del informe. `"captions": false` en el segmento lo
    # apaga sin mover ni un corte -y el cursor de la linea de tiempo tiene que
    # seguir avanzando igual, o los subtitulos de despues salen corridos-.
    palabras = {"v": [w("hola", 1.0, 1.4), w("mundo", 1.4, 1.8),
                      w("y", 11.0, 11.2), w("adios", 11.2, 11.6)]}
    segs = [{"path": "v", "ini": 0.0, "fin": 10.0, "captions": False},
            {"path": "v", "ini": 10.0, "fin": 20.0}]
    finales, cursor = [], 0.0
    for s in segs:
        if s.get("captions") is not False:
            finales += palabras_del_tramo(palabras[s["path"]], s["ini"],
                                          s["fin"], cursor)
        cursor += s["fin"] - s["ini"]
    dichas = [x["word"] for x in finales]
    ok("el segmento con captions:false no aporta subtitulos",
       "hola" not in dichas and "mundo" not in dichas)
    ok("el que no lo declara si los aporta", dichas == ["y", "adios"])
    ok("el cursor no se salta: el caption siguiente cae donde toca",
       abs(finales[0]["start"] - 11.0) < 1e-6)
    ok("y el total de la linea de tiempo no cambia", abs(cursor - 20.0) < 1e-6)


# ------------------------------------------- fotogramas de referencia
def pruebas_referencias():
    print("\n[catalogo de fotogramas de referencia]")
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import referencias as ref
    except ImportError as e:
        saltar("referencias.py", "falta %s" % e.name)
        return

    # de que lado mira, a partir de los 5 puntos de YuNet
    def pts(ojo_d, ojo_i, nariz):
        return [(ojo_d, 10), (ojo_i, 10), (nariz, 20), (0, 30), (0, 30)]

    ok("de frente da giro ~0", abs(ref._giro(pts(10, 30, 20))) < 0.05)
    ok("con la nariz pegada al ojo derecho, giro negativo",
       ref._giro(pts(10, 30, 13)) < -0.3)
    ok("con la nariz pegada al ojo izquierdo, giro positivo",
       ref._giro(pts(10, 30, 27)) > 0.3)
    ok("los cubos de pose reparten", [ref._cubo(g) for g in
                                      (-0.5, -0.2, 0.0, 0.2, 0.5)] ==
       ["perfil izq", "tres cuartos izq", "frontal",
        "tres cuartos der", "perfil der"])

    # El fallo real que esto vigila: durante un rato se FILTRABA por la
    # nitidez del barrido (una miniatura de 640 px) y se ENTREGABA la medida
    # en resolucion real. Un fotograma podia parecer limpio reducido y estar
    # barrido en el original, y colarse ademas por la puerta de atras: si su
    # grupo de pose estaba vacio, entraba aunque fuera el peor del lote.
    def c(fuente, giro, nit, seg, grupo="G"):
        return {"fuente": fuente, "grupo": grupo, "giro": giro,
                "nitidez_real": nit, "seg": seg, "cara_px": 300}

    lote = [c("A", 0.0, n, i) for i, n in
            enumerate([300, 400, 500, 600, 700, 800, 900, 950, 1000, 1000])]
    lote.append(c("A", 0.5, 50, 99))          # unico de su pose, y barrido
    salida = ref.podar(lote, cuantos=20)
    ok("el barrido no entra aunque sea el unico de su pose",
       all(x["nitidez_real"] != 50 for x in salida))
    ok("y tampoco entran los que quedan bajo el suelo de su fuente",
       min(x["nitidez_real"] for x in salida) >= 0.55 * 700)

    # el suelo va contra la MEDIANA, no contra el mejor: un unico fotograma
    # excepcional no puede subirle la vara al resto de su fuente. Con el p90
    # esto dejaba fuera seis de siete.
    pico = [c("B", 0.0, 3000, 0)] + [c("B", 0.0, n, i + 1) for i, n in
                                     enumerate([300, 290, 280, 270, 260, 250])]
    salida3 = ref.podar(pico, cuantos=10)
    ok("un fotograma excepcional no se lleva por delante a los demas",
       len(salida3) == 7)

    # y en el otro sentido: el suelo NO puede cargarse la variedad. Un perfil
    # nitido tiene que entrar, y pronto, porque es el unico de su pose.
    lote2 = [c("A", 0.0, n, i) for i, n in
             enumerate([300, 400, 500, 600, 700, 800, 900, 950, 1000, 1000])]
    lote2.append(c("A", 0.5, 800, 99))
    salida2 = ref.podar(lote2, cuantos=4)
    ok("un perfil nitido si entra, y en los primeros",
       any(abs(x["giro"] - 0.5) < 1e-9 for x in salida2))

    # La deteccion que no era una cara. Caso real: en un clip de 15 fotogramas
    # con la cara centrada en y~1500, uno salio en y~2400 -era la camisa de
    # puntos con un subtitulo encima- y su nitidez, 2576 contra 38-290 del
    # resto, lo mandaba directo a lo alto de la seleccion. El score no ayudo:
    # 0.82, por encima del corte.
    def d(seg, cy, alto=780):
        return {"fuente": "clip", "grupo": "g", "seg": seg, "giro": 0.0,
                "caja": (0, cy - alto / 2.0, 600, alto), "nitidez": 100}

    clip = [d(i * 0.5, 1500) for i in range(14)] + [d(99.0, 2400, 1060)]
    vivos = ref.sin_saltos(clip)
    ok("la deteccion que salta al torso se cae",
       len(vivos) == 14 and all(x["seg"] != 99.0 for x in vivos))
    ok("y no se lleva por delante las buenas",
       all(abs(x["caja"][1] + x["caja"][3] / 2 - 1500) < 1 for x in vivos))

    # en el otro sentido: moverse dentro del encuadre es normal y NO se toca.
    # Medido sobre 5762 fotogramas reales, lo sano llega a 0.81 altos de cara.
    movido = [d(i * 0.5, 1500 + (i % 5) * 120) for i in range(20)]
    ok("moverse en el encuadre no se confunde con una deteccion falsa",
       len(ref.sin_saltos(movido)) == 20)
    ok("con pocas muestras no se descarta nada (la mediana no dice nada)",
       len(ref.sin_saltos([d(0, 1500), d(1, 2400, 1060)])) == 2)

    # El cupo por CARPETA. Nueve clips de una misma sesion son nueve archivos
    # distintos y un solo look: sin este tope se llevaron 24 de 41 plazas de
    # un catalogo real, y el resto de dias quedo casi sin representar.
    sesion = [c("clip%d" % i, 0.0, 900 + i, 0, grupo="sesion feb")
              for i in range(9)]
    otro = [c("largo", 0.0, 900, i * 10, grupo="sep") for i in range(9)]
    reparto = ref.podar(sesion + otro, cuantos=10, por_grupo=5)
    ok("una sesion partida en 9 archivos no se lleva la seleccion",
       sum(1 for x in reparto if x["grupo"] == "sesion feb") <= 5)
    ok("y la otra carpeta si entra",
       sum(1 for x in reparto if x["grupo"] == "sep") >= 4)

    # rutas: 'archivo@ini-fin' es un tramo; una ruta de Windows no lo es
    ruta, tramos = ref._fuente("C:/x/y.mp4@0-182,1098-1173")
    ok("se leen los tramos de la fuente",
       ruta == "C:/x/y.mp4" and tramos == [(0.0, 182.0), (1098.0, 1173.0)])
    ok("una ruta sin tramos se deja entera",
       ref._fuente("C:/x/y.mp4") == ("C:/x/y.mp4", None))
    ok("una ruta con @ que no es un tramo no se parte",
       ref._fuente("C:/correo@casa/y.mp4") == ("C:/correo@casa/y.mp4", None))


def pruebas_reel_frase():
    """El reel de una frase sobre imagenes: donde cae cada cambio de escena.

    Lo que se cuida: que el corte caiga en la PAUSA entre dos partes de la
    frase y no sobre una palabra, y que ninguna escena quede tan corta que se
    vea como un parpadeo. Antes la herramienta solo aceptaba una o dos
    imagenes; con cinco se cuenta una historia por capitulos en un solo reel.
    """
    print("\n== reel_frase (una frase sobre varias imagenes) ==")
    import reel_frase

    def palabras_de(grupos, pausa=0.6, paso=0.5):
        """Palabras con una pausa clara entre grupo y grupo."""
        p, t = [], 0.0
        for g in grupos:
            for w in g:
                p.append({"word": w, "start": round(t, 2), "end": round(t + 0.4, 2)})
                t += paso
            t += pausa
        return p

    grupos = [["uno", "dos"], ["tres", "cuatro"], ["cinco", "seis"]]
    palabras = palabras_de(grupos)
    partes = [" ".join(g) for g in grupos]
    dur = round(palabras[-1]["end"] + 1.6, 2)

    d = reel_frase.repartir_escenas(palabras, partes, dur, log=lambda *a: None)
    ok("una duracion por parte de la frase", len(d) == 3)
    ok("las escenas suman la duracion del reel", abs(sum(d) - dur) < 0.03)
    corte1 = round(d[0], 2)
    pausa1 = (palabras[1]["end"] + palabras[2]["start"]) / 2.0
    ok("el corte cae en la pausa entre partes, no sobre una palabra",
       abs(corte1 - pausa1) < 0.03)
    ok("y el segundo corte tambien",
       abs(d[0] + d[1] - (palabras[3]["end"] + palabras[4]["start"]) / 2.0) < 0.03)

    # cinco capitulos: el caso que la herramienta no aceptaba antes
    cinco = [["a", "b"], ["c", "d"], ["e", "f"], ["g", "h"], ["i", "j"]]
    pal5 = palabras_de(cinco)
    dur5 = round(pal5[-1]["end"] + 1.6, 2)
    d5 = reel_frase.repartir_escenas(pal5, [" ".join(g) for g in cinco], dur5,
                               log=lambda *a: None)
    ok("cinco imagenes dan cinco escenas", len(d5) == 5)
    ok("y siguen sumando el total", abs(sum(d5) - dur5) < 0.03)
    ok("ninguna escena es un parpadeo", min(d5) >= reel_frase.MIN_ESCENA - 0.01)

    # el caso malo: el giro cae casi al principio y dejaria una escena de 0.5 s
    corto = palabras_de([["uno"], ["dos", "tres", "cuatro", "cinco"]])
    dur_c = round(corto[-1]["end"] + 1.6, 2)
    avisos = []
    d_c = reel_frase.repartir_escenas(corto, ["uno", "dos tres cuatro cinco"], dur_c,
                                log=avisos.append)
    ok("una escena que quedaria muy corta se estira al minimo",
       d_c[0] >= reel_frase.MIN_ESCENA - 0.01 and abs(sum(d_c) - dur_c) < 0.03)
    ok("y lo avisa en vez de callarselo", any("giro" in a for a in avisos))

    # 🔴 La imagen fija entra a los FPS del reel. Sin -framerate, ffmpeg la lee a
    # 25 y zoompan la saca a 30: cada escena duraba 5/6 de lo pedido y el corte
    # se adelantaba (medido: 10.5 s donde el plan decia 12.5).
    ent = reel_frase._entrada_imagen("x.jpg", 12.0)
    ok("la imagen entra con los FPS del reel",
       "-framerate" in ent and ent[ent.index("-framerate") + 1] == str(reel_frase.FPS))
    ok("y el -framerate va antes del -loop",
       ent.index("-framerate") < ent.index("-loop"))
    ok("con su duracion y su ruta", "12.000" in ent and ent[-1] == "x.jpg")

    # y el caso de siempre sigue igual: una sola imagen, una sola escena
    ok("con una sola parte no hay corte",
       reel_frase.repartir_escenas(palabras, [" ".join(w["word"] for w in palabras)],
                             dur, log=lambda *a: None) == [dur])

    # El movimiento de camara va por RITMO, no por recorrido fijo: con recorrido
    # fijo, una escena larga se mueve mas lento y deja de sentirse. Reportado por
    # el usuario sobre escenas de 9 a 16 s.
    # con duraciones que no topen: el tope existe y cambia con el ritmo, asi que
    # estas dos se eligen dentro del rango a proposito
    ok("una escena el doble de larga recorre el doble",
       abs(reel_frase.recorrido(3.0) - 2 * reel_frase.recorrido(1.5)) < 1e-9
       or abs(reel_frase.recorrido(6.0) - 2 * reel_frase.recorrido(3.0)) < 1e-9)
    # entre el minimo y el tope, el ritmo por segundo es el mismo
    ok("el ritmo es el mismo en una escena corta y en una larga",
       abs(reel_frase.recorrido(4.0) / 4.0 - reel_frase.recorrido(8.0) / 8.0) < 1e-9)
    # y pasado el tope BAJA, a proposito: mas recorrido pixelaria
    largo = reel_frase.RECORRIDO_MAX / reel_frase.RITMO
    ok("pasado el tope el ritmo baja, que es lo que se quiere",
       reel_frase.recorrido(largo * 2) / (largo * 2) < reel_frase.RITMO)
    ok("una escena cortisima igual se mueve (hay minimo)",
       reel_frase.recorrido(0.5) == reel_frase.RECORRIDO_MIN)
    ok("una escena larguisima no pixela (hay tope)",
       reel_frase.recorrido(60.0) == reel_frase.RECORRIDO_MAX)
    # el zoom maximo se comprueba abajo, contando la BASE: sin ella el numero
    # queda corto y la prueba deja pasar un zoom que si pixela
    # lo que motivo el cambio: una escena de 12.5 s de un reel de 5 capitulos
    ok("la escena de 12.5 s se mueve mas que con el recorrido fijo de antes",
       reel_frase.recorrido(12.5) > 0.24)

    # 🔴 El paneo solo puede correrse por lo que el zoom recorta: con zoom 1.00 el
    # margen es cero y no hay paneo posible. Por eso hay una base y todos los
    # movimientos -menos "quieto"- panean. Lo pedido: "que se sienta movimiento".
    def arranque(mov):
        z = reel_frase._zoompan(mov, 10.0).split("z='")[1].split("'")[0]
        return float(z.split("+")[0].split("-")[0])
    for mov in ("acercar", "abrir", "lateral"):
        ok("%s arranca con margen para panear" % mov,
           arranque(mov) >= 1.0 + reel_frase.BASE - 1e-9)
    ok("quieto sigue quieto",
       reel_frase.MOVIMIENTOS["quieto"][1][0] == reel_frase.MOVIMIENTOS["quieto"][1][1])
    ok("los tres movimientos panean de verdad",
       all(reel_frase.MOVIMIENTOS[m][1][0] != reel_frase.MOVIMIENTOS[m][1][1]
           for m in ("acercar", "abrir", "lateral")))
    ok("lateral recorre la imagen casi completa",
       reel_frase.MOVIMIENTOS["lateral"][1][0] < 0.1
       and reel_frase.MOVIMIENTOS["lateral"][1][1] > 0.9)
    ok("y el zoom maximo sigue siendo el que la imagen aguanta",
       1.0 + reel_frase.BASE + reel_frase.RECORRIDO_MAX <= 1.8)

    # 🔴 La voz cuenta, no recita: por defecto va el modelo EXPRESIVO (v3).
    # Los primeros reels salieron con el multilingue y el veredicto fue: "se
    # oye sin sabor, todo asi, sin intensidad".
    import inspect
    from pipeline import voz_off as _voz
    ok("el reel se sintetiza con el modelo expresivo por defecto",
       inspect.signature(reel_frase.hacer).parameters["modelo"].default == _voz.MODELO_EXPRESIVO)
    ok("y el expresivo es el v3", _voz.MODELO_EXPRESIVO.startswith("eleven_v3"))
    ok("v3 no manda velocidad, que ahi no hace nada",
       "speed" not in _voz._ajustes(_voz.MODELO_EXPRESIVO, 0.9, 0.5))

    # El tono por defecto es el CREATIVO (0.0): mas emocion. Lo pedido:
    # "mas storytelling, mas emocion". El 0.5 natural sirve para leer, no para
    # contar una historia.
    ok("el reel se cuenta en tono creativo por defecto",
       inspect.signature(reel_frase.hacer).parameters["estabilidad"].default == reel_frase.CREATIVO
       and reel_frase.CREATIVO == 0.0)
    # Y las etiquetas de emocion del guion no pueden acabar en el subtitulo
    letras = "[serio] Hola"
    pal = _voz.palabras_desde_alineacion(list(letras), list(range(len(letras))),
                                         [i + 1 for i in range(len(letras))])
    ok("las etiquetas de emocion no salen en los subtitulos",
       [p["word"] for p in pal] == ["Hola"])
    ok("y el multilingue si la manda",
       "speed" in _voz._ajustes(_voz.MODELO, 0.9, 0.5))

    # 🔴 El proyecto de CapCut es de donde sale lo que se publica: sus clips
    # tienen que llevar el MISMO movimiento que el MP4. Antes eran fijos (medido:
    # 0.0% de escala y 0.0% de corrimiento) y el movimiento lo ponia el zoom
    # "suave" de CapCut: 1.00 -> 1.05 en toda la escena e igual en las cinco.
    cmd = reel_frase._clip_base("x.jpg", "acercar", 10.0, "out.mp4")
    ok("el clip del proyecto lleva el movimiento, no es una imagen fija",
       any("zoompan" in a for a in cmd))
    ok("y entra con los FPS del reel", "-framerate" in cmd)
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "reel_frase.py"), encoding="utf-8") as fh:
        fuente = fh.read()
    ok("y no se le pide ademas el zoom de CapCut, que encimaria dos",
       'zoom="no"' in fuente and 'zoom="suave"' not in fuente)

    # 🎙️ La VOZ GRABADA. Alguien lee el guion con su voz, y quien
    # lee no dice el texto exacto: cambia una palabra, se salta otra, agrega una.
    # Los tiempos salen de la grabacion; el TEXTO, del guion.
    def dicha(palabras_y_tiempos):
        return [{"word": w, "start": s, "end": s + 0.3} for w, s in palabras_y_tiempos]

    guion = "Doña Lupe tiene una fonda. ¿Y sabes qué?".split()
    igual = dicha([("Doña", 0.0), ("Lupe", 0.5), ("tiene", 1.0), ("una", 1.5),
                   ("fonda.", 2.0), ("¿Y", 3.0), ("sabes", 3.5), ("qué?", 4.0)])
    al = reel_frase.alinear_guion(guion, igual)
    ok("voz grabada: una palabra por palabra del GUION", len(al) == len(guion))
    ok("y con el texto del guion, signos incluidos",
       [p["word"] for p in al] == guion)
    ok("leido igual, cada palabra toma su tiempo",
       [p["start"] for p in al] == [d["start"] for d in igual])

    # la transcripcion se equivoca en el nombre: el subtitulo NO hereda el error
    veto = [dict(d) for d in igual]
    veto[1]["word"] = "Lupa"
    al = reel_frase.alinear_guion(guion, veto)
    ok("si la transcripcion oye 'Lupa', el subtitulo dice 'Lupe'",
       al[1]["word"] == "Lupe" and al[1]["start"] == 0.5)

    # se salta una palabra: el conteo sigue siendo el del guion
    salto = [d for d in igual if d["word"] != "una"]
    al = reel_frase.alinear_guion(guion, salto)
    ok("si se salta una palabra, el conteo sigue siendo el del guion",
       len(al) == len(guion))
    ok("y la que no dijo queda entre sus vecinas",
       al[2]["start"] <= al[3]["start"] <= al[4]["start"])

    # agrega palabras que no estan en el guion
    extra = dicha([("Doña", 0.0), ("Lupe", 0.5), ("pues", 0.8), ("tiene", 1.0),
                   ("una", 1.5), ("fonda", 2.0), ("¿Y", 3.0), ("sabes", 3.5),
                   ("qué?", 4.0)])
    al = reel_frase.alinear_guion(guion, extra)
    ok("si agrega una palabra, no aparece en el subtitulo",
       [p["word"] for p in al] == guion)
    ok("los tiempos nunca van hacia atras",
       all(al[i]["start"] <= al[i + 1]["start"] for i in range(len(al) - 1)))

    # una grabacion de OTRO texto no puede "alinearse": se detiene
    otra = dicha([("hola", 0.0), ("esto", 0.5), ("es", 1.0), ("otra", 1.5),
                  ("cosa", 2.0), ("distinta", 2.5)])
    try:
        reel_frase.alinear_guion(guion, otra)
        ok("una grabacion de otro texto se detiene en vez de inventar cortes", False)
    except RuntimeError:
        ok("una grabacion de otro texto se detiene en vez de inventar cortes", True)

    # y el corte de escena sigue cayendo en la pausa aunque haya agregado palabras
    partes = ["Doña Lupe tiene una fonda.", "¿Y sabes qué?"]
    al = reel_frase.alinear_guion(" ".join(partes).split(), extra)
    d = reel_frase.repartir_escenas(al, partes, 5.6, log=lambda *a: None)
    corte = d[0]
    ok("con palabras de mas, el corte sigue cayendo en la pausa del giro",
       2.3 <= corte <= 3.0)

    # Con voz grabada se REVISA que cada corte caiga en una pausa del audio. No
    # se corrige: la alarma que parecia pedirlo (15 de 18 "sobre la palabra")
    # venia de comparar contra los tiempos de ElevenLabs, y contra el audio
    # los 18 cortes ya estaban en silencio.
    huecos = [(1.5, 2.2), (4.0, 4.6)]
    ok("un corte dentro de una pausa no avisa",
       reel_frase.cortes_sobre_voz([1.8, 4.3], huecos) == [])
    ok("un corte mientras se habla avisa, con su numero",
       reel_frase.cortes_sobre_voz([1.8, 3.1], huecos) == [(2, 3.1)])
    # una pausa mas corta que el minimo de silencios (hay quien las hace de
    # 0.1 s) se reconoce midiendo el volumen JUSTO en el corte; a media voz, no.
    import subprocess, tempfile
    wav = os.path.join(tempfile.mkdtemp(), "pausa_corta.wav")
    subprocess.run(["ffmpeg", "-v", "error", "-y",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=1",
                    "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
                    "-f", "lavfi", "-i", "sine=frequency=220:duration=1",
                    "-filter_complex", "[1]atrim=duration=0.12[s];[0][s][2]concat=n=3:v=0:a=1",
                    wav], check=True)
    ok("una pausa de 0.12 s no la encuentra silencios (minimo 0.2)",
       not any(a <= 1.06 <= b for a, b in reel_frase.silencios(wav)))
    ok("pero medida en el punto exacto si es pausa, y a media voz se sigue avisando",
       reel_frase.cortes_en_voz(wav, [1.06, 0.5]) == [(2, 0.5)])
    # un corte que cae 60 ms antes de la pausa se mueve a ella; uno sin
    # pausa cerca se queda donde estaba (no se inventa un silencio)
    ok("el corte pegado a una pausa se mueve DENTRO de ella",
       1.0 <= reel_frase.acomodar_cortes(wav, [0.94])[0] <= 1.12)
    # el subtitulo no se queda encima de la escena siguiente
    bq = reel_frase.recortar_bloques([{"ini": 10.0, "fin": 12.5, "texto": "a", "voz_fin": 11.0},
                                {"ini": 12.4, "fin": 14.0, "texto": "b", "voz_fin": 13.5}],
                               [11.6, 13.0])
    ok("un subtitulo cuya voz acabo antes del corte se cierra en el corte",
       bq[0]["fin"] == 11.6 and "voz_fin" not in bq[0])
    ok("y uno que todavia se esta diciendo en el corte no se toca", bq[1]["fin"] == 14.0)
    # una tarjeta de 3 palabras y 25 caracteres se saldria de la pantalla
    frase = [{"word": w, "start": i * 0.4, "end": i * 0.4 + 0.3}
             for i, w in enumerate("La cena estaba lista. Tampoco llegaron después.".split())]
    gr = reel_frase.agrupar(frase)
    ok("ninguna tarjeta de varias palabras pasa el tope duro de caracteres",
       all(len(g) == 1 or len(" ".join(x["word"] for x in g)) <= reel_frase.DURO_CHARS for g in gr))
    ok("y el que no tiene pausa cerca no se mueve",
       reel_frase.acomodar_cortes(wav, [1.6]) == [1.6])
    # el "creativo" (0.0) de v3 se mandaba tambien al multilingue, donde
    # es el ajuste mas variable. Sin tono pedido, cada modelo va con el suyo.
    ok("sin --tono, el multilingue va con 0.5 y no con el 0.0 creativo de v3",
       reel_frase.estabilidad_para(reel_frase.voz_off.MODELO) == 0.5
       and reel_frase.estabilidad_para(reel_frase.voz_off.MODELO_EXPRESIVO) == reel_frase.CREATIVO
       and reel_frase.estabilidad_para(reel_frase.voz_off.MODELO, "robusto") == 1.0)
    ok("y ya no hay correccion a ciegas de los cortes",
       not hasattr(reel_frase, "pegar_a_silencios"))
    # 🔴 el umbral es de CADA grabacion: con -30 dB fijo la primera grabacion
    # real dio cero pausas (un cuarto tiene ruido; la voz artificial no)
    ok("el umbral de silencio sale de la voz tipica de la grabacion",
       reel_frase.umbral_desde_rms([-40, -20, -19, -21, -18]) == -26.0)
    ok("una grabacion mas fuerte sube el umbral con ella",
       reel_frase.umbral_desde_rms([-12, -10, -9]) > reel_frase.umbral_desde_rms([-22, -20, -19]))
    ok("sin niveles medibles no revienta",
       reel_frase.umbral_desde_rms([]) == -30.0)

    # 🔴 Las tarjetas respetan las oraciones (en un reel real 13 de 94
    # cruzaban un punto y 12 quedaban de una sola palabra).
    def tarjetas_de(texto, pausas=()):
        pal, t = [], 0.0
        for i, w in enumerate(texto.split()):
            pal.append({"word": w, "start": t, "end": t + 0.3})
            t += 0.4 + (0.8 if i in pausas else 0)
        return [" ".join(x["word"] for x in g) for g in reel_frase.agrupar(pal)]

    tj = tarjetas_de("El problema de doña Lupe nunca fue cocinar bien su comida. "
                     "El problema era que no sabía cuándo iba a llegar gente.")
    ok("ninguna tarjeta cruza un punto",
       not any(reel_frase.FIN_DE_ORACION.search(w) for c in tj for w in c.split()[:-1]))
    ok("y no quedan palabras sueltas en una oracion larga",
       all(len(c.split()) >= 2 for c in tj))
    enlace = {"y", "de", "el", "la", "en", "a", "al", "un", "que"}
    ok("ninguna tarjeta (salvo la ultima) termina en 'de', 'el', 'y'...",
       not any(c.split()[-1].lower().strip(".,") in enlace for c in tj))
    ok("una pausa corta a mitad de frase no parte la tarjeta",
       tarjetas_de("Y de repente llegaba otra semana.", pausas=(1,))
       == tarjetas_de("Y de repente llegaba otra semana."))
    ok("la coma parte cuando de cada lado quedan dos palabras",
       tarjetas_de("Carros afuera, gente esperando, teléfono sonando...")
       == ["Carros afuera,", "gente esperando,", "teléfono sonando..."])
    ok("una oracion corta se queda entera",
       tarjetas_de("Lo vio. Lo cerró.") == ["Lo vio.", "Lo cerró."])
    ok("una palabra que ES la oracion si puede ir sola",
       tarjetas_de("Bueno. Vamos a probar.") == ["Bueno.", "Vamos a probar."])

    # 🔴 El zoom de cuerpo entero apunta a la CARA, no al cinturon
    ok("acercar de siempre sigue apuntando al centro (no cambia lo aprobado)",
       "y='ih/2-(ih/zoom/2)'" in reel_frase._zoompan("acercar", 8.0))
    ok("acercar-arriba apunta al tercio de arriba",
       "y='(ih-ih/zoom)*0.25'" in reel_frase._zoompan("acercar-arriba", 8.0))
    ok("abrir-arriba tambien", "0.25" in reel_frase._zoompan("abrir-arriba", 8.0))

    # la cache de la transcripcion lleva la huella del audio: regrabar con el
    # mismo nombre de proyecto no puede devolver la transcripcion vieja
    ok("la transcripcion se cachea por huella del audio, no por nombre",
       "transcripcion_%s.json" in fuente and "hashlib.sha1" in fuente)


if __name__ == "__main__":
    if sys.argv[1:2] == ["--huellas"]:
        imprimir_huellas(sys.argv[2:])
        sys.exit(0)
    pruebas_fragmentos()
    pruebas_palabras_del_tramo()
    pruebas_tomas()
    pruebas_plan()
    pruebas_zoom()
    pruebas_encuadre()
    pruebas_sonidos()
    pruebas_voz()
    pruebas_exportar()
    pruebas_voz_off()
    pruebas_pertinencia()
    pruebas_plan_de_guion()
    pruebas_guion_cubre_el_audio()
    pruebas_frases()
    pruebas_video_largo()
    pruebas_captions_por_segmento()
    pruebas_referencias()
    pruebas_reel_frase()
    pruebas_reels_intactos()
    print("\n" + "=" * 52)
    if FALLOS:
        print("%d PRUEBA(S) FALLARON:" % len(FALLOS))
        for f in FALLOS:
            print("  - %s" % f)
        sys.exit(1)
    print("Todo en orden%s." % (" (%d saltadas)" % SALTADAS if SALTADAS else ""))
