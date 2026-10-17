"""Paso 2: de `orden.json` (que frases y en que orden) al corte exacto, medido en el audio.

Cada tramo se pide por FRASES, no por segundos: «desde "hola cuanto cuesta" hasta "la
relacion", despues del segundo 13.5». Se encuentran en la transcripcion y los bordes se
deciden con el VOLUMEN del audio, porque Whisper da fines tempranos y se desfasa en tomas
largas. Escribe `edl.json` (los trozos) y `guion_armado.txt` (lo que dice cada tramo).

    python largo.py cortar <proyecto>

Formato de cada tramo en orden.json:

    {"toma": "A", "desde": "hola cuanto cuesta", "hasta": "la relacion", "despues": 13.5,
     "etiqueta": "gancho", "nota": "por que va aqui",
     "arranca_en": 114.9,          # opcional: el tramo empieza EN ese segundo (un arranque a medias antes)
     "abre_en": 321.58,            # opcional: abre ahi aunque la voz sea tan bajita que parezca silencio
     "quitar": ["frase colada", [350.1, 351.0]]}   # opcional: frases o rangos a sacar de dentro
"""
import os

from largo.comun import buscar, escribir, leer, niveles_db, norm, palabras

# Dos umbrales de voz, medidos en grabaciones reales:
#  VOZ  -45 dB: lo que de verdad es habla. Con -66 las respiraciones y el ruido del cuarto
#       contaban como voz y cada corte quedaba con 0.5-1 s de pausa: «se siente muy cortado».
#  COLA -58 dB: desde el borde de la voz se estira como MAXIMO 0.2 s mientras siga habiendo
#       sonido, para no comerse el arranque o el final suave de una palabra, sin llevarse la
#       respiracion entera (dura 0.3-0.6 s).
#  Una pausa interna de mas de 0.35 s se recorta.
VOZ, COLA, ESTIRA, HUECO, PAD = -45.0, -58.0, 0.20, 0.35, 0.06


def islas(db, s, e):
    """Los trozos con voz entre s y e (segundos), con su cola suave."""
    import numpy as np
    a, b = int(s / 0.01), int(e / 0.01)
    idx = np.where(db[a:b] > VOZ)[0]
    if len(idx) == 0:
        return []
    res, ini, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if (i - prev) * 0.01 > HUECO:
            res.append((ini, prev))
            ini = i
        prev = i
    res.append((ini, prev))
    out = []
    for p, qq in res:
        p0, q0 = a + p, a + qq
        k = 0
        while k < ESTIRA / 0.01 and p0 - 1 > a and db[p0 - 1] > COLA:
            p0 -= 1
            k += 1
        k = 0
        while k < ESTIRA / 0.01 and q0 + 1 < b and db[q0 + 1] > COLA:
            q0 += 1
            k += 1
        out.append((max(s, p0 * 0.01 - PAD), min(e, (q0 + 1) * 0.01 + PAD)))
    return out


def fin_por_audio(db, t, tope=0.8, silencio=0.08):
    """Donde de verdad se calla: desde el fin que da Whisper, avanza mientras haya voz y para en
    el primer silencio de 0.08 s (lo que separa una palabra de otra). Nunca mas de 0.8 s."""
    i, lim, calla = int(t / 0.01), int((t + tope) / 0.01), 0
    while i < lim and i < len(db):
        if db[i] > COLA:
            calla = 0
        else:
            calla += 1
            if calla * 0.01 >= silencio:
                return (i - calla + 1) * 0.01 + PAD
        i += 1
    return t


def main(c):
    W = palabras(c)
    orden = leer(c, "orden.json")
    AUD = {k: niveles_db(os.path.join(c, "audio_%s.wav" % k)) for k in W}
    out, total, textos = [], 0.0, []
    for n_tramo, t in enumerate(orden, 1):
        f, et = t["toma"], t.get("etiqueta") or "tramo %d" % n_tramo
        if f not in W:
            raise SystemExit("El tramo %r pide la toma %r, que no esta en proyecto.json" % (et, f))
        ws, db = W[f], AUD[f]
        donde = "(tramo %r, toma %s)" % (et, f)
        i = buscar(ws, t["desde"], t.get("despues", 0.0), donde)
        n_fin = len([x for x in t["hasta"].split() if norm(x)])
        j = buscar(ws, t["hasta"], ws[i]["s"], donde) + n_fin - 1
        ant = ws[i - 1]["e"] if i > 0 else 0.0
        sig = ws[j + 1]["s"] if j + 1 < len(ws) else ws[j]["e"] + 0.6
        # bordes: medio hueco hacia la palabra vecina, sin pasar de 0.35 s
        s0 = max(ant + (ws[i]["s"] - ant) * 0.5, ws[i]["s"] - 0.35)
        e0 = min(ws[j]["e"] + (sig - ws[j]["e"]) * 0.5, ws[j]["e"] + 0.35)
        e0 = max(e0, fin_por_audio(db, ws[j]["e"]))   # Whisper da fines tempranos
        piezas = [(s0, e0)]
        if t.get("arranca_en") is not None:
            piezas = [(max(ps, t["arranca_en"]), pe) for ps, pe in piezas if pe > t["arranca_en"]]
        for z in t.get("quitar", []):
            if isinstance(z, list):
                cs, ce = z
            else:
                zi = buscar(ws, z, ws[i]["s"], donde)
                zj = zi + len([x for x in z.split() if norm(x)]) - 1
                cs, ce = ws[zi - 1]["e"] + 0.05, ws[zj + 1]["s"] - 0.05
            nuevas = []
            for ps, pe in piezas:
                nuevas += [(ps, cs), (ce, pe)] if ps < cs < pe else [(ps, pe)]
            piezas = nuevas
        trozos = [x for ps, pe in piezas for x in islas(db, ps, pe)]
        # una pausa de menos de 0.25 s dentro de la frase NO se quita (es la respiracion;
        # quitarla suena a brinco) y un pedacito suelto de menos de 0.25 s al arrancar se tira
        junto = []
        for a_, b_ in trozos:
            if junto and a_ - junto[-1][1] < 0.25:
                junto[-1] = (junto[-1][0], b_)
            else:
                junto.append((a_, b_))
        if len(junto) > 1 and junto[0][1] - junto[0][0] < 0.25 and junto[1][0] - junto[0][1] > 0.5:
            junto.pop(0)
        # una palabra sola al arrancar («No», «Uno») seguida de pausa corta se deja pegada:
        # si no, la imagen brinca a los 0.3 s y parece que se trabo
        if len(junto) > 1 and junto[0][1] - junto[0][0] < 0.5 and junto[1][0] - junto[0][1] <= 0.8:
            junto[:2] = [(junto[0][0], junto[1][1])]
        trozos = junto
        if t.get("abre_en") is not None:
            trozos = [(a_, b_) for a_, b_ in trozos if b_ > t["abre_en"]]
            if trozos:
                trozos[0] = (t["abre_en"], trozos[0][1])
        if not trozos:
            raise SystemExit("El tramo %r quedo sin voz: revisa sus frases y 'despues'." % et)
        dur = sum(e - s for s, e in trozos)
        total += dur
        out += [{"f": f, "s": round(s, 2), "e": round(e, 2), "et": et} for s, e in trozos]
        txt = " ".join(x["w"] for x in ws[i:j + 1])
        for z in t.get("quitar", []):
            if isinstance(z, str):
                txt = txt.replace(z, "[...]")
        textos.append(txt)
        print("%-22s %s %7.2f-%7.2f %2d tr %5.1fs | %s" % (et[:22], f, trozos[0][0], trozos[-1][1],
                                                         len(trozos), dur, txt[:90]))
    print("TOTAL %d:%04.1f en %d trozos (%d tramos)" % (total // 60, total % 60, len(out), len(orden)))
    escribir(c, "edl.json", out)
    escribir(c, "guion_armado.txt", "\n".join(textos) + "\n")
    print("\nSigue: python largo.py revisar <proyecto>   (y luego amarrar)")
