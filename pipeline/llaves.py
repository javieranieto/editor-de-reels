"""Donde viven las llaves del editor: en la carpeta `.secrets/` del propio repo.

Esa carpeta NO sube a git (esta en `.gitignore`). Un archivo por servicio:

    .secrets/elevenlabs.yaml   api_key   (voz en off, opcional)
    .secrets/pexels.yaml       api_key   (b-roll de stock, opcional)
    .secrets/pixabay.yaml      api_key   (segunda fuente de stock, opcional)

Cada archivo lleva una sola linea:  api_key: tu_llave_aqui

La ruta se resuelve RELATIVA A ESTE ARCHIVO, no al directorio desde donde se
corre: con una ruta relativa, el mismo comando funcionaba desde una carpeta y
fallaba desde otra con un "falta la clave" que no decia nada.

Un campo que todavia
trae el marcador `<PENDIENTE: ...>` cuenta como que FALTA: un marcador se ve
"lleno" en cualquier revision que solo pregunte si existe, y el programa
acabaria muriendo lejos de aqui con un 401.
"""
import os

EDITOR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARPETA = os.path.join(EDITOR, ".secrets")

CAMPOS = ("api_key", "key")


def ruta(servicio):
    """Archivo de llaves de un servicio: .secrets/<servicio>.yaml."""
    return os.path.join(CARPETA, servicio + ".yaml")


def _leer_yaml(archivo):
    """Dict del YAML. Sin PyYAML se leen las lineas `clave: valor` de la raiz."""
    with open(archivo, encoding="utf-8-sig") as f:
        texto = f.read()
    try:
        import yaml
        datos = yaml.safe_load(texto)
        return datos if isinstance(datos, dict) else {}
    except ImportError:
        pass
    datos = {}
    for linea in texto.splitlines():
        if not linea.strip() or linea.lstrip().startswith("#") or linea[:1].isspace():
            continue
        if ":" not in linea:
            continue
        clave, valor = linea.split(":", 1)
        valor = valor.split(" #", 1)[0].strip().strip('"').strip("'")
        datos[clave.strip()] = valor
    return datos


def leer(servicio, campos=CAMPOS):
    """(valor, motivo). valor es None si no hay llave usable; motivo dice por que."""
    archivo = ruta(servicio)
    if not os.path.exists(archivo):
        return None, "no existe %s" % archivo
    try:
        datos = _leer_yaml(archivo)
    except Exception as e:
        return None, "no se pudo leer %s (%s)" % (archivo, str(e)[:80])
    # Tambien se acepta la llave dentro del nombre del servicio (`pexels:\n  api_key: ...`),
    # que es como la guardan otros sistemas: copiar el archivo tal cual tiene que funcionar.
    if isinstance(datos.get(servicio), dict) and not any(datos.get(c) for c in campos):
        datos = datos[servicio]
    for campo in campos:
        valor = datos.get(campo)
        if valor is None:
            continue
        valor = str(valor).strip()
        if not valor:
            return None, "el campo '%s' de %s esta vacio" % (campo, archivo)
        if valor.startswith("<PENDIENTE"):
            return None, ("el campo '%s' de %s todavia tiene el marcador "
                          "<PENDIENTE>" % (campo, archivo))
        return valor, ""
    return None, "%s no tiene el campo '%s'" % (archivo, campos[0])


def hay(servicio):
    """True si el servicio tiene una llave usable (sin marcador)."""
    return leer(servicio)[0] is not None
