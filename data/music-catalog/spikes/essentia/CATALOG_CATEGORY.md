# `catalog_category` — dimensión editorial experimental

Estado: **experimental**, vive solo en `data/music-catalog/spikes/essentia/`.
No se ha escrito en `catalog_master.json`, en `TAXONOMY.md`, en
`vocabularies.json` ni en `/music/`. No es parte de los 11 campos del
esquema v1.

## Qué es

`catalog_category` es el rol profesional bajo el que Luis Guinea organizó
sus audios locales en `One Page Luis Guinea/audios/`. Es **editorial y
declarada por el usuario a través de la carpeta que eligió**, no una
predicción de Essentia ni un dato derivado del sonido. Essentia no se usa
para asignar ni para sugerir esta dimensión.

Es **mutuamente excluyente** en v1 (una obra cae en una sola categoría, la
de la carpeta donde el usuario puso su audio) y **está separada** de:

- `genre`, `subgenre`, `mood`, `emotion`, `theme`, `use_scene` (TAXONOMY.md
  §2–§11): son atributos del sonido o del uso, no del rol editorial.
- Créditos/roles objetivos ya presentes en `catalog_master.json`
  (`credits`, `artists`, `is_collaboration`): esos describen quién
  intervino y cómo, con evidencia objetiva por obra; `catalog_category`
  describe bajo qué faceta profesional el usuario clasificó el audio en su
  archivo personal.

## Vocabulario (IDs)

| ID | Carpeta de origen (nombre real bajo `audios/`) | Significado |
|---|---|---|
| `artist` | `Cantautor` | Canciones propias como cantautor |
| `producer` | `Productor` | Producciones a terceros |
| `instrumental` | `Instrumentales` | Instrumentales |
| `co_write` | `Coautorías` | Coautorías |

Las cuatro subcarpetas de primer nivel bajo
`One Page Luis Guinea/audios/` mapean 1:1 y sin ambigüedad a estos cuatro
IDs; no hay una quinta carpeta ni casos mixtos.

## Reglas

1. El ID se asigna **solo** por la subcarpeta de primer nivel del audio
   vinculado (evidencia declarada por el usuario), nunca por inferencia de
   audio ni por el contenido de la obra.
2. La ausencia de una obra en `audios/` **no implica** que carezca de
   categoría: el catálogo (91 obras) es más amplio que los audios
   disponibles localmente (50 ficheros, 15 vinculados sin ambigüedad en
   esta iteración). `catalog_category` solo se conoce para las obras con
   un audio local vinculado de forma inequívoca.
3. Un audio ambiguo (nombre+duración calzan con más de una obra) no recibe
   `catalog_category` hasta que se resuelva la ambigüedad; no se decide por
   intuición.
4. Si en el futuro un mismo trabajo apareciera en más de una carpeta de
   categoría, este esquema mutuamente excluyente ya no alcanzaría y habría
   que decidir explícitamente (candidata a v2, no resuelta aquí).

## Procedencia y evidencia

Se registra igual que el resto de evidencia `analisis_audio` de
TAXONOMY.md §12, pero la clase de evidencia para `catalog_category` en sí
es **`objetivo`** (carpeta elegida por el titular), no `analisis_audio`: lo
que exige TAXONOMY.md §12 (nombre + duración ±1,0 s) es la vinculación
audio↔obra, no el valor de la categoría, que ya viene dado por la ruta.

Ver `link_audio_onepage.py` y `audio_links_onepage.json` (no versionado,
contiene rutas locales) para la vinculación completa con `catalog_category`
por registro.
