"""Deteccion de tomas repetidas y falsos comienzos.

Cuando alguien graba a camara y se equivoca, repite la frase: la ultima version
es la buena. Este modulo encuentra frases muy parecidas cercanas en el tiempo
y descarta las anteriores, quedandose siempre con la ultima.
"""
import difflib
import re
import unicodedata


# Al seguir una cadena de tomas ya confirmada se afloja el umbral: la ultima
# toma casi siempre se desvia en la cola porque enlaza con la frase siguiente.
UMBRAL_CADENA = 0.62

# Un "arranque abandonado" es una frase que repite el comienzo de otra ya dicha
# completa y se queda corta. Solo cuenta si es notablemente mas corta y esta
# cerca en el tiempo: una repeticion deliberada suele venir mucho despues.
PROPORCION_ABANDONO = 0.7
MAX_HUECO_ABANDONO = 30.0


def _norm(palabra):
    p = unicodedata.normalize("NFD", palabra.lower())
    p = "".join(c for c in p if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]", "", p)


def _frases(words, pausa=0.7):
    """Agrupa palabras en frases separadas por pausas largas."""
    if not words:
        return []
    frases, actual = [], [words[0]]
    for prev, w in zip(words, words[1:]):
        if w["start"] - prev["end"] > pausa:
            frases.append(actual)
            actual = [w]
        else:
            actual.append(w)
    frases.append(actual)
    return frases


def _similitud(a, b):
    """Parecido entre dos frases a nivel de palabras normalizadas (0..1)."""
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()


def _es_prefijo(corta, larga, umbral=0.8):
    """True si `corta` es (aprox) el comienzo de `larga`: un falso arranque.

    Compara a nivel de caracteres para tolerar palabras truncadas
    ("y entonces fui..." vs "y entonces fuimos al parque").
    """
    if len(corta) < 2 or len(corta) >= len(larga):
        return False
    if corta == larga[:len(corta)]:
        return True   # arranque identico palabra por palabra
    a = " ".join(corta)
    b = " ".join(larga)[:len(a) + 4]
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() >= umbral


def detectar(words, ventana=3, umbral=0.62, pausa=0.7, min_palabras=3):
    """Encuentra tomas repetidas. Devuelve (rangos_a_excluir, reporte).

    rangos_a_excluir : [(ini, fin)] en segundos del clip original
    reporte          : lineas legibles de que se descarto y por que
    """
    frases = _frases(words, pausa=pausa)
    tokens = [[_norm(w["word"]) for w in f] for f in frases]

    descartar = set()
    reporte = []
    for i in range(len(frases)):
        if i in descartar:
            continue
        for j in range(i + 1, min(i + 1 + ventana, len(frases))):
            # una retoma ocurre a los pocos segundos; dos frases parecidas muy
            # separadas son estructura del discurso, no un error que corregir
            if frases[j][0]["start"] - frases[i][-1]["end"] > MAX_HUECO_ABANDONO:
                break
            ti, tj = tokens[i], tokens[j]
            repetida = (len(ti) >= min_palabras and len(tj) >= min_palabras
                        and _similitud(ti, tj) >= umbral)
            falso_arranque = _es_prefijo(ti, tj)
            if repetida or falso_arranque:
                descartar.add(i)
                texto_i = " ".join(w["word"] for w in frases[i])
                motivo = "toma repetida" if repetida else "falso arranque"
                reporte.append('%s: "%s" (%.1fs) -> se usa la version de %.1fs'
                               % (motivo, texto_i[:60], frases[i][0]["start"],
                                  frases[j][0]["start"]))
                break

    # Pasada hacia atras: un ARRANQUE ABANDONADO. La frase es el comienzo de
    # una que ya se dijo completa poco antes, y se queda a medias — el hablante
    # empezo de nuevo y lo dejo. Sin esto, el reel puede terminar con una frase
    # truncada, porque "la ultima toma" no siempre es la buena.
    for j in range(len(frases) - 1, -1, -1):
        if j in descartar or len(tokens[j]) < 2:
            continue
        vistos = 0
        for i in range(j - 1, -1, -1):
            if i in descartar:
                continue
            vistos += 1
            if vistos > ventana:
                break
            if frases[j][0]["start"] - frases[i][-1]["end"] > MAX_HUECO_ABANDONO:
                break
            corto, largo = tokens[j], tokens[i]
            if (len(corto) < len(largo) * PROPORCION_ABANDONO
                    and corto == largo[:len(corto)]):
                descartar.add(j)
                reporte.append('arranque abandonado: "%s" (%.1fs) -> se usa la '
                               'toma completa de %.1fs'
                               % (" ".join(w["word"] for w in frases[j])[:60],
                                  frases[j][0]["start"], frases[i][0]["start"]))
                break

    rangos = [(frases[i][0]["start"], frases[i][-1]["end"]) for i in sorted(descartar)]

    # segunda pasada: repeticiones DENTRO de una misma frase (sin pausa entre tomas)
    for i, frase in enumerate(frases):
        if i in descartar:
            continue
        for a, b in _repeticiones_internas([_norm(w["word"]) for w in frase]):
            ini, fin = frase[a]["start"], frase[b - 1]["end"]
            texto = " ".join(w["word"] for w in frase[a:b])
            rangos.append((ini, fin))
            reporte.append('toma repetida (sin pausa): "%s" (%.1fs) -> se usa la que sigue'
                           % (texto[:60], ini))

    return sorted(rangos), reporte


def _repeticiones_internas(tokens, min_bloque=3, umbral=0.8):
    """Bloques consecutivos casi identicos dentro de una frase: A A -> fuera el primero."""
    hallados = []
    i = 0
    while i < len(tokens):
        golpe = 0
        for m in range(min((len(tokens) - i) // 2, 20), min_bloque - 1, -1):
            # ancla: ambos bloques deben EMPEZAR con la misma palabra; sin esto,
            # una copia corrida de si misma tambien da similitud alta y el corte
            # queda desalineado (se come palabras del bloque bueno)
            if tokens[i] != tokens[i + m]:
                continue
            if _similitud(tokens[i:i + m], tokens[i + m:i + 2 * m]) >= umbral:
                golpe = m
                break
        if golpe:
            # cadena de tomas: el hablante puede haber repetido la linea 3 o 4
            # veces. Se sigue el rastro mientras el bloque arranque igual y se
            # parezca (umbral mas flojo: ya sabemos que esta reintentando esa
            # frase, y la ultima toma suele desviarse en la cola al enlazar con
            # lo que sigue). Se corta todo menos la ULTIMA copia.
            ultimo = i + golpe
            j = i + 2 * golpe
            while (j < len(tokens) and tokens[j] == tokens[i]
                   and _similitud(tokens[i:i + golpe],
                                  tokens[j:j + golpe]) >= UMBRAL_CADENA):
                ultimo = j
                j += golpe

            # "quedarse con la ultima" falla si la ultima quedo TRUNCA: es un
            # reinicio que el hablante abandono. En ese caso vale la anterior,
            # que si esta completa, y el arranque abandonado tambien se va.
            trunca = len(tokens) - ultimo < golpe and ultimo - golpe >= i
            if trunca:
                if ultimo - golpe > i:
                    hallados.append((i, ultimo - golpe))
                hallados.append((ultimo, len(tokens)))
                i = len(tokens)
            else:
                hallados.append((i, ultimo))
                i = ultimo
        else:
            i += 1
    return hallados


def filtrar_palabras(words, rangos):
    """Quita las palabras que caen dentro de los rangos excluidos."""
    def excluida(w):
        return any(ini - 0.05 <= w["start"] and w["end"] <= fin + 0.05
                   for ini, fin in rangos)
    return [w for w in words if not excluida(w)]
