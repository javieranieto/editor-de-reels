# Editor de reels

Corta silencios, muletillas y tomas repetidas de un video hablado a cámara (en español) y
entrega un **proyecto de CapCut ya armado** — no un MP4 cerrado. También arma reels **sin
cámara**: guion escrito → voz de ElevenLabs → escenas de stock. Y dibuja **videos animados**
por código (`animado/`). Quien edita conserva CapCut para lo creativo.

**Lo que da valor no es el automático, es la revisión.** El pipeline limpia; el criterio
editorial —qué corte sobra, cuál frase es la tesis, qué cifra merece pantalla— lo pone
Claude con el skill `revisar-reel`.

Todo lo de aquí se corre **desde la raíz de este repo** o con la
ruta completa (`python reel.py ...`): los módulos resuelven sus rutas relativas a su
propio archivo, no al directorio actual.

## Instalar — cuando te pidan instalarlo, sigue esto en orden

La persona abrió una carpeta (casi siempre vacía) y te pegó un prompt como *"instala el editor
de reels"*. **Tú haces todo lo que se pueda hacer desde la terminal**; a ella solo le toca lo que
no: bajar CapCut y, si quiere, sus llaves. Explica en una línea qué vas a instalar antes de cada
paso: le estás pidiendo permiso para correr comandos en su computadora.

1. 🔴 **Windows.** Si no es Windows, para ahí y díselo: el editor escribe el proyecto en la
   carpeta de CapCut para Windows (`%LOCALAPPDATA%\CapCut\User Data\Projects\com.lveditor.draft`)
   y no hay forma de configurarlo para Mac o Linux.
2. **El repo.** Si la carpeta no lo tiene todavía:
   `git clone https://github.com/javieranieto/editor-de-reels .` (con el punto, para que quede en
   esa misma carpeta; si no está vacía, clónalo en una subcarpeta `editor-de-reels`). Si `git` no
   existe: `winget install --id Git.Git -e`.
3. **Python 3.9 o mayor.** ⚠️ En Windows, `python` puede ser el **atajo falso de la Microsoft
   Store**: abre la tienda o no imprime nada. Compruébalo con `python --version`. Si falta o es
   el atajo: `winget install --id Python.Python.3.12 -e`.
4. **ffmpeg:** `winget install --id Gyan.FFmpeg -e`.
   ⚠️ **Lo que instala `winget` no aparece en la terminal que ya estaba abierta.** No es que
   haya fallado: el PATH se lee al abrir la terminal. Usa la ruta completa
   (`%LOCALAPPDATA%\Programs\Python\Python312\python.exe`; ffmpeg queda en
   `%LOCALAPPDATA%\Microsoft\WinGet\Links\`) o pídele que abra una terminal nueva.
5. **Las librerías:** `python -m pip install -r requirements.txt` (transcripción, CapCut,
   imágenes, gráficos y encuadre de cara) y luego `python -m playwright install chromium`.
6. **Tarjeta NVIDIA** (si `nvidia-smi` contesta): pregúntale antes, porque son varios GB, y con
   su sí: `python -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12`. Sin esto funciona igual,
   transcribiendo con el procesador (más lento).
7. **CapCut** es lo único que no puedes instalar tú: si `configurar.py` dice que falta, mándala a
   capcut.com a bajar la versión de **escritorio** y a abrirla una vez y cerrarla (así crea su
   carpeta de proyectos).
8. **Comprueba:** `python tools/configurar.py`. Cuéntale el resultado con palabras, no pegues la
   salida: qué quedó listo, qué falta y qué tiene que hacer ella.
9. **Avísale lo que va a pasar la primera vez:** la primera transcripción baja el modelo de voz
   (unos 3 GB, una sola vez), así que el primer video tarda más que los demás.
10. **Las llaves son opcionales** y van en archivos de `.secrets/` (Pexels gratis para stock,
    ElevenLabs para voz en off, Pixabay). **Nunca le pidas una llave por el chat:** crea el
    archivo si te lo pide y que ella pegue la llave ahí. El formato es una línea:
    `api_key: tu_llave`.
11. **Al final:** dile cómo usarlo (*"pásame la ruta de tu video y dime: edítalo"*) y pídele que le
    cuente a Javier cuánto tardó y dónde se atoró:
    https://javiernieto.net/profesional/recursos/editor-de-reels/ — así se mejora esta lista.

**Lo que hace falta, en resumen:** Windows, CapCut de escritorio, Claude Code (o un asistente
parecido, sin probar), Python y ffmpeg. Tarjeta NVIDIA opcional. `python tools/configurar.py`
revisa todo esto y dice qué falta.

**Llaves** (todas opcionales; sin ellas el editor corta y arma igual): van en
`.secrets/` de este repo (no sube a git), nunca en el chat. `pexels.yaml` (b-roll),
`elevenlabs.yaml` (voz en off), `pixabay.yaml` (segunda fuente de stock). Cada archivo lleva una línea:
`api_key: tu_llave`; las lee `pipeline/llaves.py`.

**Antes de saltarte un paso por una llave, vuelve a mirar.** Lo que dijo `configurar.py` al
instalar se queda viejo: la persona suele poner su llave DESPUÉS, a mitad de una sesión. Antes
del stock (o de la voz), corre otra vez `python tools/configurar.py`. Si de verdad falta, dilo y
sigue sin ese paso; nunca la des por faltante porque así estaba al principio.

**Magnific (imágenes, música por MCP) es OPCIONAL y de pago**: el editor no lo necesita para
nada. Si tienes cuenta, conéctalo **a nivel usuario**
(`claude mcp add --scope user --transport http magnific https://mcp.magnific.com`) y no en el
`.mcp.json` de otro repo: si solo vive ahí, una sesión abierta en esta carpeta **no tiene
las herramientas** y un video se queda sin imágenes sin que nada falle. Las conexiones se
cargan al **arrancar** la sesión: si agregas una, abre una conversación nueva. Todo lo que
se pide por MCP gasta créditos del plan (el «ilimitado» solo aplica en su web).

## Convenciones

- Código, mensajes y documentación en español. **Sin acentos en código y en lo que se
  imprime en consola** (la de Windows sigue en cp1252 y revienta a media lista; las
  herramientas que imprimen nombres leídos del disco llaman `entorno.consola_utf8()`).
  **Sin emojis en consola**, por lo mismo.
- 🔴 **El texto que se locuta es la excepción y va SIEMPRE acentuado.** En español la tilde
  es la pronunciación: el TTS lee «cambio» distinto de «cambió» y nada da error.
  `voz_off.revisar_acentos()` avisa si un guion largo no trae ni una tilde.

## Comandos

```bash
# video hablado
python reel.py <carpeta|videos...>                    # -> proyecto de CapCut
python reel.py <videos> --solo-plan                   # solo el analisis: guion.txt + plan.json
python reel.py --desde-plan <plan.json> --nombre <n>  # generar desde un plan revisado
python reel.py <videos> --mp4                         # MP4 cortado + SRT (sin letras quemadas)
python reel.py <video> --perfil largo --solo-plan     # video largo horizontal
pythonw interfaz.pyw                                  # interfaz (o "Editor de Reels.bat")

# reel sin camara
python reel.py --guion guiones/ejemplo_alcaraz.txt --solo-plan   # revisar antes de armar
python reel.py --guion <guion.txt> --voz <nombre publico|id>
python reel.py --ver-voces            # voces publicas y las de tu cuenta
python tools/voz.py [--probar]        # comprueba la llave y sus permisos antes de gastar
python tools/catalogo_voces.py [--capcut]   # la misma frase en todas tus voces, para elegir de oido
python tools/reel_frase.py --imagen a.jpg --frase "A... | B." --nombre "<n>"   # frase sobre imagen
python tools/reel_frase.py ... --cierre "Continuará…"   # letrero final de serie, sin voz

# estilo y encuadre
python reel.py --ver-letras | --ver-frases
python tools/encuadre.py --plan proyectos/<n>/plan.json   # frames por corte, para mirarlos
python tools/encuadre.py <video> --cabeza                 # cuanto zoom aguanta
python tools/planos.py "<proyecto>"                       # parte planos largos del video largo
python tools/repeticiones.py "<proyecto>" [--plan]        # arranques falsos dentro de un bloque
python tools/musica.py --analizar | --proponer <seg> | --beats <archivo>
python tools/analizar_sonido.py "<proyecto>" ; python tools/analizar_visual.py "<proyecto>"
python tools/biblioteca.py --guardar      # aprende los efectos que aplicaste a mano
python tools/fuentes.py ; python tools/catalogo_efectos.py   # bajar fuentes y efectos de CapCut

# video animado dibujado a mano (ver animado/LEEME.md)
python animado/render.py <video> --fotos 1 5 9   # capturas + hoja.png, antes del render
python animado/render.py <video>                 # MP4 final con audio.json
python animado/render.py <video> --alfa          # .mov transparente para CapCut
python animado/render.py <video> --ver           # vista previa en vivo

# compartir
python tools/exportar.py "<proyecto>" [destino] [--comprimir]     # o "Preparar para editora.bat"
python tools/importar.py "<carpeta devuelta>" --nombre "<nombre>"

# mantenimiento
python tools/pruebas.py               # correrlo antes de tocar el pipeline
python tools/limpiar.py [--listar]    # corridas desechables de proyectos/
python tools/validar_draft.py <carpeta del draft>
python tools/restaurar_capcut.py [--aplicar]   # si CapCut mando proyectos a su papelera
python tools/configurar.py
```

## Los flujos

**Video hablado.** Se graban clips en una carpeta (orden alfabético = orden de grabación).
`reel.py` transcribe con faster-whisper, decide qué se queda (`plan.py`, `tomas.py`), pega
los cortes al habla real (`voz.py`) y escribe el draft (`capcut_lib.py`). Cada corrida deja
en `proyectos/<nombre>/` el `guion.txt` anotado y numerado por segmento, el `plan.json` y el
`subtitulos.srt`. El flujo bueno: `--solo-plan` → revisión → `--desde-plan`.

**Reel sin cámara.** El guion va acentuado y lleva la búsqueda de stock de cada escena
**entre corchetes, en inglés** (los catálogos están etiquetados en inglés; traducir sería
adivinar). Lo entre corchetes no se locuta. Alternativas con `|`, gana la que mejor ilustre:

```text
Es tu tablero diciéndote que ya no aguanta. [electrical panel]
Media hora de revisión te ahorra un susto. [electrician checking panel | electrician]
```

La voz sale de ElevenLabs con la alineación **carácter por carácter**, así que los tiempos
de palabra son exactos y no se transcribe nada. Produce un `plan.json` normal: captions,
cifras, música, sonidos y exportar funcionan igual.

**Reel de frase** (`tools/reel_frase.py`): una frase partida con `|` sobre una o varias
imágenes, voz en off (o `--audio` con una voz grabada) y tarjetas de texto cortas. Deja un
MP4 para revisar y el proyecto de CapCut con la pista de música libre. Lo que ya aprendió:

- **Tope duro de 20 caracteres por tarjeta** (`DURO_CHARS`): los 18 de `MAX_CHARS` se
  pueden pasar un poco para no dejar palabras sueltas, esto no. Una tarjeta de 23 se salía
  de la pantalla por los dos lados: antes que eso, una palabra sola. Y si una palabra sola
  tampoco cabe, la letra se achica hasta que entre.
- **Con varias escenas, cada corte que cae sobre voz se mueve al punto más callado** a
  ±0.25 s (`acomodar_cortes`), midiendo el audio en cada candidato. Los tiempos de la
  transcripción se desfasan 50-200 ms del audio real. Sin pausa cerca, el corte no se mueve:
  no se inventa un silencio.
- **El aviso de "corte sobre voz" mide el volumen JUSTO en el corte** (`cortes_en_voz`), no
  solo contra silencios de 0.2 s: hay quien lee con pausas de 0.1 s, y el aviso salía en
  cortes que sí caían en silencio. Una alarma que sale en cada episodio se aprende a ignorar.
- **El subtítulo se cierra en el corte de escena** si su voz ya acabó: si no, la última
  frase se quedaba encima de la imagen siguiente.
- **`--cierre "Continuará…"`**: un letrero sin voz en los últimos 2 s, a la altura de los
  subtítulos (al centro tapa caras). Entra 0.6 s después de la voz, no 1.6: ese segundo de
  más saca un episodio de los 90 s de Facebook.
- **El audio del MP4 dura lo que el video** (`apad`): algunos reproductores de Windows
  cierran el video cuando se acaba el audio, y el cierre no se veía.
- **La voz va a CapCut en WAV, no en MP3**: de un MP3 de bitrate variable CapCut leyó la
  duración 1.2 s corta y cortaba el final de la voz.
- **`--tono` sin valor = cada modelo con el suyo**: v3 va creativo (0.0) y el multilingüe
  con su 0.5. En el multilingüe 0.0 es el ajuste MÁS variable ("varía mucho la emoción"),
  no el creativo.

**Video largo horizontal** (`--perfil largo`): quita muletillas y respeta el aire de una
charla; el corte narrativo se decide leyendo el `guion.txt` (ver abajo).

**Video animado dibujado a mano** (`animado/`): no se graba ni se edita, **se dibuja con
código**. Chrome pinta cada cuadro sobre un canvas con trazos que tiemblan a 12 fps y ffmpeg
lo junta con música y efectos. Un video = una carpeta `animado/videos/<nombre>/` con su
`escenas.js` y su `audio.json`; el motor (`animado/motor.js`) no se toca. Con `--alfa` sale
un **motion graphic para CapCut** (`.mov` qtrle/argb): una tarjeta que se dibuja sola, una
cifra que se encierra en un círculo, encima de un reel sin tapar nada más. Los ejemplos
(`ejemplo-dato`, `ejemplo-alcaraz`) son la plantilla; el método está en el skill
`video-animado`.

## Estructura

| Módulo | Qué hace |
|---|---|
| `pipeline/nucleo.py` | Orquestador de CLI e interfaz; une varios clips en una línea de tiempo |
| `probe.py` · `transcribe.py` | ffprobe (maneja rotación) · faster-whisper por palabra, con caché |
| `plan.py` · `tomas.py` · `voz.py` | Qué se conserva · tomas repetidas y falsos arranques · cortes pegados al habla medida |
| `capcut_lib.py` | **El generador**, sobre pycapcut |
| `zoom.py` · `datos.py` · `cifras.py` · `frases.py` · `letras.py` | Zoom · cifras del guion · cómo se ven · la frase clave en grande · estilos de letra |
| `sonidos.py` · `efectos.py` · `biblioteca.py` · `musica.py` · `adornos.py` | Sonidos · efectos y transiciones · efectos aprendidos de tus proyectos · tempo y volumen de la música · overlays con alfa |
| `voz_off.py` · `guion.py` | TTS con tiempos exactos · guion → plan |
| `broll.py` · `pixabay.py` · `pertinencia.py` · `stock.py` | Proveedores de stock · si el video ILUSTRA la escena · elegir entre proveedores |
| `render.py` · `entorno.py` · `llaves.py` | MP4 vía ffmpeg · dónde vive CapCut y si está abierto · dónde viven las llaves |

`recursos/`: sonidos CC0 (`sfx/`), fuentes OFL, el modelo YuNet, la biblioteca de efectos
aprendida, `sfx_usuario/` y `cta/` (vacías: las llena cada quien, ver sus LEEME).

## Reglas duras de CapCut — ninguna da error, todas fallan en silencio

1. **Nunca editar `root_meta_info.json`.** CapCut lo tiene en memoria y lo reescribe al
   cerrar: editarlo marca proyectos como borrados. Descubre las carpetas nuevas solo al
   reiniciarse.
2. **Nunca generar con CapCut abierto** (`capcut_lib` se niega). Y el orden importa: si vas
   a regenerar con el mismo nombre, **comprueba que está cerrado ANTES de borrar el draft
   viejo**, o el proyecto desaparece de la lista y la regeneración ni arranca.
3. Los drafts se declaran con **versión vieja** (pycapcut lo hace). CapCut migra lo viejo
   pero rechaza imitaciones de la versión actual: el proyecto aparece y no abre.
4. **Efectos, fuentes y animaciones de texto son recursos DESCARGADOS.** pycapcut escribe una
   ruta inventada o un marcador `##_material_placeholder_…` y CapCut descarta la pista (o
   dibuja la fuente por defecto) sin avisar. `_resolver_efectos()` y `letras.resolver()`
   los apuntan a `Cache/effect/<id>/` después de guardar. Una transición de catálogo con
   `path: null` sí la resuelve CapCut al abrir, si está descargada.
5. **`script.add_effect()`, nunca `add_segment()` con un `EffectSegment`**: deja el material
   sin escribir y la pista se pierde.
6. **Keyframes de escala con `scale_x` Y `scale_y`, nunca `uniform_scale`**: pycapcut lo
   traduce a solo el eje X y sale un estirón que ensancha la cara (`_kf_escala()`). La
   lección de método: "está en el draft y no se ve" tiene dos explicaciones —CapCut no lo
   lee, o se lo escribimos mal— y hay que descartar la segunda antes de anotar la primera.
7. **ffprobe reporta unos ms de más.** Pedirle a un material más de lo que dura revienta en
   pycapcut con un `ValueError` **en chino** que no dice qué clip es. Todo lo que se pide de
   un archivo se topa contra su duración **medida**, menos un margen.
8. Si la escritura falla a medias queda una carpeta sin `draft_content.json`; el generador
   la barre sola. Un proyecto de verdad siempre tiene ese archivo.
9. **Un draft recién generado tiene solo `draft_content.json` y `draft_meta_info.json`**, y
   referencias de texto colgando. Es normal: CapCut crea el resto al abrirlo. En la rejilla
   se ve con 00:00 hasta que lo abres una vez.
10. **El recorte de fondo por `matting.flag` no funciona** en un draft que CapCut no armó: la
    máscara la calcula su IA. No reintentarlo por esa vía.

## Lecciones que siguen vigentes

### Medir el archivo, no el número que pediste
ffmpeg ajusta a fotogramas enteros, el TTS no dura lo que reporta y los silencios entre
partes no los modela nadie. **La duración se mide con ffprobe sobre lo generado**, nunca se
hereda del número con el que se pidió ni se suma por partes. Un índice de tiempos que miente
unos segundos no se vuelve a usar.

### Un valor por defecto no puede viajar como medido
Si no se pudo medir (el volumen de la música, un umbral), se devuelve el valor de reserva
**y se dice en una línea**. Un 0.10 "calculado" que en realidad era el de reserva sacó la
música al triple de fuerte sin que nada avisara.

### El buscador de stock nunca dice "no tengo"
Siempre devuelve algo, y ese algo puede ser un estanque donde el guion pedía otra cosa.
`pertinencia.py` puntúa cada resultado contra la consulta y **prefiere dejar la escena sin
imagen**: la vacía se ve y se arregla; la equivocada se cuela. `stock.resumen()` nombra las
que quedaron sin imagen.

- **Pasar el filtro no es ilustrar: se MIRA el frame.** Un filtro de palabras no ve una
  mascarilla de gases, rótulos en otro idioma o velas de trading donde se hablaba de
  anuncios. Hoja de contactos con un frame por clip (`ffmpeg ... tile`) y dos minutos.
- **Consultas cortas y literales**, 2-3 palabras: el vocabulario de los catálogos es corto.
  Para negocios de servicio, **nombrar el oficio** ("car repair shop"), no la categoría
  ("shop owner", que devuelve stock corporativo).
- Dos consultas distintas pueden devolver el **mismo video**: se comprueban los archivos
  del draft, no las consultas del plan.
- La orientación sale del lienzo (`stock.orientacion_de`), nunca de una opción a mano.

### La voz en off
- **Una escena dura hasta que EMPIEZA la siguiente**, no hasta su última palabra: los
  silencios entre frases suman y el remate se quedaba sin imagen. La última se estira al
  final del audio.
- `--voz` acepta el **nombre de una voz pública o un id**; el nombre de una voz de tu
  cuenta termina metido en la URL y truena con un error que no se parece a "esa voz no
  existe". El id sale de `tools/voz.py`.
- **`eleven_v3` (expresivo) no acepta `speed`**: mandárselo no da error y no hace nada. Y
  cambia la duración en un sentido que depende de la voz: se mide cada vez.
- Las **etiquetas de emoción de v3** (`[serio]`) no se locutan pero **sí vuelven en la
  alineación**: `palabras_desde_alineacion()` las filtra o saldrían en los subtítulos. Como
  los corchetes ya son las consultas de stock, un guion con etiquetas no pasa por `--guion`:
  se sintetiza aparte y el plan se arma a mano. Que una etiqueta no se locutó se comprueba
  transcribiendo el mp3, no leyendo la alineación.
- **Los tiempos del TTS marcan cada palabra un poco ANTES de que se oiga.** "¿El corte cae
  en una pausa?" se responde con el silencio medido en el audio, no con esos tiempos.
- La síntesis se cachea por (texto, voz, modelo, velocidad): repetir un plan no cobra. La
  llave puede llevar su propio tope de créditos: es el freno contra un script en bucle.
- **Las voces clonadas de clientes no son material para otros reels** (su voz es suya):
  van en `voces_excluidas.txt` (ver el `.ejemplo`). El criterio es de quién es, no si está
  clonada.

### Lo que whisper no ve
- **Solo escribe palabras.** Un ruido de demostración o una risa no existen para él y el
  corte se cierra encima: `voz.SEGUIR_SONIDO` respeta un sonido que sigue la última palabra.
- **Una palabra de varios segundos es un tapón**: puede esconder habla (una segunda toma
  dicha de corrido). Se buscan palabras de más de ~1.2 s y se mide cuánta voz hay debajo.
- **Palabras de duración cero** (`start == end`) se caen del subtítulo. Se corrigen en la
  caché del proyecto, no en el código: tocar la regla movería los reels ya aprobados.
- **Con el idioma equivocado no falla: TRADUCE**, coherente y sin aviso. Lo delatan
  anglicismos sueltos y bucles de la misma palabra. Se confirma con `language=None` sobre
  tres muestras. El idioma pedido es parte de la clave de la caché.
- **En una pasada larga se come tramos enteros.** Antes de dar por bueno un corte narrativo,
  lista los saltos de más de ~20 s entre palabras y transcribe cada uno por separado.
- **Lo cantado no se elige por transcripción**: whisper no lo escribe o lo escribe en bucle.
  Se deja la ventana entera, sin cortes dentro.
- **Inventa en las costuras** de un material ya cortado. Los captions van quemados: se
  corrige la caché antes de generar.
- `temperature=0.0` es obligatorio (dos corridas iguales). Al cambiar cómo se producen las
  palabras, sube `FORMATO_CACHE` o las cachés viejas ocultan la mejora.
- Una copia de respaldo de una caché **no puede llamarse `cache_*.json`**: las herramientas
  toman `sorted(glob("cache_*.json"))[0]` y se llevan la vieja. Prefijo distinto.

### Los cortes
- Pegados al habla medida (`voz.ajustar`, aire de 0.05 s): con medio segundo de aire por
  lado el reel se siente lento. El ritmo aprobado no se mueve para cuadrar con la música.
- **Un plan de corte narrativo lleva `"pegar_voz": false`.** `voz.ajustar` está hecho para
  cortes en silencio; en uno a media emisión se traga palabras quitadas a propósito. Y
  entonces los tiempos del plan tienen que ser tiempos de palabra del transcript.
- **No partas la palabra**: estira cada límite al borde de la palabra que atraviesa, y
  mientras el hueco a la siguiente sea menor que una pausa real, sigue.
- **Si algo se corta con voz detrás, mide el nivel DENTRO del hueco** de la línea de tiempo,
  no en la ventana siguiente al corte (ahí reanuda el segmento siguiente y todo parece
  cortado). Ventanas de 50 ms distinguen voz (varias seguidas) de un clic (un pico).
- Un clip que empieza o acaba hablando no tiene dónde poner el aire: `voz.ajustar` recibe
  `duracion=` y topa. Se comprueba antes de generar: `ini` mínimo y `fin` máximo del plan
  contra la duración de ffprobe.
- Para cortar en paralelo dos archivos que deben quedar sincronizados (video y un audio
  limpio), **por índice de fotograma**: cortar trozo a trozo con `-ss` suma los redondeos.
  Y `-ss` va antes de `-i`, o ffmpeg decodifica desde el segundo 0.
- **Se revisa leyendo el texto de la línea de tiempo FINAL de corrido.** Los números del
  plan pueden estar bien y faltar una palabra a media frase.

### Subtítulos
- Una palabra por tarjeta; **lienzo de entrega 1080x1920** aunque la fuente sea 4K (el
  tamaño del texto es absoluto). En horizontal el factor de escala se midió en pantalla
  (`ESCALA_TEXTO_HORIZONTAL`) y el caption baja al 86%.
- Entra la palabra que **empieza** dentro del corte; la que viene arrastrando del anterior,
  solo si queda más de la mitad. Un límite entre dos planos contiguos se pone al final de
  una palabra, o sale duplicada.
- Un segmento puede llevar `"captions": false` (una pantalla con texto que leer) y el
  `.srt` para YouTube es entonces el complemento exacto. Si el video ya lleva captions
  quemados de punta a punta, **no se sube el `.srt`**: saldrían dos textos encimados.
- `"caption_altura"` en el plan cuando el cuadro es una composición: mover la constante
  global movería los reels ya aprobados.
- La mejor revisión es **el texto exportado de los captions leído de corrido**: salen
  palabras duplicadas y perdidas que el `.srt` también tenía.

### Audio y música
- **El volumen de la música se mide contra la voz** (`musica.volumen_bajo_voz`, 18 dB
  debajo). Promedio para un reel cortado al ras; **LUFS** para material con pausas, donde
  los silencios hunden el promedio de la voz. Si la pista tiene arco, **se mide en
  ventanas**: una ganancia fija la deja encima de la voz en el tramo final.
- `volumedetect` escribe en el nivel `info`: con `-v error` la medición sale vacía sin error.
- **Al beat se pegan los acentos, nunca los cortes.**
- Para YouTube, **filtrar por licencia antes que por métrica**: una instrumental de canción
  comercial hace que Content ID reclame el video entero.
- Una prueba de música para elegir de oído se normaliza (−16 LUFS) y va en dos niveles.
- El audio de origen sin margen se arregla grabando, no en post (`voz.avisar_audio()`).
  Si hay audio limpiado aparte, se **muxea al archivo de cámara antes de transcribir** y se
  comprueba midiendo que el mux se llevó la pista buena.

### Encuadre y zoom
- **Zoom seco**: escala fija por corte, la mayoría abiertos, uno solo en el pico. Si todo
  está acercado nada destaca. Sigue el sentido: abre en el contexto, cierra en la revelación.
- **El techo se mide** (`encuadre.py --cabeza`), no se supone: en un primer plano cerrado el
  pico de siempre corta la frente. Con fondo que no es pared lisa, el número miente: manda
  mirar el frame. Anclar el zoom arriba (`"ancla"`) pierde camisa en vez de frente.
- **Antes de colocar algo en pantalla, se sacan frames y se miran.** Claude lee las
  imágenes de `proyectos/_encuadre/` directamente.
- El movimiento sobre imágenes fijas va **por ritmo por segundo**, no por recorrido total,
  y nunca arranca en zoom 1.00 (sin recorte no hay paneo). Una imagen fija entra a ffmpeg
  con `-framerate` antes de `-loop`, o cada escena dura 5/6. Se mide sobre el archivo que se
  publica (el del proyecto de CapCut), no sobre el MP4 de revisión.

### Sonidos, efectos y cifras
- Reglas en `sonidos.py`: nunca dos a la vez (≥0.5 s), por prioridad y no por tiempo; el
  swish con cupo; el pop no suena en "por ciento" ni "de cada diez". **Qué parte del
  archivo suena**: un riser suena al final; recortar el principio deja un segundo mudo.
- Un video largo lleva `"sfx": false` y `"efectos": false`: los golpes de reel sobre una
  charla se sienten pegados. **Uno de más se nota mucho más que uno de menos**; variar es
  rotar, no acumular.
- Un recurso de la biblioteca que dejó de estar descargado **se caía sin una línea**; ahora
  se avisa por nombre. Ojo: la carpeta del recurso puede existir con solo `<hash>_tmp` (la
  descarga no terminó). Se arregla aplicándolo una vez en CapCut y `biblioteca.py --guardar`.
- **Cuáles cifras y cuál frase merecen pantalla es criterio**: el detector propone la edad
  de alguien y la hora del día. Una cifra larga se sale del lienzo sin error (se encoge
  sola, pero por debajo de ~0.65 está mal escrita: 10-12 caracteres). Una frase clave de
  tres líneas tapa la boca: tres palabras. **El nombre de una fuente miente**: mira el
  archivo al que resuelve.
- Los overlays (subrayados, círculos) solo sirven con **alfa real**, y su escala se calcula
  midiendo el alfa (`adornos.py`), no a ojo. Bajo un b-roll a pantalla completa no se ven.

### Video animado
- **`frame(t)` es determinista** (el azar se siembra con el cuadro y el lienzo se limpia en
  cada uno): vista previa y render son el mismo dibujo, y un cambio del motor se valida
  comparando capturas de antes y después píxel a píxel.
- **Las mismas reglas de marca que las miniaturas y las cortinillas**: las cifras de la
  fuente primaria (con URL y fecha en `escenas.js`), el logo como archivo real —nunca
  dibujado ni generado—, y si las tipografías de la marca son de licencia privada, un
  parecido libre y se dice.
- **Se revisa por la hoja de capturas antes del render completo** (`--fotos`). Lo que salió
  así, y nada daba error: un personaje de terminal aplastado (ahí el pixel es 1:2,
  `sprite(..., { aspecto: 2 })`), monedas encima del texto, el pie empujado fuera del cuadro
  por el zoom del cierre (lo fijo va fuera de `cam()`), y un dato de comparación tachado
  que se leía como «falso».
- Un `.mov` transparente se comprueba leyendo **todos** los cuadros y contando los píxeles
  opacos: con qtrle, `-ss` puede devolver un cuadro anterior.

### Tarjeta de cierre y cortinillas
- La tarjeta «video completo en YouTube» va **encima de los últimos ~2 s**, no pegada al
  final: cuesta cero segundos y el bucle sigue entrando al gancho. Detalle en
  `recursos/cta/LEEME.md` (mide la pastilla sólida, no el alfa).
- **En reels no van cortinillas**: rompen el bucle y un sello de intro cuesta en 35 s lo que
  en 14 minutos no se nota. En un video largo sí: la de cierre deja libre la mitad donde van
  las tarjetas de la pantalla final.
- Placas, cortinillas y logos **no se dibujan aquí**: los hace una persona. Aquí se miden,
  se colocan y se verifica el `@` contra la fuente en vivo.

### Clips verticales de un video largo
- **Una sola pieza continua**, con el gancho sacado de dentro de esa pieza. Tres tramos
  distantes pegados no se entienden. Primero se elige el tramo, luego el gancho.
- **35-60 s**: por debajo de ~25 s es un gancho sin remate. Un clip cierra su propia idea;
  no tiene que resolver la tesis del largo.
- **Recortar, no encajar**: la franja central de 608x1080 escalada a 1080x1920, mirando un
  frame. De una **demo de pantalla** no se recorta: se arma en dos piezas editables
  (documento arriba, webcam como overlay).
- El gancho repetido al inicio (arranque en frío) exige generar con `--sin-tomas`, o
  `tomas.py` lo toma por toma repetida y se lo lleva. Si el clip ya abre fuerte, no se toca.
- El b-roll apaisado en lienzo vertical sale en franja: `escala_para_llenar()`.

### Video largo
- **El editor quita silencios, no divagaciones.** El corte narrativo lo decide Claude
  leyendo el `guion.txt` numerado, con el motivo de cada tramo en `notas`. El usuario
  decide el gusto.
- `tools/planos.py` parte los planos largos donde el hablante respira, sin mover el audio.
  Los planos cerrados se declaran en `"momentos"`, en segundos del ORIGINAL.
- `tools/repeticiones.py` caza los arranques falsos que `tomas.py` no ve; una enumeración
  se parece a una repetición y no se toca. En una demo, correrlo es lo primero.
- **B-roll ~20% como referencia**, no como objetivo: ilustra y **tapa las costuras**, y eso
  hay que pedirlo (cruzar los puntos donde reanuda el audio contra las ventanas de b-roll).
  Nunca sobre una cifra ni sobre un plano cerrado declarado.
- **Todo video de YouTube se entrega con capítulos** (el primero en 0:00, tres o más,
  comprobados contra lo que se dice en ese segundo). Todo lo legible de la miniatura, en
  el 85% superior. **La cara de la miniatura sale de un fotograma real**: la IA compone
  alrededor, y aun así el parecido se comprueba mirando.
- Si el usuario ya trabajó el draft a mano (captions corregidos, audio limpio pegado),
  **regenerar desde `plan.json` borra su trabajo**: se copia el draft y se le añade encima.

### Compartir con quien edita
- `exportar.py` arma el paquete en una carpeta temporal y **lo renombra al final** (si no,
  alguien la manda a medias), copia solo los archivos que definen el proyecto, y verifica
  que estén los tres botones. **El peso delata el error**: una devolución buena pesa pocos
  MB; si pesa cientos, es el paquete de ida.
- Los `.ps1` paran si se abren **desde dentro del ZIP** (Windows lo extrae a un temporal que
  luego borra). Si el nombre ya existe en su CapCut, se instala al lado, nunca encima.
- Efectos, transiciones y animaciones **no viajan** (son shaders de la caché): se avisan por
  nombre y el instalador comprueba en su caché **por hash**, no por id de carpeta. Los que
  requieren CapCut Pro se marcan.
- `importar.py` **recorre todas las claves con ruta, no una lista fija**: CapCut suma claves
  en cada versión y lo que no resuelve lo descarta en silencio.
- **En el paquete, quien recibe no conoce el proyecto**: cada paso que se da por sabido es
  un viaje perdido. El LEEME empieza desde que baja el ZIP.

## Aprender el estilo de alguien

El criterio que trae el repo es el de **un** usuario. Para otro, el método que funciona es
siempre el mismo y es más rápido que teorizar: **pedirle que edite un pedazo a mano y
medirlo** (`analizar_sonido.py`, `analizar_visual.py`, o leyendo el draft). Cuando no hay
nada suyo que medir, **generarle versiones que solo difieran en lo que se está probando** y
que elija. Lo medido se escribe aquí y en el módulo, con de dónde salió. Y **un número
medido vale para la toma en la que se midió**: si algo aprobado se va derivando, se vuelve
a medir.

## Pruebas y limpieza

- `python tools/pruebas.py`: sin dependencias de red. Cubre lo que decide qué se corta y cómo
  se mueve la cámara, lo que no se debe cortar, y los fallos que ya mordieron en silencio.
  **"Todo en orden (N saltadas)" no es "Todo en orden"**: las pruebas con audio real se
  saltan si no declaras tus reels de referencia en `proyectos/_pruebas.json` (formato al
  principio de `pruebas.py`). Antes de tocar el pipeline, toma las huellas de tus reels
  aprobados: `python tools/pruebas.py --huellas "<proyecto>"`.
- Un script que corrige datos se prueba **corriéndolo dos veces seguidas** y escribe el
  valor exacto, nunca un reemplazo (`"x" -> "xs"` dos veces da `"xss"`).
- `tools/limpiar.py` nunca borra sin preguntar y conserva lo que está en `CACHES` (lista
  explícita), lo que tiene `plan_aprobado.json` y lo que tiene `CONSERVAR.txt`. Antes de
  borrar medios, se cruzan contra los drafts vivos de CapCut: un draft sin sus medios no da
  error hoy, lo dice CapCut días después.

## Lo que no viaja en el repo

`proyectos/` (tus videos, transcripciones y planes), las llaves (`.secrets/`), los sonidos
de usuario y las tarjetas de cierre (cada quien las suyas), `voces_excluidas.txt`, y los
efectos de CapCut que cada quien no tenga descargados.

## Skills

- **`revisar-reel`** — la revisión editorial. Es donde está el valor; incluye cómo aprender
  el estilo de una persona nueva.
- **`destilar-herramienta`** — analizar una herramienta externa y sacarle mejoras. Lo ya
  analizado está en `IDEAS.md`: revisarlo antes de re-analizar algo.
- **`video-animado`** — videos y motion graphics dibujados a mano por código (`animado/`).
  Se pide con «hazme un video animado de…».
