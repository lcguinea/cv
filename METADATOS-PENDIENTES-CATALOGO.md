# Metadatos pendientes del catálogo: ZIP «_MASTERS y COVER ARTS OFICIALES» (2026-10-19)

Decisión de esta integración: **no se ha publicado ninguna obra del ZIP**. El pipeline de publicación
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
| Nuevas, pendientes de autorización | 9 |
| Publicadas ahora | 0 |

Las seis canciones ocultas (#60, #61, #62, #70, #19, #31), el orden por año descendente, la exclusión
de obras orquestales de la selección aleatoria y el reproductor no se han modificado.

## Fichas editables

Cada ficha: `autorización de publicación` y `ventana de preview` sin rellenar = no publicable.

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
