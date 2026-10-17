"""La frase clave en grande: la segunda capa de texto del reel.

POR QUE EXISTE
--------------
Salio de medir la edicion que devolvio la editora (2026-08-29) sobre dos reels
que este pipeline ya habia armado. El hallazgo fue que NO movio ni un corte:
comparando la envolvente del audio contra el que le mandamos, el desfase es
constante en las 24 ventanas de 3 s (+0.10 s en uno, 0.00 s en el otro) y no
hay deriva en ninguna. El ritmo aprobado se lo quedo entero.

Todo su valor esta encima. Y lo que mas cambia la sensacion es esto: nuestros
captions palabra-por-palabra siguen abajo, y ella pone ADEMAS la frase que
carga cada bloque, en grande, con un tratamiento distinto cada vez -papel
rasgado con maquina de escribir, subrayador amarillo que se pinta solo, bloque
con contorno, badge, tarjeta de color, manuscrita-.

Ese es el motivo real de que los reels automaticos se sientan repetitivos: hoy
lo unico que cambia entre corte y corte es la escala del zoom. No se arregla
metiendo mas efectos, se arregla teniendo mas de un tratamiento por corte.

DONDE CAE
---------
No se eligio: se midio en sus frames con una rejilla del 10%. Sus tarjetas
caen centradas alrededor del 52% de la altura. Eso encaja con la tabla de
encuadre de CLAUDE.md: queda por DEBAJO de la zona de cabeza (0.15-0.49, donde
no va nada) y por ENCIMA de los captions (0.66). La misma medicion valida el
metodo: en esos frames el caption nuestro se lee al 66%, que es justo donde lo
pone `POS_CAPTION_FRASE`.

QUE DECIDE ESTE MODULO Y QUE NO
-------------------------------
Decide COMO se ve. QUE frase merece pantalla es criterio editorial y va en el
plan, igual que la consulta de stock de cada escena: el detector automatico
no sabe cual es la tesis. En el plan:

    "frases": [{"ini": 3.3, "fin": 6.1, "texto": "NO FUNCIONABA"},
               {"ini": 18.8, "fin": 21.6, "texto": "ERA EL CABLEADO",
                "estilo": "subrayador"}]

Sin `estilo` se rota solo, y la rotacion nunca repite el tratamiento anterior:
dos tarjetas seguidas iguales devuelven el problema que esto venia a resolver.

Las fuentes y las animaciones de texto son RECURSOS DESCARGABLES, con la misma
trampa que ya costo dias en los efectos y en las letras: pycapcut escribe una
ruta inventada, CapCut no la encuentra y dibuja lo de por defecto sin avisar.
Por eso aqui se valida antes de generar y se falla CON MENSAJE.

⚠️ Y EL NOMBRE DE LA FUENTE MIENTE. El estilo `maquina` se escribio pidiendo
`Classic`, que suena a letra de documento; el archivo que hay detras es
`TikTok-Display-Medium.ttf`. Se vio al leer el draft generado, no al escribir
el codigo. Al elegir una fuente hay que mirar el ARCHIVO al que resuelve:

    python -c "from pipeline import letras; print(letras.fuentes_disponibles())"
"""
import os

from . import letras

# Centro de la frase, medido en los frames de la editora (~52% de la altura).
# transform_y va de 0 (centro) a +1 (arriba); la fraccion de altura es
# (0.5 - y/2), asi que -0.05 cae al 52.5%.
ALTURA_FRASE = -0.05

MAX_ANCHO = 0.74            # ancho util de la linea, en fraccion del lienzo

# DOS lineas es lo normal, no la excepcion: casi todas las tarjetas de la
# editora son de dos ("NO / FUNCIONABA", "ERA EL / CABLEADO"). A tres ya no
# cabe: una tarjeta de tres lineas centrada aqui sube hasta la boca y baja
# hasta los captions.
MAX_LINEAS = 2

# Cuantos pixeles mide en pantalla una unidad de `size` de CapCut. No se
# dedujo: se midio sobre un caption NUESTRO (estilo `resalte`, size 22) dentro
# del video que exporto la editora -87 y 84 px de alto en dos frames-. Sirve
# para saber cuanto ocupa una tarjeta antes de generarla.
PX_POR_SIZE = 3.9

AMBAR = "#FFC233"
AMARILLO = "#FFE500"
AZUL = "#1857C8"
BLANCO = "#FFFFFF"
NEGRO = (0.0, 0.0, 0.0)


# Cada receta es el tratamiento completo de una tarjeta. Los seis salieron de
# mirar los suyos, no de inventar variantes: son los que la editora uso de
# verdad en dos reels que devolvio aprobados.
ESTILOS = {
    "bloque": {
        "descripcion": "mayusculas gruesas con contorno negro, sin caja",
        "fuente": "Anton", "tam": 40.0, "color": (1.0, 1.0, 1.0),
        "borde": 56.0, "caja": None, "mayusculas": True,
        "chars_linea": 11,
        "entrada": ("放大", 300000),
    },
    "subrayador": {
        "descripcion": "texto negro sobre plumon amarillo que se pinta solo",
        "fuente": "Poppins_Bold", "tam": 34.0, "color": NEGRO,
        "borde": 0.0, "mayusculas": True,
        "caja": {"color": AMARILLO, "style": 1, "round_radius": 0.05,
                 "height": 0.16, "width": 0.16},
        "chars_linea": 9,
        # se revela de izquierda a derecha: es lo que hace que se lea como un
        # trazo de plumon y no como una caja que aparece de golpe
        "entrada": ("向右露出", 450000),
    },
    "badge": {
        "descripcion": "pastilla ambar redondeada, entra con rebote",
        "fuente": "Rubik_Bold", "tam": 30.0, "color": (1.0, 1.0, 1.0),
        "borde": 0.0, "mayusculas": True,
        "caja": {"color": AMBAR, "style": 1, "round_radius": 0.45,
                 "height": 0.20, "width": 0.20},
        "chars_linea": 10,
        "entrada": ("弹入", 350000),
    },
    "tarjeta": {
        "descripcion": "bloque azul de una o dos lineas, sube al entrar",
        "fuente": "Poppins_Bold", "tam": 32.0, "color": (1.0, 1.0, 1.0),
        "borde": 0.0, "mayusculas": True,
        "caja": {"color": AZUL, "style": 1, "round_radius": 0.0,
                 "height": 0.18, "width": 0.18},
        "chars_linea": 10,
        "entrada": ("向上弹入", 400000),
    },
    "maquina": {
        # Su tarjeta era monoespaciada de maquina de escribir. Aqui no hay
        # ninguna monoespaciada descargada, asi que va una serif con peso
        # (Georgia Bold) y el tecleo lo pone la ANIMACION, que es lo que de
        # verdad se lee como maquina de escribir. Si algun dia se descarga una
        # monoespaciada, se cambia aqui y ya.
        "descripcion": "papel: serif sobre caja blanca, entra tecleando",
        "fuente": "serif", "tam": 30.0, "color": NEGRO,
        "borde": 0.0, "mayusculas": False,
        "caja": {"color": BLANCO, "style": 1, "round_radius": 0.02,
                 "height": 0.22, "width": 0.20},
        "chars_linea": 10,
        # el tecleo tarda: se le da mas tiempo que a los demas
        "entrada": ("复古打字机", 700000),
    },
    "marcador": {
        "descripcion": "manuscrita blanca con contorno, aparece palabra a palabra",
        "fuente": "Atomic_Marker", "tam": 38.0, "color": (1.0, 1.0, 1.0),
        "borde": 52.0, "caja": None, "mayusculas": False,
        "chars_linea": 11,
        "entrada": ("逐字显影", 500000),
    },
}

# Orden de rotacion. No es alfabetico ni casual: alterna caja / sin caja, para
# que dos tarjetas cercanas no se parezcan aunque cambie el color.
ROTACION = ["bloque", "subrayador", "marcador", "badge", "maquina", "tarjeta"]


def disponibles():
    """{estilo: (ok, motivo)} segun lo que esta descargado en esta maquina."""
    fuentes = letras.fuentes_disponibles()
    salida = {}
    for clave, r in ESTILOS.items():
        falta = []
        if r["fuente"] and r["fuente"] not in fuentes:
            falta.append("fuente %s" % r["fuente"])
        if r["entrada"] and not _animacion_descargada(r["entrada"][0]):
            falta.append("animacion %s" % r["entrada"][0])
        salida[clave] = (not falta, ", ".join(falta))
    return salida


def _animacion_descargada(nombre):
    import pycapcut as cc
    if not hasattr(cc.TextIntro, nombre):
        return False
    meta = getattr(cc.TextIntro, nombre).value
    return os.path.isdir(os.path.join(letras.CACHE_EFECTOS, str(meta.resource_id)))


def receta(clave):
    """Receta del estilo, ya validada contra lo que hay descargado."""
    if clave not in ESTILOS:
        raise SystemExit("Estilo de frase desconocido: '%s'. Hay: %s"
                         % (clave, ", ".join(sorted(ESTILOS))))
    ok, motivo = disponibles()[clave]
    if not ok:
        raise SystemExit(
            "El estilo de frase '%s' necesita %s y no esta descargado en este\n"
            "CapCut. Aplicalo una vez a mano a cualquier texto y vuelve a\n"
            "generar. Estilos listos ahora: %s"
            % (clave, motivo, ", ".join(sorted(k for k, (o, _) in
                                               disponibles().items() if o))))
    return dict(ESTILOS[clave])


def planear(lista, log=None):
    """Ordena las frases, les reparte estilo y avisa de las que estorban.

    Devuelve la lista lista para colocar. Reparte estilo solo a las que no lo
    traen escrito, y nunca le da a dos seguidas el mismo: si se repite, vuelve
    la monotonia que este modulo existe para quitar.
    """
    if not lista:
        return []
    ok = [k for k in ROTACION if disponibles().get(k, (False, ""))[0]]
    if not ok:
        raise SystemExit(
            "Ninguno de los estilos de frase tiene sus recursos descargados.\n"
            "Corre `python reel.py --ver-frases` para ver que falta.")

    salida = []
    previo = None
    turno = 0
    for f in sorted(lista, key=lambda x: float(x.get("ini", 0))):
        texto = str(f.get("texto") or "").strip()
        if not texto:
            continue
        estilo = f.get("estilo")
        if not estilo:
            # el siguiente de la rotacion que no repita el anterior
            for _ in range(len(ok)):
                cand = ok[turno % len(ok)]
                turno += 1
                if cand != previo:
                    estilo = cand
                    break
            else:
                estilo = ok[0]
        previo = estilo
        item = dict(f)
        item["texto"] = texto
        item["estilo"] = estilo
        salida.append(item)

    if log:
        for f in salida:
            n = lineas(f["texto"], ESTILOS[f["estilo"]])
            if n > MAX_LINEAS:
                log('  aviso: "%s" ocupa %d lineas en estilo %s.'
                    % (f["texto"], n, f["estilo"]))
                log("         A tres lineas la tarjeta sube hasta la boca y baja")
                log("         hasta los captions. Acortala o cambiale el estilo.")
    return salida


def lineas(texto, receta_):
    """Cuantas lineas ocupa la frase en pantalla.

    Los caracteres por linea de cada estilo NO son a ojo: se midieron con la
    fuente real (PIL, `getlength`) al tamano real en pixeles, contra el ancho
    util `MAX_ANCHO`. Se guardan como numero para no meterle una dependencia
    de PIL al pipeline ni a las pruebas.

    El reparto es el mismo que hace CapCut: se van metiendo palabras mientras
    quepan y se salta de linea al no caber. Contar caracteres a secas no vale,
    porque el salto ocurre entre palabras.
    """
    ancho = receta_.get("chars_linea") or 10
    palabras = texto_final(texto, receta_).split()
    if not palabras:
        return 0
    n = 1
    actual = 0
    for p in palabras:
        if actual == 0:
            actual = len(p)
        elif actual + 1 + len(p) <= ancho:
            actual += 1 + len(p)
        else:
            n += 1
            actual = len(p)
    return n


def texto_final(texto, receta_):
    """Como se escribe en pantalla. Solo cambia las mayusculas del estilo."""
    return texto.upper() if receta_.get("mayusculas") else texto


def aplicar_animacion(segmento, receta_, dur_us):
    """Entrada de la tarjeta. Devuelve cuantas puso (0 o 1).

    La duracion se limita a la mitad del segmento: una entrada de 0.7 s en una
    tarjeta de 1 s es una tarjeta que se pasa animandose en vez de leerse.
    """
    import pycapcut as cc
    if not receta_.get("entrada"):
        return 0
    nombre, dur = receta_["entrada"]
    segmento.add_animation(getattr(cc.TextIntro, nombre), min(dur, dur_us // 2))
    return 1
