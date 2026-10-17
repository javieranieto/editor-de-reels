"""Borra las corridas desechables de proyectos/ y deja las que valen.

Cada generacion crea una carpeta nueva en proyectos/. La mayoria son pruebas
A/B —cinco estilos de letra, cuatro de cifras— que se miran una vez y estorban
para siempre. Este script separa lo que hay que conservar de lo que sobra.

Se conserva una carpeta si cumple cualquiera de estas:

  - esta en CACHES: no es un proyecto, es cache compartida (_broll, _musica,
    _voz). Borrarlas obliga a redescargar o a volver a gastar creditos de TTS.

    OJO: la regla era "empieza por _" y protegia de mas. reel_frase.py nombra
    la carpeta de trabajo de CADA corrida con "_" delante (la linea de
    `carpeta = ... "_" + nombre`), asi que ocho versiones de prueba de un
    mismo reel quedaban blindadas como si fueran cache compartida y la
    herramienta decia "se conservan" sin que nadie lo cuestionara. Por eso
    ahora la lista es explicita: una carpeta con "_" que no este en CACHES es
    trabajo de un proyecto, y es candidata.
  - tiene plan_aprobado.json: es un reel que el usuario ya aprobo, o sea la
    referencia contra la que se mide el estilo.
  - tiene CONSERVAR.txt: marca a mano, para lo que no encaja en las de arriba.
    El contenido del archivo se muestra como el motivo.

Todo lo demas es candidato, y NUNCA se borra sin confirmar.

Uso:
    python tools/limpiar.py                # lista y pregunta
    python tools/limpiar.py --listar       # solo lista, no borra nada
    python tools/limpiar.py --si           # borra sin preguntar (para scripts)
"""
import os
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRABAJO = os.path.join(BASE, "proyectos")
MARCA = "CONSERVAR.txt"

# Cache compartida de verdad: la nombra el pipeline, no una corrida. Si anades
# una, que sea porque el codigo la busca por ese nombre fijo.
CACHES = {
    "_broll":       "descargas de Pexels que reusan todos los proyectos",
    "_musica":      "analisis de la biblioteca de musica",
    "_voz":         "TTS cacheado por (texto, voz, modelo, velocidad)",
    "_voz_v3":      "lo mismo para el modelo expresivo",
    "_voces":       "el muestrario de voces; regenerarlo gasta creditos",
    "_encuadre":    "frames que dejan las herramientas de encuadre",
    "_referencias": "fotogramas de referencia para generar video con IA",
    "_marca":       "datos de marca",
    "_recetas":     "los plan.json y documentos de entrega de lo ya borrado",
    "_clips":       "los MP4 de clips ya publicados",
}


def tamano(carpeta):
    """Bytes que ocupa una carpeta, incluyendo subcarpetas."""
    total = 0
    for raiz, _, archivos in os.walk(carpeta):
        for a in archivos:
            try:
                total += os.path.getsize(os.path.join(raiz, a))
            except OSError:
                pass
    return total


def legible(n):
    for unidad in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidad == "GB":
            return "%.0f %s" % (n, unidad) if unidad != "GB" else "%.1f GB" % n
        n /= 1024.0


def motivo_conservar(carpeta, nombre):
    """Por que se queda esta carpeta, o None si es candidata a borrar."""
    if nombre in CACHES:
        return CACHES[nombre]
    if os.path.exists(os.path.join(carpeta, "plan_aprobado.json")):
        return "tiene plan_aprobado.json"
    marca = os.path.join(carpeta, MARCA)
    if os.path.exists(marca):
        try:
            with open(marca, encoding="utf-8") as f:
                nota = f.read().strip().splitlines()
            if nota:
                return nota[0][:60]
        except OSError:
            pass
        return "marcada con %s" % MARCA
    return None


def revisar():
    """Devuelve (se_quedan, candidatas), cada una como (nombre, bytes, motivo)."""
    quedan, candidatas = [], []
    if not os.path.isdir(TRABAJO):
        return quedan, candidatas
    for nombre in sorted(os.listdir(TRABAJO)):
        ruta = os.path.join(TRABAJO, nombre)
        if not os.path.isdir(ruta):
            continue
        motivo = motivo_conservar(ruta, nombre)
        fila = (nombre, tamano(ruta), motivo)
        (quedan if motivo else candidatas).append(fila)
    return quedan, candidatas


def contenido(carpeta):
    """Los archivos sueltos de la carpeta, para saber que se pierde."""
    try:
        return sorted(os.listdir(carpeta))
    except OSError:
        return []


def main():
    solo_listar = "--listar" in sys.argv
    sin_preguntar = "--si" in sys.argv

    quedan, candidatas = revisar()
    if not quedan and not candidatas:
        sys.exit("No hay nada en proyectos/.")

    print("SE QUEDAN (%d):" % len(quedan))
    for nombre, bytes_, motivo in quedan:
        print("  %-24s %8s  %s" % (nombre, legible(bytes_), motivo))

    if not candidatas:
        print("\nNada que borrar: todo lo que hay se conserva.")
        return

    total = sum(b for _, b, _ in candidatas)
    print("\nSE BORRAN (%d, %s):" % (len(candidatas), legible(total)))
    for nombre, bytes_, _ in candidatas:
        archivos = contenido(os.path.join(TRABAJO, nombre))
        resumen = ", ".join(archivos[:4])
        if len(archivos) > 4:
            resumen += ", +%d mas" % (len(archivos) - 4)
        print("  %-24s %8s  %s" % (nombre, legible(bytes_), resumen))

    print("\nPara salvar una: crea un %s dentro con el motivo." % MARCA)

    if solo_listar:
        return
    if not sin_preguntar:
        try:
            r = input("\nBorrar esas %d carpetas? (s/n): " % len(candidatas))
        except EOFError:
            sys.exit("\nSin respuesta: no se borro nada.")
        if r.strip().lower() not in ("s", "si", "y", "yes"):
            sys.exit("No se borro nada.")

    borradas = 0
    for nombre, _, _ in candidatas:
        try:
            shutil.rmtree(os.path.join(TRABAJO, nombre))
            borradas += 1
        except OSError as e:
            print("  no pude borrar %s: %s" % (nombre, e))
    print("Borradas %d de %d carpetas (%s)." % (borradas, len(candidatas), legible(total)))


if __name__ == "__main__":
    main()
