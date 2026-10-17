# Video largo (YouTube, horizontal)

De una o varias tomas a un proyecto de CapCut armado: el corte por frases, los tiempos
medidos en el audio, subtítulos limpios, stock y —en las siguientes versiones— gráficos
animados, gancho y reels sacados del largo.

**La idea:** lo editorial lo decide quien edita (o Claude, que es lo normal) en tres archivos
de texto. Lo mecánico lo hacen los pasos. El código no sabe de qué trata tu video.

| Archivo | Quién lo escribe | Qué dice |
|---|---|---|
| `orden.json` | tú o Claude | qué frases van y en qué orden |
| `texto_limpio.txt` | tú o Claude | lo que se dijo, bien escrito (para subtítulos) |
| `stock.json` | tú o Claude | qué video de stock va en qué frase |

## Los pasos

```bash
python largo.py preparar "mi video" --toma A="C:\videos\toma.mp4" --toma R="C:\videos\retomas.mp4"
#   -> legible_A.txt: léelo y escribe orden.json
python largo.py cortar   "mi video"     # orden.json -> el corte medido en el audio
python largo.py revisar  "mi video"     # escucha cada tramo suelto y marca lo que no cuadra
python largo.py amarrar  "mi video"     # subtítulos (escribe un texto_limpio.txt la 1.a vez)
python largo.py stock    "mi video"     # baja el stock; MIRA hoja_stock.jpg
python largo.py armar    "mi video" --nombre "Mi video LARGO"     # CapCut cerrado
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

## Para Claude

Si alguien te dice *«edita este video»*: corre `preparar`, lee la transcripción completa,
entiende de qué habla y para quién, y **propón** qué sale (el largo, cuánto dura, qué se
queda fuera y por qué) antes de escribir `orden.json`. Escribe el motivo de cada tramo en
`nota`. Después `cortar` → `revisar` (arregla lo que marque) → `amarrar` (escribe tú el texto
limpio) → `stock` (mira la hoja) → `armar`. Cuenta en qué se fue cada decisión: el usuario
decide el gusto.
