"""Recupera un proyecto que edito otra persona y lo deja usable aqui.

Es el camino de vuelta de `exportar.py`. Cuando alguien edita el paquete en su
computadora y devuelve la carpeta del proyecto, todas las rutas apuntan a SU
maquina: el video, el b-roll, los sonidos y lo que haya agregado. Aqui se
reescriben a las rutas locales y se instala en el CapCut de esta computadora.

Uso:
    python tools/importar.py "<carpeta que devolvio>" [--nombre "<como llamarlo>"]

Ejemplo:
    python tools/importar.py "%USERPROFILE%/Desktop/mi reel - editado"
"""
import json
import os
import shutil
import sys

RAIZ = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
CACHE = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\User Data\Cache")
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _norm(p):
    return (p or "").replace("\\", "/")


def indice_local(carpetas):
    """{nombre de archivo: ruta local} de todo lo que tengamos por aqui."""
    idx = {}
    for c in carpetas:
        if not os.path.isdir(c):
            continue
        for raiz, _, archivos in os.walk(c):
            for a in archivos:
                idx.setdefault(a.lower(), os.path.join(raiz, a))
    return idx


_HASHES = None


def _indice_hashes():
    """{hash del recurso: carpeta local} dentro de la cache de efectos.

    Hace falta porque el MISMO recurso vive bajo un id de carpeta distinto en
    cada computadora (233653725 alla, 231313341 aca) mientras el hash interno
    es identico. Buscar por ruta exacta falla; por hash, encaja.
    """
    global _HASHES
    if _HASHES is None:
        _HASHES = {}
        base = os.path.join(CACHE, "effect")
        if os.path.isdir(base):
            for carpeta in os.listdir(base):
                sub = os.path.join(base, carpeta)
                if not os.path.isdir(sub):
                    continue
                for h in os.listdir(sub):
                    if os.path.isdir(os.path.join(sub, h)):
                        _HASHES.setdefault(h, os.path.join(sub, h))
    return _HASHES


def _carpetas_del_pack():
    """El pack de recursos que se haya usado, si se recordo su ruta."""
    marca = os.path.join(BASE, "proyectos", "_musica", "pack.txt")
    if not os.path.exists(marca):
        return []
    try:
        ruta = open(marca, encoding="utf-8").read().strip()
    except Exception:
        return []
    if not ruta or not os.path.isdir(ruta):
        return []
    # se guarda la subcarpeta que se indexo (MUSICA); los adornos .mov cuelgan
    # de la carpeta de al lado, asi que se mira tambien el pack entero
    return [ruta, os.path.dirname(os.path.normpath(ruta))]


def resolver(ruta, idx):
    """Ruta local equivalente, o None si no la tenemos.

    Tres intentos: archivo propio por nombre, recurso de CapCut por ruta
    relativa, y recurso de CapCut por hash (que es lo unico estable entre
    computadoras).
    """
    n = _norm(ruta)
    bajo = n.lower()
    marca = "/user data/cache/"
    if marca in bajo:
        relativo = n[bajo.find(marca) + len("/user data/cache/"):]
        candidato = os.path.join(CACHE, relativo.replace("/", os.sep))
        if os.path.exists(candidato):
            return candidato
        hoja = os.path.basename(n)
        return _indice_hashes().get(hoja)
    return idx.get(os.path.basename(n).lower())


def rutas_del_draft(d):
    """Todo material con ruta, sea del tipo que sea.

    Antes esto era una lista fija (videos, audios, video_effects, transitions,
    effects) y se dejaba fuera lo que no estaba en ella. Al importar un pack de
    titulos comprado (2026-08-24) quedaron sin tocar 26 rutas en `hsl`,
    `common_mask` y `color_curves` -- mascaras y ajustes de color que CapCut
    descarta en silencio si no resuelven, o sea el fallo de siempre.

    Es la misma leccion que ya se aprendio en exportar.py y en la direccion
    contraria: recorrer lo que llega, no lo que se espera. CapCut suma claves
    de materiales con cada version y una lista fija envejece sola.
    """
    salida = []
    for clave, mats in (d.get("materials") or {}).items():
        if not isinstance(mats, list):
            continue
        for m in mats:
            if not isinstance(m, dict):
                continue
            ruta = m.get("path")
            if isinstance(ruta, str) and ruta and not ruta.startswith("##"):
                salida.append((clave, m))
    return salida


def importar(carpeta, nombre=None, log=print):
    ruta_json = os.path.join(carpeta, "draft_content.json")
    if not os.path.exists(ruta_json):
        raise SystemExit("Esa carpeta no tiene draft_content.json:\n  %s" % carpeta)
    nombre = nombre or os.path.basename(os.path.normpath(carpeta))

    with open(ruta_json, encoding="utf-8") as f:
        d = json.load(f)

    # dónde buscar los archivos: el paquete que se exportó, los proyectos de
    # trabajo, los recursos del repo y la carpeta de descargas
    # el primero es la carpeta que ella devolvio: ahi vienen los archivos que
    # AGREGO, que no existen en ningun otro lado de esta computadora
    escritorio = os.path.join(os.path.expanduser("~"), "Desktop")
    donde = [
        os.path.join(os.path.dirname(os.path.normpath(carpeta)), "medios_nuevos"),
        os.path.join(os.path.normpath(carpeta), "..", "medios_nuevos"),
        os.path.join(escritorio, "%s - para editar" % nombre),
        os.path.join(BASE, "proyectos"),
        os.path.join(BASE, "recursos"),
        os.path.join(os.path.expanduser("~"), "Downloads"),
    ]
    # Cualquier paquete que siga en el Escritorio: al importar se le suele dar
    # otro nombre al proyecto ("VUELTA prueba"), y entonces la carpeta del
    # paquete no se encuentra buscandola por ese nombre.
    if os.path.isdir(escritorio):
        donde += [os.path.join(escritorio, d) for d in os.listdir(escritorio)
                  if d.endswith(" - para editar")]
    # El pack de recursos: la musica y los adornos .mov viven ahi y no en el
    # repositorio. Sin esto volvian "sin resolver" tres archivos que si estan.
    donde += _carpetas_del_pack()
    idx = indice_local(donde)

    resueltas, perdidas = 0, []
    for clave, m in rutas_del_draft(d):
        local = resolver(m["path"], idx)
        if local:
            m["path"] = _norm(local)
            resueltas += 1
        else:
            perdidas.append((clave, m.get("name") or os.path.basename(_norm(m["path"]))))

    # las fuentes de los captions cuelgan de la version de CapCut instalada
    fuentes = _carpeta_fuentes()
    if fuentes:
        raices = [carpeta]
    padre = os.path.dirname(os.path.normpath(carpeta))
    if padre and os.path.isdir(padre):
        raices.append(padre)
        abuelo = os.path.dirname(padre)
        if abuelo and os.path.isdir(abuelo):
            raices.append(abuelo)
    _reescribir_fuentes(d, fuentes, _indice_fuentes(raices))

    destino = os.path.join(RAIZ, nombre)
    if os.path.exists(destino):
        shutil.rmtree(destino)
    shutil.copytree(carpeta, destino)
    with open(os.path.join(destino, "draft_content.json"), "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    _arreglar_meta(destino, nombre)

    log("Importado como '%s'" % nombre)
    log("  %d ruta(s) resueltas" % resueltas)
    if perdidas:
        log("  %d sin resolver (no estan en esta computadora):" % len(perdidas))
        for clave, n in perdidas:
            log("     %-14s %s" % (clave, n))
        log("  Si es musica o un efecto de la biblioteca de CapCut, basta con")
        log("  agregarlo una vez a mano aqui y volver a importar.")
    return destino, perdidas


def _carpeta_fuentes():
    apps = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\Apps")
    if not os.path.isdir(apps):
        return None
    for v in sorted(os.listdir(apps), reverse=True):
        f = os.path.join(apps, v, "Resources", "Font", "SystemFont")
        if os.path.isdir(f):
            return _norm(f)
    return None


def _indice_fuentes(raices, tope=4000):
    """{nombre.ttf en minuscula: ruta} de los archivos de fuente que haya suelto.

    Los packs comprados traen sus fuentes en una carpeta aparte ("Fuentes
    Premium" y similares) mientras el draft las apunta a la CACHE de quien lo
    armo. Sin esto, CapCut no encuentra la fuente y **dibuja la de por defecto
    sin avisar**: el sintoma es "el titulo se ve, pero no con esa letra".
    Que un .ttf suelto sirva no es teoria: es lo que ya hace exportar.py, que
    copia Anton al paquete y reapunta la ruta ahi.
    """
    idx, n = {}, 0
    for raiz in raices:
        if not raiz or not os.path.isdir(raiz):
            continue
        for base, _, archivos in os.walk(raiz):
            for a in archivos:
                if a.lower().endswith((".ttf", ".otf")):
                    idx.setdefault(a.lower(), os.path.join(base, a))
                    n += 1
                    if n >= tope:
                        return idx
    return idx


def _reescribir_fuentes(d, fuentes, sueltas=None):
    sueltas = sueltas or {}
    for t in (d.get("materials") or {}).get("texts") or []:
        for campo in ("font_path",):
            p = _norm(t.get(campo))
            if "/Resources/Font/" in p:
                t[campo] = "%s/%s" % (fuentes, os.path.basename(p))
            elif p and not os.path.exists(p):
                # fuente descargada de otra maquina: por hash, o el archivo suelto
                local = resolver(p, {}) or sueltas.get(os.path.basename(p).lower())
                if local:
                    t[campo] = _norm(local)
        try:
            cont = json.loads(t.get("content") or "{}")
            cambiado = False
            for est in cont.get("styles") or []:
                p = _norm((est.get("font") or {}).get("path"))
                if "/Resources/Font/" in p:
                    est["font"]["path"] = "%s/%s" % (fuentes, os.path.basename(p))
                    cambiado = True
            if cambiado:
                t["content"] = json.dumps(cont, ensure_ascii=False)
        except Exception:
            pass


def _arreglar_meta(destino, nombre):
    ruta = os.path.join(destino, "draft_meta_info.json")
    if not os.path.exists(ruta):
        return
    with open(ruta, encoding="utf-8") as f:
        m = json.load(f)
    m["draft_name"] = nombre
    m["draft_fold_path"] = _norm(destino)
    m["draft_root_path"] = RAIZ
    if m.get("draft_cover"):
        m["draft_cover"] = _norm(os.path.join(destino, "draft_cover.jpg"))
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False)


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.entorno import consola_utf8


def main():
    consola_utf8()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    nombre = None
    if "--nombre" in sys.argv:
        i = sys.argv.index("--nombre")
        if i + 1 < len(sys.argv):
            nombre = sys.argv[i + 1]
            if nombre in args:
                args.remove(nombre)
    importar(args[0], nombre)


if __name__ == "__main__":
    main()
