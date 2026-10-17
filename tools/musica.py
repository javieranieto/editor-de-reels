"""Elige musica para un reel de entre la biblioteca de CapCut ya descargada.

    python tools/musica.py --analizar              # mide toda la biblioteca
    python tools/musica.py --proponer [segundos]   # deja 3 candidatas a mano
    python tools/musica.py --beats <archivo>       # BPM y golpes de una pista

Las pistas de `Cache/music` no tienen nombre (CapCut no guarda los titulos en
ninguna de sus bases). Se eligen escuchandolas: `--proponer` copia tres a
`proyectos/_musica/` con nombres claros y explica por que salio cada una.

Que se busca, en orden de importancia:

1. Que NO estorbe la voz. La musica va debajo de alguien hablando; una pista
   con mucha energia en la banda de 200-4000 Hz pelea con la voz por mas que
   se le baje el volumen. Es el criterio que mas manda.
2. Que tenga beat claro, o no hay nada que sincronizar.
3. Que dure lo que el reel.
4. Que las tres suenen DISTINTO entre si: una tranquila, una media y una
   movida. Proponer tres parecidas no es proponer nada.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import musica
from pipeline.entorno import consola_utf8

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(BASE, "proyectos", "_musica")
INDICE = os.path.join(CARPETA, "indice.json")

# Un pack de recursos de edicion trae la musica CON NOMBRE y por categoria, que
# es justo lo que la cache de CapCut no da (ahi son hashes). La ruta se recuerda
# para no volver a teclearla.
PACK = os.path.join(CARPETA, "pack.txt")


def _limpio(nombre):
    """Nombre de archivo seguro, conservando algo reconocible."""
    malos = '<>:"/\\|?*'
    return "".join(" " if c in malos else c for c in nombre)[:60].strip()


def carpeta_pack():
    if os.path.exists(PACK):
        ruta = open(PACK, encoding="utf-8").read().strip()
        if os.path.isdir(ruta):
            return ruta
    return None


def recordar_pack(ruta):
    os.makedirs(CARPETA, exist_ok=True)
    with open(PACK, "w", encoding="utf-8") as f:
        f.write(ruta)


def analizar_todo(pack=None, log=print):
    pack = pack or carpeta_pack()
    if pack:
        recordar_pack(pack)
        pistas = musica.pistas_locales(pack, recursivo=True)
        log("Pack: %s" % pack)
    else:
        pistas = musica.pistas_locales()
    if not pistas:
        raise SystemExit("No encuentro musica en:\n  %s"
                         % (pack or musica.CACHE_MUSICA))
    datos = musica.cargar_indice(INDICE)
    nuevas = [p for p in pistas if p not in datos]
    log("Biblioteca: %d pistas (%d por medir)" % (len(pistas), len(nuevas)))
    for i, p in enumerate(nuevas, 1):
        info = musica.analizar(p)
        if info:
            info["dur"] = musica.duracion(p)
            info["nombre"] = os.path.splitext(os.path.basename(p))[0]
            info["categoria"] = os.path.basename(os.path.dirname(p))
            datos[p] = info
        if i % 100 == 0:
            log("  %d/%d..." % (i, len(nuevas)))
            musica.guardar_indice(INDICE, datos)
    musica.guardar_indice(INDICE, datos)
    con = sum(1 for v in datos.values() if v.get("con_beat"))
    log("Medidas %d pistas; %d con beat utilizable." % (len(datos), con))
    return datos


def proponer(segundos=40.0, cuantas=3, log=print):
    datos = musica.cargar_indice(INDICE)
    if not datos:
        raise SystemExit("Primero mide la biblioteca:\n"
                         "  python tools/musica.py --analizar")

    # Limites de cordura. Se repartian las candidatas por nivel de energia y el
    # extremo agarraba pistas patologicas: una salio con energia 1.26 (eso es
    # saturacion, no musica) y 0.1% de contenido en la banda media, o sea puro
    # sub-bajo. Sonaba a error, no a cancion.
    aptas = [(k, v) for k, v in datos.items()
             if v.get("con_beat") and v.get("dur", 0) >= segundos
             and 0.03 <= v.get("energia", 0) <= 0.5
             and 0.05 <= v.get("estorbo", 1) <= 0.75]
    if not aptas:
        raise SystemExit("Ninguna pista cumple (con beat y al menos %.0fs)."
                         % segundos)

    # Menos estorbo en la banda de la voz es lo que mas pesa; entre las
    # limpias, mejor beat marcado.
    aptas.sort(key=lambda kv: (kv[1]["estorbo"], -kv[1]["conf"]))
    finalistas = aptas[:max(30, cuantas * 10)]

    # Una de cada nivel de energia, para que las tres no suenen igual.
    finalistas.sort(key=lambda kv: kv[1]["energia"])
    n = len(finalistas)
    elegidas = [finalistas[int(i * (n - 1) / max(1, cuantas - 1))]
                for i in range(cuantas)]

    if os.path.isdir(CARPETA):
        for f in os.listdir(CARPETA):
            if f.startswith("candidata"):
                os.remove(os.path.join(CARPETA, f))
    os.makedirs(CARPETA, exist_ok=True)

    etiquetas = ["tranquila", "media", "movida"]
    log("")
    log("TRES CANDIDATAS (de %d pistas aptas)" % len(aptas))
    log("")
    salida = []
    for i, (clave, v) in enumerate(elegidas):
        et = etiquetas[i] if i < len(etiquetas) else "opcion%d" % (i + 1)
        origen = clave if os.path.isabs(clave) else os.path.join(
            musica.CACHE_MUSICA, clave)
        nombre = v.get("nombre") or et
        destino = os.path.join(
            CARPETA, "candidata %d - %s%s" % (i + 1, _limpio(nombre),
                                              os.path.splitext(origen)[1]))
        shutil.copy2(origen, destino)
        log("  %d. %s" % (i + 1, nombre[:58]))
        log("      %-14s %5.1f BPM   %4.1f min   estorba la voz: %d%%"
            % (v.get("categoria", "")[:14], v["bpm"], v["dur"] / 60.0,
               round(v["estorbo"] * 100)))
        salida.append({"archivo": destino, "origen": origen, **v})
    log("")
    log("Estan en: %s" % CARPETA)
    log("Escuchalas y dime el numero. Con esa sincronizo los acentos.")
    return salida


def main():
    consola_utf8()
    args = sys.argv[1:]
    pack = None
    if "--pack" in args:
        i = args.index("--pack")
        pack = args[i + 1]
        del args[i:i + 2]
    if "--analizar" in args:
        analizar_todo(pack)
        return
    if "--beats" in args:
        i = args.index("--beats")
        ruta = args[i + 1]
        info = musica.analizar(ruta)
        if not info:
            raise SystemExit("No pude leer esa pista.")
        print("  BPM %.1f   confianza %.2f   %s"
              % (info["bpm"], info["conf"],
                 "beat utilizable" if info["con_beat"] else "SIN beat claro"))
        print("  primeros golpes: %s"
              % ", ".join("%.2f" % t for t in musica.rejilla(info, 8)))
        return
    seg = 40.0
    for a in args:
        try:
            seg = float(a)
        except ValueError:
            pass
    proponer(seg)


if __name__ == "__main__":
    main()
