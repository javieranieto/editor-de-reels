---
name: editar-largo
description: Del editor de reels. Edita un VIDEO LARGO horizontal (YouTube) de una o varias tomas hasta dejarlo armado en CapCut. Cargar cuando alguien diga "edita este video", "tengo un video largo", "hazme el video de YouTube", o pase una carpeta o un video de varios minutos.
---

# Editar un video largo

El método completo está en `largo/LEEME.md`. **Léelo antes de empezar.** Si existe
`mi_estilo.md` en la raíz del repo, **léelo también: son las reglas de ESTE usuario** y mandan
sobre los valores por defecto. Corre `python tools/configurar.py` para saber qué puedes hacer
en esta máquina (stock, gráficos, marca, cara) y dile al usuario lo que falte. Aquí va el orden.

1. **Entender antes de cortar.** `python largo.py preparar "<nombre>" --toma A=<video>`
   (y `--toma R=<retomas>` si hay). Lee `proyectos/<nombre>/legible_A.txt` completo.
2. **Proponer.** Di en pocas líneas de qué habla, para quién, qué largo sale (duración), qué
   se queda fuera y por qué. Si el usuario no pidió nada distinto, sigue con tu propuesta.
3. **`orden.json`** por frases, con `despues` en cada tramo y el motivo en `nota`. De lo
   repetido, la última toma completa.
4. `python largo.py cortar` y **`revisar`**. Arregla lo que marque (ver «Trampas» en el LEEME):
   un tramo no se da por bueno hasta que suena completo.
5. `python largo.py amarrar`: escribe tú `texto_limpio.txt` con lo que se oye, bien escrito,
   sin agregar ni quitar palabras. Vuelve a correr `amarrar`.
6. `stock.json` (~15-20 % del video, nunca sobre una cifra) → `python largo.py stock` →
   **mira `hoja_stock.jpg`** y quita lo que no venga al caso.
7. **Gráficos:** `escenas.json` (una idea por gráfico, con la marca del usuario de
   `recursos/marcas/`; si no tiene, `ejemplo` y dile cómo hacer la suya) → `motion --revisar` →
   `motion` → **mira las hojas**.
8. `python largo.py armar "<nombre>" --nombre "<Nombre> LARGO"` con CapCut cerrado.
9. **Reels:** propón 2-4 piezas continuas de 35-60 s con su gancho de dentro, su frase clave y
   su ventana en `reels.json` → `python largo.py reels "<nombre>"` → mira las hojas.
10. Si hay música (`musica.json`), el volumen se mide solo. Miniaturas: `miniatura` → mira
    `candidatos.jpg` (ojos abiertos) → `miniatura.json` → `miniatura --componer` → mira la de 320 px.
11. Cuenta qué decidiste y por qué. El usuario decide el gusto; si corrige algo en CapCut,
   pregúntale si quiere que esa forma se vuelva su regla. Cuando lo haya editado, corre
   `python largo.py aprender "<nombre>" --capcut "<proyecto>"`; lo que se repita lo escribes en
   `mi_estilo.md` (con la fecha y de qué video salió).

Lo que necesita cada parte: transcribir y armar, solo el editor. Stock: llave de Pexels en
`.secrets/pexels.yaml`. Gráficos y reels: `pip install playwright` + Chromium, y opencv-python
para medir la cara. Si falta algo, dilo y sigue con lo demás.
