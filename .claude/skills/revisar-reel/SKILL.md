---
name: revisar-reel
description: Del editor de reels. Edita un reel con criterio editorial en vez de dejarlo al automático — decide qué cortes se quedan, dónde va el énfasis del zoom, qué cifras se resaltan, dónde entra el b-roll y qué se subraya con sonido. Úsalo cuando alguien pida revisar, mejorar o "que tú cortes" un video ya procesado por el editor, o cuando el resultado automático no convenza.
---

# Revisar un reel con criterio

Todo lo de aquí se corre **desde la raíz de este repo**
(`cd editor`). Las lecciones técnicas están en `CLAUDE.md`.

El pipeline automático corta bien silencios, muletillas y tomas repetidas. Lo que **no**
sabe hacer es entender de qué habla el video: cuál frase carga el argumento, qué divaga,
dónde está el gancho, qué cifra merece pantalla. Eso es esta revisión, y es donde está el
valor real del proyecto.

## Principio

**Leer el guion como editor, no como corrector.** El automático ya limpió; aquí se decide
qué se cuenta y con qué énfasis. Casi siempre el resultado es *más corto* que el
automático, no más largo.

## Proceso

### 1. Leer

```
proyectos/<nombre>/guion.txt    ← transcripción anotada y numerada por segmento
proyectos/<nombre>/plan.json    ← los segmentos exactos
```

El `guion.txt` marca cada frase con su segmento (`#5`, `#15-16`) o como `FUERA silencio` /
`FUERA toma repetida`, y termina con un índice por segmento con su duración. **Revisar
también lo que salió**: el detector puede llevarse algo que hacía falta — un gancho entero
tomado por toma repetida deja el resto del video sin sentido.

### 2. Encontrar la estructura

Casi todos los reels de este tipo tienen la misma columna vertebral. Nombrarla antes de
cortar hace obvio qué sobra:

**gancho → problema → dato → tesis → prueba → giro → pico → cierre**

Cada corte debe servir a una de esas funciones. El que no sirve a ninguna, fuera — aunque
esté bien dicho. Los fragmentos que la frase siguiente ya dice completos sobran siempre.

**El reel abre con el gancho**, no por el principio: si la frase más fuerte está a la mitad,
se pone delante (arranque en frío) y se deja también en su sitio. Hay que generar con
`--sin-tomas` o `tomas.py` se la lleva como toma repetida. Si ya abre fuerte, no se toca.

### 3. Zoom: jerarquía, no decoración

**La mayoría de los cortes van abiertos al 100%.** Si casi todo está acercado, nada
destaca. Tres niveles:

| Nivel | Escala | Para |
| --- | --- | --- |
| leve | 112–118% | entrar a un dato |
| fuerte | 122–130% | tesis, giro, cierre |
| pico | 134–136% | **uno solo** en todo el video |

El zoom **sigue el sentido del texto**: abre cuando se da contexto, cierra cuando se revela.
El par "antes… / ahora…" se lee mejor como abierto → cerrado.

En el plan: `"zoom": {"punch": 1.28}`. Es escala fija — **zoom seco, sin animación**: las
animaciones se sienten "efecto", no cámara. **El techo depende del encuadre**: mídelo con
`python tools/encuadre.py <video> --cabeza` y, si el plano es cerrado, ancla arriba
(`"ancla"`) o comprime la escalera con las mismas proporciones.

### 4. Cifras y frase clave en pantalla

Solo las que **cargan el argumento**, no todas: el detector propone también edades, horas
y años. `"datos": [{"ini","fin","texto"}]` en segundos de la línea de tiempo final. Un par
"3/10 → 4/10" vale más que cinco números sueltos. Escríbelas de 10-12 caracteres.

La frase clave en grande (`"frases"`) es la tesis de cada bloque, de **tres palabras**: a
tres líneas tapa la boca. Va donde la imagen NO lo dice: si el stock ya lo enseña, la frase
se lo come.

### 5. B-roll

- Solo donde **ilustra**, y **nunca sobre el golpe**: tapar la frase clave con stock la
  debilita.
- Cobertura: en reels, lo que una editora devolvió aprobado cubría más de la mitad; un
  ~40% se quedó corto. No se copia un número: se mide lo que aprueba **este** usuario.
- **Mirar el frame antes de usarlo.** Pasar el filtro de pertinencia no es ilustrar: saca un
  frame de cada clip y velo. El stock corporativo genérico abarata un video cuya fuerza son
  los datos.

### 6. Sonido

Reglas medidas, en `pipeline/sonidos.py`. Se deducen solas del montaje; no hace falta
tocarlas salvo que se quiera algo puntual (`"sfx_sin": ["riser"]` quita uno). Nunca dos a
menos de 0.5 s.

### 7. Música y anotaciones

Ambas se arruinan por exceso.

**Música** — `"musica": {"archivo": ..., "debajo": 18}`. El volumen no se elige:
`musica.volumen_bajo_voz()` lo mide contra la voz. Elegir pista con
`python tools/musica.py --proponer <segundos>`; el criterio que más manda no es el tempo
sino **cuánta energía tiene en la banda de la voz** (200–4000 Hz). Preferir lo libre de
derechos, y en YouTube filtrar por licencia primero.

**Al beat se pegan los acentos, jamás los cortes del habla.**

**Anotaciones** — subrayados y círculos `.mov` con alfa sobre las cifras. **Dos por reel**,
sobre el gancho y sobre el remate; una tercera ya se siente plantilla. Solo sirven archivos
con alfa real. **No poner la escala a mano**: `"perfil": "subrayado"` o `"circulo"` y
`adornos.py` la calcula midiendo el archivo. Necesitan **1.5 s libres** de b-roll encima.

### 8. Antes de colocar algo en pantalla, mirar el encuadre

```bash
python tools/encuadre.py --plan proyectos/<nombre>/plan.json
```

Deja frames en `proyectos/_encuadre/`. **Leerlos**: dónde está la cabeza, dónde las manos,
qué franja está vacía. Un callout mal puesto tapa la cara — y eso solo se ve mirando.

### 9. Generar

```bash
python reel.py --desde-plan proyectos/<n>/plan_revisado.json --nombre "<n> v2" \
  --captions palabra --zoom no
```

Con **CapCut cerrado**. `--zoom no` porque el zoom va por segmento en el plan. Después, leer
el texto de la línea de tiempo final de corrido: una palabra perdida a media frase solo se
ve así.

### 10. Reportar

Tres a cinco líneas: qué se decidió y **por qué**, no qué se ejecutó. Mencionar lo que se
dejó fuera y la razón — eso es lo que deja aprender al usuario y lo que permite que
corrija el criterio.

## Reglas duras

- **CapCut cerrado** antes de generar (y antes de borrar un draft viejo).
- Cada generación es un proyecto **nuevo**; los intermedios se acumulan. Limpiar.
- No inventar valores de gusto: si algo no convence, ver "Aprender el estilo".

## Aprender el estilo de una persona nueva

El editor trae el criterio de **un** usuario, medido de sus ediciones. Para alguien con
otro estilo, el método que funciona es siempre el mismo — y es más rápido que teorizar:

1. Pedirle que **edite un pedazo a mano** en CapCut con lo que le gusta.
2. **Medirlo**: `tools/analizar_sonido.py`, `tools/analizar_visual.py`, o leyendo el draft.
3. Escribir las reglas medidas en `CLAUDE.md` y en el módulo correspondiente, **con
   el número y de dónde salió**.

Cuando no hay nada suyo que medir, generar varias versiones que **solo difieran en lo que
se prueba** y que elija. Así salieron el ritmo de los cortes (pegados al habla, a unas
centésimas de una edición manual), los sonidos con sus reglas, y que el riser se recorta
por el final y no por el principio.
