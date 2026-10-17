# Banco de escenas de pantalla (gráficos animados)

Gráficos animados para tus videos: tarjetas, paneles, un teléfono con chats, gráficas, un
buscador, un mapa, reseñas, un CRM. Se arman en **HTML/CSS y se capturan con Chromium**
(`capturar.py`), así que traen sombras, desenfoque, 3D y letra reales. Las animaciones dibujadas
a mano con imágenes planas se ven «de PowerPoint»; estas no.

**Salen con TU marca**: colores, letras y firma de `recursos/marcas/<tu_marca>.json` (ver su
LEEME). Necesitan `pip install playwright` y `python -m playwright install chromium`. No gastan
créditos: todo es local, ~1 minuto por escena.

**Cómo se usa:** cada escena es un HTML con `render(t, T, escena)` que pinta el segundo `t`.
`T` trae los textos y los tiempos (amarrados a las palabras del video). En un video largo no
se llama a mano: se escriben en `escenas.json` y `python largo.py motion` las captura (ver
`largo/motion.py`). **Nunca se usa idéntica dos veces**: tiene que contar la escena de ESE video.
Antes de armar, **se mira la hoja de cuadros**.

```bash
python recursos/escenas/capturar.py tarjetas/lateral.html salida.mov 5 --alfa --marca ejemplo \
    --T '{"etiqueta":"Tu tarea","titulo":"Tu último anuncio","filas":[]}' --claves 1,3
```

| Escena | Archivo | Qué muestra |
|---|---|---|
| **Tarjeta lateral** (encima del video, con alfa) | `tarjetas/lateral.html` | etiqueta, título, filas que entran en su palabra (número / ✓ / ✗ tachado), pie en acento, ícono animado |
| **Panel a pantalla completa** (con alfa) | `tarjetas/panel.html` | sube desde abajo; líneas tenue/blanco/acento, tachado que se dibuja, línea con «golpe»; `t2/lineas2` cambia de contenido sin bajar (cierre) |
| **Ventana de reel** (con alfa, vertical) | `tarjetas/ventana.html` | fondo de la marca con el HUECO donde la persona se reduce; la gráfica arriba |
| **Teléfono configurable: lista de chats** | `telefono/lista.html` (16:9 y 9:16) | filas con palomitas, «escribiendo…», notificaciones, sellos, rótulo grande y cámara que se acerca; todo sale de T |
| Teléfono: bloqueo → chats → notificación | `telefono/horizontal.html` | versión fija de la anterior |
| Teléfono: chats a distinta hora / llamada perdida | `telefono/vertical.html` (`--escena chats2` o `llamada`) | |
| **Gráfica de barras** | `datos/barras.html` | columnas que crecen contando; la destacada brilla |
| **Gráfica de línea** | `datos/lineas.html` | curva que se dibuja, área degradada, anotación con flecha |
| **Contador** | `datos/contador.html` | el número protagonista cuenta; antes → después con %; barra, anillo o «4 de cada 10» |
| **Tabla que se llena en vivo** | `datos/tabla.html` | renglones escalonados, píldoras de estado, conclusión grande |
| **Buscador** | `web/buscador.html` | se teclea la búsqueda, anuncios, negocios con mapa, clic en el destacado |
| **Mapa** | `web/mapa.html` | calles, pines que caen, tarjeta del negocio, la ruta |
| **Reseñas** | `web/resenas.html` | calificación que cuenta, reseñas y la respuesta del dueño |
| **Calendario de citas** | `negocio/calendario.html` | citas por estado; `--escena confirmar` |
| **Tablero de CRM** | `negocio/crm.html` | indicadores que cuentan, prospectos que cambian de estado |
| **Panel de anuncios** | `negocio/anuncios.html` | campañas, gasto, costo por resultado, columnas que aparecen |

Cada HTML documenta sus campos de `T` en un comentario al principio. **Toda plantilla trae
datos de EJEMPLO en su `DEFAULT`**: lo que no va se pasa vacío (`filas: []`, `pie: null`), o se
cuela el texto de ejemplo.

## Íconos animados (Lottie)

15 íconos (alerta, apretón, buscar, calendario, chat, cronómetro, dinero, estrellas, gráfica,
megáfono, notificación, palomita, pin, reloj, teléfono) que se recolorean con cada marca.
- Dentro de una pieza: `lateral.html`, `panel.html` y `ventana.html` aceptan `icono: {nombre, t, loop}`.
- Suelto: `iconos/icono.html --alfa`. Todos juntos: `iconos/vitrina.html`.
- Se rearman solos (`iconos/armar_iconos.py`) cuando agregas o cambias una marca.
- **Licencia:** animaciones públicas de LottieFiles con la *Lottie Simple License* (uso comercial,
  sin atribución obligatoria; no se revenden como archivos sueltos). Autor y página de cada uno en
  `iconos/fuentes.json`. El reproductor es lottie-web (MIT, `base/lottie-web.LICENCIA.txt`).

## Reglas que ya costaron

- 🔴 **Los datos de ejemplo NO salen de un cliente real**, ni «anonimizados»: en una ciudad chica
  un monto y un conteo identifican al negocio. Cifras redondas inventadas que cuadren entre sí,
  teléfonos enmascarados («555 ••• 7731»), dominios inventados que no existan.
- 🔴 **Estilo WhatsApp, nunca su logo ni su nombre.** Se reconoce por el estilo.
- **En 16:9 el teléfono es chico: la cámara se acerca** a lo que importa. En vertical cabe grande.
- **Lo que lo hace real:** contactos de relleno (Mamá, Trabajo, Banco), la hora que avanza,
  palomitas azules en el que lo vio y no contestó, un pequeño golpe cuando llega la notificación.
- **Los sonidos van donde PASA la cosa** en esta escena, no donde estaban en otra versión.
- Una fecha en pantalla se comprueba (`date -d AAAA-MM-DD +%A`): un día equivocado hace dudar de todo.
- **Mira la hoja de cuadros y un cuadro encima del video**: que no tape la cara, que no se encime
  texto, que ninguna tarjeta pase segundos vacía esperando su primera fila.
