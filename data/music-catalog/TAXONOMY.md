# Taxonomía editorial para discovery y sync (borrador v1)

Estado: **propuesta para evaluar**. Todavía no se aplica a `catalog_master.json`, ni a `/music/`, ni al generador.

- La versión legible por máquina está en [`vocabularies.json`](vocabularies.json). Los identificadores de cada tabla de vocabulario de este documento coinciden con los del JSON.
- **Enmienda 2026-09-28 (revisión humana).** La revisión humana del propietario, consolidada en [`spikes/essentia/human_review_decisions.json`](spikes/essentia/human_review_decisions.json), aprueba `genre: reggae`, `subgenre: reggae_pop`, `theme: food_drink`, `mood` hasta 4 valores, `emotion` hasta 3, el campo aparte `version_type` (§13.1) y la clase de evidencia `human_review` (§12). No aprueba `perceived_tempo`, `theme: commitment`, un theme de humor ni `food_beverage_commercial`. Detalle en `vocabularies.json` → `amendments`.

## 0. Principios

1. **Un concepto, un campo.** Cada término existe en un solo vocabulario. No hay «sad» en Mood y en Emotion a la vez, ni «Christmas» como género.
2. **Cada campo responde a una pregunta distinta:**

   | Campo | Pregunta | Se juzga a partir de |
   |---|---|---|
   | Genre / Subgenre | ¿Qué estilo musical es? | Lenguaje musical y producción |
   | Mood | ¿Qué atmósfera crea el sonido? | Armonía, timbre, textura y dinámica. Vale igual en instrumentales. |
   | Emotion | ¿Qué siente o expresa la voz o el protagonista? | Letra e interpretación |
   | Theme | ¿De qué trata la letra? | Contenido semántico de la letra |
   | Use/Scene | ¿En qué producción o escena encaja? | Juicio de supervisión, a partir de todo lo anterior |
   | Energy | ¿Cuánta intensidad tiene la mayor parte de la pista? | Densidad, dinámica e impulso. No es el tempo. |
   | Tempo | ¿A qué velocidad va el pulso? | BPM medido o declarado |

   Ejemplos que distinguen conceptos cercanos:

   - **Emotion `heartbreak` frente a Theme `breakup`.** La ruptura es el asunto; el desamor, lo que se siente.
   - **Mood `vintage` frente a Emotion `nostalgia`.** El primero es un rasgo de producción; el segundo, un sentimiento.
   - **Mood `calm` frente a Emotion `peace`.** La calma es sonora; la paz, interior.
   - **Theme `holiday_christmas` frente a Use/Scene `holiday_season`.** El tema exige una letra navideña. El uso puede recomendarse para cualquier pista apta para una campaña navideña.
   - **Genre `christian_worship` frente a Theme `faith_spirituality`.** Una balada pop que habla de Dios es `pop` + `faith_spirituality`. Solo es `christian_worship` si además sigue las convenciones de alabanza, CCM o góspel.

3. **Identificadores estables.** Van en minúsculas, en inglés y con `snake_case`. Cada término tiene etiqueta en inglés y en español, así que la interfaz filtra por el identificador sin depender del idioma.
4. **Vacío no es «ninguno».** Una celda vacía significa «sin clasificar». Para decir que una pista no tiene voz se usa `instrumental`, no se deja Vocal Type vacío.
5. **Nada se deduce del título, el artista, el artwork, el nombre del fichero ni la intuición.** Cada valor necesita una de las evidencias de la sección 12.
6. **Vocabulario compacto.** Si falta un término, se propone y se añade al vocabulario con su definición. No se escribe texto libre.

## 1. Formato común

- En formato tabular, los valores múltiples se separan con `;` (`pop; rock`). El primero es el principal cuando el orden importa (Genre).
- La cardinalidad indicada rige **cuando la obra está clasificada**. Una obra sin clasificar tiene todos los campos vacíos.

| Campo | Columna | Cardinalidad | Múltiple |
|---|---|---|---|
| `genre` | Genre | 1–2 | sí |
| `subgenre` | Subgenre | 0–2 | sí |
| `mood` | Mood | 1–4 | sí |
| `emotion` | Emotion | 0–3 | sí |
| `energy` | Energy | 1 | no |
| `tempo_bpm` | Tempo/BPM | 0–1 (entero de 40 a 220) | no |
| `tempo_class` | Tempo Class (columna nueva) | 0–1 | no |
| `vocals_instrumental` | Vocals/Instrumental | 1 | no |
| `vocal_type` | Vocal Type | 0–3 | sí |
| `language` | Language | 0–2 | sí |
| `theme` | Theme | 0–3 | sí |
| `use_scene` | Use/Scene | 0–4 | sí |

## 2. Genre

Estilo musical dominante. Máximo 2, el principal primero. Mercado e idioma **no** son géneros: «pop latino» se clasifica como `pop` + `language: es`. Si la obra es un cover, el género es el de **esta** grabación, no el de la original.

<!-- vocab:genre -->
| id | Etiqueta (en / es) | Significado |
|---|---|---|
| `pop` | Pop / Pop | Estructura verso-estribillo, gancho melódico, producción de radio o streaming |
| `rock` | Rock / Rock | Guitarra eléctrica y batería con backbeat como base |
| `folk_singer_songwriter` | Folk / Singer-Songwriter · Folk / Cantautor | Manda la letra; acompañamiento acústico reducido |
| `rnb_soul` | R&B / Soul | Groove de R&B o soul, melismas y armonía extendida |
| `hip_hop` | Hip-Hop | Producción basada en beats y loops, rap o estética hip-hop |
| `electronic` | Electronic / Electrónica | Sintetizadores y programación como base |
| `jazz_blues` | Jazz & Blues / Jazz y blues | Lenguaje de jazz (swing, improvisación) o forma y color de blues |
| `latin_traditional` | Latin Traditional / Latino tradicional | Bolero, trova, son, bossa nova |
| `latin_tropical` | Tropical | Salsa, bachata, cumbia, merengue |
| `latin_urban` | Latin Urban / Urbano latino | Reggaetón, dembow, trap latino |
| `regional_mexican` | Regional Mexican / Regional mexicano | Mariachi, ranchera, norteño, banda, corrido |
| `christian_worship` | Christian & Worship / Cristiana y alabanza | Alabanza, CCM o góspel (letra devocional y convenciones del género) |
| `cinematic_classical` | Cinematic & Classical / Cinematográfica y clásica | Orquesta, cámara, piano neoclásico o score |
| `reggae` | Reggae | Ritmo de reggae como base (extensión aprobada 2026-09-28) |
<!-- /vocab -->

## 3. Subgenre

Jerárquico: cada subgénero tiene un padre, y el padre **debe** estar en Genre. Máximo 2. Es opcional: si ningún subgénero describe la obra con precisión, se deja vacío en lugar de forzar uno.

<!-- vocab:subgenre -->
| id | Padre | Significado |
|---|---|---|
| `pop_ballad` | `pop` | Pop lento y lírico centrado en la voz; incluye la balada romántica latina |
| `acoustic_pop` | `pop` | Producción pop con instrumentación predominantemente acústica |
| `indie_pop` | `pop` | Pop de estética independiente |
| `synth_pop` | `pop` | Pop en el que mandan los sintetizadores |
| `dance_pop` | `pop` | Pop con pulso de pista de baile |
| `pop_rock` | `rock` | Rock con estructura y ganchos pop |
| `soft_rock` | `rock` | Rock de dinámica contenida |
| `alternative_rock` | `rock` | Rock con guitarras distorsionadas y estética alternativa |
| `indie_rock` | `rock` | Rock de estética independiente |
| `indie_folk` | `folk_singer_songwriter` | Folk en capas acústicas, con coros y ambientes |
| `contemporary_rnb` | `rnb_soul` | R&B de producción actual |
| `neo_soul` | `rnb_soul` | Soul con armonía jazzística |
| `classic_soul` | `rnb_soul` | Soul de los años 60–70 |
| `funk` | `rnb_soul` | Groove sincopado, bajo y guitarra rítmica |
| `boom_bap` | `hip_hop` | Batería sampleada y swing de los años 90 |
| `trap` | `hip_hop` | 808, hi-hats rápidos, half-time |
| `lofi_hip_hop` | `hip_hop` | Beat relajado con textura degradada |
| `ambient` | `electronic` | Texturas sin pulso protagonista |
| `downtempo` | `electronic` | Electrónica lenta y relajada con pulso |
| `house` | `electronic` | Bombo a negras (four-on-the-floor), de 115 a 130 BPM |
| `edm` | `electronic` | Build-ups y drops de festival |
| `vocal_jazz` | `jazz_blues` | Jazz con voz solista |
| `swing` | `jazz_blues` | Pulso de swing, big band o combo |
| `lounge` | `jazz_blues` | Jazz ligero de fondo |
| `blues` | `jazz_blues` | Forma y fraseo de blues |
| `bolero` | `latin_traditional` | Ritmo de bolero |
| `trova` | `latin_traditional` | Canción de autor con guitarra |
| `son` | `latin_traditional` | Son cubano o mexicano |
| `bossa_nova` | `latin_traditional` | Ritmo y armonía de bossa nova |
| `salsa` | `latin_tropical` | Clave, montuno y metales |
| `bachata` | `latin_tropical` | Requinto y güira |
| `cumbia` | `latin_tropical` | Ritmo de cumbia |
| `merengue` | `latin_tropical` | Tambora y güira |
| `reggaeton` | `latin_urban` | Patrón dembow |
| `latin_trap` | `latin_urban` | Trap de la escena urbana latina |
| `mariachi_ranchera` | `regional_mexican` | Mariachi o ranchera |
| `norteno` | `regional_mexican` | Acordeón y bajo sexto |
| `banda` | `regional_mexican` | Banda de viento y percusión |
| `corrido` | `regional_mexican` | Forma narrativa de corrido |
| `worship` | `christian_worship` | Alabanza congregacional |
| `ccm` | `christian_worship` | Pop o rock de letra cristiana, no congregacional |
| `gospel` | `christian_worship` | Góspel con coro y llamada y respuesta |
| `orchestral_score` | `cinematic_classical` | Orquesta con escritura de score |
| `neoclassical` | `cinematic_classical` | Piano o cámara de lenguaje minimalista o neoclásico |
| `trailer_epic` | `cinematic_classical` | Híbrido orquestal con percusión épica |
| `reggae_pop` | `reggae` | Reggae con estructura y ganchos pop (extensión aprobada 2026-09-28) |
<!-- /vocab -->

## 4. Mood (atmósfera sonora)

Describe **cómo suena**: el color que la música da a una escena. Se juzga con el audio, sin la letra, y es igual de aplicable a instrumentales. Entre 1 y 4 valores; el más característico primero.

<!-- vocab:mood -->
| id | Etiqueta (en / es) | Significado |
|---|---|---|
| `bright` | Bright / Luminosa | Armonía mayor y timbres claros |
| `warm` | Warm / Cálida | Timbres acústicos o analógicos cercanos: cobijo |
| `dreamy` | Dreamy / Onírica | Texturas difusas y reverberación amplia: flotante |
| `intimate` | Intimate / Íntima | Arreglo mínimo, fuente cercana y seca |
| `calm` | Calm / Tranquila | Sin tensión ni impulso marcado |
| `melancholic` | Melancholic / Melancólica | Color menor o modal: grave sin ser oscura |
| `dark` | Dark / Oscura | Registro grave y disonancia: ominosa |
| `tense` | Tense / Tensa | Ostinatos y armonía sin resolver: suspense |
| `epic` | Epic / Épica | Gran escala y crescendos |
| `groovy` | Groovy / Rítmica | El ritmo es el protagonista |
| `playful` | Playful / Juguetona | Ligera y desenfadada |
| `vintage` | Vintage | Producción que evoca una época pasada |
<!-- /vocab -->

Reglas:

- `dark` y `bright` son excluyentes. `calm` y `tense`, también.
- `melancholic` es color sonoro. Si la letra habla de tristeza, eso va en Emotion (`heartbreak`, `sorrow`), no aquí.

## 5. Emotion (emoción expresada)

Describe **qué siente la voz o el protagonista**. Se juzga con la letra y la interpretación. Entre 0 y 3 valores.

- En pistas `instrumental` o `wordless_vocal`, Emotion queda vacía salvo que una nota de programa del autor la declare. La atmósfera de un instrumental se describe con Mood.

<!-- vocab:emotion -->
| id | Etiqueta (en / es) | Significado |
|---|---|---|
| `joy` | Joy / Alegría | Felicidad o euforia |
| `love` | Love / Amor | Afecto o ternura: de pareja, familiar o fraternal |
| `longing` | Longing / Anhelo | Deseo de algo ausente, sin pérdida definitiva |
| `heartbreak` | Heartbreak / Desamor | Dolor por ruptura o rechazo amoroso |
| `sorrow` | Sorrow / Pesar | Tristeza por una pérdida no amorosa: muerte, despedida |
| `hope` | Hope / Esperanza | Expectativa positiva ante el futuro |
| `nostalgia` | Nostalgia | Añoranza del pasado |
| `gratitude` | Gratitude / Gratitud | Agradecimiento |
| `determination` | Determination / Determinación | Voluntad de superar o conseguir algo |
| `vulnerability` | Vulnerability / Vulnerabilidad | Fragilidad, miedo o confesión |
| `anger` | Anger / Rabia | Enfado, reproche o rebeldía |
| `peace` | Peace / Paz | Serenidad interior o reconciliación |
<!-- /vocab -->

Reglas:

- `longing`, `heartbreak` y `sorrow` se distinguen por la pérdida. Si no hay pérdida, es `longing`. Si la pérdida es amorosa, `heartbreak`. Si es de otro tipo, `sorrow`.
- `joy` y `sorrow` no se combinan. Para un tono agridulce se usa `nostalgia`.

## 6. Energy (escala ordinal de 5 niveles)

Mide la intensidad percibida en la **sección dominante**, la que ocupa la mayor parte de la duración, no en el pico. Es independiente del tempo: una balada lenta con banda completa en forte es `high`. Un solo valor.

<!-- vocab:energy -->
| id | Ordinal | Etiqueta (en / es) | Ancla |
|---|---|---|---|
| `very_low` | 1 | Very Low / Muy baja | 1–2 instrumentos, pp–p, sin percusión o con percusión apenas perceptible |
| `low` | 2 | Low / Baja | Arreglo reducido, percusión ligera o ausente, p–mp |
| `medium` | 3 | Medium / Media | Pulso estable, arreglo medio o banda, mf |
| `high` | 4 | High / Alta | Arreglo denso, batería marcada, f |
| `very_high` | 5 | Very High / Muy alta | ff sostenido, himno o agresividad |
<!-- /vocab -->

Regla de duda: si la pista oscila entre dos niveles, se asigna el de la sección más larga. Si las secciones duran lo mismo, el inferior. La curva (pistas con build o crescendo) **no** se codifica en v1: ver la sección 13.

## 7. Tempo: BPM y clase

- **`tempo_bpm`**: entero de 40 a 220. Solo puede venir de:
  - un valor **declarado** en una fuente: la sesión del DAW o el dato del titular;
  - una **medición** sobre un audio vinculado de forma inequívoca (sección 12).

  Nunca se estima de oído ni por el género.
- **Pulso de referencia**: la negra que marcaría un oyente al llevar el pulso. Si el valor declarado es el doble o la mitad de ese pulso (half-time o double-time), se anota el pulso percibido y en *Classifier notes* se deja constancia del valor declarado.
- **`tempo_class`** se **deriva** del BPM con los umbrales de la tabla. No se asigna a mano, salvo `free_time`, que exige dejar el BPM vacío.

<!-- vocab:tempo_class -->
| id | BPM | Etiqueta (en / es) |
|---|---|---|
| `very_slow` | 40–69 | Very Slow / Muy lento |
| `slow` | 70–89 | Slow / Lento |
| `medium` | 90–114 | Medium / Medio |
| `fast` | 115–139 | Fast / Rápido |
| `very_fast` | 140–220 | Very Fast / Muy rápido |
| `free_time` | — | Free Time / Tempo libre (rubato, ad libitum; sin BPM) |
<!-- /vocab -->

`tempo_class` es un campo **nuevo** que esta propuesta añade. `catalog_master.json` solo tiene `tempo_bpm`. Sustituye al antiguo campo «Tempo Feeling (Lento / Medio / Rápido)», que era subjetivo.

## 8. Vocals/Instrumental

Un valor. Es obligatorio en cualquier obra clasificada.

<!-- vocab:vocals_instrumental -->
| id | Etiqueta (en / es) | Criterio inequívoco |
|---|---|---|
| `vocal` | Vocal | Hay letra inteligible: cantada, rapeada o hablada |
| `wordless_vocal` | Wordless Vocal / Voz sin letra | Hay voz humana, pero ninguna palabra inteligible |
| `instrumental` | Instrumental | Ninguna voz humana |
<!-- /vocab -->

Las versiones alternativas (instrumental, a cappella) son **grabaciones distintas** con su propio `id`. No se marcan aquí.

## 9. Vocal Type

Solo describe la **voz principal**; los coros de apoyo no se etiquetan. Aplica solo si Vocals/Instrumental es `vocal` o `wordless_vocal`. Hay dos grupos:

- **lead**: como mínimo uno, obligatorio si hay voz. Un dúo es simplemente dos valores lead: `male_lead; female_lead`.
- **delivery**: opcional. Se añade al lead cuando una parte sustancial no es cantada.

<!-- vocab:vocal_type -->
| id | Grupo | Significado |
|---|---|---|
| `male_lead` | lead | Timbre adulto masculino (describe el timbre, no la identidad) |
| `female_lead` | lead | Timbre adulto femenino (describe el timbre, no la identidad) |
| `child_lead` | lead | Voz infantil |
| `group_lead` | lead | Grupo o coro como voz principal |
| `rap` | delivery | Parte sustancial rapeada |
| `spoken_word` | delivery | Parte sustancial hablada o recitada |
<!-- /vocab -->

## 10. Language

Códigos ISO 639-1 del idioma de la letra inteligible.

- Solo si Vocals/Instrumental es `vocal`.
- Máximo 2. Un segundo idioma cuenta solo si ocupa al menos una sección completa (verso o estribillo), no palabras sueltas.
- El idioma del título **no** es evidencia.
- La lista es cerrada. Para ampliarla se añade el código ISO al vocabulario.

<!-- vocab:language -->
| id | Idioma |
|---|---|
| `es` | Español |
| `en` | Inglés |
| `pt` | Portugués |
| `fr` | Francés |
| `it` | Italiano |
| `de` | Alemán |
<!-- /vocab -->

## 11. Theme y Use/Scene

**Theme**: de qué trata la letra. Entre 0 y 3 valores. Requiere letra, o una nota de programa del autor en los instrumentales. El título no es evidencia.

<!-- vocab:theme -->
| id | Etiqueta (en / es) | Significado |
|---|---|---|
| `romantic_love` | Romantic Love / Amor romántico | Relación amorosa: enamoramiento, deseo, compromiso |
| `breakup` | Breakup / Ruptura | Final o imposibilidad de una relación |
| `family` | Family / Familia | Vínculo familiar |
| `friendship` | Friendship / Amistad | Vínculo de amistad |
| `faith_spirituality` | Faith & Spirituality / Fe y espiritualidad | Dios, fe, oración |
| `self_empowerment` | Self-Empowerment / Superación | Resiliencia, ambición, superación |
| `home_belonging` | Home & Belonging / Hogar y pertenencia | Hogar, raíces, identidad |
| `journey_travel` | Journey & Travel / Viaje | Viaje, camino, partida |
| `celebration` | Celebration / Celebración | Fiesta, disfrute del momento |
| `passage_of_time` | Passage of Time / Paso del tiempo | Recuerdos, crecer, envejecer |
| `farewell_loss` | Farewell & Loss / Despedida y pérdida | Muerte, duelo, despedida no amorosa |
| `nature` | Nature / Naturaleza | Mar, paisaje, elementos naturales |
| `holiday_christmas` | Christmas / Navidad y fiestas | Navidad o fiestas de fin de año en la letra |
| `food_drink` | Food & Drink / Comida y bebida | Comida o bebida como asunto central (extensión aprobada 2026-09-28; no sustituye a `celebration`) |
<!-- /vocab -->

**Use/Scene**: recomendación de sync, es decir, dónde colocaría la pista un supervisor. Entre 0 y 4 valores.

- Es **siempre** un juicio humano posterior a clasificar el resto. Nunca se deriva automáticamente.
- No repite el mood: «escena triste» no es un uso; `reflective_montage` sí.

<!-- vocab:use_scene -->
| id | Etiqueta (en / es) | Significado |
|---|---|---|
| `romantic_scene` | Romantic Scene / Escena romántica | Cita, beso, reconciliación |
| `dramatic_moment` | Dramatic Moment / Momento dramático | Clímax, revelación, confrontación |
| `reflective_montage` | Reflective Montage / Montaje reflexivo | Recuerdo, soledad, introspección |
| `uplifting_montage` | Uplifting Montage / Montaje de superación | Progreso, entrenamiento, logro |
| `party_celebration` | Party / Celebration / Fiesta o celebración | Fiesta o bar, diegético o no |
| `road_trip_travel` | Road Trip / Travel / Viaje en carretera | Carretera, viaje, paisaje |
| `family_moment` | Family Moment / Momento familiar | Reunión familiar, infancia |
| `wedding` | Wedding / Boda | Ceremonia, primer baile |
| `holiday_season` | Holiday Season / Temporada navideña | Campaña o contenido de fin de año |
| `faith_based_content` | Faith-Based Content / Contenido religioso | Película, evento o campaña religiosa |
| `opening_titles` | Opening Titles / Créditos iniciales | Apertura |
| `end_credits` | End Credits / Créditos finales | Cierre |
| `brand_storytelling` | Brand Storytelling / Publicidad emocional | Publicidad institucional o emocional |
| `lifestyle_commercial` | Lifestyle Commercial / Publicidad lifestyle | Publicidad ligera de producto |
| `documentary` | Documentary / Documental | Documental o reportaje |
<!-- /vocab -->

## 12. Evidencia y procedencia de cada valor

Cada valor asignado lleva una clase de evidencia y un mecanismo.

| Clase | Cuándo | Qué se registra |
|---|---|---|
| `objetivo` | El valor está en una fuente existente: celda de un XLSX original con valor, o metadata declarada por el titular | Referencia exacta a la celda o el documento |
| `analisis_audio` | Hay un audio local **inequívocamente** vinculado. Deben cumplirse las dos condiciones:<br>1) su nombre normalizado coincide con el título de la obra o con el nombre de `audio_ref`;<br>2) su duración difiere de `duration_ms` en ≤ 1,0 s.<br>Además, el atributo tiene que poder medirse sobre el audio. | Ruta relativa, sha256 del audio, duración, método y versión |
| `pendiente_humano` | Ninguna de las anteriores | Campo vacío, motivo y fuentes consultadas |
| `revision_humana` | Reservada para la fase siguiente: valor asignado por una persona tras escuchar | Revisor y fecha |
| `human_review` | Valor aprobado por la revisión humana documentada del propietario (2026-09-28). Tiene autoridad sobre ML/Essentia, que queda como evidencia separada | Documento fuente y fecha; consolidado en `spikes/essentia/human_review_decisions.json` |

Qué puede demostrar cada mecanismo:

| Campo | `objetivo` | `analisis_audio` (máquina, sin escucha humana) | Resto |
|---|---|---|---|
| `tempo_bpm` / `tempo_class` | Sí (BPM declarado) | Sí, con un detector de tempo validado | — |
| `vocals_instrumental`, `vocal_type`, `language` | Sí (créditos o letra del titular) | No fiable sin un modelo validado | Escucha humana |
| `energy` | No | Solo como apoyo (sonoridad y densidad); no asigna por sí solo | Escucha humana |
| `genre`, `subgenre`, `mood`, `emotion`, `theme` | Solo si el titular lo declara | No | Escucha humana o letra |
| `use_scene` | No | No | Siempre juicio humano |

## 13. Decisiones abiertas detectadas

1. **Tipo de versión** (original, cover, acústica, medley, remix, versión en otro idioma). Es un eje muy útil para sync que no aparece entre los 11 campos, y varios títulos del catálogo lo mencionan. Se propone como campo objetivo aparte, `version_type`, que no es Genre. El título solo es evidencia si lo declara el titular. *Enmienda 2026-09-28:* la revisión humana aprueba los valores `cover_acoustic`, `mariachi`, `acoustic_piano` y `piano_vocal` (`vocabularies.json` → `separate_fields.version_type`, 0–1 valor). El resto del eje sigue abierto.
2. **Curva de energía** (estable, build, drop). Se deja fuera de v1 para no fragmentar Energy.
3. **Instrumentación.** No forma parte de los 11 campos; es candidata a v2.
4. **`tempo_class`** y la columna *Tempo Class* son un cambio de esquema que hay que aprobar antes de reincorporar la clasificación a la maestra.
