# Video largo (YouTube, horizontal)

De una o varias tomas a un proyecto de CapCut armado: el corte por frases, los tiempos
medidos en el audio, subtítulos limpios, stock, gráficos animados con tu marca y reels
verticales sacados del largo.

**La idea:** lo editorial lo decide quien edita (o Claude, que es lo normal) en tres archivos
de texto. Lo mecánico lo hacen los pasos. El código no sabe de qué trata tu video.

| Archivo | Quién lo escribe | Qué dice |
|---|---|---|
| `orden.json` | tú o Claude | qué frases van y en qué orden |
| `texto_limpio.txt` | tú o Claude | lo que se dijo, bien escrito (para subtítulos) |
| `stock.json` | tú o Claude | qué video de stock va en qué frase |
| `escenas.json` | tú o Claude | qué gráfico animado va en qué idea (ver `largo/motion.py`) |
| `reels.json` | tú o Claude | qué reels salen del largo (ver `largo/reels.py`) |

## Los pasos

```bash
python largo.py preparar "mi video" --toma A="C:\videos\toma.mp4" --toma R="C:\videos\retomas.mp4"
#   -> legible_A.txt: léelo y escribe orden.json
python largo.py cortar   "mi video"     # orden.json -> el corte medido en el audio
python largo.py revisar  "mi video"     # escucha cada tramo suelto y marca lo que no cuadra
python largo.py amarrar  "mi video"     # subtítulos (escribe un texto_limpio.txt la 1.a vez)
python largo.py stock    "mi video"     # baja el stock; MIRA hoja_stock.jpg
python largo.py motion   "mi video"     # los gráficos de escenas.json con tu marca; MIRA las hojas
python largo.py armar    "mi video" --nombre "Mi video LARGO"     # CapCut cerrado
python largo.py reels    "mi video"     # los reels de reels.json, cada uno ya armado en CapCut
python largo.py miniatura "mi video"    # cuadros candidatos (MIRA candidatos.jpg) ...
python largo.py miniatura "mi video" --componer     # ... y las miniaturas de miniatura.json
python largo.py aprender "mi video" --capcut "Mi video LARGO"   # después de editarlo tú
```

`"mi video"` vive en `proyectos/mi video/`. Puedes tener tomas A (principal) y R (retomas):
las frases que repetiste en otra toma se piden de ahí.

## `orden.json`

```json
[
 {"toma": "A", "desde": "al principio te dije", "hasta": "ni tampoco tuya", "despues": 180,
  "etiqueta": "la culpa", "nota": "primera toma, la completa"},
 {"toma": "A", "desde": "el ultimo anuncio que pagaste", "hasta": "que me escriba", "despues": 292,
  "etiqueta": "la tarea", "abre_en": 291.75}
]
```

- `desde` y `hasta` son **frases**, palabra por palabra como las dijo Whisper (en
  `legible_*.txt`). Sin acentos ni mayúsculas importan; las palabras sí.
- `despues` es el segundo a partir del cual se busca la frase. **Siempre se pone**: una frase
  que repetiste tres veces existe tres veces, y sin `despues` se agarra la primera.
- De lo que repetiste, quédate con **la última toma que salió completa**.
- Opcionales: `arranca_en` (el tramo empieza en ese segundo), `abre_en` (abre ahí aunque la
  voz sea tan bajita que parezca silencio) y `quitar` (frases o `[ini, fin]` a sacar de dentro).

## Trampas que ya salieron (y cómo se ven)

- **Whisper pone la primera palabra de una frase en otro lado.** Si te detienes después de
  «al» y retomas en «principio», Whisper puede dejar el «al» 8 segundos antes. Se ve en
  `legible_*.txt` como una palabra suelta al final del renglón anterior. Qué hacer: pide la
  frase desde la palabra siguiente y **mide dónde vuelve la voz** (o deja que `cortar` la
  encuentre): si la palabra quedó separada por silencio, usa `abre_en`; si de verdad la
  dijiste antes de una pausa larga, usa otra toma de esa frase.
- **En `revisar`, un «insert» de UNA palabra al principio de un tramo casi siempre es bueno**:
  es justo esa palabra que Whisper había puesto en otro lado y que el corte sí recuperó. Una
  palabra de más al FINAL suele ser el arranque de la frase siguiente colado: termina el tramo
  en una frase completa en vez de partirla.
- **Una diferencia de una letra** («contestas» / «contamos») suele ser Whisper dudando en un
  pedazo corto. Compara con la transcripción completa antes de mover nada.
- **El texto limpio no agrega ni quita palabras dichas.** Corrige ortografía, cifras y
  puntuación. Si dice algo distinto del corte, `amarrar` avisa (menos del 85 % amarrado).
- **Un buscador de stock nunca dice «no tengo».** Por eso existe `hoja_stock.jpg`: mírala. Un
  clip de alguien ABRIENDO una puerta salió para «le cierra la puerta». Las consultas en
  inglés, cortas y literales.
- **CapCut cerrado** para `armar`, y si ya editaste el proyecto a mano, volver a armarlo lo
  borra: genera con otro `--nombre`.

## Gráficos y reels: lo que ya se aprendió

- **Un tiempo es una FRASE**, nunca segundos: `{"frase": "agarra el último anuncio", "mas": -0.1}`.
  `python largo.py motion "<p>" --revisar` comprueba que existan todas antes de capturar.
- **L** = tarjeta a un lado mientras la persona habla; **P** = panel que ocupa la pantalla. Una
  idea por gráfico, y ninguna tarjeta pasa segundos vacía esperando su primera fila (ponle título).
- **Mira la hoja de cuadros y un cuadro encima del video**: que no tape la cara.
- **Un reel es UNA pieza continua del largo** (35-60 s) con el gancho sacado de dentro de esa
  pieza. La ventana no cae sobre el gancho ni sobre los últimos 2 s; la frase clave va fuera de la
  ventana (si choca, `reels` avisa y la quita: ánclala antes).
- **Un proyecto de CapCut con el mismo nombre no se sobreescribe**: puede que ya lo editaste.

## Música, miniaturas y tu estilo

- **Música:** `musica.json` con `{"archivo": "musica.mp3"}`. El volumen se **mide** contra tu
  voz (LUFS, 18 dB debajo); no lo pongas a ojo. La pista tiene que ser libre: de una biblioteca
  sin derechos, o generada (Magnific, por ejemplo). Una canción con derechos te silencian el video.
- **Si tu voz se grabó bajita** (−30 LUFS o menos), todo el video sale bajo: súbela al exportar.
- **Miniaturas:** la cara sale de un cuadro REAL. El detector escoge cuadros con la cara grande y
  nítida, pero **no sabe si tienes los ojos cerrados**: mira `candidatos.jpg`. Texto a la
  izquierda, la cara a la derecha, todo en el 85 % de arriba; revisa la vista de 320 px.
- **Aprender tu estilo:** cada `armar`/`reels` guarda cómo salió el proyecto. Edítalo en CapCut
  como siempre y corre `aprender`: dice qué quitaste, si apretaste los cortes, el volumen, el
  zoom y los textos corregidos. Lo que se repita en dos o tres videos se escribe en
  `mi_estilo.md` (raíz del repo, solo en tu máquina) y Claude lo aplica la próxima vez.

## Para Claude

Si alguien te dice *«edita este video»*: corre `preparar`, lee la transcripción completa,
entiende de qué habla y para quién, y **propón** qué sale (el largo, cuánto dura, qué se
queda fuera y por qué) antes de escribir `orden.json`. Escribe el motivo de cada tramo en
`nota`. Después `cortar` → `revisar` (arregla lo que marque) → `amarrar` (escribe tú el texto
limpio) → `stock` (mira la hoja) → `motion` (mira las hojas) → `armar` → `reels`. Cuenta en qué se fue cada decisión: el usuario
decide el gusto.
