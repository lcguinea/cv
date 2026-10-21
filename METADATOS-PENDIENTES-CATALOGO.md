# Metadatos pendientes del catálogo: ZIP «_MASTERS y COVER ARTS OFICIALES» (2026-10-19)

> **Estado al 2026-10-21:** las nueve obras nuevas están **integradas en local** (`js/music-data.js`, 67 obras) y
> pendientes de la revisión final del propietario; no hay commit, push ni despliegue. Ver «Fase 5». Las dos
> duplicadas no se han tocado. Lo que sigue describe el estado inicial del 2026-10-19 y las fases intermedias.

Decisión inicial (2026-10-19): **no se publicó ninguna obra del ZIP**. El pipeline de publicación
(`public_music_selection.json` → `music_preview_manifest.json` → `js/music-data.js`) exige, por obra,
(a) una revisión humana con `review_id` y rol verificado, (b) una ventana de preview aprobada por el
propietario con base `human_authorization` y (c) género/mood solo de revisión humana. Ninguna de las 11
obras del ZIP tiene esa evidencia, y no se inventan créditos, fechas, identificadores, géneros, moods ni
derechos. Rellena cada ficha y la obra podrá integrarse con el pipeline existente.

Notación: **[M]** medido (ffprobe/sha256 sobre el master extraído) · **[E]** estimado · **[?]** sin confirmar.
BPM, género, subgénero, mood, energía e instrumentación: **sin medir** (Essentia no está instalado en este
entorno; no se estiman a oído). Los masters están en
`One Page Luis Guinea/audios/_zip_extraido_20261019/` (ignorado por Git; el ZIP y los masters previos no se tocaron;
sha256 del ZIP `3e02d56f4922a153e125ec16a7c24527b55d03021a2cfc5877e5add775a0320e`, sin cambios).
Todos los WAV son estéreo 44,1 kHz; todas las portadas son JPG/JPEG cuadradas.

## Resumen

| Estado | Obras |
| --- | --- |
| Encontradas | 11 masters WAV + 11 portadas |
| Duplicadas (ya en catálogo) | Cómo Decirte; Jinee Jinee (probable) |
| Nuevas, integradas en local (2026-10-21, sin publicar) | 9 |
| Publicadas en la web | 0 (pendiente de autorizar commit y push) |

Las seis canciones ocultas (#60, #61, #62, #70, #19, #31), el orden por año descendente, la exclusión
de obras orquestales de la selección aleatoria y el reproductor no se han modificado.

## Fase 2 (2026-10-20): nueve obras preparadas para revisión, sin publicar

El propietario autorizó el 2026-10-20 incluir las nueve obras nuevas en el catálogo público. Esa
autorización no aprueba ningún campo: cada registro queda con
`provisional: ["title", "artists", "credits", "release", "artwork", "editorial"]`, y el generador
rechaza publicar una grabación con campos provisionales. `js/music-data.js` no cambia.

- **Registros:** nueve altas al final de `data/music-catalog/catalog_recordings.json`, con la evidencia en `basis`.
- **Verificado en Apple Music (API de búsqueda de iTunes, 2026-10-20; duración igual a la del master):**
  - 1000 Días: 2021, como «1000 Días (feat. Paz, Alvarez)».
  - En El Momento Justo: 2023.
  - Solo Esta Noche: 2022.
  - Tonto Enamorado: 2023.
  - Juntos Somos Imparables: 2025, de «Canciones de Puño y Letra feat. Luis Guinea».
- **Sin localizar en Apple Music (mx, us, es):** Allí Estás, El Sembrador, Gracias Por Todo y Hasta el Final de mis Días.
  Quedan como inéditas de forma provisional.
- **Portadas:** WebP de 600 × 600 a `cwebp -q 75` en `assets/images/`. Están asociadas solo por nombre de archivo.
  La imagen de «Allí Estás» rotula **«Ahí Estás»**.
- **Previews:** dos propuestas de 40 s por obra (A y B), codificadas con `encode()` de
  `generate_music_previews.py`. Las ventanas se eligieron por sonoridad EBU R128, sin transcripción.
  Están en `One Page Luis Guinea/revision_zip_20261020/previews/`, que Git ignora y no se despliega. Se escuchan en
  `One Page Luis Guinea/revision_zip_20261020/revision.html`.
- **Datos personales (PyL):** el nombre del master, la portada y `audio_ref` incluyen los nombres de pila de los
  destinatarios: Claudia y Carlos; Familia y Chucho; Nietos y Tita; Coté y Javier; Sofi y Tony. El título propuesto
  los omite, como «Jinne, Jinne». La portada candidata los muestra impresos. Antes de publicar hace falta la
  autorización de los destinatarios, o bien una portada sin nombres.

### Fase 3 (2026-10-20): decisiones registradas

Casos **#76–#84** de `spikes/essentia/human_review_decisions.json`, en el orden de la tabla:

- **Ventanas de preview:** las nueve, aprobadas por el propietario tras escucharlas. Cada caso registra el
  intervalo exacto, el sha256 del master y el del preview de revisión.

  | Obra | Opción aprobada | Ventana (s) |
  | --- | --- | --- |
  | 1000 Días | B | 74,8–114,8 |
  | En El Momento Justo | B | 161,5–201,5 |
  | Solo Esta Noche | A | 200,4–240,4 |
  | Tonto Enamorado | A | 175,4–215,4 |
  | Allí Estás | A | 199,6–239,6 |
  | El Sembrador | B | 24,7–64,7 |
  | Gracias Por Todo | B | 47,6–87,6 |
  | Hasta el Final de mis Días | B | 48,9–88,9 |
  | Juntos Somos Imparables | B | 34,5–74,5 |

  Volver a codificar cada ventana con `encode()` reproduce exactamente esos bytes.
- **Créditos de Luis Guinea en las cuatro obras de Pablo Delgado (#76–#79):** `co_producer`, `co_arranger`,
  `recording_engineer` y `performer` (multiinstrumentista). La edición no tiene rol propio en `CREDIT_ROLES` y
  consta en `credits_decision.statement`. Los instrumentos (guitarras, teclados, cuerdas, sintetizadores, bajo,
  bongós, baterías y percusiones) se conservan como información general del conjunto de sesiones, sin
  atribuirlos a ninguna obra. Las cuatro obras quedan sin `public_facet` explícito.
- **¿Admite el pipeline estas ventanas?** Todavía no. `music_preview_manifest.json` exige exactamente una entrada
  por obra de `public_music_selection.json`, de modo que no puede guardar ventanas de obras no seleccionadas.
  Además, las políticas existentes describen aprobaciones del 2026-10-05 (v1) y del 2026-10-13 (v2) basadas en
  Whisper y croma, y estas ventanas son del 2026-10-20 y se propusieron por sonoridad EBU R128. Por eso las
  ventanas se registran en el banco humano y `approved-preview-window-v3` se añadirá al publicar.

### Fase 4 (2026-10-20): decisiones editoriales y propuesta de clasificación

**Decisiones registradas** en los casos #76–#84 (notas, `negative_decisions` y `credits_decision`) y en `basis`.

- **Pablo Delgado:**
  - Títulos, artistas y años confirmados. «1000 Días» lleva a Paz Álvarez como artista invitada.
  - «Warm» es un tecnicismo del master, no parte del título.
  - Portadas originales confirmadas.
  - Créditos de Luis Guinea reconfirmados; solo se publican créditos confirmados.
  - Disponibles para sincronización según el propietario, sin afirmar one-stop ni derechos liberados.
  - Provisional: `editorial`.
- **Canciones de Puño y Letra:**
  - Título definitivo «Ahí Estás». El id pasa a `ahi-estas--canciones-de-puno-y-letra` y la portada a
    `Ahí-Estás---Canciones-de-Puño-y-Letra.webp`.
  - Artista principal: Canciones de Puño y Letra.
  - Luis Guinea, como `songwriter`, `arranger`, `producer`, `performer` y `recording_engineer`. Edición, mezcla
    y masterización constan en `credits_decision.statement`, porque `CREDIT_ROLES` no tiene esos roles.
  - Portadas con los nombres de los destinatarios, con autorización expresa declarada por el propietario.
  - Solo portafolio: no se ofrecen para sincronización.
  - Provisional: `release` (estado y año sin confirmar) y `editorial`.
- **`use_scene`:** el vocabulario define una lista de escenas (de 0 a 4), no un booleano. La disponibilidad para
  sincronización queda como decisión escrita y la lista sigue vacía hasta que se elijan escenas.

**Propuesta de género y mood, pendiente de aprobación.** No está escrita en `values`. La evidencia sale de
Essentia, con el runtime y los modelos del spike verificados contra `models.lock.json`, de `map_taxonomy.py`
(regla: 2 de 3 modelos ≥ 0,10) y de ffmpeg EBU R128 sobre los masters completos. El mapeo no produjo ninguna
sugerencia de mood, así que todos los moods propuestos son inferencias.

| Obra | Género propuesto | Alternativa | Mood propuesto | Alternativa |
| --- | --- | --- | --- | --- |
| 1000 Días | pop, rock | pop, folk_singer_songwriter | bright, warm | — |
| En El Momento Justo | pop, rock | — | bright | bright, warm |
| Solo Esta Noche | pop | pop, rock | warm | warm, melancholic |
| Tonto Enamorado | rock, pop | — | bright | bright, groovy |
| Ahí Estás | pop | pop, rock / pop, folk_singer_songwriter | warm | warm, intimate |
| El Sembrador | folk_singer_songwriter, pop | — | bright, warm | bright, warm, playful |
| Gracias Por Todo | pop | pop, folk_singer_songwriter | warm, intimate | warm, calm |
| Hasta el Final de mis Días | pop, rock | pop | warm | warm, bright |
| Juntos Somos Imparables | pop, reggae | pop, latin_urban | bright, groovy | bright, playful |

Ninguna se propone como `cinematic_classical`, de modo que ninguna quedaría excluida de la reproducción
aleatoria.

### Fase 5 (2026-10-20/21): consolidación e integración local

- **Decisiones finales** consolidadas en los casos #76–#84 (género, mood, fechas, sincronización y rol
  principal Producer en las nueve); ningún registro de `catalog_recordings.json` queda con campos provisionales.
- **Previews:** política nueva `approved-preview-window-v3` en `generate_music_previews.py`; las nueve
  entradas `verified` del manifiesto reproducen byte a byte la opción aprobada (40 s cada una).
- **Fechas:** las cuatro PyL privadas (Ahí Estás, El Sembrador, Gracias Por Todo, Hasta el Final de mis
  Días) se crearon en 2022 y nunca se publicaron: figuran como inéditas sin año público (el año público es el
  de lanzamiento). Juntos Somos Imparables: lanzamiento 2025.
- **Spotify:** las cinco publicadas (1000 Días, En El Momento Justo, Solo Esta Noche, Tonto Enamorado, Juntos
  Somos Imparables) llevan solo Apple Music, reverificado con la API de iTunes el 2026-10-21. Su URL de
  Spotify **no está verificada** (no se afirma que no existan en Spotify) y su `basis` lo dice con
  «Spotify sin verificar». Decisión del propietario del 2026-10-21: una obra comercial puede publicarse solo
  con Apple Music. El generador exige ahora esa frase en el `basis` de toda publicada sin Spotify y que la URL
  de Spotify coincida con su `track_id`; la prueba de enlaces fija la lista exacta de esas cinco.
- **Sincronización:** campo interno nuevo `sync_availability` en cada grabación de `catalog_recordings.json`
  (`on_request` | `not_offered` | `null` sin decisión), validado por `recording_works()` y nunca publicado.
  `on_request`: las cuatro de Pablo Delgado (consultas sujetas a autorizaciones). `not_offered`: las cinco PyL
  (solo portafolio; con este valor `use_scene` debe estar vacío). Ninguna es one-stop ni se declaran derechos
  liberados. `use_scene` sigue vacío en las nueve hasta que se aprueben escenas concretas.
- **Verificación:** pruebas focalizadas del catálogo y del reproductor, `check_public_music.py`,
  `check_integrity.py` y `scripts/verificar_catalogo_masters.py` en verde; sitio local generado con 67 obras,
  sin WAV ni datos internos; las seis ocultas siguen ocultas y «Cómo Decirte» y «Jinne, Jinne» aparecen una sola vez.

### Procedimiento para completar la autorización humana

1. **Decisión del propietario por obra:**
   - título;
   - artistas;
   - rol y créditos de Luis Guinea;
   - estado y año;
   - género y mood, del vocabulario de `vocabularies.json`;
   - `sync_availability` (`on_request` / `not_offered`) y, aparte, las escenas de `use_scene`;
   - portada;
   - ventana de preview (A, B u otra).

   Las obras PyL necesitan además constancia de la autorización de sus destinatarios.
2. **Registro:** rellenar `credits` y `editorial` de la grabación y vaciar `provisional`.
3. **Revisión humana:** abrir un caso nuevo en `spikes/essentia/human_review_decisions.json` con:
   - `review_id`;
   - `catalog_link` con `status: "mapped"`;
   - `credits_decision`;
   - género y mood revisados.

   Si una obra lleva el género `cinematic_classical`, queda excluida de la reproducción aleatoria.
4. **Selección pública:** añadir el `review_id` a `public_music_selection.json`. Las seis ocultas no se tocan.
5. **Manifiesto de previews:** añadir a `music_preview_manifest.json` una entrada `verified` con:
   - `association.basis: "human_authorization"`;
   - `window.approved_s`;
   - el sha256 del master.

   Hace falta una política nueva (`approved-preview-window-v3`) en `POLICIES` de `generate_music_previews.py`.
6. **Generación:** ejecutar `generate_music_previews.py`, registrar `preview_sha256` y después ejecutar
   `generate_public_music_data.py`.
7. **Verificación:** ejecutar `check_public_music.py`, las pruebas focalizadas y
   `scripts/verificar_catalogo_masters.py`. En ese momento hay que actualizar la lista `NUEVAS` de ese script,
   que hoy exige que estas obras no estén publicadas.

## Fichas editables

Fichas del inventario inicial (2026-10-19), conservadas como evidencia. Las nueve NUEVAS quedaron resueltas
en las fases 3–5 («Allí Estás» es ahora «Ahí Estás»); sus campos «Faltan» ya no están pendientes.

### Cómo Decirte — DUPLICADA
- Master ZIP: `Pablo Delgado y Luis Guinea - Cómo Decirte.wav` · pcm_s24le 44,1 kHz estéreo · 208,5 s [M] · sha256 `cfa7e0c4…16373a`
- Portada ZIP: `Cover Art Cómo Decirte.jpeg` (3000×3000) [M]
- Catálogo: `como-decirte--luis-guinea--2022` (audio_ref `PDelgado_Cómo Decirte_SPOTIFY.wav`, portada propia ya asociada)
- Decisión pendiente: ¿el WAV del ZIP es un master distinto/mejor que el ya referenciado? No se sobrescribe nada. [?]

### Jinee Jinee (Friends and Jinee) — DUPLICADA PROBABLE
- Master: `PyL Jinee Jinee (Friends and Jinee) - Pablo Delgado y Luis Guinea (SPOTIFY).wav` · pcm_s24le 252,3 s [M] · sha256 `563b4083…ec56f4`
- Portada: `PyL Cover Art Jinee Jinee (Friends and Jinee).jpg` 3000×3000 [M]
- Catálogo: `jinne-jinne--canciones-de-puno-y-letra` (#52, publicada, título «Jinne, Jinne», mp3 «Jinee Jinee (Jinee and Friends)»)
- Decisión pendiente: confirmar que es la misma obra, grafía oficial del título (Jinee vs Jinne) y si la portada oficial sustituye a la genérica. [?]

### 1000 Días — NUEVA
- Master: `Pablo Delgado - 1000 Días.wav` · pcm_s16le 226,0 s [M] · sha256 `81e9c32d…ce9609`; portada `Cover Art 1000 Días.jpg` 3000×3000 [M]
- Faltan: artistas/créditos de Luis Guinea, año, ISRC, estado de lanzamiento, enlaces, autorización, ventana de preview, género/mood. Portada: correspondencia por nombre de archivo, no verificada por el propietario. [?]

### En El Momento Justo — NUEVA
- Master: `Pablo Delgado - En El Momento Justo.wav` · pcm_s16le 237,8 s [M] · sha256 `3efdcdac…6f289ed`; portada `Cover Art En El Momento Justo.jpg` 3000×3000 [M]
- Faltan los mismos campos que en «1000 Días». [?]

### Solo Esta Noche — NUEVA
- Master: `Pablo Delgado - Solo Esta Noche.wav` · pcm_s24le 255,1 s [M] · sha256 `c470a352…338f60`; portada `Cover Art Solo Esta Noche.jpg` 3500×3500 [M]
- Faltan los mismos campos. [?]

### Tonto Enamorado — NUEVA (¿versión «Warm»?)
- Master: `Pablo Delgado - Tonto Enamorado.wav` · pcm_s24le 256,6 s [M] · sha256 `9775a2ca…e371f0`; portada `Cover Art Tonto Enamorado (Warm).jpeg` 3000×3000 [M]
- La portada dice «Warm»: confirmar si el master corresponde a esa versión. Faltan los mismos campos. [?]

### PyL Allí Estás (Claudia y Carlos) — NUEVA, derechos dudosos
- Master: `PyL Allí Estás (Claudia y Carlos) - Pablo Delgado y Luis Guinea (SPOTIFY).wav` · 249,9 s [M] · sha256 `45d2f6dd…519951`; portada 3000×3000 [M]
- Canción personalizada de «Canciones de Puño y Letra» para personas concretas: se requiere autorización de publicación del propietario y, si procede, de los destinatarios. [?]

### PyL El Sembrador (Familia y Chucho) — NUEVA, derechos dudosos
- Master: `…El Sembrador (Familia y Chucho) - Luis Guinea (SPOTIFY).wav` · 170,7 s [M] · sha256 `a16ab119…b2cd84`... (completo: `a16ab1194101dcf10744b2057ca89c10a01ee9ed9fc099b06014e00525cd2a84`); portada 3000×3000 [M]
- Misma decisión de derechos que arriba. [?]

### PyL Gracias Por Todo (Nietos y Tita) — NUEVA, derechos dudosos
- Master: `…Gracias Por Todo (Nietos y Tita) - Pablo Delgado y Luis Guinea (SPOTIFY).wav` · 168,8 s [M] · sha256 `79ed1b0e…c1007c5e18`... (completo: `79ed1b0e0cabb9934681906b7130430bdf740ebe57b50f26c64460c1007c5e18`); portada 3000×3000 [M]
- Misma decisión de derechos. [?]

### PyL Hasta el Final de mis Días (Coté y Javier) — NUEVA, derechos dudosos
- Master: `…Hasta el Final de mis Días (Coté y Javier) - Luis Guinea (SPOTIFY).wav` · 173,0 s [M] · sha256 `55fe3ff13eb58a3d71d6311a5c998ccf39c66055365afce4b9e1b37c73533311`; portada 3000×3000 [M]
- Misma decisión de derechos. [?]

### PyL Juntos Somos Imparables (Sofi y Tony) — NUEVA, derechos dudosos
- Master: `…Juntos Somos Imparables (Sofi y Tony) - Luis Guinea (SPOTIFY).wav` · 213,1 s [M] · sha256 `27664e369860c4992f676ba4326f2043298e9ba2a0349c7a0f3c9fb3166aa609`; portada 3000×3000 [M]
- Misma decisión de derechos. [?]

## Para integrar una obra cuando se resuelva

1. Añadir su grabación a `data/music-catalog/catalog_recordings.json` con `basis` y `provisional: []`.
2. Revisión humana (género, mood, rol) y `review_id` en el banco de decisiones; añadir a `public_music_selection.json`.
3. Ventana de preview aprobada en `music_preview_manifest.json`; generar con `generate_music_previews.py`.
4. Convertir la portada oficial a `assets/images/*.webp` y asociarla en `public_artwork_corrections.json`.
5. Regenerar con `generate_public_music_data.py` y pasar `scripts/verificar_catalogo_masters.py`.
