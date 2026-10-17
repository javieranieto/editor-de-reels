"""Lee los efectos de sonido de un proyecto de CapCut editado a mano.

Sirve para aprender del usuario en vez de adivinar: que sonidos usa, donde los
pone respecto a los cortes, y a que volumen. Es el mismo truco que destrabo el
ritmo de los cortes — medir su edicion manual en vez de teorizar.

Uso:
    python tools/analizar_sonido.py "<nombre del proyecto en CapCut>"
"""
import json
import os
import sys

RAIZ = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
US = 1_000_000


def cargar(nombre):
    ruta = os.path.join(RAIZ, nombre, "draft_content.json")
    if not os.path.exists(ruta):
        disponibles = [d for d in os.listdir(RAIZ)
                       if os.path.isdir(os.path.join(RAIZ, d))]
        sys.exit("No encuentro '%s'.\nProyectos: %s" % (nombre, ", ".join(disponibles)))
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def cortes(d):
    """Inicios de cada corte de la pista principal, en segundos."""
    for t in d.get("tracks", []):
        if t.get("type") == "video" and t.get("name") in (None, "", "video"):
            return [s["target_timerange"]["start"] / US for s in t["segments"]]
    return []


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    d = cargar(sys.argv[1])
    audios = {a["id"]: a for a in d.get("materials", {}).get("audios") or []}
    inicios = cortes(d)

    print("Proyecto: %s   (%.1f s, %d cortes)"
          % (sys.argv[1], d.get("duration", 0) / US, len(inicios)))

    eventos = []
    for t in d.get("tracks", []):
        if t.get("type") != "audio":
            continue
        for s in t["segments"]:
            m = audios.get(s.get("material_id"), {})
            ini = s["target_timerange"]["start"] / US
            eventos.append({
                "ini": ini,
                "dur": s["target_timerange"]["duration"] / US,
                "desde": (s.get("source_timerange") or {}).get("start", 0) / US,
                "volumen": s.get("volume", 1.0),
                "nombre": m.get("name") or os.path.basename(m.get("path", "")) or "?",
                "archivo": m.get("path", ""),
                "tipo": m.get("type", ""),
                "pista": t.get("name") or t.get("type"),
            })

    if not eventos:
        print("\nEste proyecto no tiene pistas de audio anadidas.")
        return

    print("\n%-8s %-6s %-6s %-34s %s" % ("EN", "DURA", "VOL", "SONIDO", "RESPECTO AL CORTE"))
    for e in sorted(eventos, key=lambda x: x["ini"]):
        if inicios:
            cerca = min(inicios, key=lambda c: abs(c - e["ini"]))
            delta = e["ini"] - cerca
            rel = ("%+.2fs del corte en %.2f" % (delta, cerca)) if abs(delta) < 2.5 else "(suelto)"
        else:
            rel = ""
        print("%7.2fs %5.2fs %5.2f %-34s %s"
              % (e["ini"], e["dur"], e["volumen"], e["nombre"][:34], rel))

    print("\n--- resumen ---")
    familias = {}
    for e in eventos:
        familias.setdefault(e["nombre"], []).append(e)
    for nombre, usos in sorted(familias.items(), key=lambda x: -len(x[1])):
        vols = [u["volumen"] for u in usos]
        print("  %-34s %d uso(s), volumen %.2f-%.2f"
              % (nombre[:34], len(usos), min(vols), max(vols)))

    if inicios:
        deltas = []
        for e in eventos:
            cerca = min(inicios, key=lambda c: abs(c - e["ini"]))
            if abs(e["ini"] - cerca) < 2.5:
                deltas.append(e["ini"] - cerca)
        if deltas:
            print("  desfase medio respecto al corte: %+.3fs (%d efectos pegados a un corte)"
                  % (sum(deltas) / len(deltas), len(deltas)))
        print("  densidad: %.1f efectos por minuto"
              % (len(eventos) / (d.get("duration", 1) / US / 60)))

    print("\nArchivos (para reutilizar los mismos sonidos):")
    for ruta in sorted({e["archivo"] for e in eventos if e["archivo"]}):
        print("  %s  %s" % ("OK " if os.path.exists(ruta) else "NO ", ruta))


if __name__ == "__main__":
    main()
