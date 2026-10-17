"""Prepara un proyecto para mandarlo, eligiendo de una lista.

Pensado para doble clic desde "Preparar para editora.bat": muestra los proyectos
que hay en CapCut, se elige uno por numero y arma el paquete en el Escritorio.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.entorno import consola_utf8

RAIZ = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")


def proyectos():
    """Los que existen en CapCut, del mas reciente al mas viejo."""
    if not os.path.isdir(RAIZ):
        return []
    salida = []
    for d in os.listdir(RAIZ):
        ruta = os.path.join(RAIZ, d)
        if d.startswith(".") or not os.path.isdir(ruta):
            continue
        contenido = os.path.join(ruta, "draft_content.json")
        if os.path.exists(contenido):
            salida.append((os.path.getmtime(contenido), d))
    return [d for _, d in sorted(salida, reverse=True)]


def main():
    consola_utf8()
    print()
    print("  PREPARAR UN PROYECTO PARA MANDARLO")
    print("  " + "=" * 48)
    print()

    lista = proyectos()
    if not lista:
        print("  No encuentro proyectos en CapCut.")
        input("\n  Enter para salir...")
        return

    for i, nombre in enumerate(lista, 1):
        print("   %2d. %s" % (i, nombre))
    print()

    try:
        eleccion = input("  Numero del proyecto (Enter para salir): ").strip()
    except (EOFError, KeyboardInterrupt):
        return
    if not eleccion:
        return
    try:
        nombre = lista[int(eleccion) - 1]
    except (ValueError, IndexError):
        print("\n  Ese numero no esta en la lista.")
        input("\n  Enter para salir...")
        return

    print()
    print("  Se va a comprimir el video para que pese poco y se pueda mandar")
    print("  por Drive. Tarda unos minutos si el video es largo.")
    respuesta = input("  Comprimir? (s/n, Enter = si): ").strip().lower()
    comprimir = respuesta != "n"

    print()
    print("  Preparando '%s'..." % nombre)
    print()
    from tools.exportar import exportar
    try:
        paquete = exportar(nombre, comprimir_video=comprimir,
                           log=lambda t: print("  " + t))
    except SystemExit as e:
        print("\n  %s" % e)
        input("\n  Enter para salir...")
        return

    print()
    print("  LISTO. La carpeta esta en tu Escritorio:")
    print("    %s" % os.path.basename(paquete))
    print()
    print("  Comprimela en ZIP, subela a Drive y manda el enlace.")
    print("  Quien la reciba solo tiene que abrir el LEEME y seguir 2 pasos.")
    input("\n  Enter para salir...")


if __name__ == "__main__":
    main()
