# Tarjetas de cierre (CTA) — «el video completo está en YouTube»

Una placa de marca que va **encima de los últimos ~2 s** de un clip vertical para mandar al
video largo. No es una cortinilla: no añade tiempo y no rompe el bucle del reel (un reel se
repite solo, y una placa al final se reproduciría en cada vuelta, justo donde la gente
desliza).

**Esta carpeta viene vacía a propósito.** Aquí va la placa de cada marca que trabajes, un
PNG por marca, con un nombre que diga de quién es.

## Cómo hacer la tuya

- **La hace una persona, no el código.** Las placas generadas por código salen "correctas" y
  se ven baratas. Un diseñador, Canva con el kit de marca de ese cliente, lo que sea: aquí
  solo se **mide y se coloca**.
- **PNG con canal alfa**, fondo transparente. Un lienzo ancho (del orden de 2000x700) con
  una pastilla que diga el handle.
- **El dato que va en pantalla es el `@handle`**, no el nombre visible de la marca: en
  Instagram y TikTok no hay enlace, así que tiene que poder **buscarse**, y un nombre de
  marca lo repiten otros canales. Sácalo del código del sitio de esa marca o del perfil en
  vivo, **nunca del manual**, y léelo letra por letra en el PNG: un `@` mal escrito se
  publica en todos los clips de la tanda.

## Cómo se usa en un plan

```json
"overlays": [{"archivo": "<ruta al png>", "pista": "cta",
              "ini": <total - 2>, "fin": <total>,
              "escala": <la que dé el 80%>, "y": <la banda libre>}]
```

- **`"pista": "cta"` no es opcional** si el clip ya tiene otro overlay que se solape en el
  tiempo (la webcam de un clip de pantalla dura todo el clip): pycapcut rechaza dos
  segmentos encimados en la misma pista.
- **La escala se calcula por placa.** Lo que se ve bien es que la pastilla ocupe ~80% del
  ancho del cuadro, y cada placa lo logra con otra escala porque su pastilla ocupa otra
  parte de su propio lienzo: `escala = 0.80 * 1080 / ancho_de_la_pastilla_a_escala_1`.

## 🔴 La trampa del alfa: mide la pastilla SÓLIDA

**No midas con el `getbbox()` del canal alfa a secas.** El alfa incluye la sombra difusa,
que puede bajar cientos de píxeles más allá de donde acaba lo que se ve. Medido así, la
tarjeta queda descolocada. Se mide la máscara **alfa > 200**:

```python
from PIL import Image
a = Image.open("placa.png").getchannel("A")
caja = a.point(lambda v: 255 if v > 200 else 0).getbbox()   # la pastilla que se VE
```

Y de ahí salen dos números por placa:

1. **El ancho de la pastilla**, para la escala del 80%.
2. **El desfase de su centro.** `transform_y` coloca el centro del **lienzo**, no el de la
   pastilla. Si la sombra deja más aire abajo que arriba, lo que se ve cae más arriba del
   centro del archivo, y hay que descontarlo. Es distinto en cada placa: una puede venir
   centrada y otra no.

## Dónde va: no hay una altura única

La regla es **«la banda libre más baja que no sea cara, ni subtítulo, ni interfaz de la
app»**, y sale distinta en cada clip:

- En un clip **a cámara** (recorte de un video largo), bajo la barbilla.
- En un clip de **demo de pantalla**, con la cara abajo, al pie del panel del documento,
  encima del subtítulo: tapa las últimas filas de la tabla 2 s, que a esa altura nadie lee.
- ⚠️ Se dice que la app se come ~10% de arriba y ~20% de abajo, pero **eso no está medido**:
  se mide capturando un reel ya publicado DENTRO de cada app. Úsalo de orientación.
- ⚠️ **Se comprueba mirando varios fotogramas de la ventana, no uno.** La persona se mueve:
  una banda libre en un fotograma puede tener su frente dentro medio segundo después, y la
  tarjeta dura 2 s.
