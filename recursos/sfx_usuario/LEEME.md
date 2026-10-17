# Sonidos de usuario — los pone cada quien

El editor coloca **cuatro sonidos** en el reel, con reglas medidas de una edición real
(ver `pipeline/sonidos.py`):

| Archivo | Qué es | Dónde va |
|---|---|---|
| `riser.mp3` | un sonido que crece y revienta al final | abre el video, en 0.00 s |
| `reveal.mp3` | un "aparece algo" corto | una sola vez, en la primera cifra en pantalla |
| `swish.mp3` | un barrido de aire | en los cortes que separan escenas, con cupo |
| `pop.mp3` | un golpe corto | en cada número que carga la frase |

Vale `.mp3`, `.wav` o `.m4a` con ese nombre (`riser.wav` sirve igual).

## Por qué la carpeta viene vacía

Los que usaba la agencia de origen salieron de la biblioteca de CapCut. Su licencia vale
**dentro de CapCut**, no para redistribuirlos en un repositorio. Cada quien pone los suyos.

**Sin sonidos el editor funciona igual:** el reel sale sin efectos de sonido y lo avisa en
una línea. Si falta solo alguno, ese no suena y los demás sí.

## De dónde sacarlos

1. **De tu propio CapCut**, para usarlos en tus proyectos de CapCut: aplica el sonido una vez
   en un proyecto y búscalo en `%LOCALAPPDATA%\CapCut\User Data\Cache\music`. Cópialo aquí
   con el nombre de la tabla. Se quedan en tu computadora (git ignora esta carpeta).
2. **Libres de verdad (CC0):** `recursos/sfx/` trae cuatro de Openverse (`riser.wav`,
   `pop.wav`, `whoosh.wav`, `impacto.wav`, créditos en `creditos.txt`). Copia `riser.wav` y
   `pop.wav` tal cual, y `whoosh.wav` como `swish.wav`, y ya tienes tres de cuatro.
3. [Freesound](https://freesound.org) filtrando por licencia CC0.

⚠️ **Qué parte del archivo suena importa.** Un riser dura varios segundos y lo que suena es
el **final**; recortar el principio deja un segundo mudo. `sonidos.donde_suena()` lo
detecta comparando el nivel de las dos mitades, así que un riser propio funciona sin
configurar nada.

⚠️ **El gusto se mide, no se supone.** Si tus sonidos o tu densidad no son los de estas
reglas, edita un reel a mano con lo que te gusta y mídelo con
`python tools/analizar_sonido.py "<proyecto>"` (ver el skill `revisar-reel`).
