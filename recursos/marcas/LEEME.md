# Marcas

Cada marca es un archivo `<id>.json` con sus colores, sus letras y su firma. Los gráficos
animados (`recursos/escenas/`) y los íconos salen con la marca que se pida:

```bash
python recursos/escenas/capturar.py tarjetas/lateral.html salida.mov 5 --alfa --marca mi_marca
```

Para hacer la tuya, copia `ejemplo.json` como `mi_marca.json` y cambia:

- `colores`: `acento` es TU color (botones, cifras, lo que resalta); `fondo1-3` el degradado del
  fondo (de claro a oscuro); `texto` y `tenue` el texto principal y el secundario; `tarjeta` el
  vidrio de las tarjetas (con transparencia).
- `letras`: familias que existan en `recursos/fuentes/`. Para una letra nueva, pon su `.ttf` en
  esa carpeta y su nombre en `archivos_de_letra` (`{"Montserrat": "Montserrat-VF.ttf"}`).
- `firma`: el texto chico que va abajo en los paneles (déjalo vacío si no quieres firma).

Después corre `python recursos/escenas/iconos/armar_iconos.py` para que los íconos tengan tus
colores. **Solo `ejemplo.json` sube al repo**: las demás son tuyas y se quedan en tu máquina.
