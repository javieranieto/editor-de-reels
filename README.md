# Editor de reels → CapCut

Corta silencios, muletillas y tomas repetidas de un video hablado a cámara y deja un
**proyecto de CapCut ya armado**: abres CapCut y la línea de tiempo trae los cortes, los
subtítulos, el zoom, las cifras y los sonidos. Tú haces la parte creativa.

También arma **reels sin cámara**: escribes un guion, lo lee una voz de ElevenLabs y cada
escena se ilustra con video de stock (Pexels, y Pixabay si tienes llave).

Lo hice para mi propio trabajo: antes me tomaba 5 horas editar un video y ahora son 10
minutos. Lo comparto gratis y como código abierto (licencia MIT). — **Javier Nieto**

**Lo mejor sale con Claude Code.** El automático limpia; la revisión con criterio (qué
frase sobra, dónde va el énfasis) la hace Claude con el skill `revisar-reel`, que ya viene
en este repo. Yo lo uso con el plan de paga de Claude Code; con otras herramientas puede
funcionar, pero no lo he probado y no lo garantizo.

**Se comparte tal cual, sin soporte.** Cada tantos meses le paso las mejoras que le hago al
mío. Si quieres que te ayude a instalarlo o a adaptarlo a tu forma de trabajar, eso sí lo
cobro: escríbeme por mensaje en cualquiera de mis redes. Y si te sirvió, dale una estrella
al repo y cuéntame qué le mejorarías.

## Así lo tengo yo (y me funciona)

| | |
|---|---|
| Sistema | Windows 11 Home (build 26200) |
| Procesador | Intel Core i5-12400F (6 núcleos, 12 hilos) |
| Memoria | 64 GB |
| Tarjeta de video | NVIDIA GeForce RTX 3050, 8 GB (transcribe en la tarjeta) |
| CapCut | CapCut **Pro** de escritorio 9.3 |
| Claude | Claude Code, plan **Max** de 100 dólares |
| Programas | Python 3.13, ffmpeg 8.1, Git 2.51 |
| Librerías | faster-whisper 1.2 (large-v3), Playwright 1.57 + Chromium, OpenCV 5 headless |

**Lo que no he probado:** CapCut gratis con todo el flujo; Claude con un plan menor u otros
asistentes (Codex, Cursor) — muy seguramente funciona, porque las instrucciones vienen en el
repo, pero no lo garantizo; equipos sin tarjeta NVIDIA (transcribe con el procesador, más lento)
o con menos de 16 GB de memoria.

## Antes de instalar: ¿tu computadora sirve?

🔴 **Solo Windows con CapCut de escritorio.** No corre en Mac ni en Linux: el editor escribe
el proyecto directo en la carpeta de CapCut para Windows. Si no es tu caso, no sigas.

Necesitas además **Python 3.9+** y **ffmpeg**: si no los tienes, Claude los instala en el paso de
abajo. Una tarjeta NVIDIA es opcional: solo acelera la transcripción.

## Instalar

Si ya usas Claude Code o VS Code, esto te toma unos minutos. Si no sabes de qué te hablo, estos
pasos no te lo van a enseñar, pero te puedo ayudar con la instalación guiada (abajo).

**Con Claude Code (lo más fácil).** Abre una carpeta vacía en VS Code (o donde uses Claude Code)
y pégale esto:

```text
Instala el editor de reels de https://github.com/javieranieto/editor-de-reels en esta carpeta. Sigue la sección «Instalar» de su CLAUDE.md, instala lo que me falte y al final corre tools/configurar.py y dime qué quedó listo y qué tengo que hacer yo.
```

Claude baja el repo, instala Python, ffmpeg y las librerías si te faltan (te pide permiso en cada
comando) y te dice qué queda de tu lado. Lo único que no puede hacer por ti es bajar **CapCut de
escritorio** (capcut.com): ábrelo una vez y ciérralo, así crea su carpeta de proyectos.

**A mano**, si prefieres:

```bash
git clone https://github.com/javieranieto/editor-de-reels
cd editor-de-reels
winget install --id Gyan.FFmpeg -e      # si no tienes ffmpeg; luego abre una terminal nueva
python -m pip install -r requirements.txt
python -m playwright install chromium
python tools/configurar.py              # dice exactamente qué te falta
```

La primera vez que transcribe baja el modelo de voz (unos 3 GB, una sola vez).

**¿Cuánto te tardó y dónde te atoraste?** Cuéntamelo en la
[página del editor](https://javiernieto.net/profesional/recursos/editor-de-reels/): con eso se
mejora esta lista. Y si no programas y prefieres que lo instalemos juntos, ahí mismo está la
instalación guiada.

**Llaves (opcionales):** el editor corta y arma sin ninguna. Para b-roll hace falta la de
Pexels (gratis en pexels.com/api) y para voz en off la de ElevenLabs. Van en
`.secrets/pexels.yaml` y `.secrets/elevenlabs.yaml` dentro de esta carpeta (no suben a
git), con una sola línea cada uno: `api_key: tu_llave`.

## Usar

```bash
# Un video hablado: primero mira qué cortaría, luego genera
python reel.py "C:\ruta\mi_video.mp4" --solo-plan
python reel.py "C:\ruta\carpeta_con_los_clips"

# Un reel sin cámara, desde un guion (hay uno de ejemplo)
python reel.py --guion guiones/ejemplo_alcaraz.txt --solo-plan
```

O doble clic en **`Editor de Reels.bat`** para la interfaz.

**Genera con CapCut cerrado.** Al terminar, ábrelo: el proyecto aparece en tu lista.

Lo que más vale no es el automático sino la revisión: abre Claude Code y pídele
*"revisa <nombre del proyecto>"*. Decide qué corte sobra, cuál frase es la tesis y qué cifra
merece pantalla, y te explica por qué.

## Video largo de YouTube

De una o varias tomas a un proyecto de CapCut armado: el corte por frases medido en el audio,
subtítulos limpios para YouTube y stock. Lo más cómodo es pedírselo a Claude: *«edita este
video»*. Paso por paso y las trampas conocidas: `largo/LEEME.md`.

```bash
python largo.py preparar "mi video" --toma A="C:\videos\toma.mp4"
python largo.py cortar "mi video" && python largo.py revisar "mi video"
python largo.py amarrar "mi video" && python largo.py armar "mi video"
```

## Videos animados dibujados a mano

`animado/` dibuja un video por código —trazos a mano, cifras, un personaje— o una
capa con fondo transparente para poner encima de un reel en CapCut. Necesita además
`pip install playwright` y Chrome. Pídele a Claude *"hazme un video animado de…"* o mira
`animado/LEEME.md`:

```bash
python animado/render.py ejemplo-dato --fotos 0.3 1.2 2.8 --alfa   # capturas para revisar
python animado/render.py ejemplo-dato --alfa                       # el .mov para CapCut
```

## Opcional, pero cambia el resultado

- **Tus sonidos**: el repo no trae los de CapCut (su licencia no permite redistribuirlos).
  Ver `recursos/sfx_usuario/LEEME.md`. Sin ellos el reel sale sin efectos de sonido.
- **Tu tarjeta de cierre** «video completo en YouTube»: `recursos/cta/LEEME.md`.
- **Tus efectos de CapCut**: solo funcionan los que tengas descargados. Aplica uno a mano una
  vez y corre `python tools/biblioteca.py --guardar`.

## Mandarle un proyecto a quien edita

Doble clic en **`Preparar para editora.bat`**: eliges el proyecto y deja en tu Escritorio
una carpeta con dos botones (abrir en su CapCut y devolverlo) y un LEEME paso a paso. Cuando
te lo devuelva: `python tools/importar.py "<carpeta>" --nombre "<nombre>"`.

Todo lo demás —comandos, estructura y las lecciones que evitan romper algo— está en
`CLAUDE.md`.
