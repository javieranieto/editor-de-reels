# Prompt: preparar una tanda para publicar

Para pegar al empezar una conversación nueva, cuando ya hay un **video largo y sus clips
verticales editados y aprobados** y lo que falta es dejarlos listos para subir: la tarjeta
de cierre, los nombres, la carpeta, el copy, la miniatura y el calendario.

Se copia desde «## EL PROMPT» hasta el final, y se llenan los `<...>` del bloque de datos.

---

## EL PROMPT

Ya tengo editado el video largo de YouTube y sus clips verticales de la marca **`<MARCA>`**,
y quiero dejarlos listos para publicar.

**Lee primero, antes de tocar nada:**

1. En `CLAUDE.md`: «Del video largo salen los clips verticales», «La tarjeta de
   cierre» y «El paquete de publicación».
2. `recursos/cta/LEEME.md`: cómo se mide y se coloca la tarjeta de cierre, y por
   qué no hay una altura única.

**Lo que hay que hacer, en orden:**

1. **Inventario primero, y me lo confirmas antes de tocar nada.** Dime qué proyectos de
   CapCut y qué `proyectos/*/plan.json` crees que son de esta tanda, con su
   duración, y espera mi sí. No des por hecho cuál es el largo por su nombre: el nombre de
   la carpeta y el `draft_name` de adentro pueden no coincidir.
2. **La tarjeta de cierre la hago yo (o mi diseñador), no la generes.** Va en
   `recursos/cta/`. 🔴 **Si no está, PARA y pídemela** — ni por código ni con una IA.
   Mídele la pastilla sólida (alfa > 200, no el `getbbox()` del alfa a secas) y el desfase
   de su centro.
3. **Colócala en cada clip, midiendo por clip**: la banda libre más baja que no sea cara,
   ni subtítulo, ni interfaz de la app. Saca **tres fotogramas de la ventana del CTA**, no
   uno, y enséñamelos compuestos antes de generar. Va como `"overlays"` con
   `"pista": "cta"`.
4. **Lee el texto de cada clip de corrido y comprueba los cortes.** Un clip puede arrancar
   dentro de una palabra o cortar con voz audible detrás. Para eso se mide el nivel
   **dentro del hueco** de la línea de tiempo, no en la ventana siguiente al corte.
5. **Nómbralos para que se distingan en la rejilla de CapCut**, que corta el nombre a unos
   18-20 caracteres: `<PREFIJO> LARGO - <tema>` y `<PREFIJO> 01 - <tema>`, numerados en
   orden de publicación. Cada copia con `draft_id` nuevo; nunca toques
   `root_meta_info.json`.
6. **Arma la carpeta en el Escritorio** con los documentos numerados que describe
   `CLAUDE.md` (cómo exportar y qué proyectos NO exportar, el copy, la miniatura, el
   calendario con fecha, día y hora, y el campo por campo de YouTube).
   El copy va **con las redes que tiene ESTA marca**, sacadas de su sitio o sus perfiles en
   vivo, y con ninguna más.
7. **Verifica al final mirando**: cuando yo exporte, saca un fotograma del MP4 en el
   momento del CTA y compruébalo.

**Reglas que no se discuten:**

- 🔴 **Comprueba que CapCut esté CERRADO antes de borrar o reemplazar un draft**, no
  después.
- 🔴 **Los datos de la marca salen de su fuente en vivo**, no de un documento: el código
  de su sitio o su perfil. Y de ahí sale también **lo que NO debe salir en pantalla** (un
  teléfono personal, un correo que no es de la empresa).
- ⚠️ **El largo se publica ANTES que los clips**: los clips dicen «video completo en
  YouTube» y uno publicado antes manda a buscar algo que no existe.
- ⚠️ **Un clip de menos de ~25 s suele quedarse en gancho sin remate.** Si alguno baja de
  ahí, dímelo.

**Los datos de esta marca** (compruébalos contra la fuente igual; esto es una copia):

- Marca: **`<MARCA>`** — prefijo para los nombres: **`<PREFIJO>`**
- Handle: **`<@handle>`**, en: `<redes donde existe, una por una>`
- Fuente de las redes: `<archivo del sitio o perfil de donde se sacó>`
- Paleta y tipografía: `<del CSS en vivo del sitio>`
- Tarjeta de cierre: `recursos/cta/<marca> - video completo en youtube.png` —
  pastilla sólida `<ancho>x<alto>`, desfase `<...>`, escala para el 80%: `<...>`
