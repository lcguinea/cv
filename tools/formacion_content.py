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

# Class plans paid with Stripe (mission 04). NOT published while "published" is False: the plans section, the student
# area (alumnos/index.html), js/plans.js, js/alumnos.js and their copy are only generated once Luis approves going live.
# "endpoint": public /exec URL of the Apps Script web app (the same one as /agenda/). Preview without publishing:
#     python3 tools/build_formacion.py --preview http://127.0.0.1:8792/exec --out <scratch dir>
SUBSCRIPTIONS = {"published": True,
                 "endpoint": "https://script.google.com/macros/s/AKfycbxj7SKKv5Pn4zb3oyqC8w3K8F3Ye4Zs4EHaUeBVvV3nIrBxbKvzBg8csvQhbXWpprpe/exec"}

# Provider data published in /formacion/condiciones/ (information duties of LSSI art. 10 and TRLGDCU art. 97). The
# build refuses to publish the plans while any value is empty: these data are never invented.
PROVIDER = {
    "name": "Luis Carlos Guinea Moctezuma",
    "nif": "16830408C",
    "address": "C/ Joaquín Ballester, 15, 12, 46009 Valencia",
    "classPlace": "Jazztone Studios, C/ Pérez Escrich, 15 (Extramurs), 46008 Valencia",
    "email": "lguinea@berklee.edu",
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


# ---------- class plans and student area (only built when SUBSCRIPTIONS["published"] or --preview) ----------

L["legalNote"] = ("Este texto se ofrece en español.", "This text is provided in Spanish, which is the binding version.")

L["plans"] = {
    "kicker": ("06 / Planes", "06 / Plans"),
    "title": ("Clases presenciales, cada semana o cada quince días.", "In-person lessons, every week or every two weeks."),
    "intro": ("Cuatro clases individuales de 60 minutos por 148 €. Tú eliges el ritmo y reservas tus horas desde tu área "
              "de alumno, sin escribirme cada vez.",
              "Four one-to-one 60-minute lessons for €148. You choose the pace and book your times from your student "
              "area, without writing to me each time."),
    "legend": ("Elige tu ritmo", "Choose your pace"),
    "cardTitle": ("Clases individuales · 60 minutos", "One-to-one lessons · 60 minutes"),
    "weekly": {
        "name": ("Semanal", "Weekly"),
        "rhythm": ("Una clase cada semana", "One lesson every week"),
        "price": ("148 €", "€148"),
        "per": ("cada 4 semanas", "every 4 weeks"),
        "detail": ("4 clases de 60 minutos · 37 € por clase · se renueva cada 28 días",
                   "4 lessons of 60 minutes · €37 per lesson · renews every 28 days"),
    },
    "biweekly": {
        "name": ("Quincenal", "Every two weeks"),
        "rhythm": ("Una clase cada dos semanas", "One lesson every two weeks"),
        "per": ("cada 8 semanas", "every 8 weeks"),
        "detail": ("4 clases de 60 minutos · 37 € por clase · se renueva cada 56 días",
                   "4 lessons of 60 minutes · €37 per lesson · renews every 56 days"),
    },
    "termsTitle": ("Antes de contratar", "Before you subscribe"),
    "terms": [
        ("Precio final por periodo, sin matrícula ni cargos adicionales.", "Final price per period, with no sign-up fee or extra charges."),
        ("La suscripción se renueva automáticamente. Puedes cancelar la renovación cuando quieras desde tu área de "
         "alumno; tendrá efecto al final del periodo ya pagado y conservas las clases pagadas.",
         "The subscription renews automatically. You can cancel the renewal at any time from your student area; it "
         "takes effect at the end of the period already paid and you keep the lessons you paid for."),
        ("Reservas, cambias o cancelas cada clase tú mismo hasta 24 horas antes.",
         "You book, move or cancel each lesson yourself up to 24 hours before."),
        ("Si soy yo quien cancela una clase, la conservas íntegra.", "If I am the one who cancels a lesson, you keep it in full."),
        ("Clases sin usar: hasta dos pasan al periodo siguiente y tienes 30 días para recuperarlas.",
         "Unused lessons: up to two move on to the next period and you have 30 days to make them up."),
        ("Si faltas sin avisar, la clase cuenta como realizada; con un motivo justificado, la conservas.",
         "If you miss a lesson without notice, it counts as done; with a justified reason, you keep it."),
        ("Puedes pasar de semanal a quincenal, o al revés, desde la siguiente renovación, sin ajustes de precio.",
         "You can switch between weekly and every two weeks from the next renewal, with no price adjustments."),
        ("Tienes 14 días naturales para desistir del contrato.", "You have 14 calendar days to withdraw from the contract."),
    ],
    "conditionsSummary": ("Leer las condiciones completas", "Read the full conditions"),
    "conditions": [
        (("Qué contratas", "What you buy"),
         ("Un plan de clases particulares presenciales e individuales de música con Luis Guinea en Valencia. Cada periodo "
          "pagado incluye cuatro clases de 60 minutos. Plan semanal: 148 € cada 4 semanas (28 días). Plan quincenal: "
          "148 € cada 8 semanas (56 días).",
          "A plan of one-to-one, in-person private music lessons with Luis Guinea in Valencia. Each paid period includes "
          "four 60-minute lessons. Weekly plan: €148 every 4 weeks (28 days). Every-two-weeks plan: €148 every 8 weeks (56 days).")),
        (("Pago y renovación", "Payment and renewal"),
         ("El pago se hace con tarjeta a través de Stripe, que guarda los datos de pago: este sitio nunca los ve. El "
          "importe se cobra al contratar y después al inicio de cada periodo hasta que canceles la renovación. Recibirás "
          "el recibo de cada cobro por correo.",
          "Payment is made by card through Stripe, which keeps the payment details: this site never sees them. The "
          "amount is charged when you subscribe and then at the start of each period until you cancel the renewal. "
          "You receive a receipt by email for each charge.")),
        (("Cancelación", "Cancellation"),
         ("Puedes cancelar la renovación en cualquier momento desde tu área de alumno, sin permanencia ni penalización. "
          "La cancelación evita los cobros siguientes; las clases ya pagadas siguen disponibles.",
          "You can cancel the renewal at any time from your student area, with no minimum term or penalty. Cancelling "
          "stops future charges; lessons already paid for remain available.")),
        (("Reservas y cambios", "Bookings and changes"),
         ("Cada clase pagada se reserva desde tu área de alumno según la disponibilidad publicada. Puedes cambiarla o "
          "cancelarla hasta 24 horas antes; con menos antelación, escríbeme. Si yo cancelo una clase, la conservas sin "
          "fecha límite.",
          "Each paid lesson is booked from your student area according to the published availability. You can move or "
          "cancel it up to 24 hours before; with less notice, write to me. If I cancel a lesson, you keep it with no deadline.")),
        (("Clases sin usar", "Unused lessons"),
         ("Las clases de un periodo están pensadas para ese periodo. Al terminar, hasta dos clases sin usar pasan al "
          "periodo siguiente y pueden recuperarse durante los 30 días posteriores. Si no hay horarios adecuados, "
          "escríbeme y buscamos una solución.",
          "The lessons of a period are meant for that period. When it ends, up to two unused lessons move on to the next "
          "period and can be made up within the following 30 days. If there are no suitable times, write to me and "
          "we will find a solution.")),
        (("Desistimiento", "Right of withdrawal"),
         ("Dispones de 14 días naturales desde la contratación para desistir sin indicar el motivo, escribiendo a "
          "lguinea@berklee.edu. Si has pedido empezar las clases dentro de ese plazo, se descontará la parte "
          "proporcional de las clases ya recibidas.",
          "You have 14 calendar days from subscribing to withdraw without giving a reason, by writing to "
          "lguinea@berklee.edu. If you asked to start the lessons within that period, the proportional part of the "
          "lessons already received will be deducted.")),
    ],
    "acceptTerms": ("He leído y acepto las condiciones de contratación y la política de privacidad. Soy mayor de edad o "
                    "contrato como representante legal del alumno menor.",
                    "I have read and accept the terms and the privacy policy. I am of age or I am subscribing as the "
                    "legal representative of the underage student."),
    "termsLink": ("Condiciones de contratación y privacidad", "Terms and privacy policy"),
    "earlyStart": ("Quiero empezar las clases antes de que terminen los 14 días de desistimiento. Si desisto, pagaré "
                   "solo la parte proporcional de las clases recibidas.",
                   "I want to start the lessons before the 14-day withdrawal period ends. If I withdraw, I will only "
                   "pay the proportional part of the lessons received."),
    "submit": ("Contratar plan", "Subscribe"),
    "secure": ("Pagas en Stripe Checkout, donde verás de nuevo el importe y la frecuencia de renovación antes de confirmar.",
               "You pay on Stripe Checkout, where you will see the amount and the renewal frequency again before confirming."),
    "already": ("¿Ya eres alumno?", "Already a student?"),
    "studentLink": ("Entra en tu área de alumno", "Go to your student area"),
    "redirecting": ("Te llevamos a Stripe…", "Taking you to Stripe…"),
    "errPlan": ("Elige un plan.", "Choose a plan."),
    "errTerms": ("Acepta las condiciones para continuar.", "Accept the conditions to continue."),
    "errEarly": ("Para reservar clases dentro de los 14 primeros días, necesitamos tu solicitud expresa.",
                 "To book lessons within the first 14 days, we need your express request."),
    "errGeneric": ("No se ha podido abrir el pago. Inténtalo de nuevo en unos minutos.",
                   "The payment could not be opened. Please try again in a few minutes."),
    "errOff": ("La contratación en línea todavía no está disponible. Escríbeme y te reservo plaza.",
               "Online subscription is not available yet. Write to me and I will keep a place for you."),
}

L["students"] = {
    "pageTitle": ("Área de alumno · Luis Guinea", "Student area · Luis Guinea"),
    "eyebrow": ("Área de alumno", "Student area"),
    "title": ("Tus clases, en un solo sitio.", "Your lessons, in one place."),
    "titleAccent": ("un solo sitio.", "one place."),
    "loginTitle": ("Entra con tu correo", "Sign in with your email"),
    "loginIntro": ("Escribe el correo con el que contrataste tu plan y te enviaremos un enlace de acceso. Sin contraseñas.",
                   "Enter the email you used for your plan and we will send you an access link. No passwords."),
    "email": ("Correo electrónico", "Email"),
    "sendLink": ("Enviar enlace", "Send link"),
    "linkSent": ("Si ese correo corresponde a un alumno, acabamos de enviarle un enlace de acceso. Revisa también el correo no deseado.",
                 "If that email belongs to a student, we have just sent it an access link. Check your spam folder too."),
    "errEmail": ("Revisa el correo electrónico.", "Check the email address."),
    "errRate": ("Demasiadas solicitudes. Prueba dentro de una hora.", "Too many requests. Try again in an hour."),
    "errLink": ("Este enlace ya se usó o ha caducado. Pide uno nuevo.", "This link was already used or has expired. Ask for a new one."),
    "errSession": ("Tu sesión ha caducado. Vuelve a entrar con tu correo.", "Your session has expired. Sign in again with your email."),
    "errGeneric": ("No se ha podido completar. Inténtalo de nuevo en unos minutos.", "That did not work. Please try again in a few minutes."),
    "errBusy": ("Hay otra operación en curso. Inténtalo de nuevo en unos segundos.", "Another operation is in progress. Try again in a few seconds."),
    "checkingPayment": ("Comprobando tu pago con Stripe…", "Checking your payment with Stripe…"),
    "paymentReady": ("Pago confirmado. Tus clases ya están disponibles y te hemos enviado a tu correo el enlace para entrar.",
                     "Payment confirmed. Your lessons are ready and we have emailed you the link to sign in."),
    "paymentPending": ("Estamos esperando la confirmación de Stripe. Esta página se actualizará sola; no hace falta pagar de nuevo.",
                       "We are waiting for Stripe's confirmation. This page will update by itself; there is no need to pay again."),
    "paymentOpen": ("El pago no se ha completado. No se ha hecho ningún cargo.", "The payment was not completed. You have not been charged."),
    "paymentExpired": ("La sesión de pago caducó sin cobro. Puedes volver a elegir tu plan.", "The payment session expired without a charge. You can choose your plan again."),
    "backToPlans": ("Volver a los planes", "Back to the plans"),
    "hello": ("Hola, {name}", "Hello, {name}"),
    "helloAnon": ("Hola", "Hello"),
    "signOut": ("Cerrar sesión", "Sign out"),
    "planTitle": ("Mi plan", "My plan"),
    "noPlan": ("No hay ningún plan activo.", "There is no active plan."),
    "plan_weekly": ("Semanal · una clase cada semana", "Weekly · one lesson every week"),
    "plan_biweekly": ("Quincenal · una clase cada dos semanas", "Every two weeks · one lesson every two weeks"),
    "price": ("{amount} cada {weeks} semanas", "{amount} every {weeks} weeks"),
    "renews": ("Próxima renovación: {date}", "Next renewal: {date}"),
    "ends": ("Termina el {date}. No habrá más cobros.", "Ends on {date}. There will be no further charges."),
    "status_active": ("Activa", "Active"),
    "status_past_due": ("Pago pendiente", "Payment due"),
    "status_unpaid": ("Impagada", "Unpaid"),
    "status_canceled": ("Terminada", "Ended"),
    "status_incomplete": ("Pendiente de pago", "Awaiting payment"),
    "status_other": ("En revisión", "Under review"),
    "pastDueNote": ("Stripe no ha podido cobrar la renovación. Actualiza tu tarjeta en Facturación; las clases nuevas llegan al confirmarse el pago.",
                    "Stripe could not charge the renewal. Update your card in Billing; new lessons arrive once the payment is confirmed."),
    "classesTitle": ("Mis clases", "My lessons"),
    "available": ("Disponibles", "Available"),
    "reserved": ("Reservadas", "Booked"),
    "done": ("Realizadas", "Done"),
    "carried": ("Para recuperar", "To make up"),
    "deadline": ("Usar antes del {date}", "Use before {date}"),
    "noDeadline": ("Sin fecha límite", "No deadline"),
    "carriedTag": ("trasladada", "carried over"),
    "pastDeadline": ("Fuera de plazo: escríbeme y lo resolvemos", "Past its deadline: write to me and we will sort it out"),
    "expiredReview": ("Plazo vencido, en revisión: escríbeme", "Deadline passed, under review: write to me"),
    "bookTitle": ("Reservar clases", "Book lessons"),
    "bookIntro": ("Elige hasta {n} horas (una por clase disponible). Clases presenciales de 60 minutos.",
                  "Choose up to {n} times (one per available lesson). In-person 60-minute lessons."),
    "bookIntroOne": ("Elige una hora para tu clase disponible. Clase presencial de 60 minutos.",
                     "Choose a time for your available lesson. In-person 60-minute lesson."),
    "deadlineSoft": ("Pensada para usar antes del {date}", "Meant to be used before {date}"),
    "noCredits": ("No te quedan clases por reservar.", "You have no lessons left to book."),
    "loadingSlots": ("Cargando horarios…", "Loading times…"),
    "noSlots": ("No hay horarios libres ahora mismo. Escríbeme y buscamos uno.", "There are no free times right now. Write to me and we will find one."),
    "selected": ("{n} seleccionadas", "{n} selected"),
    "confirmBook": ("Reservar {n}", "Book {n}"),
    "booked": ("Reserva hecha. Recibirás la invitación de Google Calendar.", "Booked. You will receive the Google Calendar invitation."),
    "errSlot": ("Alguno de esos horarios acaba de ocuparse. Elige otro.", "One of those times has just been taken. Choose another."),
    "errNoCredits": ("No tienes clases suficientes para esa reserva.", "You do not have enough lessons for that booking."),
    "errOverlap": ("Dos de las horas se solapan.", "Two of the times overlap."),
    "bookingsTitle": ("Mis reservas", "My bookings"),
    "noBookings": ("Todavía no has reservado ninguna clase.", "You have not booked any lessons yet."),
    "inPerson": ("Presencial", "In person"),
    "status_reservada": ("Reservada", "Booked"),
    "status_realizada": ("Realizada", "Done"),
    "status_cancelada": ("Cancelada", "Cancelled"),
    "cancelledByTeacher": ("Cancelada por Luis: la clase vuelve a tu saldo", "Cancelled by Luis: the lesson is back in your balance"),
    "move": ("Cambiar hora", "Change time"),
    "cancel": ("Cancelar clase", "Cancel lesson"),
    "confirmCancel": ("Sí, cancelar", "Yes, cancel"),
    "keep": ("No, mantener", "No, keep it"),
    "changeUntil": ("Puedes cambiarla hasta el {date}", "You can change it until {date}"),
    "chooseNew": ("Elige la nueva hora", "Choose the new time"),
    "moved": ("Clase cambiada. La invitación se ha actualizado.", "Lesson moved. The invitation has been updated."),
    "cancelled": ("Clase cancelada. Recuperas la clase.", "Lesson cancelled. You get the lesson back."),
    "errTooLate": ("Ya no se puede cambiar desde aquí: faltan menos de 24 horas.", "It can no longer be changed here: less than 24 hours to go."),
    "errLimit": ("Has alcanzado el número máximo de cambios para esta clase.", "You have reached the maximum number of changes for this lesson."),
    "errAfterDeadline": ("Esa hora es posterior a la fecha límite de la clase.", "That time is after the lesson's deadline."),
    "billingTitle": ("Facturación", "Billing"),
    "billingIntro": ("Tarjeta, recibos y cancelación de la renovación, en el portal seguro de Stripe.",
                     "Card, receipts and cancelling the renewal, on Stripe's secure portal."),
    "portal": ("Abrir el portal de facturación", "Open the billing portal"),
    "policyNote": ("Puedes cambiar o cancelar una clase hasta {h} horas antes. Hasta {carry} clases sin usar pasan al periodo siguiente durante {days} días.",
                   "You can move or cancel a lesson up to {h} hours before. Up to {carry} unused lessons move on to the next period for {days} days."),
    "help": ("¿Dudas? Escríbeme a lguinea@berklee.edu", "Questions? Write to me at lguinea@berklee.edu"),
    "changePlanTo_weekly": ("Pasar al plan semanal desde la próxima renovación", "Switch to the weekly plan from the next renewal"),
    "changePlanTo_biweekly": ("Pasar al plan quincenal desde la próxima renovación", "Switch to the every-two-weeks plan from the next renewal"),
    "changePlanConfirm": ("El cambio se aplicará el {date}, al terminar el periodo que ya has pagado. Hoy no se cobra nada y no hay ajustes de precio.",
                          "The change will apply on {date}, when the period you have already paid ends. Nothing is charged today and there are no price adjustments."),
    "confirmChange": ("Confirmar el cambio", "Confirm the change"),
    "pendingChange": ("Desde el {date} tendrás el plan {plan}. Hasta entonces sigue tu plan actual y no se cobra nada.",
                      "From {date} you will be on the {plan} plan. Until then your current plan continues and nothing is charged."),
    "planName_weekly": ("semanal", "weekly"),
    "planName_biweekly": ("quincenal", "every-two-weeks"),
    "keepPlan": ("Mantener mi plan actual", "Keep my current plan"),
    "planChanged": ("Cambio de plan programado.", "Plan change scheduled."),
    "planKept": ("Mantienes tu plan actual.", "You keep your current plan."),
    "errNotActive": ("Solo se puede cambiar de plan con una suscripción activa y sin cancelación programada.",
                     "You can only change plan with an active subscription that is not set to cancel."),
    "repeat_weekly": ("Repetir esta hora cada semana", "Repeat this time every week"),
    "repeat_biweekly": ("Repetir esta hora cada dos semanas", "Repeat this time every two weeks"),
    "repeatPartial": ("Algunas semanas no tienen esa hora libre: elige otra para esas.", "Some weeks do not have that time free: choose another for those."),
    "lateTitle": ("Faltan menos de 24 horas.", "Less than 24 hours to go."),
    "lateBody": ("Ya no puedes cambiarla desde aquí. Escríbeme cuanto antes: si hay un motivo justificado, conservas la clase. Si faltas sin avisar, la clase cuenta como realizada.",
                 "You can no longer change it here. Write to me as soon as you can: with a justified reason, you keep the lesson. If you miss it without notice, it counts as done."),
    "writeLuis": ("Escribir a Luis", "Write to Luis"),
    "justified": ("Ausencia justificada: la clase vuelve a tu saldo", "Justified absence: the lesson is back in your balance"),
}


# ---------- terms and privacy page (/formacion/condiciones/), Spanish only: the Spanish text is the binding one ----------
# {name}, {nif}, {address}, {classPlace}, {email} come from PROVIDER. Version must match TERMS_VERSION in Billing.gs.
LEGAL_VERSION = "2026-11-12-v1"
LEGAL = [
    ("1. Prestador del servicio", [
        "{name}, profesional autónomo, NIF {nif}, con domicilio en {address}. Contacto: {email}.",
        "Los cobros se procesan a través de Stripe en la cuenta del titular, cuyo nombre comercial en Stripe es «Santo Chilaquil». "
        "En tu extracto bancario el cargo aparecerá como LUISGUINEA CLASES o con ese nombre comercial.",
    ]),
    ("2. Servicio", [
        "Clases particulares de música (piano, armonía, composición o producción musical), individuales y presenciales, de 60 minutos, "
        "en {classPlace}. El contenido se adapta al nivel y los objetivos de cada alumno.",
    ]),
    ("3. Planes y precio", [
        "Plan semanal: 148 € cada 28 días, que incluyen 4 clases (una por semana como calendario habitual).",
        "Plan quincenal: 148 € cada 56 días, que incluyen 4 clases (una cada dos semanas como calendario habitual).",
        "Es el precio final por periodo. No hay matrícula, permanencia ni otros cargos. El pago se hace con tarjeta a través de Stripe; "
        "el prestador no recibe ni guarda los datos de la tarjeta.",
    ]),
    ("4. Contratación y renovación automática", [
        "El contrato se formaliza al confirmarse el pago del primer periodo. Recibirás por correo la confirmación y el acceso a tu área de alumno.",
        "La suscripción se renueva automáticamente al terminar cada periodo, por el mismo importe y duración, hasta que la canceles. "
        "Antes de pagar, la pantalla de pago muestra el importe y la frecuencia de renovación. Recibirás un recibo por cada cobro.",
    ]),
    ("5. Cancelación", [
        "Puedes cancelar la renovación cuando quieras desde tu área de alumno (portal de facturación de Stripe), sin penalización. "
        "La cancelación evita los cobros siguientes y tiene efecto al final del periodo ya pagado. Conservas las clases que ya has pagado.",
    ]),
    ("6. Derecho de desistimiento", [
        "Puedes desistir del contrato en los 14 días naturales siguientes a la contratación, sin indicar el motivo, escribiendo a {email} "
        "(puedes usar el modelo del final de esta página). Te devolveremos el importe en un máximo de 14 días por el mismo medio de pago.",
        "Si al contratar pediste expresamente empezar las clases dentro de ese plazo y después desistes, se descontará la parte proporcional "
        "de las clases ya recibidas: 37 € por clase.",
    ]),
    ("7. Reservas, cambios y cancelaciones de clases", [
        "Reservas tus clases desde tu área de alumno según la disponibilidad publicada. Puedes cambiar o cancelar cada clase sin penalización "
        "hasta 24 horas antes de su inicio (hasta 3 cambios por clase). Con menos de 24 horas, escríbeme y lo valoraremos según el apartado 8.",
        "Si soy yo quien cancela una clase, la conservas íntegra y sin fecha límite.",
    ]),
    ("8. Ausencias", [
        "Si no asistes a una clase reservada sin haber avisado con al menos 24 horas, la clase se considera realizada. "
        "Si hay una causa justificada (por ejemplo, enfermedad o fuerza mayor) y me la comunicas, conservas la clase.",
    ]),
    ("9. Clases no utilizadas y recuperación", [
        "Las clases de cada periodo están pensadas para ese periodo. Al terminarlo, hasta dos clases sin usar pasan al periodo siguiente y "
        "pueden recuperarse durante los 30 días posteriores; se usan primero las de fecha límite más próxima. Las clases de recuperación se "
        "reservan en horarios libres.",
        "Actualmente las clases no utilizadas no caducan de forma automática. Cualquier cambio de esta condición se comunicará con antelación "
        "y no afectará a las clases ya pagadas. Si no hay horarios adecuados para recuperar una clase, buscaremos una solución.",
    ]),
    ("10. Cambio de plan", [
        "Puedes pasar del plan semanal al quincenal, o al revés, desde tu área de alumno. El cambio se aplica en la siguiente renovación, "
        "sin prorrateos ni cobros adicionales.",
    ]),
    ("11. Reembolsos e impagos", [
        "Las solicitudes de reembolso se estudian individualmente y se responden por escrito. Un reembolso puede anular las clases que cubre, "
        "lo que se te indicará.",
        "Si falla el cobro de una renovación, Stripe reintentará el cargo y te avisará. Hasta que se pague no se añaden clases nuevas; las ya "
        "pagadas se mantienen.",
    ]),
    ("12. Menores de edad", [
        "Si el alumno es menor de edad, la contratación la realiza su madre, padre o representante legal, que acepta estas condiciones y "
        "gestiona el área de alumno.",
    ]),
    ("13. Atención al cliente y reclamaciones", [
        "Puedes enviar consultas y reclamaciones a {email}. Responderé en un plazo máximo de 7 días. Este contrato se rige por la ley española; "
        "como consumidor, puedes acudir a los tribunales de tu domicilio y a los organismos de consumo competentes.",
    ]),
    ("14. Modificaciones", [
        "Cualquier cambio de precio o condiciones se comunicará al menos 30 días antes de la siguiente renovación, y podrás cancelar sin coste.",
    ]),
]
PRIVACY = [
    ("Responsable", ["{name}, NIF {nif}, {address}. Contacto: {email}."]),
    ("Datos y finalidades", [
        "Nombre, correo electrónico y las fechas de tus clases, para prestar el servicio (reservas, recordatorios y avisos); datos de cobro "
        "para gestionar la suscripción y cumplir las obligaciones fiscales y contables. Los datos de la tarjeta los trata Stripe y no llegan "
        "al prestador. No se usan para publicidad ni para decisiones automatizadas.",
        "Base jurídica: la ejecución del contrato y el cumplimiento de obligaciones legales.",
    ]),
    ("Conservación", [
        "Mientras dure la relación y, después, durante los plazos legales (la documentación contable y fiscal, hasta seis años). "
        "Los enlaces de acceso caducan a las 72 horas y las sesiones del área de alumno a los 30 días.",
    ]),
    ("Proveedores", [
        "Stripe (pagos y suscripciones), Google (calendario, correo y registro privado de clases), Cloudflare (reenvío técnico de avisos de "
        "Stripe, sin datos personales) y GitHub (alojamiento de la web). Algunos pueden tratar datos fuera del Espacio Económico Europeo con "
        "las garantías previstas en el RGPD (cláusulas contractuales tipo o Marco de Privacidad de Datos UE-EE. UU.).",
    ]),
    ("Menores", ["Si el alumno es menor de 14 años, sus datos los facilita y gestiona su representante legal."]),
    ("Tus derechos", [
        "Puedes ejercer los derechos de acceso, rectificación, supresión, oposición, limitación y portabilidad escribiendo a {email}, "
        "y reclamar ante la Agencia Española de Protección de Datos (aepd.es).",
    ]),
    ("Cookies y almacenamiento", [
        "La web no usa cookies de publicidad ni de analítica. El área de alumno guarda en tu navegador solo el identificador de tu sesión, "
        "necesario para el servicio; se borra al cerrar sesión.",
    ]),
]
WITHDRAWAL_FORM = ("A la atención de {name}, {address}, {email}: por la presente le comunico que desisto de mi contrato de clases "
                   "(plan …), contratado el …. Nombre del consumidor: …. Domicilio: …. Fecha: ….")
