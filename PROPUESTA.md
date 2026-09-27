# Propuesta de arquitectura, contenido y diseño

Esta propuesta se limita a la fase previa a implementación. Las decisiones factuales se apoyan en `CV_MASTER.md`; las decisiones visuales, de voz e interacción se apoyan en `BRAND.md`.

## Estado real del repositorio

Estado observado antes de crear este documento:

- En la raíz existen `.gitignore`, `BRAND.md`, `CV_MASTER.md`, `README.md`, `cover.png` y `profile_pic.png`.
- También existen directorios operativos `.claude/`, `.orchestrator/` y `estado/`, además de `.git/`. No forman parte del sitio propuesto.
- `git status --short` muestra sin seguimiento `BRAND.md`, `CV_MASTER.md`, `cover.png` y `profile_pic.png`. `README.md` y `.gitignore` no aparecen como modificados.
- `PROPUESTA.md` es el único archivo añadido en esta fase y, al terminar, también quedará sin seguimiento.
- `README.md` dice que este es el CV o portfolio interactivo de Luis Guinea y que el repositorio está en fase inicial, sin stack, arquitectura ni diseño decididos.

No existe todavía `index.html`, `cv.html`, código CSS o JavaScript, carpeta `assets`, PDF del CV ni configuración de despliegue.

## Árbol de archivos

Estructura prevista para la fase de implementación, todavía no creada:

```text
interactive-cv/
├── .nojekyll                    # Evita el procesamiento de Jekyll en GitHub Pages.
├── .gitignore                   # Conserva las exclusiones del repositorio.
├── index.html                   # Portfolio principal, EN por defecto y ES mediante i18n.
├── cv.html                      # CV semántico e imprimible en una página A4.
├── PROPUESTA.md                 # Decisiones aprobadas antes de implementar.
├── README.md                    # Instalación, preview, validación y despliegue, actualizado en fase posterior.
├── BRAND.md                     # Autoridad de diseño, voz e interacción, conservada intacta.
├── CV_MASTER.md                 # Autoridad factual, conservada intacta.
├── cover.png                    # Original conservado intacto aunque se descarte o derive otra imagen.
├── profile_pic.png              # Original conservado intacto; nunca se sobrescribe al optimizar.
├── css/
│   ├── styles.css               # Tokens, tipografía, layout, componentes, temas y responsive.
│   └── print.css                # Reglas A4, ocultación de UI y control de saltos de impresión.
├── js/
│   ├── main.js                  # Inicialización y mejoras progresivas.
│   ├── i18n.js                  # Selección de idioma, DOM, localStorage y fallback.
│   ├── strings.js               # Todos los strings EN y ES centralizados.
│   └── experience-filter.js     # Filtro accesible de experiencia por faceta.
└── assets/
    ├── cv.pdf                   # TODO: exportación aprobada del CV, no existe todavía.
    ├── fonts/
    │   ├── instrument-serif-latin.woff2
    │   ├── inter-latin.woff2
    │   └── ibm-plex-mono-latin.woff2
    └── images/
        ├── profile.webp         # Derivado optimizado, si se aprueba el retrato.
        ├── profile.avif         # Derivado moderno opcional con fallback WebP.
        └── og-image.jpg         # Imagen social aprobada, con composición tipográfica y fotografía autorizada.
```

El SVG editorial del artículo principal se incluiría en línea dentro de `index.html`, no como archivo separado, para asociar correctamente `title`, `desc`, etiquetas y tabla de datos. No se propone ninguna dependencia, framework ni proceso de build. `.gitignore`, `BRAND.md`, `CV_MASTER.md`, `cover.png`, `profile_pic.png` y `PROPUESTA.md` se conservan intactos durante la implementación.

## Tokens

La paleta usa únicamente los cinco colores de `BRAND.md` §8:

```css
:root {
  --color-ink: #111111;
  --color-paper: #F2EFE8;
  --color-graphite: #555555;
  --color-mist: #D8D5CE;
  --color-accent: #C85A32;

  --color-bg: var(--color-paper);
  --color-text: var(--color-ink);
  --color-text-muted: var(--color-graphite);
  --color-rule: var(--color-mist);

  --space-1: 0.25rem;
  --space-2: 0.5rem;
  --space-3: 0.75rem;
  --space-4: 1rem;
  --space-5: 1.5rem;
  --space-6: 2rem;
  --space-7: 3rem;
  --space-8: 4.5rem;
  --space-9: 7rem;
  --space-section: clamp(5rem, 10vw, 10rem);

  --line-thin: 1px;
  --line-strong: 2px;
  --radius-none: 0;
  --radius-small: 2px;

  --motion-fast: 140ms;
  --motion-base: 220ms;
  --ease-precise: cubic-bezier(0.2, 0.7, 0.2, 1);
}

@media (prefers-color-scheme: dark) {
  :root {
    --color-bg: var(--color-ink);
    --color-text: var(--color-paper);
    --color-text-muted: var(--color-mist);
    --color-rule: var(--color-mist);
  }
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --motion-fast: 0ms;
    --motion-base: 0ms;
  }
}
```

Contrastes calculados con la fórmula de luminancia relativa de WCAG:

| Uso | Par | Contraste | Decisión |
|---|---|---:|---|
| Texto principal claro | Ink sobre Paper | 16.44:1 | Cumple AAA para texto normal. |
| Texto secundario claro | Graphite sobre Paper | 6.49:1 | Cumple AA y AAA para texto grande. |
| Acento claro | Accent sobre Paper | 3.68:1 | No cumple 4.5:1 para texto normal; solo sirve para texto grande, elementos no textuales o decoración redundante. |
| Texto principal oscuro | Paper sobre Ink | 16.44:1 | Cumple AAA para texto normal. |
| Texto secundario oscuro | Mist sobre Ink | 12.88:1 | Cumple AAA para texto normal. |
| Acento oscuro | Accent sobre Ink | 4.46:1 | Queda por debajo de 4.5:1; no se usará como texto normal. Sí supera 3:1 para texto grande y elementos no textuales. |
| Combinación prohibida | Graphite sobre Ink | 2.53:1 | No cumple. Graphite no será texto ni control significativo sobre Ink. |
| Combinación prohibida | Mist sobre Paper | 1.28:1 | No cumple como texto. Mist queda limitado a líneas decorativas claras. |
| Alternativa oscura segura | Ink sobre Mist | 12.88:1 | Cumple AAA si un estado necesita fondo Mist y texto Ink. |
| Combinación prohibida | Paper sobre Accent | 3.68:1 | No cumple para texto normal. No habrá botones sólidos Accent con texto Paper. |

En claro, los enlaces conservan texto Ink y se distinguen mediante subrayado, peso, icono textual o posición; Accent puede marcar una línea, un punto o un estado adicional. En oscuro, el texto de enlace será Paper o Mist y Accent será una señal no textual. El foco tendrá forma y grosor visibles, no dependerá solo de color. Así, eliminar `--color-accent` no altera jerarquía, significado, navegación ni estado: composición, escala, subrayado, borde y texto siguen comunicando todo.

Los radios se limitan a cero o 2 px. El motion se limita a opacidad y transformaciones breves que no bloquean lectura. Con `prefers-reduced-motion`, los reveals aparecen ya en su estado final y desaparece cualquier desplazamiento o transición no esencial.

## Escala tipográfica

Instrument Serif aporta la voz editorial; Inter resuelve cuerpo e interfaz; IBM Plex Mono queda reservada para fechas, fuentes, métricas y datos, según `BRAND.md` §§9–10.

```css
--font-display: "Instrument Serif", Georgia, serif;
--font-sans: "Inter", Arial, sans-serif;
--font-mono: "IBM Plex Mono", "Courier New", monospace;

--type-hero: clamp(3.25rem, 10vw, 9rem);       /* 52–144 px, lh 0.88 */
--type-section: clamp(2.5rem, 5.4vw, 5.5rem);  /* 40–88 px, lh 0.96 */
--type-article: clamp(1.75rem, 3vw, 3.5rem);   /* 28–56 px, lh 1.02 */
--type-body: clamp(1rem, 0.35vw + 0.94rem, 1.1875rem); /* 16–19 px, lh 1.55 */
--type-meta: clamp(0.8125rem, 0.18vw + 0.78rem, 0.9375rem); /* 13–15 px, lh 1.4 */
--type-metric: clamp(2.25rem, 4.8vw, 5.25rem); /* 36–84 px, lh 0.95 */
```

- Hero y títulos de sección: Instrument Serif, peso normal, tracking levemente negativo solo si la fuente renderizada lo permite sin colisiones.
- Título de artículo: Instrument Serif, con una anchura que permita titulares largos sin parecer una tarjeta.
- Cuerpo e interfaz: Inter, peso 400; estados o etiquetas pueden usar 600.
- Metadatos y métricas: IBM Plex Mono, sin bajar de 13 px en pantalla.
- Texto largo: `max-inline-size: 68ch`, dentro del objetivo de 55 a 75 caracteres de `BRAND.md` §10. Resúmenes breves pueden quedar en 55–62ch.

La estrategia recomendada es alojar localmente archivos WOFF2 con `font-display: swap`, declarar fallbacks métricamente razonables y crear subconjuntos Latin y Latin Extended que conserven español, francés, signos matemáticos, flechas y el símbolo `×`. Esto evita una dependencia de terceros, reduce solicitudes y respeta rendimiento y necesidad funcional de `BRAND.md` §§29 y 31. La descarga, licencia y generación de subconjuntos deben verificarse antes de añadir los archivos. Si no se consiguen fuentes autorizadas, se usan los fallbacks del sistema sin bloquear la implementación.

## Grid

Base desktop a partir de 960 px:

- Contenedor máximo: 1440 px.
- Márgenes: `clamp(24px, 4vw, 72px)`.
- Doce columnas `minmax(0, 1fr)`.
- Gutter: `clamp(16px, 1.6vw, 28px)`.
- Ritmo vertical por secciones mediante `--space-section`, no mediante cajas repetidas.
- Todas las celdas llevan `min-inline-size: 0` para evitar desbordamientos.

Ocupación prevista:

| Sección y bloque | Columnas desktop |
|---|---|
| Hero, nombre | 1–12, con quiebre deliberado si mejora el ritmo. |
| Hero, descriptor | 2–8. |
| Hero, reveal de disciplinas | 7–12, posterior al descriptor. |
| Hero, navegación y selector | 1–12 como línea inferior editorial. |
| Writing, cabecera | 1–4. |
| Artículo principal, título y resumen | 4–10. |
| Artículo principal, métrica | 10–12. |
| Artículo principal, SVG y tabla accesible | 4–12. |
| Artículos 2 y 3 | Alternan 2–8 y 6–12. |
| Artículos 4 y 5 | Alternan 1–7 y 5–11. |
| Facets, introducción | 1–4. |
| Facets, índice editorial | 5–12, con filas de alturas definidas por contenido. |
| Experience, filtros | 1–3. |
| Experience, índice cronológico | 4–12. |
| Education, título | 1–3. |
| Education, tres entradas | 4–12 como lista, no como tres cards. |
| Skills, título | 1–3. |
| Skills, grupos | 4–12 en dos columnas textuales desiguales. |
| Contact, llamada y email | 1–8. |
| Contact, Medium, CV y PDF | 9–12. |

La asimetría procede del ancho del contenido, los cambios de escala y la alternancia de alineaciones. No habrá una cuadrícula de cards idénticas. Cada artículo mantiene la misma anatomía semántica, pero cambia de peso según la evidencia disponible.

## Lógica responsive

Breakpoints propuestos:

- 0–639 px: móvil diseñado como una secuencia editorial de una columna.
- 640–959 px: tablet, seis columnas y navegación reordenada.
- 960–1279 px: desktop, doce columnas.
- 1280 px o más: desktop amplio, mismo grid y mayor espacio negativo, sin ensanchar el cuerpo de texto.

Rediseño por sección:

- Hero: en móvil, `LUIS` y `GUINEA` pueden ocupar dos líneas intencionales. El descriptor aparece completo debajo. El reveal de disciplinas se convierte en una frase breve posterior, no en una nube de etiquetas. La navegación usa dos filas con objetivos táctiles de al menos 44 por 44 px; EN/ES queda al final, no flotante.
- Writing & Research: el artículo principal pasa a orden título, métrica, resumen, fuentes, visualización y enlace. Los otros cuatro son entradas editoriales separadas por reglas, no mini cards en dos columnas. Los metadatos nunca se fuerzan a una sola línea.
- SVG: usa `viewBox`, `inline-size: 100%`, `height: auto`, texto escalable y dos paneles apilados por CSS en móvil. A 360 px se muestra una lectura simplificada con los tres puntos; la tabla HTML accesible ofrece los mismos valores. No hay zoom ni paneo horizontal.
- Facets: se convierte en índice numerado vertical. Cada faceta abre contenido con un botón o `details`; sin hover obligatorio y sin mosaico.
- Experience: los botones de filtro desktop se sustituyen por un `select` etiquetado en móvil para evitar una fila horizontal de pills. Cada entrada presenta año, organización y rol primero; disciplina y resultado aparecen debajo. La mejora JavaScript no elimina la lista completa si falla.
- Education y Skills: listas lineales con encabezados claros. Skills conserva grupos pero pasa de dos columnas a una.
- Contact: email, Medium, CV HTML y PDF se apilan como enlaces de texto de ancho completo. No aparece el teléfono.
- `cv.html`: en pantalla móvil se lee como documento lineal. Las restricciones de dos columnas y A4 solo se activan en `@media print`.

Para garantizar ausencia de scroll horizontal a 360 px: `box-sizing: border-box` global, columnas con `minmax(0, 1fr)`, medios con `max-inline-size: 100%`, URLs con `overflow-wrap: anywhere`, sin anchos mínimos rígidos, navegación con wrap, filtros sin carrusel horizontal y prueba explícita a 360 px. El SVG y sus etiquetas se comprueban por separado. No se usará `overflow-x: hidden` para ocultar errores de layout.

## Plan sección por sección

### Hero

Contenido: `LUIS GUINEA`, `Creative × Analytical × Entrepreneurial`, Valencia y una frase breve derivada del perfil web que conecta trabajo creativo, música, datos y escritura sin enumerar profesiones como un listado. Después aparecen los destinos Writing, Experience, CV y Contact y el selector EN/ES. El hero nunca usa “Music Journalist”. Nombre, descriptor, base y perfil proceden de `CV_MASTER.md` §§1–2.

El reveal sería progresivo por orden de lectura, no por animación obligatoria: primero identidad, luego la intersección de pensamiento creativo y analítico, y al final las rutas. Los enlaces son destinos, no una lista de profesiones, lo que mantiene la intención de `BRAND.md` §20.

Test de `BRAND.md` §35: el hero ayuda a entender quién es Luis y cuál es el hilo entre sus disciplinas antes de pedir al visitante que explorelas.

### Writing & Research

Esta sección aparece inmediatamente después del hero, ocupa más espacio que cualquier otra y presenta las cinco piezas como casos editoriales con pregunta, método, hallazgo, fuentes y resultado. Los títulos propios se mantienen tal como constan en `CV_MASTER.md` §4.

1. **I Tracked a Phantom AI Artist for 18 Months. The Problem Isn't Technological, It's Economic**. Idioma EN / ES. Callout: `1 release every 1.97 days`. Resumen: seguimiento de “Poderosas Palabras” para observar cómo un catálogo probablemente generado por IA compite por el mismo pool de royalties; el hallazgo documentado es que las plataformas pagan por atención, no por esfuerzo, y que el volumen obtiene una ventaja estructural. Fuentes: Chartmetric, Spotify, TikTok, Shazam y YouTube. Enlace: <https://medium.com/@soyluisguinea/i-tracked-a-likely-ai-generated-artist-for-18-months-the-problem-is-bigger-than-i-thought-a9bbb92d93bc>. Fuente factual: `CV_MASTER.md` §4.1.
2. **Are We Measuring Artist Growth Wrong?** Idioma EN. Callout: `r = 0.77`. Resumen: compara dos periodos de 180 días en 19 artistas españoles mediante historial de Chartmetric API y correlación de Pearson; el crecimiento de seguidores predijo fuertemente la persistencia, mientras los picos de oyentes no mostraron poder predictivo. Fuentes: Chartmetric API y análisis de correlación en Python. Enlace: <https://medium.com/@soyluisguinea/are-we-measuring-artist-growth-wrong-522c3d6a9280>. La redacción nunca dirá “perfectly” ni “almost perfectly”. Fuente factual: `CV_MASTER.md` §4.2.
3. **Seven Days to Turn a Viral Moment into a Career**. Idioma EN / ES. Callout: `559 → 332K followers`. Resumen: estudia a Macario Martínez entre enero de 2024 y junio de 2026, con evolución diaria en Spotify, TikTok e Instagram y un catálogo de 91.3M reproducciones; la secuencia de siete días va de TikTok a Instagram, seguidores de Spotify y, finalmente, oyentes mensuales. Fuentes: Chartmetric y datos públicos de Spotify, TikTok e Instagram. Enlace: <https://medium.com/@soyluisguinea/seven-days-to-turn-a-viral-moment-into-a-career-2f53d1cb7179>. Fuente factual: `CV_MASTER.md` §4.3.
4. **How RATA Turned an Explosion of Listeners into a Real Fan Base**. Idioma EN / ES. Callout: `+1,128% monthly listeners`. Resumen: analiza de mediados de 2025 a mediados de 2026 el salto tras una colaboración con Hens y distingue alcance de intención mediante oyentes y seguidores. Fuentes: Chartmetric API y revisión cualitativa de lanzamientos. Enlace: <https://medium.com/@soyluisguinea/how-rata-turned-an-explosion-of-listeners-into-a-real-fan-base-560dbabd2242>. Fuente factual: `CV_MASTER.md` §4.4.
5. **¿Las polémicas de Aleks Syntek son marketing?** Idioma ES. Callout: `12 months of data`. Resumen: contrasta datos de Spotify, YouTube, Instagram y TikTok entre septiembre de 2025 y septiembre de 2026 con la cronología pública; documenta cambios de audiencia sin atribuir una causalidad simple a la polémica. Fuentes: Chartmetric API, las cuatro plataformas y cronología pública de medios. Enlace: <https://medium.com/@soyluisguinea/las-pol%C3%A9micas-de-aleks-syntek-son-marketing-50cd7a723318>. Se etiqueta como parte 1 sin insinuar que la parte 2 ya existe. Fuente factual: `CV_MASTER.md` §4.5.

El único SVG de datos corresponde al artículo 4.1, que `CV_MASTER.md` marca como candidato. Presenta dos paneles coordinados, “Tracks” y “Streams”, para no mezclar escalas incompatibles:

- Enero de 2025: 170 tracks y 460,000 streams.
- Julio de 2025: 273 tracks y 4.4M streams.
- Agosto de 2026: 340 tracks y aproximadamente 13M streams.

El SVG lleva `role="img"`, `title` y `desc` enlazados con `aria-labelledby`. Los puntos tienen etiquetas visibles, no dependen solo del color y conservan el calificativo “about” para los 13M. Una tabla HTML con las seis cifras se ofrece junto al gráfico, visible o mediante un patrón accesible que no la oculte a lectores de pantalla. El texto narrativo explica la tendencia sin afirmar causalidad adicional. Datos: `CV_MASTER.md` §4.1.

Test de `BRAND.md` §35: la sección muestra cómo Luis formula preguntas, verifica narrativas con datos y convierte hallazgos en escritura publicada.

### Facets

Las cinco facetas funcionan como rutas de lectura, no como cinco identidades:

- **Music & Audio**: experiencia verificada en Jazztone, Peermusic, trabajo independiente, Tipazo, Mandala, Moctezuma Music Group, docencia y dirección musical. Puede mostrar `50+ artists`, `10M+ streams`, `20 releases` y `11-piece ensemble` solo junto a su contexto. `TODO: añadir una muestra, portada y enlace autorizado por cada proyecto o alias musical` antes de convertir esta faceta en escaparate sonoro. Fuentes: `CV_MASTER.md` §§3, 5 y 6.
- **Data & Technology**: los cinco estudios, automatización y bases de datos en Peermusic y Panaria. LedgerApp y las integraciones MCP se muestran únicamente como `TODO: caso pendiente de contexto, autoría, capturas, resultado y métricas`, sin publicar stack como sustituto de evidencia. Fuentes: `CV_MASTER.md` §§4–6.
- **Business & Entrepreneurship**: Moctezuma Music Group, Tipazo, Parvin y Melaleuca con resultados verificados y contextualizados. La empresa familiar no aporta métricas hasta resolver `VERIFY`. Fuentes: `CV_MASTER.md` §§3 y 5.
- **Creative Direction**: dirección artística, branding, narrativa y trabajo musical documentado en Mandala, Parvin, Moctezuma Music Group e Independent. Marcador visible en preview: `TODO: fotografía documental de proceso en contexto real`. No se presenta la fotografía como experiencia profesional. Fuentes factuales: `CV_MASTER.md` §5; marcador requerido por el encargo y `BRAND.md` §§13 y 35.
- **Projects & Experiments**: `TODO: completar casos de LedgerApp, integraciones MCP, proyectos y alias musicales, y focus blocker con repositorio o demo`. Hasta entonces es un índice transparente de trabajo pendiente, no una colección de claims. Fuente: `CV_MASTER.md` §6.

Test de `BRAND.md` §35: las facetas permiten ver un mismo método aplicado a música, datos, negocio, dirección creativa y experimentos sin fragmentar la identidad.

### Experience

Se propone un índice cronológico de mejora progresiva. Sin JavaScript se ven todas las entradas. Con JavaScript se filtran mediante botones con `aria-pressed` en desktop y un `select` etiquetado en móvil. Cada fila contiene organización, rol, periodo, faceta y un resultado verificable. El filtro usa las cinco facetas de `BRAND.md` §6; `writing` no se añade como sexta faceta porque ya tiene una sección principal propia.

Entradas con visibilidad web y print:

- Jazztone Studios, Music Producer. Se publican las funciones verificadas y el periodo Jan 2026 – Present, según `CV_MASTER.md` §5.
- Santo Chilaquil, Brand & Digital Growth. El rol y el nombre están autorizados y verificados; la versión pública omite las métricas que siguen en `VERIFY`. Fuente: `CV_MASTER.md` §5.
- Peermusic Spain, A&R / Admin Intern. Entra con las funciones verificadas y periodo Jul 2024 – Dec 2025. Fuente: `CV_MASTER.md` §5.
- Panaria, Data Analyst. Entra con título Data Analyst, funciones verificadas y `Aug 2024 – TODO end` durante revisión. No se cambia a Data Scientist sin decisión. Fuente: `CV_MASTER.md` §5.
- Independent, Singer-Songwriter & Producer. Entran lanzamiento, composición, sync y directo solo en la redacción verificada. Los campos de títulos de películas, marca y venues pueden mostrarse como `TODO` en preview; se omiten del despliegue si siguen vacíos. Se distinguen las 12 canciones originales de Luis y las 23 producciones para otros artistas. Fuente: `CV_MASTER.md` §5.
- Tipazo Music Group, A&R Manager. Entra con 20 lanzamientos y coordinación con el equipo A&R de Sony Music. Fuente: `CV_MASTER.md` §§3 y 5.
- MAP College of Music, Piano Teacher. Entra con docencia adaptada e integración de piano y producción. Fuente: `CV_MASTER.md` §5.
- Mandala Love Music, Music Director & Keyboardist. Entra con el ensemble de 11 integrantes y las funciones verificadas. Fuente: `CV_MASTER.md` §§3 y 5.
- Moctezuma Music Group, Founder & Label Director. Entra como periodo de servicios a artistas 2015–2023, con 50+ artistas y 10M+ streams; la continuidad del imprint y los ejemplos de sync quedan pendientes. Fuente: `CV_MASTER.md` §§3 y 5.
- Parvin Music, Key Account Brand Manager. Entra con Landia y el comercial de La Villita. Fuente: `CV_MASTER.md` §5.
- Melaleuca, Sales Director. Entra con equipo de 15 y 500+ clientes recurrentes. Fuente: `CV_MASTER.md` §§3 y 5.

Entradas solo print y opcionales: Academic Assistant en VoxGarten + MusicLab, Marketing Director en Sell It y Data Curator en Trade Marketing Solutions. No aparecen en `index.html`. En `cv.html` se recortan por espacio salvo que una candidatura las necesite. Fuente: `CV_MASTER.md` §5.

Voice work tiene visibilidad web pero estado `TODO` completo. Se omite de la web pública; durante revisión solo puede aparecer como marcador `TODO: clientes, programas, fechas y muestras`, sin presentar experiencia no verificada. Fuente: `CV_MASTER.md` §5.

Test de `BRAND.md` §35: el índice permite ver dónde trabajó Luis, qué responsabilidad tuvo y qué resultado existe, sin sustituir evidencia por una cronología extensa.

### Education

Lista cronológica compacta con MA in Global Entertainment and Music Business, Berklee College of Music, Valencia, Jun 2023 – Jul 2024; Bachelor's Degree in Music Production, REC Música, Aug 2017 – Jun 2021; y Bachelor's Degree in Communication and Digital Media, Tec de Monterrey, Aug 2011 – Aug 2015. Los nombres propios no se traducen. “Pianist since age four” puede aparecer como detalle de perfil, no como título académico. Fuente: `CV_MASTER.md` §7.

Test de `BRAND.md` §35: la educación explica la base formal que conecta música, negocio y comunicación sin dominar la experiencia publicada.

### Skills

Listas agrupadas, sin barras, porcentajes ni logotipos: Research & writing; Data & technology; Music; Industry; Business; Visual; Languages. Se usan exactamente las competencias de `CV_MASTER.md` §8. Los grupos se pueden filtrar visualmente con el mismo sistema tipográfico, pero no se asignan niveles que no existen en la fuente.

Test de `BRAND.md` §35: las listas ayudan a interpretar las herramientas presentes en los casos y trabajos, sin convertir capacidad en una puntuación arbitraria.

### Contact

Incluye `lguinea@berklee.edu`, Medium en <https://medium.com/@soyluisguinea>, enlace a `cv.html` y un enlace claramente marcado `CV PDF · TODO` a `assets/cv.pdf` solo cuando el archivo exista. El teléfono no aparece en `index.html`, su metadata, JSON-LD ni enlace. LinkedIn y Spotify se omiten mientras sigan en `TODO`. Fuente: `CV_MASTER.md` §§1 y 9.

Test de `BRAND.md` §35: Contact reduce la interacción a vías reales para leer el trabajo, consultar el CV o escribir a Luis.

### `cv.html`

El CV usa HTML semántico y una hoja `print.css` con `@page { size: A4; margin: 11mm; }`. En impresión se propone una cabecera compacta y dos columnas: aproximadamente 64% para perfil, experiencia y escritura; 36% para educación, skills y contacto. Cuerpo de 9–9.5 pt con interlineado mínimo de 1.25, títulos de 11–15 pt, ausencia de fondos pesados y control de `break-inside`.

Entran el perfil corto, los cinco estudios resumidos como títulos y métricas, la experiencia print verificada no opcional con un resultado por rol, educación, skills condensadas e identidad. Se excluye la empresa familiar mientras esté en `VERIFY`; se omiten VoxGarten + MusicLab, Sell It y Trade Marketing Solutions por ser print opcional; se eliminan introducciones, visualización, navegación, Facets, proyectos `TODO` y descripciones secundarias. Si las diez entradas verificadas no caben con legibilidad real, la prioridad de recorte será Piano Teacher, Parvin y Melaleuca antes de reducir texto por debajo del umbral fijado. Esa selección necesita aprobación porque `CV_MASTER.md` no establece prioridades para un A4.

El teléfono `+34 629 85 84 91` aparece solo en `cv.html` y en su PDF aprobado. Fuente: `CV_MASTER.md` §1. La versión de pantalla puede ser lineal; la composición rígida se aplica solo al imprimir.

Test de `BRAND.md` §35: la versión A4 permite verificar trayectoria y contacto con rapidez, sin replicar toda la narrativa interactiva.

### Internacionalización

EN es el idioma inicial y ES el secundario. `strings.js` contiene los dos diccionarios y claves estables; `i18n.js` aplica texto, atributos accesibles y metadatos traducibles. El toggle es un botón discreto con nombre accesible y estado visible. Se intenta leer y escribir la preferencia con `localStorage` dentro de `try/catch`; si falla, la sesión funciona en EN y el cambio actual sigue activo en memoria. No se fuerza idioma por geolocalización.

Nombres propios, marcas, proyectos y títulos de artículos no se traducen. En los casos con título español oficial registrado en `CV_MASTER.md` §§4.1, 4.3 y 4.4 se puede usar esa variante en ES, pero no crear nuevas traducciones. Fechas, etiquetas y resúmenes sí se traducen de forma natural. El contenido existe en HTML EN para que un fallo de JavaScript no deje la página vacía.

### Accesibilidad e interacción

- Landmarks `header`, `nav`, `main`, `section` y `footer`; un único `h1` y jerarquía de headings sin saltos.
- Enlace “Skip to content”, foco visible con forma y contraste, orden DOM igual al orden visual y objetivos táctiles mínimos de 44 px.
- Todos los filtros y el toggle funcionan por teclado. El foco no se mueve al filtrar; una región de estado anuncia el número de resultados sin exceso.
- Enlaces externos con texto descriptivo. No se abren ventanas nuevas por defecto.
- Alt de imagen basado en contenido y propósito, no en keywords. Imágenes decorativas usan alt vacío.
- SVG con nombre, descripción, etiquetas y tabla equivalente. Ninguna métrica depende solo de color.
- Contrastes según la tabla anterior, zoom al 200%, reflow a 320–360 px y prueba con lectores de pantalla.
- `prefers-reduced-motion` elimina reveals y transiciones; no existe contenido condicionado a hover, scroll o animación.
- La interacción es mejora progresiva: artículos, experiencia y enlaces permanecen disponibles sin JavaScript.

### SEO y metadatos

- `title` propuesto: `Luis Guinea | Writing, Music, Data & Creative Work`, basado en identidad, perfil y Writing & Research de `CV_MASTER.md` §§1, 2 y 4.
- `description`: una síntesis factual del perfil web sobre música, datos, sistemas y escritura desde Valencia, sin autoproclamaciones. Fuente: `CV_MASTER.md` §§1–2.
- Open Graph y Twitter: título, descripción, URL canónica, locale EN con alternativa ES e imagen social aprobada. No se usa `cover.png` automáticamente.
- Canonical: `TODO` hasta conocer la URL definitiva de GitHub Pages.
- JSON-LD `Person`: `name` Luis Carlos Guinea Moctezuma, `alternateName` Luis Guinea, `homeLocation` Valencia, Spain, email, URL del sitio y `sameAs` con Medium. No incluye teléfono en `index.html`, claims `TODO`, una profesión reductora ni perfiles ausentes. Datos: `CV_MASTER.md` §1.
- `cv.html` tendrá título y descripción propios. El PDF, cuando exista, se enlaza pero no se inventa en metadata.

## Uso de cover.png y profile_pic.png

### `cover.png`

- Datos técnicos: PNG RGB de 1983 × 793 px, 2,021,484 bytes, aproximadamente 1.93 MiB.
- Contenido observado: estudio de grabación vacío, instrumentos, monitores y rótulos de Jazztone Studios, con iluminación naranja, negros profundos, simetría central y acabado muy cinematográfico.
- Evaluación `BRAND.md` §13: muestra un contexto real compatible con el trabajo musical, pero no muestra a Luis trabajando. El contraste, la saturación y la iluminación parecen muy procesados. La inspección visual no permite certificar si es una fotografía generada, compuesta o solo retocada, ni confirma derechos de uso.
- Evaluación `BRAND.md` §30: como imagen dominante del hero empujaría el sitio hacia el anti-patrón de portfolio oscuro de productor musical y reduciría la identidad a una sola disciplina.
- Decisión propuesta: descartarla del hero, Contact y `og:image`. Tampoco usarla en la primera versión pública hasta confirmar autoría y derechos. Si se confirma como fotografía documental propia de Jazztone, podría entrar como evidencia secundaria dentro de Music & Audio, nunca como fondo a pantalla completa.

### `profile_pic.png`

- Datos técnicos: PNG RGB de 1254 × 1254 px, 1,892,794 bytes, aproximadamente 1.81 MiB.
- Contenido observado: retrato frontal de Luis en un estudio, con teclado y monitores al fondo, luz cálida, pose cercana y contexto profesional reconocible.
- Evaluación `BRAND.md` §13: el contexto es natural y relevante, y evita una pose corporativa. La iluminación, piel, color y desenfoque tienen un acabado pulido y posiblemente procesado. A partir de los píxeles no se puede afirmar si es generado ni cuánto retoque contiene; hay que confirmar procedencia y derechos.
- Evaluación `BRAND.md` §30: usarlo a pantalla completa con fondo oscuro reforzaría demasiado el cliché musical. En tamaño contenido puede humanizar el sitio sin definirlo entero por el estudio.
- Decisión propuesta: usarlo, tras confirmar autenticidad y derechos, como retrato secundario en Contact y como base de `og:image` junto a una composición tipográfica clara. No usarlo en el hero. Si no se confirma su origen, se descarta y el OG será tipográfico.

Todo derivado debe exportarse a WebP o AVIF por debajo de 300 KB, con dimensiones ajustadas al tamaño real y fallback cuando proceda. Los PNG originales permanecen intactos. La optimización no debe suavizar piel, añadir elementos ni intensificar la estética artificial.

## Contradicciones y ambigüedades

1. El encargo pide “los cinco artículos definidos en este encargo”, pero no los enumera fuera de la referencia. Los únicos cinco casos completos están en `CV_MASTER.md` §4. La propuesta toma esos cinco como autoridad.
2. El encargo exige mantener `TODO` explícitos en la web, mientras `CV_MASTER.md`, reglas 3 y 4, permite placeholder u omisión y prohíbe publicar campos `TODO` o `VERIFY` como hechos. Recomendación: placeholders solo en preview y en los lugares exigidos; no desplegar claims sin resolver.
3. El título de `CV_MASTER.md` §4.1 dice “I Tracked a Phantom AI Artist for 18 Months. The Problem Isn't Technological, It's Economic”, pero el slug de la URL dice “likely-ai-generated-artist” y “the-problem-is-bigger-than-i-thought”. Hay que confirmar cuál es el título publicado canónico.
4. `CV_MASTER.md` §§3 y 4.1 habla de 18 meses, pero el método va de enero de 2025 a agosto de 2026. Según cómo se cuenten meses o puntos inclusivos, el intervalo aparente es mayor. No debe corregirse ni explicarse sin confirmar las fechas exactas y la metodología de conteo.
5. `BRAND.md` §8 no define una paleta oscura separada. La propuesta reasigna los mismos cinco colores para respetar el encargo, pero esa asignación requiere aprobación.
6. Accent sobre Paper da 3.68:1 y Accent sobre Ink 4.46:1. Ninguno es seguro para texto normal AA. `BRAND.md` §8 propone Accent para enlaces, pero debe limitarse a señal redundante, texto grande o elementos no textuales.
7. Graphite sobre Ink da 2.53:1. Aunque `BRAND.md` §8 lo define para texto secundario, no sirve con fondo Ink. En oscuro debe sustituirse por Mist.
8. Mist como texto sobre Paper da 1.28:1, aunque sí da 12.88:1 sobre Ink. Su uso textual depende del tema; en claro solo debe ser línea decorativa.
9. `CV_MASTER.md` introduce la faceta `writing`; `BRAND.md` §6 solo define cinco facetas. Recomendación: Writing & Research es una sección editorial prioritaria y no un sexto filtro.
10. La experiencia familiar de hostelería en `CV_MASTER.md` §§3 y 5 tiene métricas `VERIFY`: 30%+ mensual, 100+ clientes semanales y ROI positivo en menos de tres meses. Además, el significado de ROI no está definido. No se publica ninguna.
11. La experiencia Independent distingue ahora 12 canciones originales de Luis y 23 producciones para otros artistas, según la consolidación documental; los títulos y enlaces concretos siguen pendientes.
12. Panaria carece de fecha final y existe una discrepancia entre Data Analyst y Data Scientist en `CV_MASTER.md` §5. La fuente recomienda Data Analyst, que adopta esta propuesta salvo decisión contraria.
13. El nombre Santo Chilaquil está autorizado en `CV_MASTER.md` §5; sus métricas siguen en `VERIFY` y no se publican.
14. Moctezuma Music dejó de operar como sello activo tras agosto de 2023, pero continúa como consultoría y productora, según `CV_MASTER.md` §5.
15. El perfil largo usa `10+ years`, en coherencia con la métrica verificada de `CV_MASTER.md` §§2–3.
16. Voice work tiene estado `TODO` completo en `CV_MASTER.md` §5. No existen fechas, clientes, programas ni muestras. No puede presentarse como experiencia publicada.
17. LinkedIn y Spotify son `TODO` en `CV_MASTER.md` §§1 y 9. No deben aparecer enlaces vacíos ni iconos sin destino.
18. Contact debe enlazar `assets/cv.pdf`, pero ese archivo no existe. El enlace debe permanecer marcado como `TODO` en preview o no renderizarse en público.
19. La URL canónica de GitHub Pages es desconocida. Sin usuario, repositorio público y modalidad de Pages no se pueden cerrar canonical, `og:url`, sitemap ni JSON-LD URL.
20. El encargo pide un breve reveal de disciplinas y varios enlaces en hero, mientras `BRAND.md` §20 prohíbe listar todas las profesiones de golpe. La propuesta revela una idea unificadora primero y deja disciplinas y destinos para un segundo nivel.
21. `CV_MASTER.md` §4 da títulos oficiales españoles para tres artículos bilingües, pero solo proporciona una URL de Medium por artículo. Falta confirmar si esa URL contiene ambas versiones o si existen URLs españolas separadas.
22. `CV_MASTER.md` §4.5 indica que el artículo de Aleks Syntek es parte 1 y que la parte 2 está pendiente. No debe insinuarse una serie completa.
23. `CV_MASTER.md` §6 marca LedgerApp y Digital Signage como proyectos propios verificados, pero sus casos de estudio, métricas y screenshots siguen en `TODO`; se muestran solo con hechos documentados.
24. La exigencia de una sola página A4 compite con todas las entradas `print`, cinco estudios, educación y siete grupos de skills. `CV_MASTER.md` no prioriza qué experiencia recortar. La propuesta ofrece un orden de recorte que necesita aprobación y una prueba real de impresión.
25. `cover.png` y `profile_pic.png` no incluyen metadata factual sobre autoría, derechos, fecha o grado de retoque. La inspección visual no resuelve si fueron generadas o procesadas.
26. Las fuentes solicitadas no están en el repositorio. Antes de self-hosting hay que confirmar archivos, pesos y licencias; un enlace CDN añadiría una dependencia contraria al objetivo de ligereza de `BRAND.md` §29.

## Decisiones que necesito de Luis

1. **¿Tomamos los cinco casos de `CV_MASTER.md` §4 como la lista definitiva?** Recomendación: sí, sin añadir “Ya estoy aquí”, que es private por defecto.
2. **¿Confirmas el título publicado del artículo 4.1 pese a la diferencia con el slug?** Recomendación: usar exactamente el título visible en Medium una vez comprobado por Luis.
3. **¿Puedes confirmar el conteo de 18 meses entre enero de 2025 y agosto de 2026?** Recomendación: conservar el claim solo tras documentar cómo se cuenta el intervalo.
4. **¿Los placeholders `TODO` deben existir en el sitio desplegado o solo en la preview privada?** Recomendación: visibles durante revisión, omitidos del despliegue salvo que expliquen honestamente una sección deliberadamente en construcción.
5. **¿Cuál es la fecha inicial de Jazztone Studios?** Recomendación: bloquear el despliegue de esa fecha hasta confirmarla y no inferirla por archivos o imágenes.
6. **¿Cuál es la fecha final de Panaria y se confirma el título Data Analyst?** Recomendación: Data Analyst, como indica `CV_MASTER.md`, y fecha final obligatoria antes del despliegue.
7. **¿Se valida toda la entrada de la empresa familiar y sus tres métricas?** Recomendación: omitirla por completo de la web pública hasta confirmar periodo, base, retención y definición de ROI.
8. **¿Debe nombrarse Santo Chilaquil?** Recomendación: no, mantener “family hospitality venture” incluso si se verifican las funciones, salvo autorización explícita.
9. **¿Qué cifra es correcta para Independent, 12 canciones o 23 singles, y cuáles son públicos los títulos de películas, sync y venues?** Recomendación: omitir cifras y ejemplos hasta aportar una lista verificable.
10. **¿Cómo debe describirse Moctezuma Music después de agosto de 2023?** Recomendación: publicar solo el periodo 2015–2023 hasta confirmar si el imprint sigue activo y con qué nombre.
11. **¿Se aprueba `10+ years` en lugar de “ten years” en el perfil?** Recomendación: sí, por coherencia con la métrica verificada de `CV_MASTER.md` §3.
12. **¿Se excluye Voice work hasta tener fechas, clientes y muestras?** Recomendación: sí.
13. **¿Se excluyen LinkedIn y Spotify hasta recibir URLs?** Recomendación: sí, sin iconos vacíos.
14. **¿Existen URLs españolas separadas para los artículos bilingües?** Recomendación: aportarlas; mientras tanto, enlazar solo la URL verificada disponible y no fingir una versión separada.
15. **¿Autorizas el uso de `profile_pic.png` y confirmas que es una fotografía real con derechos de publicación?** Recomendación: usarla solo en Contact y OG, optimizada, no en hero.
16. **¿Autorizas y confirmas la procedencia de `cover.png`?** Recomendación: descartarla de la primera versión; reconsiderarla solo como evidencia secundaria de Jazztone.
17. **¿Apruebas recortar del A4 las tres experiencias print opcionales y, si hace falta, Piano Teacher, Parvin y Melaleuca?** Recomendación: sí, manteniendo la versión web completa con todo lo verificado.
18. **¿Cuál será la URL pública exacta de GitHub Pages?** Recomendación: decidirla antes de cerrar SEO, sin desplegar todavía.
19. **¿Proporcionarás los archivos autorizados de Instrument Serif, Inter e IBM Plex Mono y el PDF final?** Recomendación: self-host WOFF2 autorizados y generar `assets/cv.pdf` desde el `cv.html` aprobado.
20. **¿Apruebas la reasignación oscura Paper/Mist sobre Ink y el uso no textual de Accent?** Recomendación: sí, porque mantiene los cinco colores exactos y resuelve los contrastes insuficientes.

## Riesgos para la fase de implementación

- **Fuentes**: el repositorio no contiene WOFF2 ni licencias. Sin acceso a archivos oficiales no se puede verificar legalidad, subsetting, peso o renderizado. Abordaje: Luis aporta los archivos autorizados o se descargan desde la fuente oficial con permiso y se documenta licencia; después se generan subconjuntos y se mide el impacto.
- **Conversión de imágenes**: ahora solo existen PNG de 1.8–1.9 MiB. Sin una herramienta como `cwebp`, `avifenc`, ImageMagick o equivalente no se pueden producir ni medir derivados bajo 300 KB. Abordaje: comprobar herramientas disponibles, generar derivados sin sobrescribir originales y comparar tamaño y calidad visual.
- **Lighthouse**: una auditoría real necesita un navegador Chromium y Lighthouse autorizados. La política operativa actual prohíbe lanzar Chrome, Chromium o Playwright desde shell. Abordaje: usar una capacidad de auditoría del navegador autorizado de Argos o un job controlado de CI; no atribuir una puntuación a una revisión estática.
- **Validador HTML**: el repositorio no incluye validador y el servicio W3C requiere red. Abordaje: usar el validador oficial si hay acceso autorizado o incorporar temporalmente un validador local verificable, sin convertirlo en dependencia de producción. También se revisará el árbol semántico en navegador.
- **Preview local**: para probar rutas, módulos ES, navegación, impresión e i18n se necesita servir por HTTP. Abordaje: lanzar un servidor estático con el canal durable de Argos, nunca como proceso de fondo ordinario, y abrirlo únicamente mediante `argos_navegador`. El comando y puerto se documentarán en README.
- **Impresión A4**: que el contenido quepa depende de las fuentes reales, el motor de impresión y las decisiones de recorte. Abordaje: inspección de print preview, exportación a PDF, comprobación de una sola página, legibilidad, enlaces y ausencia de cortes.

## Decisiones cerradas para la primera implementación

### Dominio y estructura

- El dominio canónico es `https://luisguinea.com`.
- La home (`/`) presenta una única identidad Creative × Analytical × Entrepreneurial. Writing & Research aparece inmediatamente después del hero y enlaza claramente con las demás facetas.
- `/music/` es una sección dedicada al catálogo musical real. `cv.html` es el CV semántico e imprimible en formato A4. No se introduce framework, backend, build ni dependencia innecesaria.

### Catálogo musical

- El catálogo se normaliza desde los datasets reales de `One Page Luis Guinea` hacia una fuente estática consumible por JavaScript, manteniendo trazabilidad con los archivos heredados.
- Solo se publican títulos, artistas, créditos, metadatos, artworks y enlaces de plataformas suficientemente respaldados. Los filtros se limitan a campos con respaldo suficiente; no se completan huecos por inferencia.
- Los enlaces de plataformas solo aparecen cuando existe una URL real confirmada. Las artworks disponibles pueden usarse como derivados web sin sobrescribir los originales.

### Top 6 y previews

- La selección Top 6 se estructura por `spotifyStreams` y fecha de captura.
- `Popularity` no sustituye a `spotifyStreams`. Mientras falten streams reales, no se muestra un ranking inventado: se presenta un estado editorial honesto o se omite la selección.
- Un preview, cuando exista un derivado válido, dura como máximo 30 segundos y el reproductor mantiene un único audio activo.
- Los dos audios completos existentes no se publican ni se copian como previews. Si no hay derivados válidos, esas canciones permanecen en el catálogo sin reproducción.

### Proyectos documentados

- LedgerApp y Digital Signage se muestran como proyectos propios de Grupo Botanas únicamente con los hechos documentados en `CV_MASTER.md`.
- No se publican métricas, resultados, screenshots, ingresos, datos de clientes ni detalles de caso de estudio que sigan pendientes de verificación. Cualquier ampliación queda marcada como `TODO` hasta disponer de evidencia.
- **Accesibilidad**: contraste calculado no sustituye pruebas de teclado, lector de pantalla, zoom y reflow. Abordaje: validación manual focalizada y auditoría automatizada cuando exista el sitio.
- **Contenido sin verificar**: varias fechas, métricas, proyectos y enlaces siguen abiertos. Abordaje: mantener una lista de bloqueo previa al despliegue y no transformar `TODO` o `VERIFY` en copy definitivo.
- **GitHub Pages y SEO**: sin URL final no pueden validarse rutas absolutas, canonical, Open Graph ni JSON-LD URL. Abordaje: implementar con un único valor de configuración claramente marcado y cerrarlo solo tras la aprobación explícita de despliegue.
- **Presupuesto de rendimiento**: la fotografía, las tres familias tipográficas y el SVG pueden afectar LCP y peso. Abordaje: preload solo de la fuente crítica, subsetting, imágenes responsivas, dimensiones explícitas, lazy loading fuera del primer viewport y JavaScript mínimo.

Esta fase termina con la consolidación documental y el commit local. La implementación, el push y el despliegue quedan fuera de esta iteración.
