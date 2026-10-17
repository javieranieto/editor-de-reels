"""Empaqueta un proyecto de CapCut para que otra persona lo abra en su computadora.

Un draft guarda RUTAS ABSOLUTAS de todo (video, b-roll, sonidos, recursos de
efectos). En otra maquina ninguna existe, asi que CapCut abre el proyecto vacio
o pidiendo relocalizar. Esto copia los medios junto al proyecto y deja un
instalador que reescribe las rutas en la computadora de destino.

Uso:
    python tools/exportar.py "<proyecto>" [destino] [--comprimir]

    --comprimir  reencoda el video fuente a 1440x2560 (mucho mas ligero para
                 mandar por Drive; sobra para entregar en 1080x1920)
"""
import json
import os
import shutil
import subprocess
import sys

RAIZ = os.path.expandvars(
    r"%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft")
CACHE = os.path.expandvars(r"%LOCALAPPDATA%\CapCut\User Data\Cache")


def medios_de(draft):
    """Rutas de archivo que el proyecto necesita, por tipo."""
    fuera = {"medios": set(), "cache": set(), "fuentes": set()}
    mats = draft.get("materials") or {}
    for clave in ("videos", "audios"):
        for m in mats.get(clave) or []:
            p = m.get("path")
            if p and not p.startswith("##"):
                fuera["medios"].add(p)
    for clave in ("video_effects", "transitions", "effects"):
        for m in mats.get(clave) or []:
            p = m.get("path")
            if p and CACHE.replace("\\", "/").lower() in p.replace("\\", "/").lower():
                fuera["cache"].add(p)
    # Las animaciones de texto (el rebote y el barrido de las cifras) tambien
    # son recursos de la cache y NO estaban entrando: en la computadora de
    # ella el callout salia sin animar y sin decir por que.
    for ma in mats.get("material_animations") or []:
        for a in ma.get("animations") or []:
            p = a.get("path")
            if p and CACHE.replace("\\", "/").lower() in p.replace("\\", "/").lower():
                fuera["cache"].add(p)
    # Las fuentes vienen por dos vias distintas y hay que cubrir las dos:
    #   - las de serie viven en Apps/<version>/Resources/Font, y la version
    #     cambia en cada computadora, asi que se resuelven en destino
    #   - las DESCARGADAS (Anton) viven en la cache, con un id de carpeta
    #     propio de cada maquina. Esas se copian como archivo al paquete: son
    #     un .ttf y viajan. Antes no entraban por ningun lado y el proyecto
    #     llegaba dibujando la fuente por defecto, sin avisar.
    def _mirar_fuente(f):
        if not f:
            return
        n = f.replace("\\", "/")
        if "/Resources/Font/" in n:
            fuera["fuentes"].add(f)
        elif CACHE.replace("\\", "/").lower() in n.lower():
            fuera["medios"].add(f)

    import json as _json
    for t in mats.get("texts") or []:
        _mirar_fuente(t.get("font_path"))
        try:
            cont = _json.loads(t.get("content") or "{}")
            for est in cont.get("styles") or []:
                _mirar_fuente((est.get("font") or {}).get("path"))
        except Exception:
            pass
    return fuera


# Lo unico que define el proyecto. Todo lo demas que hay en la carpeta de un
# draft lo genera CapCut al abrirlo.
ESENCIALES = ("draft_content.json", "draft_meta_info.json", "draft_cover.jpg")


def _copiar_proyecto(origen, destino):
    """Copia SOLO lo que define el proyecto, no lo que CapCut genera al abrirlo.

    Copiar la carpeta entera parecia lo seguro y era justo el fallo: un draft
    que CapCut ya abrio guarda copias de la linea de tiempo en `Timelines/`,
    `draft_content.json.bak` y `template-2.tmp`, y todas llevan las rutas de la
    computadora de origen. El instalador reescribia solo los dos JSON, asi que
    esas copias seguian apuntando aca y CapCut decia "no tengo los archivos
    multimedia" -- medidas: 1393 rutas al origen en un paquete ya enviado.

    Un draft con solo estos archivos abre perfecto: es exactamente lo que
    genera el pipeline antes de que CapCut lo toque (regla dura 9).
    """
    os.makedirs(destino, exist_ok=True)
    copiados = []
    for nombre in ESENCIALES:
        ruta = os.path.join(origen, nombre)
        if os.path.isfile(ruta):
            shutil.copy2(ruta, os.path.join(destino, nombre))
            copiados.append(nombre)
    if "draft_content.json" not in copiados:
        raise SystemExit("El proyecto no tiene draft_content.json:\n  %s" % origen)
    return copiados


def comprimir(origen, destino, alto=2560):
    """Reencoda manteniendo proporcion. Devuelve True si funciono."""
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", origen,
         "-vf", "scale=-2:%d" % alto, "-c:v", "libx264", "-crf", "21",
         "-preset", "fast", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", destino],
        capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0 and os.path.exists(destino)


def exportar(nombre, destino=None, comprimir_video=False, log=print):
    origen = os.path.join(RAIZ, nombre)
    ruta_json = os.path.join(origen, "draft_content.json")
    if not os.path.exists(ruta_json):
        raise SystemExit("No encuentro el proyecto '%s' en CapCut" % nombre)

    destino = destino or os.path.join(os.path.expanduser("~"), "Desktop")
    final = os.path.join(destino, "%s - para editar" % nombre)

    # Se arma en una carpeta aparte y se renombra al final. Si no, la carpeta
    # buena aparece vacia desde el primer segundo y se va llenando durante
    # minutos: el usuario la comprimio y la mando a medias sin darse cuenta.
    paquete = os.path.join(destino, "~preparando %s" % nombre)
    medios = os.path.join(paquete, "medios")
    proyecto = os.path.join(paquete, "proyecto")
    if os.path.exists(paquete):
        try:
            shutil.rmtree(paquete)   # resto de un intento anterior
        except PermissionError:
            # tipico si un export anterior se corto a medias y dejo un ffmpeg
            # con el archivo abierto
            raise SystemExit(
                "No pude borrar el paquete anterior porque algo lo tiene abierto:\n"
                "  %s\n"
                "Cierra el explorador o cualquier reproductor sobre esa carpeta,\n"
                "y si un export previo se interrumpio, revisa que no quede ffmpeg\n"
                "corriendo (Administrador de tareas)." % paquete)
    os.makedirs(medios)

    _copiar_proyecto(origen, proyecto)
    with open(ruta_json, encoding="utf-8") as f:
        draft = json.load(f)

    usados = medios_de(draft)
    mapa = {}
    total = 0

    for p in sorted(usados["medios"]):
        if not os.path.isfile(p):
            log("  falta (se ignora): %s" % os.path.basename(p))
            continue
        base = os.path.basename(p)
        salida = os.path.join(medios, base)
        pesado = os.path.getsize(p) > 300 * 1024 * 1024
        if comprimir_video and pesado and base.lower().endswith((".mp4", ".mov", ".mkv")):
            log("  comprimiendo %s (%.0f MB)..." % (base, os.path.getsize(p) / 1e6))
            if not comprimir(p, salida):
                shutil.copy2(p, salida)
        else:
            shutil.copy2(p, salida)
        total += os.path.getsize(salida)
        mapa[p] = "@@MEDIOS@@/" + base
        log("  %-42s %7.1f MB" % (base[:42], os.path.getsize(salida) / 1e6))

    # los recursos de efectos viven en la cache de CapCut de cada quien:
    # se reescribe solo el prefijo, para que apunte a la cache de ELLA
    for p in sorted(usados["cache"]):
        rel = p.replace("\\", "/")
        idx = rel.lower().find("/user data/cache/")
        if idx > 0:
            mapa[p] = "@@CAPCUT@@" + rel[idx:]

    for p in sorted(usados["fuentes"]):
        mapa[p] = "@@FUENTES@@/" + os.path.basename(p.replace("\\", "/"))

    # los archivos de plomeria van a _sistema/ para que arriba solo se vean
    # los dos botones y el LEEME: quien recibe el paquete no es tecnico
    os.makedirs(os.path.join(paquete, "_sistema"), exist_ok=True)
    with open(os.path.join(paquete, "_sistema", "rutas.json"), "w",
              encoding="utf-8") as f:
        json.dump(mapa, f, ensure_ascii=False, indent=1)

    with open(os.path.join(paquete, "_sistema", "recursos.json"), "w",
              encoding="utf-8") as f:
        json.dump(recursos_con_id(draft), f, ensure_ascii=False, indent=1)

    _escribir_instalador(paquete, nombre)
    _escribir_devolucion(paquete, nombre)
    _escribir_leeme_recursos(paquete, draft)

    # Un paquete al que le falte un boton deja a la otra persona a medias y no
    # se nota hasta que ya se mando. Paso de verdad: la llamada a
    # _escribir_devolucion se perdio en un merge y el paquete salio sin el
    # boton de devolver.
    faltan = [f for f in ("1 - LEEME.txt", "2 - ABRIR EN CAPCUT.bat",
                          "3 - DEVOLVER YA EDITADO.bat", "medios", "proyecto")
              if not os.path.exists(os.path.join(paquete, f))]
    if faltan:
        raise SystemExit("El paquete quedo incompleto, falta: %s" % ", ".join(faltan))

    # ya esta completo: recien ahora aparece con su nombre definitivo
    if os.path.exists(final):
        shutil.rmtree(final)
    os.rename(paquete, final)

    log("\nPaquete: %s" % final)
    log("Medios: %.0f MB" % (total / 1e6))
    for linea in recursos_que_necesita(draft):
        log(linea)
    return final


# Los nombres internos de algunas animaciones estan en chino y no le dicen nada
# a quien recibe el paquete.
LEGIBLES = {
    "弹入": "entrada con rebote",
    "Wiping Out": "salida por barrido",
}


def recursos_con_id(draft):
    """Lo que ella tiene que tener descargado, con cómo comprobarlo.

    Cada entrada trae `ruta` (relativa a la cache) y `hash` (la hoja), para que
    el instalador pueda MIRAR en su cache si lo tiene, en vez de que se entere
    cuando la pista no se ve.

    No basta con el resource_id: el mismo recurso vive bajo un id de CARPETA
    distinto en cada computadora — la transicion White Flash esta en 231313341
    aqui y su effect_id es 7345079500327096833. Lo estable es el hash de la
    hoja, igual que ya se descubrio en `importar.py`. Comprobar por id decia
    "te falta" sobre un efecto que SI estaba.
    """
    mats = draft.get("materials") or {}
    fuera, vistos = [], set()
    marca = "/user data/cache/"

    def sumar(nombre, rid, ruta):
        if not nombre or rid in vistos:
            return
        vistos.add(rid)
        n = (ruta or "").replace("\\", "/")
        idx = n.lower().find(marca)
        fuera.append({
            "nombre": nombre,
            "legible": LEGIBLES.get(nombre, ""),
            "ruta": n[idx + len(marca):] if idx > 0 else "",
            "hash": n.rstrip("/").split("/")[-1] if n else "",
        })

    for clave in ("video_effects", "transitions"):
        for m in mats.get(clave) or []:
            sumar(m.get("name"), m.get("effect_id") or m.get("resource_id"),
                  m.get("path"))
    for ma in mats.get("material_animations") or []:
        for a in ma.get("animations") or []:
            if a.get("path"):
                sumar(a.get("name"), a.get("resource_id"), a.get("path"))
    return fuera


def _es_vip(nombre):
    """True si ese efecto o transicion requiere CapCut Pro.

    Idea tomada de claude-capcut-skill (mane23-ai, references/known-issues.md),
    que lista "Pro-only feature" como una de sus cinco causas de fallo. Aqui
    muerde mas fuerte: el usuario tiene Pro y no lo nota, pero quien recibe el
    paquete puede no tenerlo, y entonces no le basta con descargar el recurso
    -- no puede. Sin esto, el aviso dice "descargalo" sobre algo que ella no
    va a poder descargar nunca, y el fallo sigue siendo silencioso.

    pycapcut trae el dato en la metadata (is_vip). Si no se puede consultar se
    devuelve False: mejor no avisar que avisar de mas.
    """
    try:
        import pycapcut as cc
    except Exception:
        return False
    for grupo in (getattr(cc, "VideoSceneEffectType", None),
                  getattr(cc, "TransitionType", None),
                  getattr(cc, "TextIntro", None), getattr(cc, "TextOutro", None)):
        if grupo is None:
            continue
        for attr in dir(grupo):
            if attr.startswith("_"):
                continue
            meta = getattr(getattr(grupo, attr), "value", None)
            if getattr(meta, "name", None) == nombre:
                return bool(getattr(meta, "is_vip", False))
    return False


def recursos_que_necesita(draft):
    """Lo que NO se puede meter en el paquete y ella tiene que tener.

    Los efectos, transiciones y animaciones de texto son recursos de la
    biblioteca de CapCut: viven como paquetes de shaders en su cache y no
    sirven copiados a otra maquina. El instalador reapunta la ruta a la cache
    de ella, pero si no los tiene, CapCut **descarta la pista sin avisar**.

    Por eso se listan por nombre al terminar: es la unica forma de que se
    pueda avisar antes de mandar el paquete, en vez de descubrirlo cuando ella
    ya abrio el proyecto y algo no se ve.
    """
    mats = draft.get("materials") or {}
    nombres = []
    for clave in ("video_effects", "transitions"):
        for m in mats.get(clave) or []:
            if m.get("name"):
                nombres.append((clave, m["name"]))
    for ma in mats.get("material_animations") or []:
        for a in ma.get("animations") or []:
            if a.get("name") and a.get("path"):
                nombres.append(("animacion de texto", a["name"]))
    vistos, unicos = set(), []
    for tipo, n in nombres:
        if (tipo, n) not in vistos:
            vistos.add((tipo, n))
            unicos.append((tipo, n))
    if not unicos:
        return []
    salida = ["", "Esto NO viaja en el paquete: son recursos de la biblioteca",
              "de CapCut y ella tiene que tenerlos descargados.",
              "Si le falta alguno, esa pista no se vera y CapCut no avisa:"]
    vips = []
    for tipo, n in unicos:
        legible = LEGIBLES.get(n)
        vip = _es_vip(n)
        if vip:
            vips.append(n)
        salida.append("   %-20s %s%s%s"
                      % (tipo, n, "  (%s)" % legible if legible else "",
                         "   [requiere CapCut Pro]" if vip else ""))
    salida.append("")
    salida.append("Que los descargue: basta con aplicarlos una vez a mano en")
    salida.append("cualquier proyecto suyo, antes de abrir este.")
    if vips:
        salida.append("")
        salida.append("OJO: %d de ellos son de CapCut Pro. Con la version gratis"
                      % len(vips))
        salida.append("no le aparecen, asi que no es cuestion de descargarlos.")
        salida.append("Si ella no tiene Pro, hay que cambiarlos por otros antes")
        salida.append("de mandar el paquete.")
    return salida


def _escribir_leeme_recursos(paquete, draft):
    """Anade al LEEME que recursos de CapCut hacen falta en su computadora."""
    lineas = recursos_que_necesita(draft)
    if not lineas:
        return
    ruta = os.path.join(paquete, "1 - LEEME.txt")
    if not os.path.exists(ruta):
        return
    barra = "-" * 54
    partes = ["", barra, "EFECTOS QUE NECESITAS TENER", barra]
    for l in lineas[1:]:
        partes.append(l.replace("ella tiene", "tu tienes")
                       .replace("Que los descargue: basta con aplicarlos",
                                "Para descargarlos basta con aplicarlos")
                       .replace("cualquier proyecto suyo", "cualquier proyecto tuyo"))
    salto = chr(13) + chr(10)      # el LEEME lo abre el Bloc de notas
    with open(ruta, "a", encoding="utf-8") as f:
        f.write(salto.join(partes) + salto)


def _carpeta_sugerida():
    """Nombre de la carpeta fija que se le sugiere a quien edita.

    Lleva el nombre de quien manda porque el punto es que TODO lo de esta
    persona viva en el mismo sitio: si cada proyecto acaba donde cayo la
    descarga, al devolverlo hay que buscar cual de todas era.
    """
    try:
        import subprocess
        quien = subprocess.check_output(
            ["git", "config", "user.name"], stderr=subprocess.DEVNULL,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        ).decode("utf-8", "ignore").strip()
        if quien:
            return "Proyectos " + quien.split()[0]
    except Exception:
        pass
    return "Proyectos compartidos"


# Cubre desde que baja el ZIP, no desde que ya lo tiene descomprimido: el
# primer viaje real se perdio justo ahi. La editora edito en su CapCut y
# devolvio el paquete original de 314 MB, porque nunca supo que habia un
# tercer boton ni a que carpeta volver (2026-08-25).
LEEME_TXT = u"""PROYECTO: NOMBRE_PROYECTO
======================================================

Asi trabajamos: te mando una carpeta, la abres en tu CapCut de
siempre, editas normal, y me la regresas. Son dos botones, uno
al empezar y otro al terminar.

------------------------------------------------------
PASO 0  -  DONDE PONER ESTO (una sola vez)
------------------------------------------------------

Hazte UNA carpeta fija para todo lo mio, por ejemplo:

    Documentos\\CARPETA_TRABAJO

Ahi va cada proyecto que te mande, cada uno en su propia
subcarpeta. Siempre en el mismo lugar: asi al terminar sabes a
donde volver sin buscar.

------------------------------------------------------
PASO 1  -  RECIBIR Y ABRIR
------------------------------------------------------

1. Baja el ZIP que te comparti (Google Drive, WhatsApp, donde sea).

2. Click derecho sobre el ZIP > "Extraer todo..." y elige tu
   carpeta fija.

   IMPORTANTE: no le des doble clic a los botones desde DENTRO
   del ZIP. Windows deja ver lo de adentro como si ya estuviera
   descomprimido, pero no lo esta, y el proyecto se queda sin los
   videos. Hay que extraer primero, siempre.

3. Te queda asi:

       Documentos\\CARPETA_TRABAJO
          NOMBRE_PROYECTO - para editar
             1 - LEEME.txt
             2 - ABRIR EN CAPCUT.bat
             3 - DEVOLVER YA EDITADO.bat
             medios/   proyecto/   _sistema/

4. Cierra CapCut si lo tienes abierto.

5. Doble clic en "2 - ABRIR EN CAPCUT.bat".
   Se abre una ventana negra, hace lo suyo y te dice el nombre
   con el que quedo el proyecto. Apuntalo si quieres.

6. Abre CapCut: ese proyecto ya esta en tu lista. Si no aparece,
   cierra CapCut por completo y vuelve a abrirlo.

------------------------------------------------------
PASO 2  -  EDITAR
------------------------------------------------------

Edita lo que quieras y como quieras: cortes, musica, efectos,
color, textos, lo que sea. Guarda como siempre.

NO BORRES, NO MUEVAS Y NO LE CAMBIES EL NOMBRE a la carpeta que
extrajiste en el paso 1. CapCut saca los videos de ahi mientras
trabajas, y el ultimo boton la necesita otra vez al final. Si la
mueves, el proyecto se queda sin material.

SI LA LUPITA DE ESCALA NO TE DEJA ACERCAR NI ALEJAR:

No esta trabada ni descompuesta. Ese clip trae el acercamiento
ANIMADO -dos puntos clave, uno al principio y otro al final-, y
mientras esten puestos CapCut no deja mover la escala a mano:
todo lo que arrastres vuelve solo al valor que le toca en ese
punto de la linea de tiempo.

Para moverla tu:

  1. Selecciona el clip.
  2. Abre el panel de puntos clave (el rombo junto a "Escala").
  3. Borra los dos puntos clave de escala.

Ya con eso la lupita funciona normal y el movimiento lo pones tu.

Puedes tardar los dias que quieras. La carpeta se queda ahi.

------------------------------------------------------
PASO 3  -  DEVOLVERMELO
------------------------------------------------------

1. Cierra CapCut por completo, para que guarde lo ultimo.

2. Vuelve a ESA MISMA CARPETA, la del paso 1.

3. Doble clic en "3 - DEVOLVER YA EDITADO.bat".

4. En tu ESCRITORIO aparece una carpeta nueva que termina en
   "- editado".

5. Click derecho sobre ESA carpeta > "Comprimir en archivo ZIP".

6. Ese ZIP es el que me mandas. Ya esta.

Va a pesar poco, unos pocos MB. Eso es correcto y no es un
error: los videos ya los tengo yo, asi que solo viaja tu edicion
mas lo que hayas agregado tu (musica, clips, tipografias).

  >> Si lo que estas por mandarme pesa cientos de MB, es la
     carpeta equivocada: me estarias regresando la que yo te
     mande, sin tus cambios.

------------------------------------------------------
QUE TRAE HECHO EL PROYECTO
------------------------------------------------------

  - Cortes de silencios y tomas repetidas
  - Zoom por corte
  - Subtitulos palabra por palabra
  - Cifras resaltadas
  - B-roll
  - Efectos de sonido

Todo eso es un punto de partida: muevele lo que quieras.

SI ALGUN EFECTO NO SE VE

Es porque tu CapCut no lo tiene descargado. Aplicalo una vez a
mano desde la biblioteca de efectos y ya queda.

La carpeta "_sistema" hace funcionar los botones: no la toques.
"""


def _escribir_instalador(paquete, nombre):
    ps = r'''# Instala el proyecto en el CapCut de esta computadora.
$ErrorActionPreference = "Stop"
$base = Split-Path -Parent $PSScriptRoot   # la carpeta del paquete
$nombre = "NOMBRE_PROYECTO"

# Windows deja abrir un .bat desde DENTRO del ZIP: lo extrae solo a una carpeta
# temporal que luego borra. El proyecto quedaria apuntando a videos que van a
# desaparecer, y CapCut diria "no tengo los archivos multimedia" dias despues,
# sin que nada relacione una cosa con la otra.
$temporal = $env:TEMP
if ($temporal -and $base.ToLower().StartsWith($temporal.ToLower())) {
  Write-Host ""
  Write-Host "Estas abriendo esto desde DENTRO del ZIP." -ForegroundColor Red
  Write-Host ""
  Write-Host "Windows lo ensena como si ya estuviera descomprimido, pero no lo esta."
  Write-Host ""
  Write-Host "Cierra esta ventana. Ve al ZIP, click derecho > 'Extraer todo...',"
  Write-Host "elige una carpeta tuya de siempre, y abre el boton desde AHI." -ForegroundColor Yellow
  Write-Host ""
  Read-Host "Enter para salir"; exit 1
}

$drafts = Join-Path $env:LOCALAPPDATA "CapCut\User Data\Projects\com.lveditor.draft"
if (-not (Test-Path $drafts)) {
  Write-Host "No encuentro CapCut en esta computadora." -ForegroundColor Red
  Write-Host "Instala CapCut y abrelo una vez antes de correr esto."
  Read-Host "Enter para salir"; exit 1
}
if (Get-Process -Name "CapCut*" -ErrorAction SilentlyContinue) {
  Write-Host "CIERRA CAPCUT antes de instalar." -ForegroundColor Yellow
  Read-Host "Enter para salir"; exit 1
}

$medios = Join-Path $base "medios"
$capcut = Join-Path $env:LOCALAPPDATA "CapCut"

# La carpeta de fuentes cuelga de la version instalada de CapCut, que cambia en
# cada computadora. Se busca la mas nueva que exista aqui.
$fuentes = ""
$apps = Join-Path $capcut "Apps"
if (Test-Path $apps) {
  $cand = Get-ChildItem $apps -Directory | Where-Object { $_.Name -match "^\d+\." } |
          Sort-Object Name -Descending
  foreach ($c in $cand) {
    $f = Join-Path $c.FullName "Resources\Font\SystemFont"
    if (Test-Path $f) { $fuentes = $f; break }
  }
}
if (-not $fuentes) { Write-Host "Aviso: no encontre las fuentes de CapCut; los subtitulos usaran la de por defecto." -ForegroundColor Yellow }
# Si ya hay un proyecto con ese nombre NO se pregunta ni se pisa: se instala
# al lado con un numero. Antes se preguntaba "sobrescribir? (s/n)" y eso era
# las dos cosas malas a la vez -- le hacia tomar una decision que no le tocaba,
# y decir que si le borraba su proyecto ya editado.
$nombreFinal = $nombre
$destino = Join-Path $drafts $nombreFinal
$n = 2
while (Test-Path $destino) {
  $nombreFinal = "$nombre ($n)"
  $destino = Join-Path $drafts $nombreFinal
  $n++
}
if ($nombreFinal -ne $nombre) {
  Write-Host ""
  Write-Host "Ya tenias un proyecto llamado '$nombre', asi que este se instala" -ForegroundColor Yellow
  Write-Host "aparte como '$nombreFinal'. No se toco el que ya tenias." -ForegroundColor Yellow
}
Copy-Item (Join-Path $base "proyecto") $destino -Recurse

# el boton de devolver necesita saber con que nombre quedo instalado
[System.IO.File]::WriteAllText(
  (Join-Path $base "_sistema/instalado.txt"), $nombreFinal,
  (New-Object System.Text.UTF8Encoding $false))

# Reescribir las rutas: el draft guarda rutas absolutas de la otra computadora
$mapa = Get-Content (Join-Path $base "_sistema/rutas.json") -Raw -Encoding UTF8 | ConvertFrom-Json
# Se recorren TODOS los archivos de texto del proyecto, no una lista fija: si
# alguno se queda sin reescribir, sigue apuntando a la otra computadora y
# CapCut dice que no tiene los archivos multimedia.
$archivos = Get-ChildItem $destino -Recurse -File |
            Where-Object { $_.Length -lt 80MB }
foreach ($item in $archivos) {
  $ruta = $item.FullName
  if ($item.Extension -in @(".jpg", ".png", ".mp4", ".mp3", ".mov")) { continue }
  $texto = Get-Content $ruta -Raw -Encoding UTF8
  foreach ($p in $mapa.PSObject.Properties) {
    $nuevo = $p.Value.Replace("@@MEDIOS@@", $medios.Replace("\", "/"))
    $nuevo = $nuevo.Replace("@@CAPCUT@@", $capcut.Replace("\", "/"))
    if ($fuentes) { $nuevo = $nuevo.Replace("@@FUENTES@@", $fuentes.Replace("\", "/")) }
    # Dentro del JSON las rutas pueden venir de tres formas: con barra normal,
    # o con barra invertida ESCAPADA (que es como las guarda CapCut). Hay que
    # cubrir las tres o el reemplazo no encuentra nada y el proyecto queda roto.
    $conBarra   = $p.Name.Replace("\", "/")
    $escapada   = $p.Name.Replace("\", "\\")
    $texto = $texto.Replace($conBarra, $nuevo)
    $texto = $texto.Replace($escapada, $nuevo)
    $texto = $texto.Replace($p.Name, $nuevo)
  }
  [System.IO.File]::WriteAllText($ruta, $texto, (New-Object System.Text.UTF8Encoding $false))
}

# El nombre que CapCut ENSENA sale de draft_meta_info.json, no de la carpeta.
# Sin esto apareceria otro proyecto con el mismo nombre en la lista, que es
# justo la confusion que se quiere evitar.
$meta = Join-Path $destino "draft_meta_info.json"
if (Test-Path $meta) {
  $m = Get-Content $meta -Raw -Encoding UTF8 | ConvertFrom-Json
  $m.draft_name = $nombreFinal
  $m.draft_fold_path = $destino.Replace("\", "/")
  $m.draft_root_path = $drafts
  [System.IO.File]::WriteAllText(
    $meta, ($m | ConvertTo-Json -Depth 40 -Compress),
    (New-Object System.Text.UTF8Encoding $false))
}

# Comprobar en SU cache que estan los efectos que el proyecto usa. CapCut no
# avisa de esto: si le falta uno, descarta la pista en silencio y ella nunca
# sabe que ahi habia algo. Aqui si se puede mirar, porque esto corre en su
# computadora.
$faltan = @()
$cacheEfectos = Join-Path $capcut "User Data\Cache\effect"
$listaRec = Join-Path $base "_sistema/recursos.json"
if (Test-Path $listaRec) {
  $recursos = Get-Content $listaRec -Raw -Encoding UTF8 | ConvertFrom-Json
  foreach ($r in $recursos) {
    $tiene = $false
    if ($r.ruta) {
      $exacta = Join-Path $capcut ("User Data\Cache\" + $r.ruta.Replace("/", "\"))
      if (Test-Path $exacta) { $tiene = $true }
    }
    # El id de la carpeta cambia en cada computadora (la transicion White Flash
    # vive en 231313341 aqui y su effect_id es otro). Lo estable es el hash de
    # dentro, igual que ya se descubrio en importar.py. Comprobar solo por id
    # decia "te falta" sobre un efecto que SI estaba.
    if (-not $tiene -and $r.hash) {
      foreach ($c in (Get-ChildItem $cacheEfectos -Directory -ErrorAction SilentlyContinue)) {
        if (Test-Path (Join-Path $c.FullName $r.hash)) { $tiene = $true; break }
      }
    }
    if (-not $tiene) { $faltan += $r }
  }
}

Write-Host ""
if ($faltan.Count -gt 0) {
  Write-Host "OJO: te faltan $($faltan.Count) efecto(s) que usa este proyecto." -ForegroundColor Yellow
  foreach ($r in $faltan) {
    $extra = ""
    if ($r.legible) { $extra = "  (" + $r.legible + ")" }
    Write-Host ("   - " + $r.nombre + $extra)
  }
  Write-Host ""
  Write-Host "Busca cada uno en CapCut y aplicalo UNA VEZ a cualquier clip o"
  Write-Host "texto, en un proyecto tuyo. Con eso CapCut te lo descarga."
  Write-Host "Luego vuelve a abrir este archivo para instalar de nuevo."
  Write-Host ""
  Write-Host "Si abres el proyecto sin ellos igual funciona, pero esas partes"
  Write-Host "no se veran y CapCut no te va a avisar." -ForegroundColor Yellow
} else {
  Write-Host "Tienes todos los efectos que usa el proyecto." -ForegroundColor Green
}

Write-Host ""
Write-Host "LISTO." -ForegroundColor Green
Write-Host ""
Write-Host "  1. Abre CapCut y busca el proyecto: $nombreFinal"
Write-Host "     (si no aparece, cierra CapCut por completo y vuelve a abrirlo)"
Write-Host ""
Write-Host "  2. Edita lo que quieras."
Write-Host ""
Write-Host "  3. Cuando termines: cierra CapCut, vuelve a esta carpeta"
Write-Host "        $base"
Write-Host "     y abre '3 - DEVOLVER YA EDITADO.bat'." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Eso te deja en el Escritorio la carpeta a devolver. Ese es"
Write-Host "  el paso que hay que hacer al final: sin el, lo que mandes"
Write-Host "  de vuelta es el proyecto sin tus cambios." -ForegroundColor Yellow
Write-Host ""
Write-Host "  No borres ni muevas esta carpeta: el proyecto la usa."
Write-Host ""
Read-Host "Enter para salir"
'''.replace("NOMBRE_PROYECTO", nombre)
    os.makedirs(os.path.join(paquete, "_sistema"), exist_ok=True)
    with open(os.path.join(paquete, "_sistema", "instalar.ps1"), "w",
              encoding="utf-8") as f:
        f.write(ps)

    bat = ("@echo off\r\n"
           "cd /d \"%~dp0\"\r\n"
           "powershell -NoProfile -ExecutionPolicy Bypass "
           "-File \"_sistema\\instalar.ps1\"\r\n")
    with open(os.path.join(paquete, "2 - ABRIR EN CAPCUT.bat"), "w",
              encoding="utf-8") as f:
        f.write(bat)

    with open(os.path.join(paquete, "1 - LEEME.txt"), "w",
              encoding="utf-8") as f:
        f.write(LEEME_TXT.replace("NOMBRE_PROYECTO", nombre)
                         .replace("CARPETA_TRABAJO", _carpeta_sugerida())
                         .replace("\n", "\r\n"))


DEVOLUCION_PS = r'''# Prepara la carpeta para devolver el proyecto ya editado.
$ErrorActionPreference = "Stop"
$base = Split-Path -Parent $PSScriptRoot   # la carpeta del paquete
$nombre = "NOMBRE_PROYECTO"

# Windows deja abrir un .bat desde DENTRO del ZIP: lo extrae solo a una carpeta
# temporal que luego borra. El proyecto quedaria apuntando a videos que van a
# desaparecer, y CapCut diria "no tengo los archivos multimedia" dias despues,
# sin que nada relacione una cosa con la otra.
$temporal = $env:TEMP
if ($temporal -and $base.ToLower().StartsWith($temporal.ToLower())) {
  Write-Host ""
  Write-Host "Estas abriendo esto desde DENTRO del ZIP." -ForegroundColor Red
  Write-Host ""
  Write-Host "Windows lo ensena como si ya estuviera descomprimido, pero no lo esta."
  Write-Host ""
  Write-Host "Cierra esta ventana. Ve al ZIP, click derecho > 'Extraer todo...',"
  Write-Host "elige una carpeta tuya de siempre, y abre el boton desde AHI." -ForegroundColor Yellow
  Write-Host ""
  Read-Host "Enter para salir"; exit 1
}

# Si al instalar ya existia un proyecto con ese nombre, se instalo con un
# numero al lado. Hay que devolver ESE, no el del nombre original.
$marca = Join-Path $base "_sistema/instalado.txt"
if (Test-Path $marca) {
  $guardado = (Get-Content $marca -Raw -Encoding UTF8).Trim()
  if ($guardado) { $nombre = $guardado }
}

if (Get-Process -Name "CapCut*" -ErrorAction SilentlyContinue) {
  Write-Host "CIERRA CAPCUT antes de devolver, para que guarde los ultimos cambios." -ForegroundColor Yellow
  Read-Host "Enter para salir"; exit 1
}

$drafts = Join-Path $env:LOCALAPPDATA "CapCut\User Data\Projects\com.lveditor.draft"
$proyecto = Join-Path $drafts $nombre
if (-not (Test-Path $proyecto)) {
  Write-Host "No encuentro el proyecto '$nombre' en tu CapCut." -ForegroundColor Red
  Write-Host "Si lo renombraste, avisale a quien te lo mando."
  Read-Host "Enter para salir"; exit 1
}

$salida = Join-Path ([Environment]::GetFolderPath("Desktop")) "$nombre - editado"
if (Test-Path $salida) { Remove-Item $salida -Recurse -Force }
New-Item -ItemType Directory $salida | Out-Null
Copy-Item $proyecto (Join-Path $salida "proyecto") -Recurse

# Lo que venia en el paquete original no hace falta reenviarlo
$originales = @{}
$medios = Join-Path $base "medios"
if (Test-Path $medios) {
  Get-ChildItem $medios -File | ForEach-Object { $originales[$_.Name.ToLower()] = $true }
}

$json = Get-Content (Join-Path $proyecto "draft_content.json") -Raw -Encoding UTF8 | ConvertFrom-Json
$usados = @()
foreach ($grupo in @("videos", "audios")) {
  $lista = $json.materials.$grupo
  if ($lista) { foreach ($m in $lista) { if ($m.path) { $usados += $m.path } } }
}
# Las fuentes tambien son archivos y tambien se pueden cambiar al editar. Sin
# esto, si ella le pone otra tipografia el proyecto vuelve pidiendola y no hay
# de donde sacarla.
if ($json.materials.texts) {
  foreach ($t in $json.materials.texts) {
    if ($t.font_path -and ($t.font_path -match "\.(ttf|otf|ttc)$")) { $usados += $t.font_path }
  }
}

$nuevos = Join-Path $salida "medios_nuevos"
$copiados = 0
foreach ($ruta in ($usados | Sort-Object -Unique)) {
  if (-not (Test-Path $ruta)) { continue }
  $archivo = Split-Path $ruta -Leaf
  if ($originales.ContainsKey($archivo.ToLower())) { continue }
  if (-not (Test-Path $nuevos)) { New-Item -ItemType Directory $nuevos | Out-Null }
  Copy-Item $ruta (Join-Path $nuevos $archivo) -Force
  $copiados++
  Write-Host "  se incluye lo que agregaste: $archivo"
}

$mb = [math]::Round(((Get-ChildItem $salida -Recurse -File | Measure-Object Length -Sum).Sum / 1MB), 1)
Write-Host ""
Write-Host "Listo: $salida  ($mb MB, $copiados archivo(s) nuevo(s))" -ForegroundColor Green
Write-Host "Click derecho sobre ESA carpeta > Comprimir en archivo ZIP,"
Write-Host "y ese ZIP es el que mandas de vuelta." -ForegroundColor Yellow
Write-Host ""
Write-Host "Pesa poco a proposito: los videos ya los tiene quien te lo mando."
Write-Host "La carpeta que abriste al principio NO se manda, se queda aqui."
Read-Host "Enter para salir"
'''


def _escribir_devolucion(paquete, nombre):
    """Script para que la otra persona devuelva su edicion, con lo que agrego.

    Una carpeta de proyecto de CapCut es solo el JSON de la linea de tiempo: los
    medios viven aparte. Devolver solo el proyecto basta para lo que ya tenia
    (por eso una devolucion pesa 4 MB frente a los 300 que se mandaron), pero lo
    que ELLA agregue —una cancion, un clip— se queda en su computadora y llega
    como referencia rota. Esto copia el proyecto MAS los archivos nuevos.
    """
    os.makedirs(os.path.join(paquete, "_sistema"), exist_ok=True)
    with open(os.path.join(paquete, "_sistema", "devolver.ps1"), "w",
              encoding="utf-8") as f:
        f.write(DEVOLUCION_PS.replace("NOMBRE_PROYECTO", nombre))
    bat = ("@echo off\r\n"
           "cd /d \"%~dp0\"\r\n"
           "powershell -NoProfile -ExecutionPolicy Bypass "
           "-File \"_sistema\\devolver.ps1\"\r\n")
    with open(os.path.join(paquete, "3 - DEVOLVER YA EDITADO.bat"), "w",
              encoding="utf-8") as f:
        f.write(bat)


sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipeline.entorno import consola_utf8


def main():
    consola_utf8()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    nombre = args[0]
    destino = args[1] if len(args) > 1 else None
    exportar(nombre, destino, comprimir_video="--comprimir" in sys.argv)


if __name__ == "__main__":
    main()
