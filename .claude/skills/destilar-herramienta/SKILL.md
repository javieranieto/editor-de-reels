---
name: destilar-herramienta
description: Del editor de reels. Analiza una herramienta externa de edición de video (repo de GitHub, servicio, artículo) y extrae de ella mejoras concretas para el editor. Úsalo cuando el usuario comparta un enlace a un repo o herramienta de edición de video y pida revisarla, compararla, o "robarle" ideas — por ejemplo "revisa este repo", "mira esta herramienta", "¿qué le podemos sacar a esto?".
---

# Destilar una herramienta externa

Todo lo de aquí se corre **desde la raíz de este repo**
(`cd editor`).

El usuario encuentra herramientas de edición automática y quiere que el editor mejore con
lo aprendido de ellas, sin adoptar dependencias que no le sirven. El producto de este skill
NO es un resumen: son **cambios de código probados** más una entrada en la bitácora.

**Antes de empezar, busca la herramienta en `IDEAS.md`**: si ya se analizó, ahí está qué se
tomó y qué se descartó.

## Principio

Casi ninguna herramienta se adopta entera: resuelven un problema parecido pero no el mismo.
Lo valioso suele ser **una decisión de diseño validada con datos** que está enterrada en su
código, no su lista de funciones. Buscar eso.

## Proceso

### 1. Entender qué problema resuelve (5 min)

`WebFetch` al README para: qué hace, stack, madurez (estrellas, actividad, licencia), qué
produce como salida, y qué APIs de pago necesita.

Luego el árbol de archivos, que revela más que el README:

```bash
gh api repos/<owner>/<repo>/git/trees/main?recursive=1 --jq '.tree[].path' \
  | grep -E "\.py$" | grep -viE "test|frontend|node_modules"
```

### 2. Leer el código de los módulos que tocan nuestro dominio

Leer, no solo listar. Nuestro dominio: transcripción, detección de cortes, subtítulos,
movimiento de cámara, selección de momentos, render.

```bash
gh api repos/<owner>/<repo>/contents/<archivo>.py --jq '.content' | base64 -d | head -80
```

**Dónde está el oro**: comentarios que justifican una constante. Frases como "medido sobre
N clips", "esto se shippeó en X y produjo Y", "swept over…". Alguien ya pagó el costo de
experimentar; ese número vale más que su arquitectura.

### 3. Clasificar cada hallazgo

| Veredicto | Cuándo |
| --- | --- |
| **Adoptar** | Resuelve nuestro problema mejor que lo nuestro y sin arrastrar infraestructura (ej. pycapcut) |
| **Robar la idea** | Su implementación no encaja, pero la decisión de diseño sí. **El caso normal.** |
| **Anotar y esperar** | Útil solo para un flujo que el usuario todavía no tiene |
| **Descartar** | Resuelve otro problema, o exige APIs de pago / servidor para algo que ya hacemos local |

Criterios duros para descartar: requiere Docker o servidor; cobra por uso donde ya hay
solución local; produce MP4 cerrado en vez de proyecto editable; mete un "cerebro" de pago
donde la revisión editorial de Claude ya sirve.

### 4. Buscar la mejora sobre ellos

Antes de implementar, preguntar: **¿tenemos algo que ellos no?** A menudo sus limitaciones
vienen de datos que a nosotros sí nos sobran. Ejemplo real: una herramienta dispara sus
punch-ins con picos del envolvente de audio y su propio código anota que el transcript
sería mejor fuente — aquí ya hay timestamps por palabra, así que la versión nuestra dispara
sobre estructura del habla.

Sus comentarios sobre lo que les falta son un mapa de oportunidades.

### 5. Implementar con la idea aislada y atribuida

- Módulo propio cuando la idea tenga sustancia (ej. `pipeline/zoom.py`).
- Docstring que diga **de dónde salió, con archivo y qué validaron**. Cuando alguien cambie
  esa constante en un año, tiene que saber que no era arbitraria.
- Constantes con nombre, no números sueltos en el código.

### 6. Probar contra material real, no solo sintético

1. Casos borde de la función nueva (duración 0, valores invertidos, tope).
2. **Los videos reales que ya están en `proyectos/`** — ahí se ve si la idea aplica.
3. **Regresión de lo que ya funcionaba.** `python tools/pruebas.py` y las huellas de los
   reels aprobados (`proyectos/_pruebas.json`): lo que ya le gustó al usuario no se mueve.
   Contar los OK y las saltadas, no leer solo el "Todo en orden" del final.

### 7. Bitácora y commit

Añadir la entrada a `IDEAS.md`: herramienta, fecha, qué se tomó, qué se descartó y por qué,
y qué queda anotado para después. Es el registro que evita re-analizar la misma
herramienta.

Commit describiendo la idea y su origen, no solo el cambio mecánico.

### 8. Reportar al usuario

En pocas líneas: qué es la herramienta, por qué no se adopta entera (si aplica), qué se
robó, y **qué proyecto de prueba puede abrir en CapCut para sentir la diferencia**. Si un
cambio afecta el gusto (movimiento, ritmo, estilo), generar dos versiones comparables del
mismo video antes/después.

## Recordatorios operativos

- CapCut cerrado antes de generar cualquier draft de prueba.
- Si se cambia **cómo** se producen las palabras de la transcripción, subir `FORMATO_CACHE`
  en `pipeline/transcribe.py` o las cachés viejas ocultan la mejora.
- Limpiar los drafts de prueba de la lista de CapCut al terminar.
