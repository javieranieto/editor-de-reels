"""Revisa que esta computadora tenga todo lo necesario y dice que falta.

Pensado para alguien que acaba de clonar el repositorio:

    python tools/configurar.py
"""
import os
import shutil
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FALTA = []


def ok(cosa, bien, ayuda=""):
    print("  %s  %s" % ("[OK]  " if bien else "[FALTA]", cosa))
    if not bien and ayuda:
        print("          %s" % ayuda)
        FALTA.append(cosa)


def comando(nombre):
    return shutil.which(nombre) is not None


def main():
    if os.name != "nt":
        print("Este editor solo funciona en Windows con CapCut de escritorio:")
        print("escribe el proyecto en la carpeta de CapCut para Windows, y en Mac o Linux no hay donde.")
        sys.exit(1)
    print("Revisando esta computadora\n")

    print("Programas:")
    ok("ffmpeg", comando("ffmpeg"),
       "Instala con: winget install --id Gyan.FFmpeg -e   (y abre una terminal nueva)")
    ok("ffprobe", comando("ffprobe"), "Viene con ffmpeg")

    capcut = os.path.expandvars(r"%LOCALAPPDATA%\CapCut")
    drafts = os.path.join(capcut, "User Data", "Projects", "com.lveditor.draft")
    ok("CapCut instalado", os.path.isdir(capcut), "Bajalo de capcut.com (la version de ESCRITORIO, no la web)")
    ok("CapCut abierto al menos una vez", os.path.isdir(drafts),
       "Abre CapCut una vez y cierralo: crea la carpeta de proyectos")

    print("\nPython:")
    ok("version 3.9 o mayor", sys.version_info >= (3, 9),
       "Instala con: winget install --id Python.Python.3.12 -e")
    for paquete, pip in (("faster_whisper", "faster-whisper"), ("pycapcut", "pycapcut")):
        try:
            __import__(paquete)
            hay = True
        except ImportError:
            hay = False
        ok(paquete, hay, "pip install -r requirements.txt")

    print("\nGPU (opcional, acelera la transcripcion):")
    try:
        r = subprocess.run(["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                           capture_output=True, text=True, timeout=15)
        gpu = (r.stdout or "").strip().splitlines()
        print("  [OK]   %s" % gpu[0] if gpu else "  [--]   sin GPU NVIDIA (usara CPU)")
    except Exception:
        print("  [--]   sin GPU NVIDIA (usara CPU, mas lento pero funciona)")

    print("\nRecursos del proyecto:")
    sys.path.insert(0, BASE)
    try:
        from pipeline import sonidos
        n_sfx = len(sonidos.disponibles())
    except Exception:
        n_sfx = 0
    # Opcional: el repo no trae sonidos de usuario (su licencia no se puede
    # redistribuir). Sin ellos el reel sale sin sonidos, no truena.
    print("  [%s]  sonidos de usuario: %d de 4 (riser, reveal, swish, pop)"
          % ("OK" if n_sfx >= 4 else "--", n_sfx))
    if n_sfx < 4:
        print("          Opcional. Pon los tuyos en recursos/sfx_usuario/ "
              "(ver su LEEME.md).")

    try:
        sys.path.insert(0, BASE)
        from pipeline import biblioteca
        bib = biblioteca.cargar()
        total = len(bib["efectos"]) + len(bib["transiciones"])
        usables = sum(1 for g in bib.values() for m in g.values()
                      if biblioteca.usable(m))
        print("  [%s]  biblioteca de efectos: %d de %d usables aqui"
              % ("OK" if usables else "--", usables, total))
        if usables < total:
            print("          Los que faltan no los tienes descargados en tu CapCut.")
            print("          Aplicalos una vez a mano y corre: python tools/biblioteca.py --guardar")
    except Exception as e:
        print("  [--]   biblioteca: %s" % str(e)[:60])

    # Las llaves viven en .secrets/ de este repo (no suben a git).
    # Todas son opcionales: sin ellas el editor corta y arma igual.
    from pipeline import llaves
    print("\nLlaves (opcionales, en %s):" % llaves.CARPETA)
    for servicio, para in (("pexels", "b-roll de stock"),
                           ("elevenlabs", "voz en off del reel de guion"),
                           ("pixabay", "segunda fuente de stock")):
        valor, motivo = llaves.leer(servicio)
        print("  [%s]  %-11s %s" % ("OK" if valor else "--", servicio,
                                     para if valor else motivo))
    print("          Cada archivo lleva una linea: api_key: tu_llave")

    # Lo que se puede hacer con lo que hay: cada cosa dice que le falta, en vez de fallar a medias.
    print("\nQue puedes hacer en esta computadora:")
    try:
        import playwright  # noqa: F401
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            chromium = os.path.exists(p.chromium.executable_path)
    except Exception:
        playwright = chromium = None
    try:
        import cv2  # noqa: F401
        hay_cv = True
    except ImportError:
        hay_cv = False
    marcas_dir = os.path.join(BASE, "recursos", "marcas")
    propias = [f[:-5] for f in os.listdir(marcas_dir) if f.endswith(".json") and f != "ejemplo.json"] \
        if os.path.isdir(marcas_dir) else []
    pexels = llaves.leer("pexels")[0] is not None
    capacidades = [
        ("Cortar un video hablado y armarlo en CapCut (reel.py, largo.py)", not FALTA, "lo de arriba"),
        ("Stock de video en los huecos", pexels, "llave de Pexels en .secrets/pexels.yaml (gratis)"),
        ("Graficos animados y reels estilo ventana", bool(chromium),
         "pip install playwright  y luego  python -m playwright install chromium"),
        ("Encuadrar la cara en los reels y elegir cuadros para miniaturas", hay_cv, "pip install opencv-python-headless"),
        ("Graficos con TU marca", bool(propias),
         "copia recursos/marcas/ejemplo.json con tus colores (ver su LEEME.md); mientras, sale la de ejemplo"),
        ("Musica", True, ""),
    ]
    for cosa, si, falta in capacidades:
        print("  [%s]  %s" % ("SI" if si else "--", cosa))
        if not si and falta:
            print("          Falta: %s" % falta)
    if propias:
        print("          Tus marcas: %s" % ", ".join(propias))
    print("  [..]  Musica: pon tu pista (de una biblioteca libre o generada) y su nombre en musica.json;\n"
          "        el volumen se mide solo contra tu voz.")
    print("  [..]  Miniaturas con fondo recortado o imagenes generadas: Magnific (opcional, de paga, por MCP).")

    print("\n" + "=" * 54)
    if FALTA:
        print("Falta resolver %d cosa(s) antes de usarlo." % len(FALTA))
        contar_a_javier()
        sys.exit(1)
    print("Todo listo. Prueba con:")
    print('   python reel.py "C:\\ruta\\a\\tu\\video.mp4" --solo-plan')
    print("   o doble clic en \"Editor de Reels.bat\"")
    print("   o en Claude Code: \"Aqui esta mi video: <ruta>. Editalo.\"")
    print("\nLa primera transcripcion baja el modelo de voz (unos 3 GB, una sola vez).")
    contar_a_javier()


def contar_a_javier():
    print("\nCuanto te tardo instalarlo y donde te atoraste? Cuentale a Javier:")
    print("   https://javiernieto.net/profesional/recursos/editor-de-reels/")


if __name__ == "__main__":
    main()
