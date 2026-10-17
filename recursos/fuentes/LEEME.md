# Fuentes

| Archivo | Familia | Licencia |
|---|---|---|
| `Poppins-Bold.ttf`, `Poppins-SemiBold.ttf`, `Poppins-Medium.ttf` | Poppins (Indian Type Foundry) | SIL Open Font License 1.1 |
| `RobotoMono.ttf` | Roboto Mono (The Roboto Mono Project Authors) | SIL Open Font License 1.1 |

La licencia viene escrita dentro de cada `.ttf` (campo de licencia del archivo) y las dos se
bajan de [Google Fonts](https://fonts.google.com). La **OFL** permite usarlas,
incrustarlas en videos e imágenes y redistribuirlas junto con software, con una condición:
**no se venden solas** y, si se modifican, no pueden llevar el mismo nombre. Texto completo:
<https://openfontlicense.org>.

## Para qué están aquí

Son para lo que se dibuja **fuera** de CapCut (tarjetas PNG, placas, motion graphics hechas
con PIL). Lo que se escribe **dentro** de un proyecto de CapCut usa las fuentes que CapCut
tenga descargadas en su caché, no estas: ver `pipeline/letras.py` y `tools/fuentes.py`.

⚠️ Estas fuentes **no traen** ✓ ✗ ≠ y otros símbolos: si hacen falta en una imagen, se dibujan
con líneas. Y un nombre de fuente de CapCut puede no ser el archivo que parece: al elegir
una, mira el archivo al que resuelve (`letras.fuentes_disponibles()`).
