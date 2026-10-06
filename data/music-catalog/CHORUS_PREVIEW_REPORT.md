# Informe de previews de coro

## Criterio

Cada preview público de `/music/` es una ventana de coro aprobada por el propietario
(`trim_policy: approved-chorus-window-v1` en `music_preview_manifest.json`, esquema
`music-preview-manifest-v2`). Los intervalos salen del análisis local del 2026-10-05 sobre los
masters privados: repetición de letra transcrita (Whisper small con tiempos por palabra),
segmentación estructural laplaciana (croma/MFCC) y energía RMS. Trece intervalos se
identificaron con confianza; La Bamba, Allá e Imagina tenían varios candidatos y Nuestro Hogar
tenía un coro más largo que 45 s. El propietario aprobó un intervalo para cada uno de esos
cuatro casos.

Ese análisis fue temporal y no se conserva: la selección queda reproducible porque el manifest
registra para cada entrada el intervalo aprobado (`window.approved_s`), la ventana codificada
(`start_s`, `duration_s`), el sha256 del master y el sha256 del preview resultante.
`generate_music_previews.py` vuelve a codificar cada ventana con flags bitexact y falla si el
master o el preview no coinciden con esos hashes.

Codificación: MP3 128 kb/s, 44,1 kHz, estéreo, fundido de entrada de 0,5 s y de salida de 2 s,
sin metadatos. Cada borde puede apartarse como máximo 1 s del intervalo aprobado, y solo para
evitar un corte técnicamente defectuoso; el ajuste queda documentado en `window.edge_adjustment`.

## Intervalos finales

| # | Obra | Intervalo aprobado (s) | Ventana codificada (s) | Duración | Ajuste |
|---|---|---|---|---|---|
| 25 | Hasta Que Lleguemos Al Mar | 106,5–145,0 | 106,5–145,0 | 38,5 s | — |
| 02 | Hace Tanto Tiempo | 57,5–91,0 | 57,5–91,0 | 33,5 s | — |
| 04 | Volver a Verte (Luis Guinea) | 67,0–107,5 | 67,0–107,5 | 40,5 s | — |
| 35 | Cómo Decirte | 98,0–141,0 | 98,0–141,0 | 43,0 s | — |
| 03 | Nuestro Hogar | 69,5–114,5 | 69,5–114,4 | 44,9 s | final −0,1 s |
| 05 | 12 Meses | 86,0–129,5 | 86,0–129,5 | 43,5 s | — |
| 11 | La Bamba | 130,5–170,5 | 130,5–170,5 | 40,0 s | — |
| 01 | Abrazo Imaginario | 168,0–205,0 | 168,0–205,0 | 37,0 s | — |
| 06 | Allá | 170,0–213,5 | 170,0–213,5 | 43,5 s | — |
| 07 | Anoche Me Enamoré | 75,0–115,0 | 75,0–115,0 | 40,0 s | — |
| 08 | Eres Veneno | 126,5–164,0 | 126,5–164,0 | 37,5 s | — |
| 09 | Imagina | 72,0–106,0 | 72,0–106,0 | 34,0 s | — |
| 10 | Invencible | 120,0–165,0 | 120,0–164,9 | 44,9 s | final −0,1 s |
| 13 | Si Antes Te Hubiera Conocido – Cover Acústico | 47,0–83,0 | 47,0–83,0 | 36,0 s | — |
| 14 | Vida Tras Vida | 44,0–83,0 | 44,0–83,0 | 39,0 s | — |
| 15 | Volver a Verte (Ana Guinea) | 70,3–111,0 | 70,3–111,0 | 40,7 s | — |

**Motivo de los dos ajustes:** con una ventana de 45,0 s exactos, ffprobe informa 45,000 s,
pero el recorrido de frames MP3 que usa la validación pública (`audio_stdlib.mp3_duration`)
mide 45,06 s por la cabecera Info y el relleno de LAME, así que la publicación rechazaría el
preview. Adelantar el final 0,1 s lo deja por debajo de 45 s. `check_preview` aplica
ambas mediciones.

El preview de #04 mide 40,47 s en lugar de 40,5 s. El master es AAC (`.m4a`), y la diferencia de
0,03 s es compatible con el cebado del códec al decodificar. No es un ajuste de borde.

## Créditos de las ocho obras nuevas

Igual que 12 Meses y La Bamba, su rol público sale de la regla documentada en
`spikes/essentia/CATALOG_CATEGORY.md`: la carpeta de primer nivel del audio vinculado. Las ocho
tienen su audio en `audios/Productor/` con vínculo inequívoco, así que se publican como
`Producer`. Ese crédito está consolidado en `spikes/essentia/human_review_decisions.json`
(`credits` y `credits_decision` de cada obra); no se añadió ningún otro. Ninguna obra nueva quedó
excluida por falta de datos de créditos.

## Excluidas de la salida pública

Siguen en la selección y en el manifest como `blocked`, sin preview. Se registran en
`public_catalog_exclusions.json`: #33 Adiós Amor (Versión Bolero), #34 Blue Moon,
#36 A Escondidas, #37 Lo Que Queda de Mí y #38 Shape of You – Acoustic. Motivo:
`no_authorized_preview`, porque no hay un master privado autorizado.

## Artefactos retirados

`analyze_chorus_candidates.py` y `chorus_candidates.json` (análisis previo con la biblioteca
estándar; no superó sus propios umbrales y propone otros intervalos) no son necesarios para
reproducir la selección aprobada y no forman parte del repositorio.
