"""Arma el banco de ÍCONOS ANIMADOS (Lottie) a partir de las candidatas elegidas: los pone en los colores de cada
marca y los junta en iconos.js (window.ICONOS[marca][nombre] = animación), que leen las escenas sin internet.
Recolor, pensado para ir ENCIMA de tarjetas oscuras: tinta oscura / gris -> el blanco de la marca; el color con
más presencia -> acento; el segundo -> acento claro; el resto -> tenue. Los blancos se quedan.
Uso: python armar_iconos.py   ->  iconos.js + fuentes.json (de dónde salió cada uno) + hoja_iconos.jpg"""
import colorsys, json, os, copy
AQ = os.path.dirname(os.path.abspath(__file__)); C = os.path.join(AQ, "candidatas")
ELEGIDAS = {"alerta": "alerta_1", "apreton": "apreton_1", "buscar": "buscar_1", "calendario": "calendario_2", "chat": "chat_3",
            "cronometro": "cronometro_1", "dinero": "dinero_1", "estrellas": "estrellas_1", "grafica": "grafica_1",
            "megafono": "megafono_1", "notificacion": "notificacion_2", "palomita": "palomita_1", "pin": "pin_3",
            "reloj": "reloj_1", "telefono": "telefono_1"}
# el color de cada animación que pasa a ACENTO, cuando no es el que más se repite (el confeti le ganaba al círculo)
PRINCIPAL = {"alerta": "#ff7000", "palomita": "#34b233"}
# Las paletas salen de recursos/marcas/*.json: cada marca que tengas ahi recibe sus iconos.
_DIR_MARCAS = os.path.join(AQ, "..", "..", "marcas")
MARCAS = {}
for _f in sorted(os.listdir(_DIR_MARCAS)):
    if _f.endswith(".json"):
        _m = json.load(open(os.path.join(_DIR_MARCAS, _f), encoding="utf-8"))
        MARCAS[_m["id"]] = {k: _m["colores"][k] for k in ("texto", "acento", "acento2", "tenue")}
hexrgb = lambda h: [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]

def colores(o, out):
    """junta todos los colores sólidos de relleno/trazo: c.k = [r,g,b(,a)] o fotogramas con s=[...]"""
    if isinstance(o, dict):
        if o.get("ty") in ("fl", "st") and isinstance(o.get("c"), dict):
            k = o["c"].get("k")
            if isinstance(k, list) and k and isinstance(k[0], (int, float)): out.append(tuple(round(x, 3) for x in k[:3]))
            elif isinstance(k, list):
                for fr in k:
                    if isinstance(fr, dict) and isinstance(fr.get("s"), list): out.append(tuple(round(x, 3) for x in fr["s"][:3]))
        for v in o.values(): colores(v, out)
    elif isinstance(o, list):
        for v in o: colores(v, out)

def tipo(c):
    h, l, s = colorsys.rgb_to_hls(*c)
    if l > 0.88: return "blanco"
    if s < 0.18 or l < 0.16: return "tinta"
    return "color"

def recolorear(data, pal, principal=None):
    lista = []; colores(data, lista)
    cuenta = {}
    for c in lista: cuenta[c] = cuenta.get(c, 0) + 1
    vivos = sorted([c for c in cuenta if tipo(c) == "color"], key=lambda c: -cuenta[c])
    if principal:
        p = tuple(round(x, 3) for x in hexrgb(principal)); cerca = min(vivos, key=lambda c: sum((a - b) ** 2 for a, b in zip(c, p)))
        vivos.remove(cerca); vivos.insert(0, cerca)
    mapa = {}
    for c in cuenta:
        t = tipo(c)
        if t == "blanco": mapa[c] = list(c)
        elif t == "tinta": mapa[c] = hexrgb(pal["texto"])
        else:
            i = vivos.index(c); mapa[c] = hexrgb(pal["acento"] if i == 0 else pal["acento2"] if i == 1 else pal["tenue"])
    def aplica(o):
        if isinstance(o, dict):
            if o.get("ty") in ("fl", "st") and isinstance(o.get("c"), dict):
                o["c"].pop("x", None)       # color calculado por una fórmula (un «controlador»): se quita y manda el nuestro
                k = o["c"].get("k")
                if isinstance(k, list) and k and isinstance(k[0], (int, float)):
                    n = mapa.get(tuple(round(x, 3) for x in k[:3]))
                    if n: o["c"]["k"] = n + list(k[3:])
                elif isinstance(k, list):
                    for fr in k:
                        if isinstance(fr, dict) and isinstance(fr.get("s"), list):
                            n = mapa.get(tuple(round(x, 3) for x in fr["s"][:3]))
                            if n: fr["s"] = n + list(fr["s"][3:])
                            if isinstance(fr.get("e"), list):
                                n = mapa.get(tuple(round(x, 3) for x in fr["e"][:3]))
                                if n: fr["e"] = n + list(fr["e"][3:])
            for v in o.values(): aplica(v)
        elif isinstance(o, list):
            for v in o: aplica(v)
    d = copy.deepcopy(data); aplica(d); return d, len(cuenta)

if __name__ != "__main__": raise SystemExit  # importable sin regenerar
fuentes_todas = json.load(open(os.path.join(C, "fuentes.json"), encoding="utf-8"))
banco = {m: {} for m in MARCAS}; fuentes = {}
for nombre, cand in ELEGIDAS.items():
    data = json.load(open(os.path.join(C, cand + ".json"), encoding="utf-8"))
    for m, pal in MARCAS.items():
        banco[m][nombre], n = recolorear(data, pal, PRINCIPAL.get(nombre))
    fuentes[nombre] = dict(fuentes_todas[cand], archivo=cand + ".json", colores=n)
open(os.path.join(AQ, "iconos.js"), "w", encoding="utf-8").write(
    "// Banco de íconos animados (Lottie), ya en los colores de cada marca. Generado por armar_iconos.py: NO editar a mano.\n"
    "// De dónde salió cada uno y su licencia: fuentes.json\nwindow.ICONOS = " + json.dumps(banco, ensure_ascii=False, separators=(",", ":")) + ";\n")
json.dump(fuentes, open(os.path.join(AQ, "fuentes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(ELEGIDAS), "íconos ·", round(os.path.getsize(os.path.join(AQ, "iconos.js")) / 1024), "KB")
