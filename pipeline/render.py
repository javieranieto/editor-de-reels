"""Renderiza el video ya cortado con ffmpeg (la via robusta, sin drafts de CapCut).

Une los trozos del plan en un MP4 nuevo y normaliza el volumen a -14 LUFS
(el estandar de reels). El resultado se importa a CapCut como cualquier clip.
"""
import os
import subprocess


def tiene_audio(ruta):
    """ffprobe dice si el archivo trae pista de audio.

    Los clips de stock NO la traen, y el filtro daba por hecho que si: pedir
    `[N:a]` de un archivo mudo revienta con "matches no streams", que no dice
    nada de lo que pasa. Ante la duda se responde False y se pone silencio.
    """
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "a",
             "-show_entries", "stream=index", "-of", "csv=p=0", ruta],
            capture_output=True, text=True, encoding="utf-8", errors="replace")
        return bool((r.stdout or "").strip())
    except Exception:
        return False


# 30 ms a cada lado del corte. Valor de browser-use/video-use, que lo lista
# entre sus reglas de correccion de produccion: sin el, chasquido en cada corte.
FADE_CORTE = 0.030


def renderizar_segmentos(segmentos, salida, crf=18, normalizar=True,
                         voz_path=None):
    """Como renderizar(), pero los tramos pueden venir de VARIOS archivos.

    segmentos: [{"path": ruta, "ini": seg, "fin": seg}] en orden final.
    voz_path: si se pasa, esa pista MANDA y sustituye al audio de los clips.
        Es el caso del reel de guion: el stock va mudo y la voz en off lleva
        todo el peso.
    """
    if not segmentos:
        raise ValueError("No hay tramos que renderizar")

    rutas = []
    for s in segmentos:
        ruta = os.path.abspath(s["path"])
        if ruta not in rutas:
            rutas.append(ruta)
    idx = {r: i for i, r in enumerate(rutas)}
    con_audio = {r: tiene_audio(r) for r in rutas}

    cadenas, pares = [], []
    for i, s in enumerate(segmentos):
        n = idx[os.path.abspath(s["path"])]
        dur = s["fin"] - s["ini"]
        # Micro-fade en cada borde: un empalme sobre audio con amplitud no nula
        # produce un chasquido. Medido en el material real, los cortes caen
        # entre -66 y -44 dB (el ajuste a la voz ya los deja en zona casi muda),
        # asi que esto es un seguro barato mas que una urgencia.
        # Regla tomada de browser-use/video-use (SKILL.md, "Hard Rules").
        fade = ""
        if dur > 2 * FADE_CORTE + 0.02:
            fade = (",afade=t=in:st=0:d=%.3f,afade=t=out:st=%.3f:d=%.3f"
                    % (FADE_CORTE, dur - FADE_CORTE, FADE_CORTE))
        cadenas.append("[%d:v]trim=start=%.3f:end=%.3f,setpts=PTS-STARTPTS[v%d]"
                       % (n, s["ini"], s["fin"], i))
        if voz_path:
            # con voz en off el audio de los clips no se usa para nada: ni se
            # construye, o ffmpeg se queja de una salida sin conectar
            pares.append("[v%d]" % i)
            continue
        if con_audio.get(rutas[n]):
            cadenas.append(
                "[%d:a]atrim=start=%.3f:end=%.3f,asetpts=PTS-STARTPTS%s[a%d]"
                % (n, s["ini"], s["fin"], fade, i))
        else:
            # un clip mudo aporta silencio de su misma duracion; si no, el
            # concat de audio se desalinea del video
            cadenas.append("anullsrc=r=44100:cl=stereo,atrim=end=%.3f,"
                           "asetpts=PTS-STARTPTS[a%d]" % (dur, i))
        pares.append("[v%d][a%d]" % (i, i))

    if voz_path:
        filtro = ";".join(cadenas) + (";%sconcat=n=%d:v=1:a=0[vcat]"
                                      % ("".join(pares), len(segmentos)))
        # la voz en off manda: sustituye al audio de los clips, que van mudos
        filtro += ";[%d:a]asetpts=PTS-STARTPTS[avoz]" % len(rutas)
        ultima = "[avoz]"
    else:
        filtro = ";".join(cadenas) + (";%sconcat=n=%d:v=1:a=1[vcat][acat]"
                                      % ("".join(pares), len(segmentos)))
        ultima = "[acat]"
    if normalizar:
        filtro += ";%sloudnorm=I=-14:TP=-1.5:LRA=11[aout]" % ultima
        mapa_a = "[aout]"
    else:
        mapa_a = ultima

    cmd = ["ffmpeg", "-v", "error", "-y"]
    for r in rutas:
        cmd += ["-i", r]
    if voz_path:
        cmd += ["-i", os.path.abspath(voz_path)]
    cmd += [
        "-filter_complex", filtro,
        "-map", "[vcat]", "-map", mapa_a,
        "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        salida,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg fallo:\n" + (r.stderr or "").strip()[-1500:])
    return os.path.getsize(salida)


def renderizar(video_path, keeps, salida, crf=18, normalizar=True):
    """Corta y concatena los tramos `keeps` [(ini, fin)] en un solo MP4."""
    if not keeps:
        raise ValueError("No hay tramos que renderizar")

    partes_v, partes_a, cadenas = [], [], []
    for i, (ini, fin) in enumerate(keeps):
        cadenas.append(
            "[0:v]trim=start=%.3f:end=%.3f,setpts=PTS-STARTPTS[v%d];"
            "[0:a]atrim=start=%.3f:end=%.3f,asetpts=PTS-STARTPTS[a%d]"
            % (ini, fin, i, ini, fin, i))
        partes_v.append("[v%d]" % i)
        partes_a.append("[a%d]" % i)

    entradas = "".join(v + a for v, a in zip(partes_v, partes_a))
    filtro = ";".join(cadenas) + (";%sconcat=n=%d:v=1:a=1[vcat][acat]"
                                  % (entradas, len(keeps)))
    if normalizar:
        filtro += ";[acat]loudnorm=I=-14:TP=-1.5:LRA=11[aout]"
        mapa_a = "[aout]"
    else:
        mapa_a = "[acat]"

    cmd = [
        "ffmpeg", "-v", "error", "-y",
        "-i", video_path,
        "-filter_complex", filtro,
        "-map", "[vcat]", "-map", mapa_a,
        "-c:v", "libx264", "-crf", str(crf), "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        salida,
    ]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg fallo:\n" + (r.stderr or "").strip()[-1500:])
    return os.path.getsize(salida)
