"""Decide que trozos del video se conservan y cuales se cortan."""
import re, unicodedata

# Muletillas de hesitacion: casi siempre seguras de eliminar.
HESITACIONES = {
    "eh", "ehh", "ehhh", "eeh", "em", "emm", "ehm", "mm", "mmm", "hmm", "hm",
    "ah", "ahh", "uh", "uhm", "mhm", "este", "esteee", "aaa", "eee", "uy",
}
# Solo se eliminan en modo agresivo: son palabras reales usadas como relleno.
RELLENO_AGRESIVO = {"bueno", "digamos", "verdad", "no?", "osea", "entonces"}

PERFILES = {
    "conservador": dict(max_gap=0.70, pad_in=0.12, pad_out=0.20,
                        quitar_hesitaciones=False, relleno_agresivo=False),
    "dinamico":    dict(max_gap=0.28, pad_in=0.06, pad_out=0.10,
                        quitar_hesitaciones=True, relleno_agresivo=False),
    "agresivo":    dict(max_gap=0.18, pad_in=0.04, pad_out=0.06,
                        quitar_hesitaciones=True, relleno_agresivo=True),
    # Video largo hablado a camara (el de YouTube, horizontal). NO intenta el
    # corte narrativo: de 26 a 13 minutos no se llega bajando umbrales, se
    # llega decidiendo QUE BLOQUES SE VAN, y eso es criterio, no deteccion.
    # Lo que si hace es quitar la muletilla -que en 26 minutos se acumula- y
    # respetar el aire de una charla larga: con el max_gap de un reel el
    # resultado se siente jadeante durante media hora.
    # El corte de verdad se hace revisando plan.json con guion.txt al lado
    # (los numeros de segmento estan en las dos partes) y regenerando con
    # --desde-plan.
    "largo":       dict(max_gap=0.55, pad_in=0.10, pad_out=0.16,
                        quitar_hesitaciones=True, relleno_agresivo=False),
}

# Los perfiles pensados para reel vertical. El de video largo se comporta
# distinto a proposito y no debe entrar en una comparativa de reels.
PERFILES_REEL = ("conservador", "dinamico", "agresivo")

MIN_SEGMENTO = 0.30   # descarta trozos mas cortos que esto
MIN_AHORRO = 0.12     # no vale la pena cortar si ahorra menos que esto


def _norm(w):
    w = unicodedata.normalize("NFD", w.lower())
    w = "".join(c for c in w if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w?]", "", w)


def planear(words, duracion, perfil="dinamico", **overrides):
    """Devuelve (keeps, stats). keeps = [(inicio, fin)] en segundos del original."""
    if perfil not in PERFILES:
        raise ValueError(f"perfil desconocido: {perfil}. Usa {list(PERFILES)}")
    cfg = {**PERFILES[perfil], **overrides}

    if not words:
        return [(0.0, duracion)], {"nota": "sin transcripcion: no se corto nada"}

    # 1. Marcar palabras a descartar
    descartadas = []
    utiles = []
    for i, w in enumerate(words):
        n = _norm(w["word"])
        es_hesitacion = cfg["quitar_hesitaciones"] and n in HESITACIONES
        es_relleno = cfg["relleno_agresivo"] and n in RELLENO_AGRESIVO
        # 'este' solo se quita si va seguido de pausa (si no, es demostrativo valido)
        if n == "este" and es_hesitacion:
            sig = words[i + 1] if i + 1 < len(words) else None
            if sig and sig["start"] - w["end"] < 0.25:
                es_hesitacion = False
        if es_hesitacion or es_relleno:
            descartadas.append(w)
        else:
            utiles.append(w)

    if not utiles:
        return [(0.0, duracion)], {"nota": "todo se clasifico como muletilla; no se corto"}

    # 2. Agrupar palabras utiles en bloques separados por pausas largas
    bloques = []
    actual = [utiles[0]]
    for prev, w in zip(utiles, utiles[1:]):
        if w["start"] - prev["end"] > cfg["max_gap"]:
            bloques.append(actual)
            actual = [w]
        else:
            actual.append(w)
    bloques.append(actual)

    # 3. Convertir a intervalos con margen (padding) para no cortar respiraciones
    keeps = []
    for b in bloques:
        ini = max(0.0, b[0]["start"] - cfg["pad_in"])
        fin = min(duracion, b[-1]["end"] + cfg["pad_out"])
        if fin - ini >= MIN_SEGMENTO:
            keeps.append([ini, fin])

    # 4. Fusionar los que se solapan o cuyo hueco es tan chico que el corte se nota feo
    fusionados = [keeps[0]]
    for ini, fin in keeps[1:]:
        if ini - fusionados[-1][1] < MIN_AHORRO:
            fusionados[-1][1] = max(fusionados[-1][1], fin)
        else:
            fusionados.append([ini, fin])

    # un trozo muy corto con hueco pequeno al siguiente produce un corte-tartamudeo:
    # mejor conservar la pausa y mantener la frase entera
    MIN_TROZO_SOLO = 1.2
    HUECO_FUSION = 0.6
    i = 0
    while i < len(fusionados) - 1:
        dur_actual = fusionados[i][1] - fusionados[i][0]
        dur_sig = fusionados[i + 1][1] - fusionados[i + 1][0]
        hueco = fusionados[i + 1][0] - fusionados[i][1]
        if hueco < HUECO_FUSION and (dur_actual < MIN_TROZO_SOLO or dur_sig < MIN_TROZO_SOLO):
            fusionados[i][1] = fusionados[i + 1][1]
            del fusionados[i + 1]
        else:
            i += 1

    keeps = [(round(a, 3), round(b, 3)) for a, b in fusionados]
    total = sum(b - a for a, b in keeps)
    stats = {
        "perfil": perfil,
        "duracion_original": round(duracion, 2),
        "duracion_final": round(total, 2),
        "ahorro_seg": round(duracion - total, 2),
        "ahorro_pct": round(100 * (duracion - total) / duracion, 1) if duracion else 0,
        "cortes": len(keeps),
        "muletillas_eliminadas": len(descartadas),
        "muletillas": [w["word"] for w in descartadas][:40],
    }
    return keeps, stats
