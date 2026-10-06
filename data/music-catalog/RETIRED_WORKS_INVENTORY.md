# Inventario de obras retiradas de `/music/`

Fecha: 2026-09-30. Documento de trabajo: **no publica nada**. La selección pública sigue siendo
`public_music_selection.json` y la proyección la genera `generate_public_music_data.py`.

## Origen: las 15 obras originales

La lista manual de 15 obras es `js/music-data.js` en el commit `064fc25`
(`git show 064fc25:js/music-data.js`). Su orden fue:

| # | Obra | Artista | Rol en el sitio antiguo | Estado actual |
|---|---|---|---|---|
| 1 | Adiós Amor (Versión Bolero) | Luis Guinea | Artist | pública (#33) |
| 2 | Hasta Que Lleguemos Al Mar | Luis Guinea | Artist | pública (#25) |
| 3 | Hace Tanto Tiempo | Luis Guinea | Artist | pública (#02) |
| 4 | Blue Moon | Luis Guinea | Artist | pública, faceta Composer (#34) |
| 5 | Volver a Verte | Luis Guinea | Artist | pública (#04) |
| 6 | Cómo Decirte | Luis Guinea | Artist | pública, faceta Producer (#35) |
| 7 | Nuestro Hogar | Luis Guinea | Artist | pública (#03) |
| 8 | 12 Meses | Rogelio Edel | Producer | pública (#05) |
| 9 | La Bamba | Rogelio Edel | Producer | pública (#11) |
| 10 | A Escondidas | Isabella Macías | Producer | pública (#36) |
| 11 | Lo Que Queda de Mí | Escala de Grises | Producer | pública (#37) |
| 12 | Abrazo Imaginario | Ricardo Bojalil | Producer | **pública de nuevo (#01)** |
| 13 | Shape of You - Acoustic | Segundo Piso | Producer | pública (#38) |
| 14 | Ya No Soy Esclavo | Patty Gleason | Producer | excluida por decisión humana (#39) |
| 15 | Lo Que Venga | Patty Gleason | Producer | excluida por decisión humana (#40) |

El comentario de ese fichero decía que los roles salían de los libros de catálogo. Pero la columna
`Role` de `catalogo_completo_para_web_y_supervisores.xlsx` (hojas `Spotify` y `Local`) y de
`catalogo_sin_duplicados_con_isrc_prioridad.xlsx` (hojas `Released` y `Local`) está **vacía** en las
8 obras retiradas. Tampoco hay valores en `Composer(s)`, `Performer(s)` ni `Master Owner`. Así que el
rol antiguo no tiene fuente verificable.

El campo `site_role` de la antigua muestra de clasificación, que no se conserva en el repositorio,
tampoco sirve como evidencia de rol: copia el rol del sitio antiguo y, además, es histórico e
independiente de la proyección viva.

## Abrazo Imaginario — Ricardo Bojalil (2022) · review_id 01 · decisión aplicada

- **Decisión humana** (Luis Guinea, 2026-09-30): Ricardo Bojalil es el intérprete vocal. Luis Guinea
  compuso y escribió la canción, la produjo y la grabó.
- **Dónde está registrada.** En `spikes/essentia/human_review_decisions.json`, caso `01`:
  - `credits`: Ricardo Bojalil `vocal_performer`; Luis Guinea `songwriter`, `producer` y
    `recording_engineer`.
  - `credits_decision`: fuente, fecha y enunciado.

  El valor literal `values.catalog_category: artist` (carpeta `Cantautor`) se conserva. En esta
  misión solo se validó la decisión; no se reescribió.
- **Identidad.** `catalog_link.status = mapped` con `work_id = abrazo-imaginario--ricardo-bojalil--2022`.
  La fila 01 de `human_classification_bank.json` tiene el mismo `work_id` y `Catalog Link = mapped`.
- **Datos objetivos** en `catalog_master.json`: `release.status = released`, `type = single`,
  `year = 2022`, `artists = ["Ricardo Bojalil"]`. El fichero
  `assets/images/Abrazo-Imaginario---Ricardo-Bojalil.webp` existe. La maestra no se modificó.
- **Selección.** Se añadió `{ "review_id": "01" }` al final de `public_music_selection.json`. Es la
  posición que le corresponde según el orden original: en `064fc25` iba después de *La Bamba*, que
  es la última obra hoy publicada.
- **Proyección generada:**
  - `role: 'Producer'`: faceta primaria del filtro.
  - `roles: ['Songwriter', 'Producer', 'Recording Engineer']`.
  - Sin `Artist` ni interpretación vocal atribuida a Luis. Ricardo Bojalil figura en `artist`.

## Decisiones humanas aplicadas a las 8 obras

Los casos #33–#40 amplían la capa humana sin modificar los 32 casos históricos ni inventar
secciones en `One Page Luis Guinea/CLASIFICACION_HUMANA_MUSICA.md`. Las ocho identidades quedan
`mapped`: este inventario sustenta un candidato único en `catalog_master.json` por título, artista y
año, y la decisión humana explícita de Luis Guinea lo confirma.

Los créditos proceden exclusivamente de esas decisiones. No se convierten en créditos los indicios
de carpetas de Drive, audio, Essentia o el sitio histórico. Se publican seis obras; las dos de Patty
Gleason permanecen fuera mediante `public_exclusion: true`. Recuentos resultantes: **40
clasificaciones, 29 mappings y 11 casos abiertos**.

`CREDIT_ROLES` mantiene separados `artist`, `songwriter`, `producer` y `recording_engineer`. La
faceta pública `role` admite `Artist`, `Producer` o `Composer`; `Composer` requiere el crédito
detallado `songwriter`.

---

### 1. Adiós Amor (Versión Bolero) — Luis Guinea (2020)

- review_id: `33`.
- work_id: `adios-amor-version-bolero--luis-guinea--2020`. Single, `released`,
  artista único Luis Guinea, `is_collaboration: false`. El artwork web existe.
- Estado: **pública**. Decisión: Luis `artist` y `producer`; Salvador Garza `songwriter`; Luis no es
  compositor. Faceta `Artist`.
- Casos técnicos, independientes de la identidad y del rol:
  - `audio_ref: null`.
  - `lista_archivos_audio_LuisGuinea.xlsx` tiene dos assets: fila 108, `Adios Amor (Master).mp3`
    (`…/Luis Guinea/Shows 2020/Audios/`), y fila 242, `Adios Amor (Master).wav`
    (`…/Luis Guinea/Adiós Amor (Versión Bolero)/`). No están vinculados ni se ha comprobado su
    duración, así que no se afirma que sean el mismo máster.
  - ISRC `pendiente_manual` en `internal/conflicts.json`: la fuente secundaria da `MXE772000025` y
    la principal está vacía.

### 2. Blue Moon — Luis Guinea (2015)

- review_id: `34`.
- work_id: `blue-moon--luis-guinea--2015`. Pista 2 de *Memories*, `type: single`
  según la fuente principal (`Released` fila 67, `Album Type = single`). `released`, artista único
  Luis Guinea. El artwork web existe.
- Estado: **pública**. Decisión: Luis `songwriter`, `artist` y `producer`. Faceta `Composer`. Esta
  decisión no se contradice por inferencias sobre canciones homónimas.
- Casos técnicos, independientes:
  - `audio_ref: null` y ningún asset en las listas `lista_archivos_audio_*.xlsx`.
  - ISRC `pendiente_manual`: la secundaria da `BGA471521987`.
  - El artwork se resolvió automáticamente: fuente `Luis Guinea - Memories.jpg` →
    `Blue Moon - Luis Guinea.jpg`.

### 3. Cómo Decirte — Luis Guinea, Pablo Delgado (2022)

- review_id: `35`.
- work_id: `como-decirte--luis-guinea--2022`. Single, `released`,
  `is_collaboration: true`, ISRC `MXE772200006`. El artwork web existe.
- Estado: **pública**. Decisión: Luis `artist`, `songwriter` y `producer`. Faceta `Producer`. No se
  asignan roles concretos a Pablo Delgado que la decisión no declara.
- Indicios históricos, no convertidos en créditos:
  - Luis Guinea figura en `artists`, lo que apunta a `artist`.
  - El único audio local está en `One Page Luis Guinea/audios/Productor/Pablo Delgado/PDelgado_Cómo Decirte_MixV1_.mp3`,
    lo que apunta a `producer`.
  - `audio_links_onepage.json` lo deja `unmatched` («sin coincidencia de nombre»), así que según
    `CATALOG_CATEGORY.md` (reglas 1 y 3) **no** recibe `catalog_category`.
  - Hay una demo en `Songwriting/Demo Editoras/Cómo Decirte.mp3` (`audio_links.json` → `rejected[4]`),
    lo que apunta a `songwriter`, pero solo como indicio.
  - El sitio antiguo decía `Artist`, y la bio de `One Page Luis Guinea/index.html` la cita entre sus
    singles.
- Casos técnicos, independientes:
  - El `audio_ref` `PDelgado_Cómo Decirte_SPOTIFY.wav` está vinculado con Δ 0,0 s
    (`audio_links.json` → `linked[12]`).
  - Dos candidatos rechazados por duración: `Producciones/Pablo Delgado/Cómo Decirte/Cómo Decirte.mp3`
    (Δ 13,757 s) y la demo (Δ 15,063 s).
  - No se afirma que `MixV1_.mp3` y `SPOTIFY.wav` sean la misma grabación ni el mismo máster.

### 4. A Escondidas — Isabella Macías (2018)

- review_id: `36`.
- work_id: `a-escondidas--isabella-macias--2018`. Single, `released`, ISRC
  `MXE771800054`. El artwork web existe.
- Estado: **pública**. Decisión: Luis `producer` únicamente. Faceta `Producer`.
- Indicios históricos, no convertidos en créditos:
  - Indicio no canónico: el `audio_ref` está en Drive `Producciones/Bela/`.
  - El sitio antiguo decía `Producer`.
- Casos técnicos, independientes:
  - `audio_ref` `A ESCONDIDAS MSTR 1.5.m4a` vinculado con Δ 0,056 s (`audio_links.json` →
    `linked[1]`).
  - Tiene análisis Essentia en `spikes/essentia/out/`, que es solo evidencia de sonido y no de rol.

### 5. Lo Que Queda de Mí — Escala de Grises (2016)

- review_id: `37`.
- work_id: `lo-que-queda-de-mi--escala-de-grises--2016`. Single, `released`, ISRC
  `QZ5AB1602754`. El artwork web existe.
- Estado: **pública**. Decisión: Luis `songwriter`, `producer` y `artist`. Faceta `Producer`.
- Indicios históricos, no convertidos en créditos:
  - El `audio_ref` `Lo Que Queda De Mí.mp3` está vinculado a Drive `Songwriting/Demo Editoras/`
    (Δ 0,077 s, `audio_links.json` → `linked[33]` y `linked[34]`), lo que apunta a `songwriter`.
  - `lista_archivos_audio_Songwriting.xlsx`, fila 151, lista esa demo, y la antigua muestra de
    clasificación (no versionada) registraba esa misma lista como su inventario de audio.
  - Hay dos candidatos rechazados en carpetas de producción: `Producciones/Escala de Grises/`
    (Δ 21,68 s) y `Producciones/Luis Guinea/Producciones Varias/Lo que queda de mí.m4a` (Δ 9,498 s),
    lo que apunta a `producer`.
  - El sitio antiguo decía `Producer`.
- Casos técnicos, independientes:
  - `apple_music.url` `pendiente_manual` por `slug_no_coincide_con_titulo`: la URL apunta a
    «sin-perdón-feat-jaro-desperdizio».
  - No se afirma que la demo y la versión publicada sean el mismo máster.

### 6. Shape of You - Acoustic — Segundo Piso (2017)

- review_id: `38`.
- work_id: `shape-of-you-acoustic--segundo-piso--2017`. Single, `released`, ISRC
  `QZ5AB1787944`. El artwork web existe.
- Estado: **pública**. Decisión: Luis `producer` únicamente; es un cover. Faceta `Producer`. No se
  atribuyen `songwriter`, `artist` ni `recording_engineer`.
- Indicios históricos, no convertidos en créditos:
  - Indicio no canónico: el `audio_ref` apunta a Drive `Producciones/Luis Guinea/Shape of you.mp3`.
  - El sitio antiguo decía `Producer`.
- Casos técnicos, independientes:
  - El `audio_ref` **no está validado**: el fichero dura 365,4 s y el catálogo 184 s, con Δ 181,4 s
    (`audio_links.json` → `rejected[19]`). Puede ser otra edición o versión; no se asume.
  - `apple_music.url` con marcador `0`, resuelto automáticamente a sin URL.
- La discrepancia entre `Shape of you.mp3` (365,4 s) y la pista publicada (184 s) sigue abierta como
  `R11`; la decisión de crédito no resuelve versión ni identidad de máster.

### 7. Ya No Soy Esclavo — Patty Gleason (2020)

- review_id: `39`.
- work_id: `ya-no-soy-esclavo--patty-gleason--2020`. Pista 2 del álbum *Covers*,
  `type: album`, `released`. El artwork web existe.
- Estado: **excluida del catálogo público**. Decisión: Luis no participó; `credits: []` y
  `public_exclusion: true`. El rol `Producer` del sitio antiguo no se conserva como crédito.
- Casos técnicos, independientes:
  - `audio_ref: null`.
  - ISRC `pendiente_manual`: la secundaria da `usl4q2005463`.
- Contexto: *Covers* tiene 11 pistas en `catalog_master.json`; esta decisión se limita a la obra
  identificada y no se extrapola al álbum.

### 8. Lo Que Venga — Patty Gleason (2020)

- review_id: `40`.
- work_id: `lo-que-venga--patty-gleason--2020`. Pista 7 de *Covers*,
  `type: album`, `released`. El artwork web existe.
- Estado: **excluida del catálogo público**. Decisión: Luis no participó; `credits: []` y
  `public_exclusion: true`. El rol `Producer` del sitio antiguo no se conserva como crédito.
- Casos técnicos, independientes:
  - `audio_ref: null`.
  - ISRC `pendiente_manual`: la secundaria da `usl4q2005468`.
