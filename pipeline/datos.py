"""Deteccion de cifras en el guion para resaltarlas en pantalla.

En un reel donde el argumento SON los numeros ("subio 30 por ciento",
"120 contra 150", "antes eran tres, ahora cuatro"), sacar la cifra a pantalla
en el momento exacto en que se dice vale mas que cualquier b-roll de stock: no
es relleno, es el argumento hecho imagen.

Este modulo encuentra los momentos candidatos y propone un texto. La eleccion
final de cuales resaltar y con que redaccion se decide en el plan (es criterio,
no automatismo).
"""
import re
import unicodedata

# numeros escritos con letra que aparecen al hablar
# "un/una/uno" quedan FUERA a proposito: hablando son casi siempre articulos
# ("un negocio"), y colarlos llena el video de callouts que dicen "1".
PALABRAS_NUM = {
    "cero": "0", "dos": "2", "tres": "3",
    "cuatro": "4", "cinco": "5", "seis": "6", "siete": "7", "ocho": "8",
    "nueve": "9", "diez": "10", "once": "11", "doce": "12", "trece": "13",
    "catorce": "14", "quince": "15", "veinte": "20", "treinta": "30",
    "cuarenta": "40", "cincuenta": "50", "sesenta": "60", "setenta": "70",
    "ochenta": "80", "noventa": "90", "cien": "100", "ciento": "100",
    "mil": "1000", "millon": "1000000", "millones": "1000000",
}
# conectores que no rompen una expresion numerica
PUENTES = {"por", "ciento", "de", "cada", "contra", "y", "a", "mas", "menos",
           "pesos", "veces", "por-ciento"}

CIFRA = re.compile(r"\d")


def _norm(p):
    p = unicodedata.normalize("NFD", p.lower())
    p = "".join(c for c in p if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w%]", "", p)


def _es_numero(token):
    return bool(CIFRA.search(token)) or token in PALABRAS_NUM


def detectar(palabras, max_puente=2):
    """Momentos con cifras. Devuelve [{ini, fin, texto, frase}].

    Agrupa numeros cercanos en una sola expresion ("120 contra 150" es un dato,
    no dos) permitiendo hasta `max_puente` conectores entre ellos.
    """
    tokens = [_norm(w["word"]) for w in palabras]
    grupos, actual, puente = [], [], 0

    for i, t in enumerate(tokens):
        if _es_numero(t):
            actual.append(i)
            puente = 0
        elif actual:
            if t in PUENTES and puente < max_puente:
                actual.append(i)
                puente += 1
            else:
                grupos.append(actual)
                actual, puente = [], 0
    if actual:
        grupos.append(actual)

    salida = []
    for g in grupos:
        # recortar conectores sobrantes en los extremos
        while g and not _es_numero(tokens[g[-1]]):
            g.pop()
        if not g or not any(_es_numero(tokens[i]) for i in g):
            continue
        ini_i, fin_i = g[0], g[-1]
        crudo = " ".join(palabras[i]["word"] for i in range(ini_i, fin_i + 1))
        salida.append({
            "ini": round(palabras[ini_i]["start"], 3),
            "fin": round(palabras[fin_i]["end"], 3),
            "texto": formatear(crudo),
            "frase": crudo,
        })
    return salida


def formatear(crudo):
    """Convierte lo dicho en una etiqueta corta para pantalla."""
    t = crudo.strip().rstrip(".,;:")
    plano = _norm(t.replace(" ", "-"))

    # "30 por ciento" -> "30%"
    t = re.sub(r"(\d+)\s+por\s+ciento", r"\1%", t, flags=re.I)
    # "120 contra 150" -> "120 -> 150"
    t = re.sub(r"(\d+)\s+contra\s+(\d+)", r"\1 → \2", t, flags=re.I)
    # "tres de cada diez" -> "3/10"
    def _fraccion(m):
        a = PALABRAS_NUM.get(_norm(m.group(1)), m.group(1))
        b = PALABRAS_NUM.get(_norm(m.group(2)), m.group(2))
        return "%s/%s" % (a, b)
    t = re.sub(r"(\w+)\s+de\s+cada\s+(\w+)", _fraccion, t, flags=re.I)
    # numeros escritos con letra sueltos
    palabras_t = []
    for p in t.split():
        limpio = _norm(p)
        palabras_t.append(PALABRAS_NUM.get(limpio, p) if limpio in PALABRAS_NUM else p)
    t = " ".join(palabras_t)

    # dinero: "cero pesos" -> "$0"
    m = re.match(r"^(\d+)\s+pesos", t, flags=re.I)
    if m:
        t = "$%s" % m.group(1)
    return t.strip()
