"""Elige la imagen de cada escena entre varios proveedores, y sabe decir que NO.

Es la pieza que faltaba entre `guion.py` y los catalogos de stock. Antes
`guion_a_plan` recibia un buscador que se quedaba con el primer resultado; como
la busqueda siempre devuelve algo, el reel salia ilustrado con lo que fuera.

Aqui se pide a cada proveedor y se puntua contra la consulta (`pertinencia`).
Gana el de mejor puntaje; si ninguno llega al umbral, la escena se queda SIN
imagen y se dice en el reporte, con las consultas que fallaron. Una escena
vacia se ve y se arregla; una imagen que no viene al caso se cuela.
"""
import os
import shutil

from . import broll, pertinencia, pixabay


def orientacion_de(canvas):
    """La orientacion que pide el proyecto, sacada de su LIENZO.

    No es una opcion que alguien elija: el canvas ya se calcula del primer
    clip, asi que un reel vertical pide "portrait" y el video largo de
    YouTube (1920x1080) pide "landscape" sin que nadie tenga que acordarse.
    """
    ancho, alto = canvas[0], canvas[1]
    return "landscape" if ancho > alto else "portrait"


def proveedores(usar_pixabay=True):
    """Los que se pueden usar en esta computadora. Sin clave, no participa."""
    lista = [("pexels", broll)]
    if usar_pixabay and pixabay.hay_clave():
        lista.append(("pixabay", pixabay))
    return lista


def mejor_candidato(consulta, umbral=pertinencia.UMBRAL, cantidad=12,
                    usar_pixabay=True, orientacion="portrait", log=None):
    """El video que mejor ilustra la consulta entre todos los proveedores."""
    candidatos = []
    for nombre, prov in proveedores(usar_pixabay):
        try:
            candidatos += prov.buscar(consulta, cantidad=cantidad,
                                      orientacion=orientacion)
        except Exception as e:
            if log:
                log("  aviso: %s fallo en '%s': %s" % (nombre, consulta, e))
    return pertinencia.mejor(consulta, candidatos, umbral)


def crear_buscador(carpeta, umbral=pertinencia.UMBRAL, usar_pixabay=True,
                   orientacion="portrait", log=print):
    """Devuelve la funcion `buscar(consulta, segundos)` que espera `guion.py`.

    Guarda el registro de lo que encontro y lo que no en `.informe`, para poder
    decirlo al final en vez de que una escena sin imagen pase inadvertida.
    """
    destino = os.path.join(carpeta, "stock")
    os.makedirs(destino, exist_ok=True)
    informe = {"puestas": [], "sin_imagen": [], "creditos": []}
    ya = {}

    def buscar(consulta, segundos=None):
        if consulta in ya:
            return ya[consulta]
        # una anotacion puede traer alternativas separadas por |, porque el
        # vocabulario del stock es limitado y a veces la palabra exacta no
        # existe: gana la que mejor ilustre, no la primera que conteste
        opciones = [t.strip() for t in consulta.split("|") if t.strip()]
        video = None
        for opcion in opciones:
            video = mejor_candidato(opcion, umbral, usar_pixabay=usar_pixabay,
                                    orientacion=orientacion, log=log)
            if video:
                consulta = opcion
                break
        if not video:
            informe["sin_imagen"].append(consulta)
            log("  sin imagen: '%s' (nada que ilustre la escena)" % consulta)
            ya[consulta] = None
            return None
        prov = pixabay if video.get("fuente") == "pixabay" else broll
        origen = prov.descargar(video)
        ruta = os.path.join(destino, os.path.basename(origen))
        if not os.path.exists(ruta):
            shutil.copy2(origen, ruta)
        informe["puestas"].append({
            "consulta": consulta, "fuente": video.get("fuente"),
            "descripcion": video.get("descripcion", ""),
            "puntaje": round(pertinencia.puntuar(
                consulta, video.get("descripcion", "")), 2),
            "archivo": os.path.basename(ruta)})
        if video.get("autor"):
            informe["creditos"].append("%s - %s (%s)" % (
                video["autor"], video.get("pagina", ""), video.get("fuente")))
        ya[consulta] = ruta
        return ruta

    buscar.informe = informe
    return buscar


def resumen(informe, log=print):
    """Dice cuantas escenas se ilustraron y cuales no. Sin esto, el cero pasa."""
    puestas, sin = informe["puestas"], informe["sin_imagen"]
    total = len(puestas) + len(sin)
    log("Stock: %d de %d consultas ilustradas" % (len(puestas), total))
    if sin:
        log("  SIN IMAGEN (%d): %s" % (len(sin), ", ".join(sin)))
        log("  Cambia esas consultas en el plan por algo que exista en video de")
        log("  archivo, o reescribe la escena.")
