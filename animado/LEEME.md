# Videos animados dibujados a mano

Un video que **no se graba ni se edita: se dibuja con código**. Cada cuadro lo pinta
Chrome sobre un canvas, con trazos que tiemblan a 12 fps como en la animación a mano,
y ffmpeg lo junta en un MP4 con música y efectos.

Sirve para lo que un video grabado no puede contar bien: **lanzamientos, explicaciones,
cifras, comparativas, un personaje de marca**. Y con `--alfa` sale con fondo
transparente para ponerlo **encima** de un reel o un video largo en CapCut, como un
motion graphic: una tarjeta que se dibuja sola, una cifra que se encierra en un círculo.

## Requisitos

`pip install playwright` y **Chrome** instalado (si no lo hay, el render usa el Chromium de
Playwright: `python -m playwright install chromium`). ffmpeg/ffprobe para el MP4 y el
`.mov`; Pillow para la hoja de capturas. `render.py` dice cuál falta.

## Comandos

Desde la raíz del repo:

```bash
python animado/render.py <video> --fotos 1 5 9.5   # capturas + hoja.png para revisar
python animado/render.py <video>                   # MP4 final con audio
python animado/render.py <video> --alfa            # .mov transparente para CapCut
python animado/render.py <video> --ver             # vista previa en vivo (&t=12 = desde el 12)

python animado/render.py ejemplo-dato --fotos 0.3 1.2 2.8 --alfa   # el ejemplo más chico
```

`<video>` es una carpeta de `animado/videos/`. La salida va a `proyectos/animado/<video>/`
(fuera de git); `--salida` la manda a otro lado (con `--fotos`, es la carpeta de capturas).
En la hoja, **el rosa es transparente**.

## Cómo está armado

| Archivo | Qué es |
| --- | --- |
| `motor.js` | Lo común: trazos a mano (`line`, `poly`, `rect`, `blob`, `hatch`, `arcHand`, `arrow`, `swoosh`), texto con revelado (`txt`), fondos de papel, cámara con zoom y sacudida (`cam`, `punch`, `shakeAt`), personajes de pixeles (`sprite`), utilería (monedas, bichos, trofeo, maletín, cursor, líneas de código) y el cuadro `frame(t)` |
| `videos/<nombre>/escenas.js` | Lo de ESE video: su paleta (`Object.assign(C, {...})`), `configurar({...})` (lienzo, salida, duración, fuentes, fondos) y sus escenas con `escena(inicio, fin, fn)` |
| `videos/<nombre>/audio.json` | Música, efectos con su segundo exacto y el LUFS final. Si no existe, el video sale mudo |
| `videos/<nombre>/assets/` | Logos y archivos propios del video (se cargan con `imagen()`) |
| `fuentes/` | Tipografías libres (OFL, ver su `LEEME.md`) |
| `render.py` | Captura cada cuadro con Playwright y codifica con ffmpeg |

Un video nuevo = una carpeta nueva con su `escenas.js`. El motor no se toca.

- `videos/ejemplo-dato/` — el mínimo: un dato de 3 s, vertical, con fondo transparente.
- `videos/ejemplo-alcaraz/` — el que se copia para un video completo: dos escenas de 16:9
  con fondos claro y oscuro, cámara, un personaje de pixeles y un pie fijo. Es del negocio
  demo ficticio (Servicios Alcaraz).

Las rutas de `fuentes` y de `imagen()` son relativas a `animado/`; las de `audio.json`,
relativas a la raíz del repo. Una familia que el video usa y no declaró (`header()` usa `Pix`) no
da error: el navegador pone otra letra. Se ve en la hoja.

```json
{
  "musica": {"archivo": "recursos/sfx_usuario/mi_pista.mp3", "desde": 0, "volumen": 0.55, "fade_out": 1.5},
  "efectos": [
    {"archivo": "recursos/sfx/riser.wav", "en": 0, "recorte": 1.8},
    {"archivo": "recursos/sfx/whoosh.wav", "en": 2.87},
    {"archivo": "recursos/sfx/pop.wav", "en": 4.2}
  ],
  "volumen_efectos": 0.6,
  "lufs": -14
}
```

## Lo que costó el primero, y vale para todos

- 🔑 **`frame(t)` es determinista.** El azar de los trazos se siembra con el cuadro y el
  lienzo se limpia en cada cuadro, así que la vista previa y el render dibujan exactamente
  lo mismo, y un cambio en el motor se comprueba comparando capturas de antes y después
  píxel a píxel.
- 🔑 **Los cortes caen en la música.** La rejilla sale de `pipeline/musica.py`
  (`analizar` + `rejilla`) y las escenas se declaran por tiempos de beat, no a ojo.
- 🔴 **Las cifras se sacan de la fuente primaria**, y se anotan en `escenas.js` con su URL
  y la fecha en que se comprobaron. Un agregador puede citar un número que la página
  oficial no tiene: ese número no entra.
- 🔴 **El logo es el archivo real, nunca dibujado ni generado.** Las tipografías de una
  marca suelen tener licencia privada: se usa un parecido libre y se dice.
- ⚠️ **Un personaje que imita una terminal lleva pixeles de 1:2.** Hecho con pixeles
  cuadrados sale aplastado: en la terminal cada bloque es el doble de alto que de ancho.
  `sprite(..., { aspecto: 2 })`.
- ⚠️ **Lo que va fijo en pantalla (créditos, pies) se dibuja FUERA de `cam()`.** Con el
  zoom lento de un cierre, los pies de página se salen del cuadro en el último segundo.
- ⚠️ **Tachar un dato de comparación dice «falso».** El dato viejo contra el nuevo va en
  gris, sin tachar.
- 🔑 **Se revisa por capturas antes del render completo** (`--fotos`, una al final de cada
  escena, y se abre `hoja.png`), y al terminar se sacan cuadros **del MP4 final**, no de
  los PNG. Así salen monedas encima del texto, un «%» fuera de su sello o un personaje
  parado donde no va. Ninguno da error.
- ⚠️ **Para revisar un `.mov` transparente, `-ss` puede mentir.** Con qtrle, pedir un
  segundo puede devolver un cuadro anterior. La comprobación buena lee **todos** los
  cuadros y cuenta los píxeles opacos de cada uno.
- 📌 **Música libre de verdad**: la de Kevin MacLeod (CC BY) exige el crédito, y va en el
  pie del cierre. La de un pack de recursos no es libre solo por venir en el pack.
