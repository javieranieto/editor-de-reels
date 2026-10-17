"""Transcripcion con timestamps por palabra usando faster-whisper."""
import json
import os
import sys

_CACHE = {}

# Sube este numero cuando cambie COMO se producen las palabras: invalida las
# caches viejas para que no se arrastre el formato anterior.
FORMATO_CACHE = 2


def _habilitar_dlls_cuda():
    """Anade las DLL de CUDA instaladas via pip al buscador de librerias de Windows.

    faster-whisper necesita cuBLAS y cuDNN. Si se instalaron con
    'pip install nvidia-cublas-cu12 nvidia-cudnn-cu12' no quedan en el PATH,
    asi que hay que registrarlas a mano o la GPU falla al ejecutar (no al cargar).
    """
    if sys.platform != "win32":
        return
    try:
        import nvidia
    except ImportError:
        return
    # 'nvidia' es un paquete de espacio de nombres: no tiene __file__, solo __path__
    for base in list(getattr(nvidia, "__path__", [])):
        for sub in ("cublas", "cudnn"):
            d = os.path.join(base, sub, "bin")
            if os.path.isdir(d):
                try:
                    os.add_dll_directory(d)
                except OSError:
                    pass
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")


def _load(model_size, device):
    from faster_whisper import WhisperModel

    if device == "cuda":
        _habilitar_dlls_cuda()

    clave = (model_size, device)
    if clave in _CACHE:
        return _CACHE[clave]

    ct = "float16" if device == "cuda" else "int8"
    m = WhisperModel(model_size, device=device, compute_type=ct)
    _CACHE[clave] = m
    return m


MAX_ESTIRAR = 0.4   # segundos que un fragmento puede extender la palabra anterior


def fusionar_fragmentos(crudas):
    """Une los fragmentos de continuacion con la palabra a la que pertenecen.

    faster-whisper marca el limite de palabra con un ESPACIO INICIAL. Un token
    sin ese espacio ("%", ".200", "-algo") es continuacion del anterior: sin
    fusionarlo, "44%" acaba partido en dos captions. (Idea de OpenShorts,
    subtitles.py::merge_continuation_words.)

    A diferencia de ellos, el final solo se estira si el fragmento viene
    pegado: whisper a veces le cuelga a un signo de puntuacion un timestamp
    muy posterior, y una palabra de 3 segundos desalinea cortes y captions.
    """
    salida = []
    for c in crudas:
        texto = c.get("crudo") or ""
        if salida and texto and not texto.startswith(" "):
            prev = salida[-1]
            prev["word"] += texto.strip()
            if c["end"] - prev["end"] <= MAX_ESTIRAR:
                prev["end"] = round(c["end"], 3)
            prev["prob"] = min(prev["prob"], round(c["prob"], 3))
        else:
            salida.append({
                "start": round(c["start"], 3),
                "end": round(c["end"], 3),
                "word": texto.strip(),
                "prob": round(c["prob"], 3),
            })
    return salida


def _es_fallo_cuda(err):
    t = str(err).lower()
    return any(s in t for s in ("cublas", "cudnn", "cuda", "dll", "libcu"))


def _ejecutar(model, video_path, language):
    segments, info = model.transcribe(
        video_path,
        language=language,
        word_timestamps=True,
        vad_filter=True,                       # descarta silencio antes de transcribir
        vad_parameters={"min_silence_duration_ms": 300},
        beam_size=5,
        condition_on_previous_text=False,      # evita bucles de repeticion
        temperature=0.0,                       # sin fallback aleatorio: dos corridas
                                               # del mismo clip dan el mismo texto,
                                               # y los planes guardados siguen validos
    )
    # se consume aqui dentro: el generador solo falla al iterarlo, no al crearlo,
    # y necesitamos que el fallo ocurra donde podemos capturarlo.
    return list(segments), info


def transcribe(video_path, cache_path=None, model_size="medium", language="es", device="auto"):
    """Devuelve {'language','words':[{start,end,word}],'text'}. Cachea en disco."""
    if cache_path and os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as f:
            cached = json.load(f)
        # El idioma TAMBIEN es parte de la clave. Sin el, volver a correr el
        # mismo video con otro --idioma devolvia la cache anterior en silencio.
        # Y el idioma equivocado no falla: un video hablado en INGLES
        # transcrito con --idioma es sale TRADUCIDO al espanol, coherente y
        # sin un aviso. Se compara el idioma PEDIDO, no el detectado. Las
        # caches viejas no traen ese campo, asi que para ellas se cae al
        # detectado: no se invalida ninguna (y por eso no hace falta subir
        # FORMATO_CACHE).
        pedido = cached.get("idioma_pedido", cached.get("language"))
        if (cached.get("source") == os.path.abspath(video_path)
                and cached.get("modelo") == model_size
                and cached.get("formato") == FORMATO_CACHE
                and pedido == language):
            print("  transcripcion en cache (%d palabras, %s)"
                  % (len(cached["words"]), pedido))
            return cached

    intentos = ["cuda", "cpu"] if device == "auto" else [device]
    segments = info = None
    for i, dev in enumerate(intentos):
        try:
            model = _load(model_size, dev)
            segments, info = _ejecutar(model, video_path, language)
            print("  modelo '%s' ejecutado en %s" % (model_size, dev))
            break
        except Exception as e:
            ultimo = i == len(intentos) - 1
            if ultimo or not _es_fallo_cuda(e):
                raise
            print("  GPU no disponible (%s); uso CPU" % str(e).strip().splitlines()[0][:70])

    words, texts = [], []
    for seg in segments:
        texts.append(seg.text)
        words.extend(fusionar_fragmentos(
            [{"crudo": w.word, "start": w.start, "end": w.end,
              "prob": w.probability} for w in seg.words or []]))

    result = {
        "source": os.path.abspath(video_path),
        "modelo": model_size,
        "formato": FORMATO_CACHE,
        "language": info.language,
        "idioma_pedido": language,
        "text": "".join(texts).strip(),
        "words": words,
    }
    if cache_path:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=1)
    print("  %d palabras transcritas (%s)" % (len(words), info.language))
    return result
