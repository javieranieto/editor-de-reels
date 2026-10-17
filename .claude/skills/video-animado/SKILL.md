---
name: video-animado
description: Del editor de reels (la herramienta vive en animado/). Hace un video animado "dibujado a mano" por código (canvas + Chrome + ffmpeg) — lanzamientos, explicaciones, cifras, comparativas, un personaje de marca — o un motion graphic con fondo transparente para poner encima de un reel o video largo en CapCut. Úsalo cuando pidan "un video animado", "una animación", "motion graphics", "un explainer" o "un video de lanzamiento/presentación".
---

# Video animado dibujado a mano

La herramienta está en `animado/` y las
rutas de aquí son relativas a la raíz del repo. Todo el detalle en `animado/LEEME.md`.
`animado/videos/ejemplo-alcaraz/` es la referencia para un video completo y
`animado/videos/ejemplo-dato/` para una capa transparente: **copiar su estructura, no
empezar de cero.**

## Antes de dibujar, tres preguntas

1. **¿Video completo o capa encima?** Completo = MP4 con fondo (16:9 o 9:16). Capa =
   `--alfa`, un `.mov` transparente que va en una pista de CapCut sobre su video.
2. **¿De qué marca?** Define paleta, tipografías, logo y handle. Los datos de marca se
   sacan del **código en vivo** del sitio (su CSS, su configuración), no de memoria ni de
   un documento.
3. **¿Qué cifras?** Cada número viene de la **fuente primaria** y se anota en
   `escenas.js` con su URL y fecha. Un número sin fuente no entra.

## Proceso

1. **Investigar y guardar los datos** con su fuente. Descartar lo que solo digan
   agregadores.
2. **Conseguir los assets reales**: el logo en vector del sitio oficial, las fuentes (si
   son de licencia privada, un parecido libre de Google Fonts, y decirlo). **Nunca se
   dibuja ni se genera un logo.** Cada fuente nueva se anota en `animado/fuentes/LEEME.md`
   con la licencia leída del archivo.
3. **Elegir la música y medirla primero** con `pipeline/musica.py` (`analizar`,
   `rejilla`). Las escenas se cortan en los beats (a 120 BPM un compás de 4 tiempos dura
   2 s). Música libre de derechos de verdad: Kevin MacLeod (CC BY, lleva crédito) o la
   biblioteca de audio de YouTube.
4. **Guion por escenas**: una idea por escena, texto corto (se lee en 2 s), un personaje
   que hace algo en cada una. Alternar fondos claro y oscuro para que cada corte se note.
5. **Escribir `animado/videos/<nombre>/escenas.js`** copiando el de `ejemplo-alcaraz`: la
   paleta, `configurar()`, `CUT` con los beats, y una `escena()` por escena. Lo fijo en
   pantalla (créditos, pies) va fuera de `cam()`.
6. **Revisar por capturas**: `python animado/render.py <nombre> --fotos ...` con una
   captura al final de cada escena, y **abrir `hoja.png`**. Aquí salen los textos
   encimados, lo que se sale del cuadro y los personajes mal proporcionados (un personaje
   de terminal lleva `aspecto: 2`). Nada de eso da error.
7. **Render completo** y `audio.json` con los efectos en su segundo (swish 0.13 s antes
   del corte, pops en los datos, uno cada ~3 s como máximo).
8. **Comprobar el archivo**, no el log: duración con ffprobe, LUFS por ventanas, y
   cuadros sacados **del MP4 final**. Si es `--alfa`, contar píxeles opacos en todos los
   cuadros (`-ss` sobre qtrle puede devolver un cuadro anterior).

## Lo que se le dice al entregar

- Ruta del archivo, duración, resolución y peso.
- De dónde sale cada cifra.
- Qué se sustituyó (tipografías) y qué crédito lleva la música.
- Si usa la marca de otro, que es un video **no oficial** y no se presenta como si lo
  fuera. Y la marca de otro se usa solo con el archivo real de su logo.
