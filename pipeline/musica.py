"""Analiza musica: tempo, rejilla de beats y si encaja debajo de una voz.

Existe porque el usuario pidio musica "que vaya acorde al video, sincronizar
el beat y todo eso para que este mas pro".

Trabaja sobre la musica de CapCut que ya esta descargada en la maquina
(`Cache/music`). Son de su biblioteca, asi que estan
licenciadas para sus videos. Lo que NO hay es el nombre: se buscaron los
titulos en las nueve bases de datos de CapCut y ninguna los guarda, asi que
las pistas se identifican por su hash y se eligen escuchandolas.

No usa librosa ni scipy a proposito: ffmpeg ya esta y numpy tambien, y todo lo
que hace falta son una FFT y una autocorrelacion.

Lo que se mide de cada pista:

    bpm         tempo, plegado al rango 70-150 donde vive el tempo percibido
    conf        cuanta energia de ataque cae EN la rejilla frente a fuera.
                Por debajo de 0.35 la pista no tiene beat utilizable (pasa con
                las ambientales) y no se debe sincronizar nada contra ella.
    energia     nivel medio; que tan movida es
    brillo      centroide espectral; agudo = electronico, grave = calido
    estorbo     cuanta de su energia cae en la banda de la voz (200-4000 Hz).
                ES EL DATO QUE MAS IMPORTA para este proyecto: la musica va
                DEBAJO de alguien hablando, y una pista con mucho contenido en
                esa banda pelea con la voz por mas que se le baje el volumen.
"""
import json
import os
import re
import subprocess

import numpy as np

SR = 22050          # suficiente para tempo y timbre; decodifica rapido
HOP = 512
FPS = SR / HOP

CACHE_MUSICA = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Cache\music")

CONF_MINIMA = 0.35      # por debajo de esto, la pista no tiene beat usable
DUR_MINIMA = 40.0       # menos que esto es un efecto de sonido, no musica
VOZ_BAJA, VOZ_ALTA = 200.0, 4000.0


def _decodificar(ruta, segundos):
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-i", ruta, "-t", str(segundos),
         "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"],
        capture_output=True)
    return np.frombuffer(r.stdout, dtype=np.float32)


def duracion(ruta):
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", ruta], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def _espectro(x, win=1024):
    """Magnitudes por ventana. Devuelve (frames, bins)."""
    n = 1 + (len(x) - win) // HOP
    if n < 8:
        return np.zeros((0, win // 2 + 1), dtype=np.float32)
    w = np.hanning(win).astype(np.float32)
    trozos = np.lib.stride_tricks.as_strided(
        x, (n, win), (x.strides[0] * HOP, x.strides[0]))
    return np.abs(np.fft.rfft(trozos * w, axis=1))


def _flujo(esp):
    """Flujo espectral positivo, normalizado: donde estan los ataques."""
    f = np.sum(np.maximum(np.diff(esp, axis=0), 0), axis=1)
    return (f - f.mean()) / (f.std() + 1e-9)


def _tempo(f):
    """(bpm, lag en frames, fase en frames, confianza)."""
    ac = np.correlate(f, f, "full")[len(f) - 1:]
    lo, hi = max(2, int(FPS * 60 / 240)), min(len(ac) - 1, int(FPS * 60 / 50))
    if hi <= lo:
        return 0.0, 0, 0, 0.0
    lag = lo + int(np.argmax(ac[lo:hi]))
    bpm = 60.0 * FPS / lag
    # La autocorrelacion pica igual de fuerte en el doble y el cuadruple del
    # tempo real. Se pliega al rango que la gente percibe como "el" tempo.
    while bpm > 150:
        bpm /= 2
    while bpm < 70:
        bpm *= 2
    lag = max(2, int(round(60.0 * FPS / bpm)))

    mejor, fase = -1e18, 0
    for p in range(lag):
        s = f[np.arange(p, len(f), lag)].sum()
        if s > mejor:
            mejor, fase = s, p

    # El ataque casi nunca cae exacto en el frame del beat: se toma el maximo
    # en +-1 frame. Sin esa ventana la confianza sale por los suelos hasta en
    # pistas con bombo evidente (medido: 0.06 -> 0.22, y 0.16 -> 0.49).
    idx = np.arange(fase, len(f) - 1, lag)
    idx = idx[idx >= 1]
    if len(idx) < 4:
        return bpm, lag, fase, 0.0
    dentro = np.maximum(np.maximum(f[idx - 1], f[idx]), f[idx + 1]).mean()
    fuera_idx = np.setdiff1d(np.arange(1, len(f) - 1),
                             np.concatenate([idx - 1, idx, idx + 1]))
    fuera = f[fuera_idx].mean() if len(fuera_idx) else 0.0
    return bpm, lag, fase, float(dentro - fuera)


def analizar(ruta, segundos=60):
    """Todo lo medible de una pista. None si no se pudo leer."""
    x = _decodificar(ruta, segundos)
    if len(x) < SR * 3:
        return None
    esp = _espectro(x)
    if not len(esp):
        return None
    f = _flujo(esp)
    bpm, lag, fase, conf = _tempo(f)

    frecs = np.fft.rfftfreq(1024, 1.0 / SR)
    medio = esp.mean(axis=0)
    total = medio.sum() + 1e-9
    banda = (frecs >= VOZ_BAJA) & (frecs <= VOZ_ALTA)
    return {
        "bpm": round(bpm, 1),
        "conf": round(conf, 2),
        "lag": lag,
        "fase": fase,
        "energia": round(float(np.sqrt(np.mean(x ** 2))), 4),
        "brillo": round(float((medio * frecs).sum() / total), 1),
        "estorbo": round(float(medio[banda].sum() / total), 3),
        "con_beat": conf >= CONF_MINIMA,
    }


def rejilla(info, hasta):
    """Tiempos de los beats hasta `hasta` segundos, desde un analisis."""
    if not info or not info.get("lag"):
        return []
    paso = info["lag"] / FPS
    t0 = info["fase"] / FPS
    n = int((hasta - t0) / paso) + 1
    return [round(t0 + i * paso, 3) for i in range(max(0, n))]


def pegar_tramos(tramos, beats, tolerancia=0.20, hueco=0.05):
    """Pega el ARRANQUE de cada tramo (ini, fin) al beat, sin solaparlos.

    Mover solo los arranques crea choques: al pegar una cifra 95 ms mas tarde
    su final se metio 10 ms dentro de la siguiente y la generacion entera
    reventaba. Aqui el final se recorta para dejar `hueco` antes del siguiente.
    """
    inis, _ = pegar_al_beat([t[0] for t in tramos], beats, tolerancia)
    fuera = []
    for i, (ini_viejo, fin_viejo) in enumerate(tramos):
        ini = inis[i]
        fin = fin_viejo + (ini - ini_viejo)      # conserva la duracion
        if i + 1 < len(tramos) and fin > inis[i + 1] - hueco:
            fin = inis[i + 1] - hueco
        if fin - ini < 0.2:                      # quedaria invisible: no se mueve
            ini, fin = ini_viejo, fin_viejo
        fuera.append((round(ini, 3), round(fin, 3)))
    return fuera


def pegar_al_beat(tiempos, beats, tolerancia=0.20):
    """Mueve cada tiempo al beat mas cercano, si esta dentro de la tolerancia.

    La tolerancia existe para no arrastrar un acento a un golpe que queda
    lejos: si el efecto cae a medio compas, moverlo medio segundo lo despega
    de la frase que subrayaba, que es peor que no cuadrarlo.
    """
    if not beats:
        return list(tiempos), 0
    arr = np.asarray(beats)
    fuera = []
    movidos = 0
    for t in tiempos:
        i = int(np.argmin(np.abs(arr - t)))
        if abs(arr[i] - t) <= tolerancia:
            fuera.append(float(arr[i]))
            if abs(arr[i] - t) > 1e-6:
                movidos += 1
        else:
            fuera.append(float(t))
    return fuera, movidos


# ------------------------------------------------------------- biblioteca


AUDIO = (".mp3", ".m4a", ".wav", ".aac", ".flac", ".ogg")


def pistas_locales(carpeta=None, recursivo=False):
    """Archivos de audio de una carpeta. Recursivo para packs con subcarpetas."""
    carpeta = carpeta or CACHE_MUSICA
    if not os.path.isdir(carpeta):
        return []
    if not recursivo:
        return sorted(os.path.join(carpeta, f) for f in os.listdir(carpeta)
                      if f.lower().endswith(AUDIO))
    salida = []
    for raiz, _, archivos in os.walk(carpeta):
        for f in archivos:
            # los "._algo" son basura de macOS: no son audio aunque lo parezcan
            if f.lower().endswith(AUDIO) and not f.startswith("._"):
                salida.append(os.path.join(raiz, f))
    return sorted(salida)


def nivel_medio(ruta, desde=5, dur=25, sin_video=False):
    """Nivel medio en dB segun ffmpeg, o None.

    Ojo: volumedetect escribe en el nivel `info`, asi que NO se puede pasar
    `-v error` o la medicion sale vacia sin dar error (perdido un rato ahi).
    """
    cmd = ["ffmpeg", "-nostdin", "-ss", str(desde), "-t", str(dur), "-i", ruta]
    if sin_video:
        cmd.append("-vn")
    cmd += ["-af", "volumedetect", "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    for linea in (r.stderr or "").splitlines():
        if "mean_volume" in linea:
            try:
                return float(linea.split(":")[-1].replace("dB", "").strip())
            except ValueError:
                return None
    return None


DEBAJO_DE_LA_VOZ = 18.0     # dB; a menos se pelea con el habla, a mas no se oye


def sonoridad(ruta):
    """Sonoridad integrada (LUFS) via loudnorm. None si no se pudo medir.

    A diferencia del nivel medio, LUFS **descarta los silencios**: es lo que
    hace falta para comparar voz contra musica, porque la voz calla entre
    palabras y la musica no.
    """
    try:
        # `encoding` explicito, como en `nivel_medio`: sin el, Python decodifica
        # la salida de ffmpeg con la cp1252 de la consola y un solo byte raro
        # -el titulo del mp3, un acento en la ruta- lanza UnicodeDecodeError.
        # Aqui lo tragaba el `except` y la medicion volvia como None, o sea que
        # `volumen_bajo_voz` devolvia su valor POR DEFECTO haciendolo pasar por
        # medido. Le paso a una pista cuyo nombre llevaba un emoji.
        r = subprocess.run(
            ["ffmpeg", "-hide_banner", "-i", ruta, "-af",
             "loudnorm=I=-24:print_format=json", "-f", "null", "-"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        m = re.search(r'"input_i"\s*:\s*"(-?[\d.]+)"', r.stderr)
        return float(m.group(1)) if m else None
    except Exception:
        return None


def volumen_bajo_voz(pista, voz, debajo=DEBAJO_DE_LA_VOZ, por_defecto=0.10,
                     metodo="medio", log=None):
    """Volumen (0-1) para que la musica quede N dB debajo de la voz.

    Se mide en vez de suponerse: en el caso real la pista estaba 4 dB MAS
    fuerte que la voz, asi que un 0.25 "razonable" la habria dejado casi
    encima. Medido dio 0.079.

    ⚠️ `metodo="medio"` compara PROMEDIOS, y eso solo funciona cuando la voz
    viene cortada al ras -o sea, en un reel-. En una charla larga los
    silencios entre frases hunden el promedio de la voz (medido: -32.9 dB de
    promedio contra -30.1 LUFS) y la musica sale inaudible. Se queda de
    momento como valor por defecto porque es con lo que se aprobo la musica
    de los reels y no se toca lo aprobado.

    `metodo="lufs"` es el correcto para material con pausas.
    """
    if metodo == "lufs":
        nv, nm = sonoridad(voz), sonoridad(pista)
    else:
        nv, nm = nivel_medio(voz, sin_video=True), nivel_medio(pista)
    if nv is None or nm is None:
        # El valor por defecto se DEVUELVE, pero se dice. Un numero que no se
        # midio y viaja como si se hubiera medido es peor que un error: se
        # publica un volumen puesto a ojo creyendo que esta calculado.
        if log:
            log("  aviso: no se pudo medir %s; se usa el volumen por defecto "
                "(%.3f), NO medido" %
                ('la voz' if nv is None else 'la pista', por_defecto))
        return por_defecto
    ganancia = (nv - debajo) - nm
    return round(min(1.0, max(0.001, 10 ** (ganancia / 20.0))), 4)


def cargar_indice(ruta):
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    return {}


def guardar_indice(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
