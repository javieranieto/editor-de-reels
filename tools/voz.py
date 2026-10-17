"""Comprueba la clave de ElevenLabs y lista las voces de la cuenta.

    python tools/voz.py                 # que voces tienes
    python tools/voz.py --probar        # sintetiza una frase corta y la guarda

Sirve para saber si la clave y sus permisos quedaron bien ANTES de gastar
creditos en un reel entero. La prueba usa una frase de unos 60 caracteres:
medio por mil de la cuota mensual.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline import voz_off

FRASE = "Esta es una prueba de la voz para los reels. Uno, dos, tres."
DESTINO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "proyectos", "_voz", "prueba.mp3")


def main():
    try:
        clave = voz_off.leer_clave()
    except RuntimeError as e:
        print("")
        print(str(e))
        print("")
        return 1

    print("")
    # ni un pedazo de la clave en pantalla: la consola acaba pegada en un chat
    print("Clave leida de %s (%d caracteres)" % (voz_off.CLAVE, len(clave)))

    try:
        lista = voz_off.voces(clave)
    except Exception as e:
        # Restringir la clave a solo Text to Speech deja fuera voices_read, y
        # entonces no se pueden listar las voces de la cuenta. La sintesis SI
        # funciona, asi que se sigue con las voces publicas en vez de abortar.
        print("")
        print("No puedo listar TUS voces: %s" % str(e)[:120])
        print("A la clave le falta el permiso 'voices_read' (solo lectura).")
        print("Para tenerlo: elevenlabs.io -> Profile -> API Keys -> editar la")
        print("clave y darle Access a 'Voices'. No hace falta para sintetizar.")
        print("")
        print("Mientras tanto, uso las voces publicas de ElevenLabs:")
        lista = [(vid, n, "publica") for n, vid in voz_off.VOCES_PUBLICAS]

    print("")
    print("VOCES DISPONIBLES (%d):" % len(lista))
    for vid, nombre, etiqueta in lista:
        print("   %-26s %-34s %s" % (nombre[:26], vid, etiqueta[:20]))
    print("")

    if "--probar" not in sys.argv:
        print("Para oir una: python tools/voz.py --probar")
        print("")
        return 0

    vid = lista[0][0]
    for v, n, _ in lista:
        if "spanish" in (n or "").lower() or "espa" in (n or "").lower():
            vid, nombre = v, n
            break
    else:
        nombre = lista[0][1]

    print("Sintetizando con '%s'..." % nombre)
    os.makedirs(os.path.dirname(DESTINO), exist_ok=True)
    try:
        r = voz_off.sintetizar(FRASE, vid, DESTINO, clave=clave,
                               log=lambda t: print(" " + t))
    except RuntimeError as e:
        print("")
        print(str(e)[:400])
        print("")
        return 1
    print("")
    print("  archivo: %s" % r["archivo"])
    print("  %d palabras, %.2f s" % (len(r["palabras"]), r["duracion"]))
    print("  primeras: %s"
          % ", ".join("%s(%.2f)" % (w["word"], w["start"])
                      for w in r["palabras"][:6]))
    print("")
    print("Si eso suena bien y los tiempos cuadran, la clave esta lista.")
    print("")
    return 0


if __name__ == "__main__":
    sys.exit(main())
