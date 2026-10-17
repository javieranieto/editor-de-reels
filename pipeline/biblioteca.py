"""Biblioteca de efectos y transiciones aprendida de los proyectos del usuario.

pycapcut solo conoce el catalogo de la version de CapCut para la que se
escribio: "Holographic Scan" (id 7604783367015681285), por ejemplo, no esta.
Y la cache de recursos guarda 1281 efectos descargados pero con nombres
internos ilegibles, asi que tampoco sirve de catalogo.

La via que si funciona: el usuario aplica los efectos que le gustan en un
proyecto de CapCut, y de ahi se leen sus materiales COMPLETOS (nombre,
resource_id, ruta local, parametros). Con eso se pueden escribir despues en
cualquier proyecto, aunque pycapcut no los conozca.

    python tools/biblioteca.py            # escanea y muestra lo que hay
    python tools/biblioteca.py --guardar  # lo deja en recursos/biblioteca.json
"""
import copy
import glob
import json
import os
import uuid

DRAFTS = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
ARCHIVO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "recursos", "biblioteca.json")


def _drafts():
    return (glob.glob(os.path.join(DRAFTS, "*", "draft_content.json"))
            + glob.glob(os.path.join(DRAFTS, ".recycle_bin", "*", "draft_content.json")))


def escanear(rutas=None):
    """{'efectos', 'transiciones', 'voz': {nombre: material}}.

    Se queda con el material tal cual lo escribio CapCut: es la unica forma de
    reproducirlo con fidelidad, incluidos los campos que no documenta nadie.

    Los de VOZ (`audio_effects`) se guardan tambien: un acento puede no ser
    UN efecto sino DOS -uno en la imagen ("B&W VHS") y otro en la voz
    ("Phonograph"), sobre el mismo segmento-, y guardando solo el visual
    salia a medias: la imagen cambiaba y la voz no.
    """
    efectos, transiciones, voz = {}, {}, {}
    for f in rutas or _drafts():
        try:
            with open(f, encoding="utf-8") as fh:
                d = json.load(fh)
        except Exception:
            continue
        mats = d.get("materials") or {}
        for e in mats.get("video_effects") or []:
            nombre = (e.get("name") or "").strip()
            if nombre and nombre not in efectos and e.get("path"):
                efectos[nombre] = e
        for t in mats.get("transitions") or []:
            nombre = (t.get("name") or "").strip()
            if nombre and nombre not in transiciones and t.get("path"):
                transiciones[nombre] = t
        for a in mats.get("audio_effects") or []:
            nombre = (a.get("name") or "").strip()
            if nombre and nombre not in voz:
                voz[nombre] = a
    return {"efectos": efectos, "transiciones": transiciones, "voz": voz}


# La cache de CapCut vive bajo %LOCALAPPDATA%, que cambia con cada usuario y
# cada maquina. Se guarda con un marcador para que la biblioteca se pueda
# compartir por el repositorio y siga funcionando en la computadora de otro:
# si esa persona tiene el mismo efecto descargado, le funciona igual.
MARCA = "@LOCALAPPDATA@"
BASE_LOCAL = os.environ.get("LOCALAPPDATA", "").replace("\\", "/")


def _portable(texto):
    if BASE_LOCAL and texto:
        return texto.replace(BASE_LOCAL, MARCA).replace(
            BASE_LOCAL.replace("/", "\\"), MARCA)
    return texto


def _local(texto):
    return texto.replace(MARCA, BASE_LOCAL) if texto else texto


def guardar(datos=None, ruta=None):
    datos = datos or escanear()
    ruta = ruta or ARCHIVO
    portable = {"efectos": {}, "transiciones": {}}
    for grupo in portable:
        for nombre, mat in (datos.get(grupo) or {}).items():
            copia = copy.deepcopy(mat)
            copia["path"] = _portable(copia.get("path", ""))
            portable[grupo][nombre] = copia
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(portable, f, ensure_ascii=False, indent=1)
    return ruta


def cargar(ruta=None):
    ruta = ruta or ARCHIVO
    if not os.path.exists(ruta):
        return {"efectos": {}, "transiciones": {}}
    with open(ruta, encoding="utf-8") as f:
        datos = json.load(f)
    for grupo in ("efectos", "transiciones"):
        for mat in (datos.get(grupo) or {}).values():
            mat["path"] = _local(mat.get("path", ""))
    return datos


def usable(material):
    """True si el recurso sigue descargado; si no, CapCut descartaria la pista."""
    ruta = material.get("path") or ""
    return bool(ruta) and os.path.exists(ruta)


def _nuevo_id():
    return uuid.uuid4().hex


def clonar(material):
    """Copia del material con id propio, lista para meter en otro proyecto."""
    nuevo = copy.deepcopy(material)
    nuevo["id"] = _nuevo_id()
    return nuevo


# --- escritura directa sobre un draft ya guardado -------------------------

def inyectar(carpeta, efectos=None, transiciones=None, biblioteca=None):
    """Anade efectos y transiciones de la biblioteca a un draft ya escrito.

    Va por post-proceso a proposito: asi funciona con cualquier efecto que el
    usuario tenga, sin depender de que pycapcut lo conozca.

    efectos      : [{"nombre", "ini", "dur"}]  segundos de la linea de tiempo
    transiciones : [{"nombre", "corte", "dur"}] corte = indice del clip tras el
                   cual va la transicion
    """
    ruta = os.path.join(carpeta, "draft_content.json")
    if not os.path.exists(ruta) or not (efectos or transiciones):
        return {"efectos": 0, "transiciones": 0}

    bib = biblioteca or cargar()
    with open(ruta, encoding="utf-8") as f:
        d = json.load(f)
    US = 1_000_000
    puestos = {"efectos": 0, "transiciones": 0}

    # --- efectos: material + pista propia
    pendientes = []
    for e in efectos or []:
        base = bib.get("efectos", {}).get(e.get("nombre"))
        if not (base and usable(base)):
            continue
        mat = clonar(base)
        d.setdefault("materials", {}).setdefault("video_effects", []).append(mat)
        pendientes.append((mat["id"], e))
    if pendientes:
        pista = _pista_efectos(d)
        for mid, e in pendientes:
            ini = int(round(float(e.get("ini", 0)) * US))
            dur = int(round(float(e.get("dur", 1.0)) * US))
            dur = min(dur, max(0, d.get("duration", 0) - ini))
            if dur < 100_000:
                continue
            pista["segments"].append(_segmento_efecto(mid, ini, dur))
            puestos["efectos"] += 1

    # --- transiciones: material + referencia en el clip que la precede
    principal = _pista_principal(d)
    for t in transiciones or []:
        base = bib.get("transiciones", {}).get(t.get("nombre"))
        if not (base and usable(base) and principal):
            continue
        idx = int(t.get("corte", -1))
        if not (0 <= idx < len(principal["segments"])):
            continue
        mat = clonar(base)
        if t.get("dur"):
            mat["duration"] = int(round(float(t["dur"]) * US))
        d["materials"].setdefault("transitions", []).append(mat)
        seg = principal["segments"][idx]
        seg.setdefault("extra_material_refs", []).append(mat["id"])
        puestos["transiciones"] += 1

    with open(ruta, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False)
    return puestos


def _pista_principal(d):
    for t in d.get("tracks", []):
        if t.get("type") == "video" and t.get("name") in (None, "", "video"):
            return t
    return None


def _pista_efectos(d):
    for t in d.get("tracks", []):
        if t.get("type") == "effect":
            return t
    pista = {"attribute": 0, "flag": 0, "id": _nuevo_id().upper(),
             "is_default_name": True, "name": "efectos", "segments": [],
             "type": "effect"}
    d.setdefault("tracks", []).append(pista)
    return pista


def _segmento_efecto(material_id, ini_us, dur_us):
    return {
        "caption_info": None, "cartoon": False, "clip": None,
        "color_correct_alg_result": "", "common_keyframes": [],
        "desc": "", "digital_human_template_group_id": "",
        "enable_adjust": False, "enable_adjust_mask": False,
        "enable_color_correct_adjust": False, "enable_color_curves": True,
        "enable_color_match_adjust": False, "enable_color_wheels": True,
        "enable_hsl": False, "enable_lut": False, "enable_smart_color_adjust": False,
        "enable_video_mask": True, "extra_material_refs": [],
        "group_id": "", "hdr_settings": None, "id": _nuevo_id().upper(),
        "intensifies_audio": False, "is_loop": False, "is_placeholder": False,
        "is_tone_modify": False, "keyframe_refs": [], "last_nonzero_volume": 1.0,
        "lyric_keyframes": None, "material_id": material_id, "raw_segment_id": "",
        "render_index": 11000, "render_timerange": {"duration": 0, "start": 0},
        "responsive_layout": {"enable": False, "horizontal_pos_layout": 0,
                              "size_layout": 0, "target_follow": "",
                              "vertical_pos_layout": 0},
        "reverse": False, "source_timerange": None, "speed": 1.0, "state": 0,
        "target_timerange": {"duration": dur_us, "start": ini_us},
        "template_id": "", "template_scene": "default", "track_attribute": 0,
        "track_render_index": 0, "uniform_scale": None, "visible": True,
        "volume": 1.0,
    }
