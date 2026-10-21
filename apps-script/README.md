# Reservas con Google Apps Script

Backend de `https://luisguinea.com/agenda/`. Este directorio **no se publica** con el sitio
(`tools/build_site.py` solo copia una lista cerrada de archivos). Nada de lo que sigue se ha
desplegado ni probado contra Google: la implementación solo está verificada con servicios simulados
(`tests/support/reservas_scenarios.js`) y con la página real en Chrome contra un backend falso.

## Arquitectura

```
GitHub Pages (agenda/index.html + js/agenda.js)
   │  fetch GET  ?action=slots&duration=60                 (sin cabeceras, sin cookies)
   │  fetch POST text/plain con JSON {op: book|confirm|status}   (petición "simple": sin preflight)
   ▼
Apps Script web app (apps-script/Code.gs, se ejecuta como tú, acceso "Cualquier persona")
   ├─ CalendarApp        → calendario de disponibilidad (solo horas de inicio/fin)
   ├─ Calendar.Freebusy  → ocupado de tus calendarios (solo intervalos; nunca títulos ni detalles)
   ├─ LockService        → un solo proceso de reserva a la vez; disponibilidad revalidada dentro del bloqueo
   ├─ Calendar.Events    → bloqueo provisional sin invitados → invitación (+ Meet si es virtual) tras confirmar el correo
   ├─ MailApp            → un único correo de texto fijo con el enlace de confirmación
   ├─ PropertiesService  → estado de cada reserva (duradero) y hash del token, nunca el token
   └─ CacheService       → lista de horarios 60 s y contadores de límite (mejor esfuerzo)
```

### Reserva en dos pasos (verificación del correo)

Un correo escrito en un formulario **no** está verificado. Por eso nadie puede usar esta web para
hacer que tu cuenta envíe invitaciones de Google Calendar a direcciones ajenas:

1. `op: "book"` → dentro del bloqueo se vuelve a leer la disponibilidad y se crea en el calendario de
   reservas un **bloqueo provisional** `[Pendiente de confirmar] Encuentro virtual|presencial con …`: sin
   invitados, sin Meet y con `sendUpdates: 'none'`. Se envía un correo de texto fijo (sin el nombre, el
   motivo ni las notas del visitante; solo la modalidad, que es uno de dos valores fijos)
   con el enlace `https://luisguinea.com/agenda/#confirm=<id>.<secreto>`. El horario deja de ofrecerse.
2. `op: "confirm"` → quien abre el enlace demuestra que lee ese buzón. Solo entonces se añade como
   invitado, se envía la invitación (`sendUpdates: 'all'`) y, solo si es virtual, se pide la sala de Meet. El evento queda
   marcado con `lgEmailVerified=true` en sus propiedades privadas.
3. Si nadie confirma en `HOLD_MINUTES` (30 por defecto), el bloqueo se borra y el horario se libera.

El token va en el fragmento (`#`), así que nunca llega a los registros de GitHub Pages, y la página lo
quita de la barra de direcciones antes de usarlo. En Script Properties solo se guarda su SHA-256.

### Idempotencia y concurrencia

- Cada envío del formulario lleva un `requestId` aleatorio que la página reutiliza si el mismo envío se
  repite (reintento de red, doble clic, recarga de la pestaña). El servidor responde a un reintento con
  el resultado original: no crea otro bloqueo ni envía otro correo. El mismo `requestId` con otros datos
  se rechaza.
- El evento se crea con un id derivado del `requestId` (`lg` + 32 hex). Si Google lo creó pero la
  respuesta se perdió, el reintento recibe "ya existe", lo lee, comprueba que es suyo y lo reutiliza.
- La sala de Meet se pide con `requestId` = id de la reserva: confirmar dos veces no crea dos salas.
- Todo lo que escribe (bloqueo, confirmación, limpieza) ocurre dentro de `LockService`, después de
  volver a leer los calendarios. Una segunda petición simultánea recibe `busy` y no crea nada.

### Modalidad: virtual o presencial

La página obliga a elegir **Virtual** (marcada al inicio) o **Presencial**, y ofrece un campo opcional
para el motivo del encuentro. Contrato de `op: "book"` (además de `requestId`, `name`, `email`, `start`,
`duration`, `notes`, `website`, `lang`):

| Campo | Valores | Error si no es válido |
|---|---|---|
| `modality` | obligatorio: exactamente `"virtual"` o `"in_person"` | `invalid_modality` |
| `reason` | opcional: texto de hasta 150 caracteres, sin caracteres de control | `invalid_reason` |

- Ambos forman parte de la huella del `requestId`: el mismo `requestId` con otra modalidad o motivo se
  rechaza (`invalid_request`).
- Se guardan en el registro de la reserva y se devuelven en las respuestas `verification_sent` y
  `confirmed` (`modality`, `reason`), que la página muestra.
- Evento: título `Encuentro virtual con …` / `Encuentro presencial con …` (en inglés si el visitante usa
  la web en inglés) y una descripción con la modalidad, el motivo y las notas. En las presenciales,
  `location` = `Pendiente de acordar` y la descripción indica que el lugar está por acordar. La propiedad
  privada `lgModality` guarda la modalidad.
- **Virtual:** al confirmar se pide Meet (`conferenceData` + `conferenceDataVersion: 1`), como antes.
- **Presencial:** el `patch` de confirmación no lleva `conferenceData` ni `conferenceDataVersion`, así que
  Google no puede crear una sala; la respuesta trae `meet: {status: "none"}` y la página indica que el
  lugar se acordará por correo.
- La disponibilidad, los bloqueos, la caducidad, la idempotencia y la verificación por correo son
  idénticos para las dos modalidades.

### Google Meet

Solo en reservas virtuales. La respuesta de confirmación incluye `meet: {status: "ready", link}` solo si Google ya devolvió un
enlace `https://meet.google.com/…`. Si la sala sigue en `pending`, la página no muestra enlace, lo dice
y consulta `op: "status"` unas veces más; si Google responde `failure`, lo dice y ofrece el correo. La
invitación se envía en todo caso.

### Comunicación GitHub Pages ↔ Apps Script (CORS)

Las web apps de Apps Script responden a `/exec` con una redirección 302 a
`script.googleusercontent.com`, que sirve el contenido de `ContentService` con
`Access-Control-Allow-Origin: *`. Por eso la página usa solo peticiones "simples": `GET` sin cabeceras y
`POST` con `Content-Type: text/plain`, `credentials: 'omit'` y `redirect: 'follow'`. No hay preflight
`OPTIONS` (Apps Script no lo admite), no se usa `mode: 'no-cors'` (impediría leer la respuesta) y no se
puede ni se intenta añadir cabeceras CORS propias. Como no hay cookies ni credenciales, el `*` no expone
nada. Límites conocidos: `ContentService` no permite códigos HTTP de error (todo es 200 con `ok:false`)
y el POST, tras la redirección, se lee con un GET a `googleusercontent.com`, que ya contiene la
respuesta calculada; el `doPost` se ejecuta una sola vez.

### HTML Service: evaluado y descartado

`HtmlService` serviría la interfaz desde `script.google.com`, pero obligaría a incrustarla con un
`iframe` (sistema paralelo que se pidió no conservar), perdería la identidad visual y el
idioma EN/ES del sitio y mostraría la URL de Google. Se adopta una página estática en GitHub Pages que
llama a la web app como API JSON. No hay credenciales en el navegador; la URL `/exec` es pública por diseño.

## Seguridad (medidas contra abuso)

`LockService` solo evita carreras entre reservas legítimas; **no** protege contra solicitudes
maliciosas. Una web app de Apps Script no recibe la IP del visitante, así que todo identificador del
cliente (correo, `requestId`) se puede inventar. Por eso los límites no dependen solo de él:

- **Ninguna invitación sin verificar el buzón** (ver arriba). El correo de confirmación es de texto fijo.
- Los contadores **solo suben cuando se crea un bloqueo y sale su correo**. Peticiones inválidas,
  horarios no disponibles, reintentos y errores no consumen el cupo de nadie.
- `RATE_GLOBAL_HOUR` (20/h): bloqueos+correos en total por hora; protege la cuota de MailApp.
- `RATE_PER_EMAIL_HOUR` (3/h) por dirección (con hash, para no superar el límite de 250 caracteres de las
  claves de caché) y **un solo bloqueo pendiente por dirección** (`pending_exists`).
- `MAX_PENDING_HOLDS` (10): máximo de bloqueos sin confirmar a la vez, para que no se pueda llenar el
  calendario; los confirmados no cuentan. Confirmar y consultar estado no tienen límite (exigen token).
- Cuerpo máximo de 4 KB; campos desconocidos rechazados; nombre (2-80), correo (RFC práctico, 254 máx.),
  notas (500), duración 30/60/120/180, inicio en cuadrícula de 30 min en ISO UTC, campo trampa `website`,
  caracteres de control y bidireccionales rechazados; fallo cerrado si no se puede leer un calendario.
- La lista de horarios se guarda 60 s en `CacheService` solo si cabe (≤ 90 KB; el límite es 100 KB); si
  no cabe o la caché falla, se sirve igual sin cachear. Crear, confirmar o liberar un bloqueo borra la
  caché de las cuatro duraciones, así que nunca se anuncia libre un horario ya reservado o retenido.

Riesgo residual: alguien con muchos buzones propios puede agotar el cupo global o los bloqueos
pendientes durante un rato (la reserva vuelve a funcionar al caducar). Si ocurre, baja
`HOLD_MINUTES`, ajusta los límites o añade un captcha (no incluido para no depender de terceros).

## Configuración manual (pasos exactos)

1. **Calendario de disponibilidad**: en Google Calendar → *Otros calendarios → + → Crear calendario*,
   nómbralo p. ej. "Disponibilidad luisguinea.com" (nuevo y exclusivo, distinto del personal). Crea en él
   eventos normales (no de día completo) que cubran las franjas que quieres ofrecer; el título da igual
   y nunca se lee. Copia su ID: *Configuración del calendario → Integrar el calendario → ID del calendario*.
2. **Calendarios que bloquean tiempo**: anota el ID de cada calendario cuyo ocupado deba impedir reservas
   (principal = tu dirección de Gmail; otros, desde la misma pantalla). Deben ser visibles para la cuenta
   que despliega (al menos "ver solo libre/ocupado").
3. **Proyecto Apps Script**: en <https://script.google.com> → *Nuevo proyecto*. Pega `Code.gs`. En
   *Configuración del proyecto* activa *Mostrar el archivo de manifiesto "appsscript.json"* y pega el
   contenido de `appsscript.json` (zona horaria `Europe/Madrid`, permisos `calendar` y `script.send_mail`).
   En *Servicios (+)* añade **Google Calendar API**, versión v3, identificador `Calendar`.
4. **Propiedades de la secuencia de comandos** (*Configuración del proyecto → Propiedades de la secuencia
   de comandos*). Ningún valor es secreto, pero tampoco van en el repositorio:

   | Propiedad | Obligatoria | Valor |
   |---|---|---|
   | `AVAILABILITY_CALENDAR_ID` | sí | ID del calendario del paso 1 |
   | `BOOKING_CALENDAR_ID` | sí | Calendario donde se crean bloqueos y reservas (tu correo = calendario principal) |
   | `BUSY_CALENDAR_IDS` | no | IDs separados por comas del paso 2 (el de reservas se añade solo) |
   | `CONFIRM_URL` | no | `https://luisguinea.com/agenda/` por defecto; debe ser `https://` sin `?` ni `#` |
   | `TIMEZONE` | no | `Europe/Madrid` por defecto |
   | `MIN_NOTICE_HOURS` | no | Antelación mínima, 24 por defecto |
   | `MAX_DAYS_AHEAD` | no | Antelación máxima, 60 por defecto |
   | `BUFFER_MINUTES` | no | Margen antes y después de cada reunión, 15 por defecto |
   | `HOLD_MINUTES` | no | Validez del enlace de confirmación y del bloqueo, 30 por defecto (mínimo 5) |
   | `MAX_PENDING_HOLDS` | no | Bloqueos sin confirmar simultáneos, 10 por defecto |
   | `RATE_PER_EMAIL_HOUR` / `RATE_GLOBAL_HOUR` | no | 3 y 20 por defecto (correos enviados por hora) |

5. **Autorizar y comprobar**: en el editor elige la función `checkSetup` y pulsa *Ejecutar*. Acepta los
   permisos (Calendar y "Enviar correo como tú"; la pantalla de "app no verificada" es normal para un
   script propio: *Configuración avanzada → Ir a …*). `checkSetup` solo lee: en el *Registro de
   ejecución* debe mostrar las franjas encontradas, los calendarios legibles, la cuota de correo y cuántos
   horarios ofrecería cada duración. Si falla con `busy_calendar_unreadable`, revisa los IDs del paso 2.
6. **Activador de limpieza (recomendado)**: *Activadores (reloj) → Añadir activador* → función
   `sweepExpiredHolds`, fuente *Según tiempo*, *Temporizador por minutos*, *Cada 15 minutos*. Sin él,
   los bloqueos caducados se liberan igualmente en la siguiente consulta o reserva de un visitante.
7. **Deploy**: *Implementar → Nueva implementación → tipo Aplicación web*; *Ejecutar como*: **Yo**;
   *Quién tiene acceso*: **Cualquier persona**. Copia la URL que termina en `/exec`. Cada cambio de
   código exige *Gestionar implementaciones → Editar → Versión: nueva* (la URL se mantiene).
8. **Conectar la web**: pon esa URL en `agenda/index.html`:
   `<section id="agenda-app" ... data-endpoint="https://script.google.com/macros/s/XXXX/exec">`.
   Mientras esté vacío, la página muestra "reserva no disponible" y enlaza al correo.
9. **Publicar el sitio** y hacer una reserva real de prueba (ver abajo).

**Actualizar a la versión con modalidad (virtual/presencial):** el backend nuevo exige `modality`, y la
página anterior no la envía. Pega el `Code.gs` nuevo, crea una *versión nueva* de la implementación
existente (misma URL) y publica la web nueva **a la vez**; entre ambos pasos, la página antigua
recibiría `invalid_modality`. No hay propiedades nuevas ni permisos nuevos. Las reservas antiguas
pendientes sin modalidad se tratan como virtuales.

## Primera reserva real de prueba

1. Antes de publicar, abre en el navegador `<URL /exec>?action=slots&duration=60`: debe devolver
   `{"ok":true,...,"slots":[...]}` con las horas esperadas en `Europe/Madrid`.
2. Publica y abre `https://luisguinea.com/agenda/` en una ventana privada. Elige una duración y un
   horario, deja **Virtual** y reserva con **otra dirección tuya** (no la del calendario de reservas).
3. Comprueba: aparece "Revisa tu correo"; en tu calendario hay un evento `[Pendiente de confirmar]` sin
   invitados; el horario ya no se ofrece; llega un único correo sin tu nombre ni tus notas.
4. Abre el enlace del correo: la página muestra "Reserva confirmada", el evento pasa a `Encuentro virtual con …` con
   el invitado y Meet, llega la invitación de Google Calendar y el enlace de Meet aparece (o se indica que
   está pendiente). Vuelve a abrir el enlace: debe mostrar lo mismo sin crear nada nuevo.
5. Repite eligiendo **Presencial** y un motivo: el correo dice que el lugar está pendiente de acordar,
   el evento confirmado tiene `location` "Pendiente de acordar", el motivo en la descripción y **ningún**
   enlace de Meet, y la invitación llega sin videollamada.
6. Repite con otra duración y deja caducar una reserva sin confirmar: tras `HOLD_MINUTES` el evento
   provisional desaparece y el horario vuelve a ofrecerse.
7. Comprueba la consola del navegador en `/agenda/`: no debe haber errores CORS.
8. Borra los eventos de prueba (borrarlos manda una cancelación al invitado, que eres tú).

## Pruebas locales

```
python3 -m unittest tests/test_reservas.py      # exige Node.js: sin él falla, no se omite
python3 tools/build_site.py --out "$TMPDIR/site"
```

## Pendiente de verificar con Google (no comprobable sin credenciales)

- Autorización real y pantalla de consentimiento con los dos permisos.
- `Calendar.Freebusy`, `Events.insert` con id propio (y su error "ya existe"), `Events.patch` con
  `conferenceDataVersion: 1`, estados reales de Meet y envío real de la invitación.
- Que un evento sin invitados creado con `sendUpdates: 'none'` no notifique a nadie (esperado).
- Entrega de `MailApp` (posible carpeta de spam) y su cuota diaria (100 destinatarios/día en cuentas
  gratuitas; 1.500 en Workspace).
- Comportamiento CORS real de la redirección `script.googleusercontent.com` desde `luisguinea.com`
  (paso 7 de la prueba). Si el navegador bloquease la respuesta, no hay alternativa segura sin otro
  servidor; no se ha implementado JSONP porque expondría el POST.
- `LockService` y `CacheService` reales bajo carga.
