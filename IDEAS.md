# Bitácora de ideas destiladas

Herramientas externas que ya se analizaron y qué se tomó de cada una. El proceso está en el
skill `destilar-herramienta`. **Antes de analizar una herramienta, busca aquí si ya se hizo.**
Una entrada nueva va al final, con fecha, qué se tomó, qué se descartó y por qué.

El patrón que se repite: casi ninguna se adopta entera, porque **casi todas entregan un MP4
cerrado** y este editor existe para entregar un **proyecto de CapCut editable**. Lo que vale
es una decisión de diseño validada con datos, enterrada en su código.

---

## OpenShorts — github.com/mutonby/openshorts (MIT)

Extrae clips virales de videos largos con Gemini, reencuadra a 9:16 y dobla con ElevenLabs.

- **Descartado adoptarla:** resuelve otro problema, exige Docker y tres APIs de pago.
- **Tomado — fusión de fragmentos de palabra:** faster-whisper marca el límite de palabra con
  un espacio inicial; un token sin él (`%`, `.200`) continúa el anterior. Sin fusionarlo,
  "44%" sale partido en dos captions. → `pipeline/transcribe.py`.
- **Tomado — envolvente asimétrica y densidad del punch:** entra rápido, sostiene, suelta
  lento; más de ~3 punches por minuto se siente como tic; tope ~15%. → `pipeline/zoom.py`.
- **Mejora sobre ellos:** disparan el punch con picos de audio y su propio código anota que el
  transcript sería mejor fuente. Aquí se dispara por estructura del habla (la frase tras una
  pausa larga, las que traen cifras).
- **Efecto secundario:** probar sus ideas contra material real destapó que la transcripción
  no era determinista (se fijó `temperature=0.0`).

## video-use (browser-use) — github.com/browser-use/video-use (MIT)

Skill de Claude Code para editar video conversando; renderiza un MP4 final.

- **Tomado — sus "Hard Rules":** 30 ms de fade en cada borde de corte (`render.py`). Se midió
  antes de adoptarlo: los bordes ya caían entre −66 y −44 dB, así que es un seguro barato,
  no una urgencia. Vale medir antes de creerle a una regla ajena.
- **Anotado:** corrección de color automática acotada a ±8% por eje.

## hyperframes-student-kit (MIT el código)

Motion graphics en HTML + GSAP renderizados con Chrome headless.

- **Descartado:** Node, Chrome, 16 GB de RAM y MP4 final.
- **Anotado:** la idea de overlays animados sí sirve, pero se hace con un `.mov` con canal
  alfa generado aquí e insertado como una capa más.

## OpenCut — github.com/OpenCut-app/OpenCut (MIT)

Alternativa abierta a CapCut.

- **Nada que tomar:** es un editor, no una librería, y no tiene edición automática. Guarda
  proyectos en IndexedDB, no en archivos. Revisarlo solo si algún día exporta un formato de
  proyecto en archivo: ahí sería un refugio si CapCut cambia su formato.

## Reels de guion con voz en off — OpenReels, AutoShorts AI y otros

- **Descartado adoptar:** los cinco revisados entregan MP4 cerrado.
- **Tomado — verificar que el stock ilustre la escena** (umbral 0.6) → `pertinencia.py`.
- **Tomado — partir una escena larga en dos clips:** el plano fijo largo delata al video
  automático.
- **Confirmado:** el plan revisable (`plan.json` + `--desde-plan`) es el mismo patrón al que
  llegó OpenReels por su cuenta.
- **Adoptado — las APIs:** ElevenLabs con `/with-timestamps` (tiempos de palabra exactos, sin
  transcribir) y Pixabay como segunda fuente de stock.

## Proyectos de Claude Code + CapCut — pireel, cutcli-cookbook, capcut-ai-editor y otros

- **Descartado:** la arquitectura que proponen (Claude para el criterio, ffmpeg para lo
  determinista, draft de CapCut como salida) es literalmente este proyecto.
- **Confirmado:** el sistema de coordenadas de CapCut (centro 0,0; arriba +1; evitar ±1).
- **Hallazgo grande:** el cookbook documenta los keyframes de escala como `scale_x` y
  `scale_y`. pycapcut traduce `uniform_scale` a solo el eje X: lo que salía era un estirón,
  no un zoom. → `capcut_lib._kf_escala()` escribe los dos ejes.
- **Tomado:** avisar de los recursos que requieren CapCut Pro al exportar
  (`exportar._es_vip()`), porque quien recibe el paquete puede no tenerlo.
- **Probado y descartado:** puntuar palabras de énfasis para elegir el zoom. Medido contra
  revisiones ya hechas, empeoró la coincidencia. La carga de la prueba la tenía el cambio.

## auto-editor — github.com/WyattBlue/auto-editor (Unlicense)

La referencia del corte por silencios.

- **Descartado:** corta por nivel de audio a secas y no exporta a CapCut.
- **Confirmado:** constantes parecidas por caminos independientes (clip mínimo, corte
  mínimo, margen más generoso al final que al principio).
- **Probado y descartado:** avisar de cortes menores a 0.2 s. Saltaba sobre material ya
  aprobado: un aviso que salta sobre lo bueno enseña a ignorar los avisos.
- **Tomado:** medir la salud del audio de origen (pico y rango) → `voz.avisar_audio()`.

## Editar por transcript: el estado del arte

Gling, Descript, rescript, CutScript, FunClip, ClipsAI, Premiere y Resolve con texto.

- **Confirmado:** el corte grueso de un video hablado se decide leyendo, no escuchando, y
  nadie automatiza el corte narrativo: lo decide alguien. Aquí ese alguien es Claude con el
  `guion.txt` numerado.
- **Anotado:** FunClip / ClipsAI para ELEGIR momentos de un largo hacia clips; una
  herramienta chica que calcule el rango de palabras a quitar a partir de una frase.
