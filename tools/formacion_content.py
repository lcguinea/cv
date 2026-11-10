"""Copy of the Formación Musical section (/formacion/ and its subpages), Spanish first, then English.

This is the only place to edit these texts, photographs and commercial terms. Every text leaf is a pair (es, en).
After any change run:

    python3 tools/build_formacion.py

which rewrites formacion/**/index.html (static Spanish, indexable) and js/learn-strings.js (both languages for the
EN/ES switch). Facts must come from CV_MASTER.md; voice and design rules from BRAND.md. No em dashes.

Second iteration (2026-11-10, mission 02): less explanation, more visual evidence. Detail that is not needed in the
first 15 seconds lives in <details> disclosures or on the subpages; nothing pedagogical was dropped from the
subpages.
"""

EMAIL = "lguinea@berklee.edu"

# Enquiry backend. Empty: the form writes an email in the visitor's mail app (mailto). Set it to the public /exec
# URL of the Apps Script web app once Luis has deployed op "enquiry" (apps-script/proposals/enquiry.gs) to send the
# enquiry for real. It is a public address, not a secret.
ENQUIRY_ENDPOINT = ""

# Commercial terms: provisional, NOT published while "published" is False (mission 02 §8). Flipping it renders the
# fees, the free orientation call and the cancellation line; tests/test_formacion.py must then be updated.
COMMERCIAL = {
    "published": False,
    "fees": {"piano": 40, "armonia": 45, "composicion": 45, "produccion": 45, "mentoria": 50},
    "orientationMinutes": 15,
    "sessionMinutes": 60,
    "cancelHours": 24,
}

# Areas, in the order of the hub. AREA_PAGES: areas with their own subpage (slug).
AREAS = ["piano", "composicion", "produccion", "armonia", "carrera"]
AREA_PAGES = {"piano": "piano", "composicion": "composicion", "produccion": "produccion-musical"}

# Photographs: derivatives in assets/images/learn/ made from the originals listed in the mission report, shown in
# black and white. None: a typographic composition stands in until Luis provides a real photograph.
PHOTOS = {
    "hero": {"src": "assets/images/profile.webp", "w": 1200, "h": 1200},
    "piano": {"src": "assets/images/learn/piano.webp", "w": 640, "h": 360},
    "produccion": {"src": "assets/images/learn/estudio.webp", "w": 980, "h": 430},
    "carrera": {"src": "assets/images/learn/guitarra.webp", "w": 800, "h": 999},
    "about": {"src": "assets/images/learn/artista.webp", "w": 1000, "h": 1250},
    "composicion": None,
    "armonia": None,
}

L = {
    "crumbLabel": ("Ruta de navegación", "Breadcrumb"),
    "crumbHome": ("Inicio", "Home"),
    "crumbLearn": ("Formación musical", "Music lessons"),
    "allAreas": ("Todas las áreas", "All areas"),
    "bookTalk": ("Reserva una conversación", "Book a conversation"),
    "faqKicker": ("Preguntas frecuentes", "Questions"),
    "seeContents": ("Ver contenidos", "See what we cover"),
    "labelWho": ("Para quién", "Who it is for"),
    "labelOutcome": ("Lo que consigues", "What you get out of it"),
    "relatedKicker": ("Otras áreas", "Other areas"),
    "ctaIntro": ("Cuéntame tu nivel y tu objetivo, y te propongo cómo empezar.",
                 "Tell me your level and your goal, and I will suggest how to start."),
    "ctaButton": ("Solicitar información", "Request information"),

    # Area names, shared by the hub, the selector, the form and the subpages.
    "area": {
        "piano": ("Piano", "Piano"),
        "composicion": ("Composición y songwriting", "Songwriting and composition"),
        "produccion": ("Producción musical", "Music production"),
        "armonia": ("Armonía y teoría aplicada", "Applied harmony and theory"),
        "carrera": ("Carrera artística y negocio musical", "Artist career and music business"),
        "mentoria": ("Mentoría sobre un proyecto", "Mentoring on a project"),
        "nose": ("Aún no lo sé", "Not sure yet"),
    },

    "hub": {
        "pageTitle": ("Clases de piano, composición y producción musical en Valencia · Luis Guinea",
                      "Piano, songwriting and music production lessons in Valencia · Luis Guinea"),
        "eyebrow": ("Formación musical · Valencia y online", "Music lessons · Valencia and online"),
        "title": ("Aprende música haciendo música.", "Learn music by making music."),
        "titleAccent": ("haciendo", "making"),
        "lede": ("Clases personalizadas de piano, composición, armonía y producción musical. En Valencia y online, "
                 "desde tus primeras notas hasta tus propios proyectos.",
                 "Personalised lessons in piano, songwriting, harmony and music production. In Valencia and online, "
                 "from your first notes to your own projects."),
        "cta": ("Explorar las clases", "Explore the lessons"),
        "cta2": ("Solicitar información", "Request information"),
        "caption": ("Luis Guinea · pianista, compositor y productor", "Luis Guinea · pianist, songwriter and producer"),

        # Goal selector: what the visitor wants, a musical detail set in type, and where it leads.
        "goalsKicker": ("01 / Por dónde empezar", "01 / Where to start"),
        "goalsTitle": ("¿Qué te gustaría conseguir?", "What would you like to achieve?"),
        "goals": {
            "piano": {"goal": ("Aprender a tocar el piano", "Learn to play the piano"),
                      "detail": ("Técnica · Repertorio · Improvisación", "Technique · Repertoire · Improvisation")},
            "composicion": {"goal": ("Componer mis propias canciones", "Write my own songs"),
                            "detail": ("Estrofa · Estribillo · Puente", "Verse · Chorus · Bridge")},
            "produccion": {"goal": ("Producir mi música", "Produce my music"),
                           "detail": ("Idea · Grabación · Mezcla", "Idea · Recording · Mix")},
            "armonia": {"goal": ("Entender la armonía", "Understand harmony"),
                        "detail": ("ii · V · I", "ii · V · I")},
            "carrera": {"goal": ("Desarrollar mi carrera artística", "Develop my artist career"),
                        "detail": ("Lanzamientos · Derechos · Estrategia", "Releases · Rights · Strategy")},
        },

        "areasKicker": ("02 / Áreas", "02 / Areas"),
        "areasTitle": ("Cinco áreas, una misma forma de enseñar.", "Five areas, one way of teaching."),
        "areasIntro": ("Puedes centrarte en una o combinarlas: hay quien empieza por el piano y acaba escribiendo sus "
                       "propias canciones.",
                       "You can focus on one or combine them: some people start with piano and end up writing their "
                       "own songs."),
        "areas": {
            "piano": {
                "line": ("Aprende a tocar, interpretar y acompañar la música que te gusta.",
                         "Learn to play, interpret and accompany the music you love."),
                "skills": [("Técnica", "Technique"), ("Repertorio", "Repertoire"), ("Improvisación", "Improvisation")],
                "link": ("Explorar clases de piano", "Explore piano lessons"),
                "caption": ("Al piano", "At the piano"),
            },
            "composicion": {
                "line": ("Convierte tus ideas en canciones terminadas.", "Turn your ideas into finished songs."),
                "skills": [("Melodía", "Melody"), ("Letra", "Lyrics"), ("Estructura", "Structure")],
                "link": ("Explorar clases de composición", "Explore songwriting lessons"),
            },
            "produccion": {
                "line": ("Lleva una canción de la idea a la grabación final.",
                         "Take a song from the idea to the final recording."),
                "skills": [("DAW", "DAW"), ("Grabación", "Recording"), ("Mezcla", "Mixing")],
                "link": ("Explorar clases de producción", "Explore production lessons"),
                "caption": ("Jazztone Studios, Valencia, donde trabajo como productor",
                            "Jazztone Studios, Valencia, where I work as a producer"),
            },
            "armonia": {
                "line": ("Entiende por qué funciona la música que tocas y escuchas.",
                         "Understand why the music you play and hear works."),
                "skills": [("Acordes", "Chords"), ("Progresiones", "Progressions"), ("Análisis", "Analysis")],
                "learn": [("Intervalos, escalas y construcción de acordes", "Intervals, scales and chord construction"),
                          ("Funciones armónicas y progresiones habituales", "Harmonic function and common progressions"),
                          ("Análisis de canciones de distintos estilos", "Analysing songs across styles"),
                          ("Rearmonización, voicings y oído", "Reharmonisation, voicings and ear training")],
                "who": ("Músicos que tocan de oído, cantantes, compositores y productores.",
                        "Musicians who play by ear, singers, songwriters and producers."),
                "outcome": ("Sacar canciones de oído más rápido y usar la armonía con intención.",
                            "Work out songs by ear faster and use harmony with intent."),
            },
            "carrera": {
                "line": ("Publica y gestiona tu música con criterio profesional.",
                         "Release and manage your music with professional judgement."),
                "skills": [("Lanzamientos", "Releases"), ("Derechos", "Rights"), ("Estrategia", "Strategy")],
                "learn": [("Identidad artística y plan de lanzamientos", "Artist identity and release planning"),
                          ("Distribución digital, metadatos y plataformas", "Digital distribution, metadata and platforms"),
                          ("Derechos de autor, derechos conexos y publishing", "Copyright, neighbouring rights and publishing"),
                          ("Marketing, presupuesto y gestión del proyecto", "Marketing, budgeting and project management")],
                "who": ("Artistas independientes, bandas y equipos que gestionan su propia música.",
                        "Independent artists, bands and teams managing their own music."),
                "outcome": ("Un plan de lanzamiento realista y criterio para decidir sobre tus derechos.",
                            "A realistic release plan and the judgement to decide about your rights."),
                "caption": ("Más de diez años en la industria: sellos, una editorial musical y proyectos propios",
                            "More than ten years in the industry: labels, a music publisher and my own projects"),
            },
        },

        "methodKicker": ("03 / Método", "03 / Method"),
        "method": [
            (("Partimos de ti.", "We start with you."),
             ("Tu nivel, tus intereses y tus objetivos.", "Your level, your interests and your goals.")),
            (("Aprendemos haciendo.", "We learn by doing."),
             ("Cada concepto se convierte en práctica musical.", "Every concept becomes musical practice.")),
            (("Trabajamos con música real.", "We work with real music."),
             ("Canciones, repertorio, grabaciones o proyectos propios.",
              "Songs, repertoire, recordings or your own projects.")),
        ],

        "aboutKicker": ("04 / Sobre mí", "04 / About me"),
        "aboutTitle": ("Músico, compositor y productor.", "Musician, songwriter and producer."),
        "aboutText": ("Empecé a tocar el piano a los cuatro años y la música ha sido mi oficio desde entonces. En clase "
                      "llevo lo que funciona en canciones reales.",
                      "I started playing the piano at four and music has been my craft ever since. In my lessons I "
                      "bring what works in real songs."),
        "aboutCaption": ("Luis Guinea, 2024", "Luis Guinea, 2024"),
        "about": [
            (("Formación", "Training"),
             ("Licenciatura en Producción Musical (REC Música) y máster en Global Entertainment and Music Business "
              "por Berklee College of Music.",
              "Bachelor's degree in Music Production (REC Música) and an MA in Global Entertainment and Music "
              "Business from Berklee College of Music.")),
            (("Trayectoria", "Career"),
             ("Pianista desde los cuatro años. 23 sencillos producidos para otros artistas, dirección musical de un "
              "ensamble de 11 músicos y música adicional para cuatro largometrajes.",
              "Pianist since the age of four. 23 singles produced for other artists, music direction of an 11-piece "
              "ensemble and additional music for four feature films.")),
            (("Docencia y presente", "Teaching and today"),
             ("Profesor de piano en MAP College of Music, Audio and Production. Hoy, productor en Jazztone Studios, "
              "en Valencia.",
              "Piano teacher at MAP College of Music, Audio and Production. Today, producer at Jazztone Studios in "
              "Valencia.")),
        ],
        "evidenceMusic": ("Escucha mi trabajo", "Listen to my work"),
        "evidenceCv": ("Consulta el CV", "View the CV"),
        "evidenceAbout": ("Lee mi historia", "Read my story"),

        "modesKicker": ("05 / Modalidades", "05 / Formats"),
        "modesTitle": ("Presencial, online o mentoría.", "In person, online or mentoring."),
        "modes": {
            "presencial": (("Presencial en Valencia", "In person in Valencia"),
                           ("Clases individuales en un espacio adecuado a la especialidad, sujeto a disponibilidad.",
                            "One-to-one lessons in a space suited to each subject, subject to availability.")),
            "online": (("Online", "Online"),
                       ("Sesiones en directo y trabajo práctico compartido.",
                        "Live sessions and shared hands-on work.")),
            "mentorias": (("Mentoría personalizada", "Personal mentoring"),
                          ("Orientación sobre canciones, producciones y proyectos musicales.",
                           "Guidance on songs, productions and music projects.")),
        },
        "terms": [("Sesiones de 60 minutos", "60-minute sessions"), ("Español o inglés", "Spanish or English"),
                  ("Tarifa confirmada por escrito antes de empezar", "Fee confirmed in writing before you start")],

        "faqTitle": ("Antes de empezar.", "Before you start."),
        "faq": [
            (("¿Necesito experiencia previa?", "Do I need previous experience?"),
             ("No. Empezamos desde tu nivel, sea cual sea.", "No. We start from your level, whatever it is.")),
            (("¿Para qué edades son las clases?", "What ages are the lessons for?"),
             ("Para niños, jóvenes y adultos. Con los más pequeños lo hablamos antes con la familia.",
              "Children, teenagers and adults. With younger children we talk with the family first.")),
            (("¿Qué necesito para empezar?", "What do I need to start?"),
             ("Para piano, un instrumento para practicar. Para producción, un ordenador, un DAW y auriculares. Te "
              "oriento antes de comprar nada.",
              "For piano, an instrument to practise on. For production, a computer, a DAW and headphones. I can "
              "advise you before you buy anything.")),
            (("¿Las clases online funcionan igual?", "Do online lessons work as well?"),
             ("Sí. En producción compartimos pantalla; en piano, la cámara enfoca el teclado.",
              "Yes. For production we share screens; for piano, the camera points at the keyboard.")),
            (("¿Cuánto cuestan las clases?", "How much do lessons cost?"),
             ("Depende del área y del formato. Te confirmo la tarifa por escrito antes de la primera clase.",
              "It depends on the area and format. I confirm the fee in writing before the first lesson.")),
        ],

        "enquiryKicker": ("06 / Consulta", "06 / Enquiry"),
        "enquiryTitle": ("Cuéntame qué quieres aprender.", "Tell me what you want to learn."),
        "enquiryIntro": ("Te respondo por correo con una propuesta para empezar.",
                         "I will reply by email with a proposal to get started."),
        "talkTitle": ("¿Prefieres hablar antes?", "Would you rather talk first?"),
        "talkLink": ("Reserva una conversación en la agenda", "Book a conversation in the calendar"),
    },

    "form": {
        "label": ("Formulario de consulta", "Enquiry form"),
        "area": ("Área de interés", "Area of interest"),
        "areaPick": ("Elige un área", "Choose an area"),
        "level": ("Nivel", "Level"),
        "levelPick": ("Elige tu nivel", "Choose your level"),
        "levels": {"inicio": ("Empiezo desde cero", "Complete beginner"),
                   "base": ("Tengo algo de base", "Some experience"),
                   "avanzado": ("Nivel avanzado", "Advanced")},
        "format": ("Modalidad", "Format"),
        "formatPick": ("Elige la modalidad", "Choose a format"),
        "formats": {"presencial": ("Presencial en Valencia", "In person in Valencia"),
                    "online": ("Online", "Online"),
                    "mentoria": ("Mentoría", "Mentoring"),
                    "igual": ("Me da igual", "Either")},
        "name": ("Nombre", "Name"),
        "email": ("Correo electrónico", "Email"),
        "message": ("¿Qué te gustaría aprender?", "What would you like to learn?"),
        "messagePlaceholder": ("Por ejemplo: acompañarme al piano cuando canto, terminar mi primer EP",
                               "For example: accompany myself on piano when I sing, finish my first EP"),
        "privacy": ("Uso tus datos solo para responder a esta consulta.",
                    "I use your details only to reply to this enquiry."),
        "send": ("Enviar consulta", "Send enquiry"),
        "sending": ("Enviando…", "Sending…"),
        "sent": ("Gracias. He recibido tu consulta y te responderé por correo.",
                 "Thank you. I have received your enquiry and will reply by email."),
        "prepare": ("Preparar el correo", "Write the email"),
        "prepareHint": ("Se abrirá tu programa de correo con el mensaje listo para enviar.",
                        "Your email app opens with the message ready to send."),
        "errArea": ("Elige un área para continuar.", "Choose an area to continue."),
        "errName": ("Escribe tu nombre.", "Write your name."),
        "errEmail": ("Revisa tu correo electrónico.", "Check your email address."),
        "errSend": ("No se ha podido enviar ahora. Puedes enviarlo por correo con el mensaje de abajo.",
                    "It could not be sent right now. You can send it by email with the message below."),
        "opened": ("Si no se ha abierto tu correo, copia el mensaje y envíalo a lguinea@berklee.edu.",
                   "If your email app did not open, copy the message and send it to lguinea@berklee.edu."),
        "copy": ("Copiar el mensaje", "Copy the message"),
        "copied": ("Mensaje copiado.", "Message copied."),
        "copyFailed": ("No se ha podido copiar. Selecciona el texto y cópialo a mano.",
                       "Could not copy. Select the text and copy it by hand."),
        "mailSubject": ("Formación musical: {area}", "Music lessons: {area}"),
        "mailHello": ("Hola, Luis:", "Hi Luis,"),
        "mailArea": ("Me interesa", "I am interested in"),
        "mailMessage": ("Lo que me gustaría aprender", "What I would like to learn"),
    },

    # Subpages: same template, different content. Programmes are disclosures: the first stage is open.
    "pages": {
        "piano": {
            "pageTitle": ("Clases de piano en Valencia y online · Luis Guinea",
                          "Piano lessons in Valencia and online · Luis Guinea"),
            "eyebrow": ("Formación musical · 01 · Valencia y online", "Music lessons · 01 · Valencia and online"),
            "title": ("Clases de piano.", "Piano lessons."),
            "titleAccent": ("piano.", "Piano"),
            "lede": ("Para tocar las piezas y canciones que te gustan, con una técnica que no te limite.",
                     "To play the pieces and songs you love, with a technique that does not hold you back."),
            "meta": [("Todos los niveles", "All levels"), ("Niños, jóvenes y adultos", "Children, teenagers and adults"),
                     ("Clases de 60 minutos", "60-minute lessons")],
            "whoKicker": ("01 / Para quién", "01 / Who it is for"),
            "who": [
                (("Empiezas desde cero", "Starting from scratch"),
                 ("Postura, lectura y tus primeras piezas desde la primera clase.",
                  "Posture, reading and your first pieces from the very first lesson.")),
                (("Quieres retomarlo", "Picking it up again"),
                 ("Recuperamos lo que sabías y elegimos repertorio que te motive.",
                  "We recover what you knew and choose repertoire that motivates you.")),
                (("Ya tocas y quieres avanzar", "Already playing"),
                 ("Técnica, interpretación, improvisación y nuevos estilos.",
                  "Technique, interpretation, improvisation and new styles.")),
            ],
            "planKicker": ("02 / Programa", "02 / Programme"),
            "planTitle": ("Por niveles, a tu ritmo.", "By level, at your pace."),
            "plan": [
                (("Iniciación", "Beginner"),
                 [("Postura, digitación y coordinación de manos", "Posture, fingering and hand coordination"),
                  ("Lectura de notas y ritmo", "Reading notes and rhythm"),
                  ("Primeros acordes y acompañamientos sencillos", "First chords and simple accompaniments"),
                  ("Piezas cortas de repertorio clásico y popular", "Short pieces from classical and popular repertoire")]),
                (("Intermedio", "Intermediate"),
                 [("Escalas, arpegios e independencia de manos", "Scales, arpeggios and hand independence"),
                  ("Lectura fluida y cifrado americano", "Fluent reading and chord symbols"),
                  ("Acompañar canciones y a otros músicos", "Accompanying songs and other musicians"),
                  ("Introducción a la improvisación", "Introduction to improvisation")]),
                (("Avanzado", "Advanced"),
                 [("Interpretación, dinámica y sonido", "Interpretation, dynamics and tone"),
                  ("Voicings, rearmonización e improvisación", "Voicings, reharmonisation and improvisation"),
                  ("Estilos contemporáneos: pop, balada y música latina", "Contemporary styles: pop, ballads and Latin music"),
                  ("El piano en la composición y en el estudio", "The piano in songwriting and in the studio")]),
            ],
            "howKicker": ("03 / Cómo son las clases", "03 / How lessons work"),
            "how": ("Técnica, repertorio y la teoría justa para entender lo que tocas. Al terminar cada clase sabes "
                    "qué practicar.",
                    "Technique, repertoire and just enough theory to understand what you play. After each lesson you "
                    "know what to practise."),
            "needTitle": ("Lo que necesitas", "What you need"),
            "need": ("Un piano o un teclado de 88 teclas contrapesadas. Si aún no lo tienes, te oriento antes de comprar.",
                     "A piano or a keyboard with 88 weighted keys. If you do not have one yet, I can advise you first."),
            "proofTitle": ("Desde el piano", "From the piano"),
            "proof": ("Pianista desde los cuatro años, profesor en MAP College of Music, Audio and Production y director "
                      "musical de un ensamble de 11 músicos.",
                      "Pianist since the age of four, teacher at MAP College of Music, Audio and Production and music "
                      "director of an 11-piece ensemble."),
            "evidence": ("Escucha mi música", "Listen to my music"),
            "evidenceHref": "music/?credit=artist",
            "faq": [
                (("¿Cuánto tardaré en tocar una canción?", "How long until I can play a song?"),
                 ("Depende de la práctica, pero desde las primeras clases trabajas piezas reales a tu nivel.",
                  "It depends on your practice, but from the first lessons you work on real pieces at your level.")),
                (("¿Enseñas a leer partitura?", "Do you teach sight reading?"),
                 ("Sí, partitura y cifrado americano. Si prefieres tocar de oído, también lo trabajamos.",
                  "Yes, sheet music and chord symbols. If you prefer to play by ear, we work on that too.")),
                (("¿Hay clases de piano online?", "Are there online piano lessons?"),
                 ("Sí, con la cámara colocada sobre el teclado. Te explico cómo prepararla.",
                  "Yes, with the camera positioned over the keyboard. I explain how to set it up.")),
            ],
            "ctaTitle": ("¿Empezamos con el piano?", "Shall we start with piano?"),
        },
        "composicion": {
            "pageTitle": ("Clases de composición y songwriting en Valencia y online · Luis Guinea",
                          "Songwriting and composition lessons in Valencia and online · Luis Guinea"),
            "eyebrow": ("Formación musical · 02 · Valencia y online", "Music lessons · 02 · Valencia and online"),
            "title": ("Composición y songwriting.", "Songwriting and composition."),
            "titleAccent": ("songwriting.", "composition."),
            "lede": ("De ideas sueltas a canciones terminadas, con una forma de escribir que suene a ti.",
                     "From scattered ideas to finished songs, with a way of writing that sounds like you."),
            "meta": [("Todos los niveles", "All levels"), ("Cualquier estilo", "Any style"),
                     ("Clases de 60 minutos", "60-minute lessons")],
            "whoKicker": ("01 / Para quién", "01 / Who it is for"),
            "who": [
                (("Cantautores", "Singer-songwriters"),
                 ("Que se atascan en el estribillo, la segunda estrofa o la armonía.",
                  "Who get stuck on the chorus, the second verse or the harmony.")),
                (("Cantantes e intérpretes", "Singers and performers"),
                 ("Que quieren escribir su propio material.", "Who want to write their own material.")),
                (("Músicos y productores", "Musicians and producers"),
                 ("Con instrumentales o ideas que necesitan melodía, letra y estructura.",
                  "With instrumentals or ideas that need melody, lyrics and structure.")),
            ],
            "planKicker": ("02 / Programa", "02 / Programme"),
            "planTitle": ("De la idea a la maqueta.", "From the idea to the demo."),
            "plan": [
                (("La idea", "The idea"),
                 [("Encontrar el tema y el punto de vista", "Finding the subject and the point of view"),
                  ("Motivos melódicos y rítmicos", "Melodic and rhythmic motifs"),
                  ("Escribir con regularidad", "Writing regularly")]),
                (("La canción", "The song"),
                 [("Estructura: estrofa, preestribillo, estribillo y puente", "Structure: verse, pre-chorus, chorus and bridge"),
                  ("Melodía y prosodia", "Melody and prosody"),
                  ("Letra: imagen, narrativa y rima", "Lyrics: imagery, storytelling and rhyme")]),
                (("La armonía", "The harmony"),
                 [("Progresiones con intención", "Progressions with intent"),
                  ("Tensión y resolución", "Tension and release"),
                  ("Cambios de tonalidad y de color", "Key changes and colour")]),
                (("La maqueta", "The demo"),
                 [("Arreglo básico al piano o a la guitarra", "A basic arrangement on piano or guitar"),
                  ("Maqueta en el DAW", "A demo in the DAW"),
                  ("Preparar la canción para presentarla o producirla", "Getting the song ready to pitch or produce")]),
            ],
            "howKicker": ("03 / Cómo son las clases", "03 / How lessons work"),
            "how": ("Trabajamos sobre tus canciones desde la primera clase y aprendemos de las referencias que te gustan.",
                    "We work on your songs from the first lesson and learn from the references you love."),
            "needTitle": ("Lo que necesitas", "What you need"),
            "need": ("Ganas de escribir y, si lo tienes, un piano o una guitarra. Para la maqueta sirve cualquier DAW, o "
                     "el móvil para empezar.",
                     "The wish to write and, if you have one, a piano or a guitar. Any DAW works for the demo, or your "
                     "phone to begin with."),
            "proofTitle": ("Desde la escritura", "From the writing desk"),
            "proof": ("12 canciones propias publicadas, coescritura para otros artistas y beca en el Taller de la Sociedad "
                      "de Autores y Compositores de México.",
                      "12 original songs released, co-writing for other artists and a scholarship at the workshop of "
                      "the Sociedad de Autores y Compositores de México."),
            "evidence": ("Escucha canciones que he escrito", "Listen to songs I have written"),
            "evidenceHref": "music/?credit=composer",
            "faq": [
                (("¿Necesito saber tocar un instrumento?", "Do I need to play an instrument?"),
                 ("Ayuda, pero no es imprescindible. Podemos empezar con la voz.",
                  "It helps, but it is not essential. We can start with your voice.")),
                (("¿Las canciones las escribes tú o yo?", "Who writes the songs, you or me?"),
                 ("Las escribes tú. Yo pregunto, propongo herramientas y señalo qué funciona.",
                  "You do. I ask questions, suggest tools and point out what works.")),
                (("¿Podemos pasar después a la producción?", "Can we move on to production afterwards?"),
                 ("Sí. Cuando la canción está escrita, hacemos la maqueta y la producimos.",
                  "Yes. Once the song is written, we make the demo and produce it.")),
            ],
            "ctaTitle": ("¿Tienes canciones a medio terminar?", "Got songs that are half finished?"),
        },
        "produccion": {
            "pageTitle": ("Clases de producción musical en Valencia y online · Luis Guinea",
                          "Music production lessons in Valencia and online · Luis Guinea"),
            "eyebrow": ("Formación musical · 03 · Valencia y online", "Music lessons · 03 · Valencia and online"),
            "title": ("Producción musical.", "Music production."),
            "titleAccent": ("musical.", "production."),
            "lede": ("De una idea a una grabación terminada, con un método que puedas repetir en cada canción.",
                     "From an idea to a finished recording, with a method you can repeat on every song."),
            "meta": [("Logic Pro · Pro Tools · Ableton Live", "Logic Pro · Pro Tools · Ableton Live"),
                     ("Todos los niveles", "All levels"), ("Valencia y online", "Valencia and online")],
            "whoKicker": ("01 / Para quién", "01 / Who it is for"),
            "who": [
                (("Artistas que quieren producirse", "Artists producing themselves"),
                 ("Para grabar y producir tus canciones sin depender de nadie.",
                  "To record and produce your songs without depending on anyone.")),
                (("Productores que empiezan", "Producers starting out"),
                 ("Para ordenar tu flujo de trabajo y entender tus plugins.",
                  "To organise your workflow and understand your plugins.")),
                (("Músicos con home studio", "Musicians with a home studio"),
                 ("Para sacar partido al equipo que ya tienes.", "To get the most out of the gear you already have.")),
            ],
            "planKicker": ("02 / Programa", "02 / Programme"),
            "planTitle": ("El recorrido completo de una canción.", "The whole journey of a song."),
            "plan": [
                (("Idea y DAW", "Idea and DAW"),
                 [("Flujo de trabajo en Logic Pro, Pro Tools o Ableton Live", "Workflow in Logic Pro, Pro Tools or Ableton Live"),
                  ("MIDI y programación de baterías", "MIDI and drum programming"),
                  ("Instrumentos virtuales y síntesis", "Virtual instruments and synthesis")]),
                (("Grabación", "Recording"),
                 [("Grabar voces e instrumentos en casa", "Recording vocals and instruments at home"),
                  ("Micrófonos y niveles de entrada", "Microphones and input levels"),
                  ("Edición y afinación", "Editing and tuning")]),
                (("Arreglo", "Arrangement"),
                 [("Construir la canción por capas", "Building the song in layers"),
                  ("Frecuencias y espacio entre instrumentos", "Frequencies and space between instruments"),
                  ("Referencias de discos reales", "References from real records")]),
                (("Mezcla y entrega", "Mixing and delivery"),
                 [("Ecualización, compresión y efectos", "EQ, compression and effects"),
                  ("Automatización y balance", "Automation and balance"),
                  ("Fundamentos de masterización y archivos para distribuir", "Mastering fundamentals and files for distribution")]),
            ],
            "howKicker": ("03 / Cómo son las clases", "03 / How lessons work"),
            "how": ("Sobre tus proyectos o sesiones preparadas para cada tema. Online compartimos pantalla y ves cada "
                    "decisión en tiempo real.",
                    "On your own projects or sessions prepared for each topic. Online we share screens and you see "
                    "every decision in real time."),
            "needTitle": ("Lo que necesitas", "What you need"),
            "need": ("Un ordenador con un DAW y auriculares o monitores. Interfaz y micrófono ayudan, pero no son "
                     "imprescindibles.",
                     "A computer with a DAW and headphones or monitors. An interface and a microphone help, but are "
                     "not essential."),
            "proofTitle": ("Desde el estudio", "From the studio"),
            "proof": ("23 sencillos producidos para otros artistas, música adicional para cuatro largometrajes y trabajo "
                      "diario como productor en Jazztone Studios.",
                      "23 singles produced for other artists, additional music for four feature films and daily work "
                      "as a producer at Jazztone Studios."),
            "evidence": ("Escucha mis producciones", "Listen to my productions"),
            "evidenceHref": "music/?credit=producer",
            "faq": [
                (("¿Qué DAW enseñas?", "Which DAW do you teach?"),
                 ("Logic Pro, Pro Tools y Ableton Live. Con otro programa, los conceptos son los mismos.",
                  "Logic Pro, Pro Tools and Ableton Live. With other software, the concepts are the same.")),
                (("¿Necesito equipo caro?", "Do I need expensive gear?"),
                 ("No. Se aprende mucho con un ordenador y buenos auriculares.",
                  "No. You can learn a lot with a computer and good headphones.")),
                (("¿Incluye mezcla y masterización?", "Does it include mixing and mastering?"),
                 ("Sí: mezcla en profundidad y fundamentos de masterización.",
                  "Yes: mixing in depth and mastering fundamentals.")),
            ],
            "ctaTitle": ("¿Tienes una canción que quieres producir?", "Have a song you want to produce?"),
        },
    },
}
