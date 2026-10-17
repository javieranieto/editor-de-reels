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
    print("Revisando esta computadora\n")

    print("Programas:")
    ok("ffmpeg", comando("ffmpeg"),
       "Instala con: winget install Gyan.FFmpeg   (y reinicia la terminal)")
    ok("ffprobe", comando("ffprobe"), "Viene con ffmpeg")

    capcut = os.path.expandvars(r"%LOCALAPPDATA%\CapCut")
    drafts = os.path.join(capcut, "User Data", "Projects", "com.lveditor.draft")
    ok("CapCut instalado", os.path.isdir(capcut), "Descarga CapCut para escritorio")
    ok("CapCut abierto al menos una vez", os.path.isdir(drafts),
       "Abre CapCut una vez y cierralo: crea la carpeta de proyectos")

    print("\nPython:")
    ok("version 3.8 o mayor", sys.version_info >= (3, 8))
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

    print("\n" + "=" * 54)
    if FALTA:
        print("Falta resolver %d cosa(s) antes de usarlo." % len(FALTA))
        sys.exit(1)
    print("Todo listo. Prueba con:")
    print('   python reel.py "C:\\ruta\\a\\tu\\video.mp4" --solo-plan')
    print("   o doble clic en \"Editor de Reels.bat\"")


if __name__ == "__main__":
    main()
