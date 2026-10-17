"""Lectura de metadatos de video con ffprobe."""
import json, subprocess


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_format", "-show_streams", path],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe fallo en {path}:\n{out.stderr.strip()}")
    d = json.loads(out.stdout)

    video = next((s for s in d["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    if video is None:
        raise RuntimeError(f"{path} no contiene pista de video")

    num, den = (video.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den or 1)

    # La rotacion en metadatos hace que ancho/alto reales esten invertidos.
    rotation = 0
    for sd in video.get("side_data_list") or []:
        if "rotation" in sd:
            rotation = abs(int(sd["rotation"])) % 360
    w, h = int(video["width"]), int(video["height"])
    if rotation in (90, 270):
        w, h = h, w

    return {
        "path": path,
        "duration": float(d["format"]["duration"]),
        "width": w,
        "height": h,
        "fps": round(fps, 3),
        "has_audio": audio is not None,
        "codec": video.get("codec_name"),
    }
