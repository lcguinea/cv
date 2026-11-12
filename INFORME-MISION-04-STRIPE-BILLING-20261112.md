# Misión 04 · Stripe Billing para Formación Musical: informe de entrega

Fecha: 12 de noviembre de 2026 · Rama: `feat/formacion-suscripciones-stripe` (solo local, sin push) ·
Estado: **implementado y probado en modo de pruebas. Nada publicado ni cobrado en real.**

Documentación técnica completa: `apps-script/BILLING.md`.

---

## 1. Auditoría de la infraestructura

| Área | Situación encontrada | Consecuencia |
|---|---|---|
| Sitio | Estático (HTML/CSS/JS sin framework) en GitHub Pages. Cada push a `main` publica. `tools/build_site.py` copia solo una lista cerrada de archivos | Lo nuevo queda fuera de esa lista hasta que lo apruebes |
| Formación | Generada por `tools/build_formacion.py` a partir de `tools/formacion_content.py`. Español por defecto con cambio a inglés. Tarifas por hora sin publicar (`COMMERCIAL.published = False`) | La sección de planes sigue el mismo patrón, con su propia bandera |
| Navegación continua | `js/soft-nav.js` cambia de página sin recargar y vuelve a ejecutar los scripts de cada página. El reproductor (`player.js`) persiste | Se ha comprobado en Chrome: de Formación al área de alumno sin recarga y con la música sonando |
| Agenda | Apps Script desplegado (URL `/exec` pública en `agenda/index.html`). Usa Calendar, Freebusy, `LockService`, ids de evento deterministas, idempotencia por `requestId`, enlaces de gestión con hash y aviso a Luis de cada reserva | Se reutiliza tal cual: mismo bloqueo, mismo calendario y mismos avisos |
| Stripe | La única cuenta del navegador es **Santo Chilaquil** (el restaurante), con dos sandboxes (Test mode y «Tiendita pruebas»). No hay cuenta de la actividad musical | **No se ha tocado nada de Santo Chilaquil.** Se creó el sandbox vacío «Luis Guinea Formacion (pruebas)» (`acct_1Uaz9MCVvccpiDKK`) sin copiar la cuenta real |
| Pruebas existentes | 251 pruebas. Falla 1 (`test_site_navigation_i18n`: claves `agenda.*` sin usar) | Ese fallo ya existe en `main`; no es de esta misión |

## 2. Arquitectura y flujo

```
Alumno ─▶ /formacion/#planes ── op checkout ──▶ Apps Script ── crea sesión ──▶ Stripe Checkout
                                                    ▲                              │ paga
         /alumnos/?checkout=cs_… ◀─────────────────┼──────────── redirección ─────┘
            │ op checkout_status (consulta a Stripe, nunca se fía del navegador)
            ▼
   «Pago confirmado» ── enlace de acceso al correo ──▶ /alumnos/#acceso=… ─▶ sesión de 30 días
            │
   reservar / cambiar / cancelar ──▶ Apps Script ──▶ Google Calendar (invitación) + registro de créditos
                                                         ▲
 Stripe ── webhook firmado ──▶ Cloudflare Worker (verifica la firma) ── id del evento ──┘
                                                 Apps Script descarga el evento de Stripe y actúa
 Activador horario: conciliación con Stripe, clases realizadas, cancelaciones tuyas, traslados, avisos, panel
```

- **Stripe es la fuente de verdad** de pagos y suscripciones. El registro de créditos es propio: solo se le añaden
  movimientos con id único, y los saldos se recalculan siempre a partir de ellos.
- **Backend: el mismo Apps Script de la agenda** (`apps-script/Billing.gs`) más una hoja de Google privada como
  registro y panel.
- **Relé de webhooks: Cloudflare Worker gratuito** (`workers/stripe-relay/`). Es necesario porque Apps Script no puede
  leer la cabecera `Stripe-Signature` y responde a los POST con un 302, que Stripe cuenta como fallo. Las alternativas
  descartadas y su justificación están en `apps-script/BILLING.md`.

## 3. Configuración de Stripe en modo de pruebas

Creada con `tools/stripe_setup.py`. El script es idempotente: busca por `lookup_key` y metadatos, así que una segunda
ejecución reutiliza lo existente (verificado).

| Objeto | Id (sandbox) | Comprobado |
|---|---|---|
| Producto «Clases particulares de música · Luis Guinea» | `prod_VcEXjawfqxl2zk` | |
| Precio semanal | `price_1Ub049CVvccpiDKKp3uJ7xTB` | 14 800 EUR, `week` × 4, recurrente, impuestos incluidos |
| Precio quincenal | `price_1Ub04BCVvccpiDKKxmyho5W2` | 14 800 EUR, `week` × 8, recurrente, impuestos incluidos |
| Customer Portal | `bpc_1Ub04DCVvccpiDKKt5NT1vTM` | Tarjeta, facturas y cancelación **al final del periodo**. Sin cambio de plan, sin pausas, sin prorrateos, sin edición del cliente |

Checkout: modo suscripción, sin cupones ni códigos promocionales, sin periodo de prueba, solo tarjeta, permite añadir
NIF, idioma del alumno, caduca en 1 hora. Encima del botón de pago aparece el texto de renovación. **No se ha creado
ningún webhook en el Dashboard**: en pruebas los entrega `stripe listen`.

## 4 a 10. Lo construido

| Entregable | Dónde | Notas |
|---|---|---|
| Página de contratación | Sección `#planes` de `/formacion/` (generada) | Dos planes, condiciones, dos consentimientos (condiciones y petición de empezar dentro del plazo de desistimiento) y enlace al área. Instrument Serif, Inter e IBM Plex Mono, paleta y reglas finas del sitio. Probada en escritorio y a 390 px |
| Integración de Checkout | `op checkout` / `checkout_status` | Idempotente por `requestId`. Al volver, el estado se pide a Stripe; si el pago ya está, las clases se conceden en ese momento sin esperar al webhook y sin duplicarlas |
| Créditos y reservas | `Billing.gs`, pestaña `movimientos` | 4 créditos por factura pagada; se usa primero el de fecha límite más próxima; reserva de 1 a 4 clases de una vez, todo o nada; cancelación y cambio con ≥ 24 h; consumo 48 h después de la clase; traslado de como máximo 2 créditos |
| Área de alumnos | `/alumnos/` + `js/alumnos.js` | Mi plan, Mis clases, Reservar, Mis reservas, Facturación (portal de Stripe). Acceso por enlace de un solo uso enviado al correo, sin contraseñas |
| Gestión administrativa | Pestaña `panel` de la hoja privada | Alumnos, planes, renovaciones, créditos, clases fuera de plazo, próximas clases e incidencias. Ajustes manuales en la pestaña `ajustes`. **Cancelar una clase = borrar el evento en Google Calendar**: el alumno la recupera sola |
| Webhooks | Worker + `stripe_event` | Firma `v1` verificada, 5 min de tolerancia, evento descargado de nuevo desde Stripe, eventos procesados registrados; los repetidos o desordenados no alteran nada |
| Notificaciones | Correo (`MailApp`) | **Alumno:** acceso al contratar, invitación de Calendar por reserva, recordatorio 24 h antes, aviso de clases a punto de vencer (solo con la política activada), confirmación de cancelación, aviso si cancelas tú. **Luis:** nueva suscripción, pago fallido, cancelación programada, suscripción terminada, incidencias, y además los avisos de reservas, cambios y cancelaciones |

Situaciones especiales, todas resueltas de forma conservadora (nunca se borra un derecho automáticamente):

| Caso | Comportamiento implementado |
|---|---|
| Cancelar con clases pendientes | Se conservan con sus fechas y se pueden seguir reservando |
| Reservada antes de vencer, programada después | Permitido mientras la política esté apagada. Encendida, la clase debe caer antes de la fecha límite del crédito → **decisión pendiente** |
| Ausencia sin aviso | La clase cuenta como realizada 48 h después, salvo que borres el evento → **decisión pendiente** |
| Cambio de frecuencia | Desactivado en el portal; un cambio hecho a mano en Stripe abre una incidencia y no concede créditos por prorrateo |
| Enfermedad o fuerza mayor | Sin regla automática: borras el evento (recupera la clase) o usas `ampliar` en `ajustes` |
| Sin horarios adecuados | Texto «escríbeme»; `ampliar` o `conceder` desde `ajustes` |
| Reembolso o disputa | Incidencia y aviso a Luis; ningún crédito cambia solo; `anular` desde `ajustes` |
| Fallo de renovación | Sin créditos nuevos; Stripe reintenta; aviso a Luis; al cobrarse llegan los 4 créditos |
| Tarjeta rechazada al contratar | Ningún alumno, crédito ni aviso (detectado y corregido gracias a la API real, ver §12) |

## 11. Pruebas automatizadas

```
python3 -m unittest tests/test_billing.py     # 34 escenarios de backend + 9 del relé + 7 estáticas: OK
python3 -m unittest tests/test_reservas.py    # agenda general: OK (13)
python3 -m unittest discover -s tests         # 251; 1 fallo previo de main (i18n de agenda)
```

Los 20 casos obligatorios están cubiertos por nombre (`test_the_twenty_required_cases_are_covered`): contratación
semanal y quincenal, pago correcto y rechazado, renovación a 4 y 8 semanas, webhook duplicado y fuera de orden,
cancelación inmediata y al final del periodo, reprogramación con más y con menos de 24 h, dos reservas simultáneas,
traslado de 1 y 2 créditos, intento de trasladar 3, vencimiento de la recuperación, cancelación con clases
pendientes, fallo temporal del backend, reintento de una petición, consulta de estado y acceso a datos de otro alumno.
Además: webhooks perdidos (recuperados por la conciliación), reembolsos, otros productos de la cuenta, cancelaciones
tuyas en Calendar, consumo de clases, recordatorios, reconstrucción del saldo y convivencia con la agenda general.

## 12. Evidencia en navegador y con la API real (Stripe en modo de pruebas)

Hechas con el código de producción (`Code.gs`, `Billing.gs` y el Worker) ejecutado en local contra la API real del
sandbox (`tools/billing_dev_server.js`) y con webhooks reales firmados (`stripe listen`).

1. Validación del formulario, selección de plan y consentimientos.
2. Checkout real: «148,00 € cada 4 semanas», insignia de entorno de prueba y texto de renovación.
3. **Tarjeta rechazada** (`4000…0002`): Stripe muestra el rechazo y no se concede nada. **Hallazgo:** Stripe crea igual
   una suscripción `incomplete` y emite `invoice.payment_failed`; la primera versión creaba una ficha de alumno y te
   avisaba de un «pago fallido». Se corrigió y se añadió el caso a las pruebas.
4. La misma sesión pagada con `4242…`: 4 créditos, correo de acceso y tu aviso de nueva suscripción, una vez cada uno.
5. Vuelta a `/alumnos/`: el id de sesión desaparece de la barra de direcciones; «Pago confirmado».
6. Acceso con el enlace mágico: plan semanal, activo, renovación el 10 de diciembre (28 días).
7. Reserva de 4 clases de una vez: 4 eventos con la alumna invitada y aviso a Luis.
8. Cancelación con confirmación (el crédito vuelve) y cambio de hora (el evento se mueve).
9. Customer Portal real: factura pagada y cancelación al final del periodo. El webhook firmado actualizó el área
   («Termina el 10 de diciembre. No habrá más cobros»), envió los dos avisos y conservó las 4 clases.
10. Navegación continua de Formación al área de alumno: misma página, música sonando (3,8 s → 5,8 s).
11. Vista móvil (390 px) de la sección de planes y del área de alumno.

Grabación: `mision04_contratacion_reserva_portal_stripe_test.gif` (carpeta de descargas de Chrome).

**Test Clocks** (`tools/stripe_testclock_e2e.py`, relojes de prueba que se borran al terminar):

| Escenario | Resultado |
|---|---|
| Semanal + 28 días | 8 créditos; dos periodos de exactamente 28,0 días |
| Reenvío del `invoice.paid` de la renovación | Siguen 8 |
| Quincenal | 4 créditos al día 28 (sin renovación) y 8 al día 56; periodos de 56,0 días |
| Renovación con tarjeta que falla | Siguen 4, suscripción `past_due`, 1 aviso a Luis; la conciliación no añade nada |

Se corrigieron también tres detalles de interfaz vistos en Chrome: paneles ocultos que se veían, la barra de reserva
tapada por el mini reproductor y el plural «hasta 1 horas».

## 13. Revisión de seguridad

- **Pagos:** el navegador nunca decide. Créditos solo por factura `paid` descargada de Stripe; ids `grant:<factura>:<n>`
  únicos; clave de una modalidad rechazada en la otra (`sk_live` nunca corre en `test`).
- **Webhooks:** firma HMAC en tiempo constante con tolerancia de 300 s; el relé reenvía solo el id con su propia
  firma; Apps Script vuelve a descargar el evento (un evento falsificado o de otra cuenta se rechaza).
- **Acceso de alumnos:** enlace de un solo uso (72 h), canjeado por una sesión revocable (30 días). Solo se guardan
  hashes SHA-256. Misma respuesta exista o no el correo. Límite de enlaces por correo y hora. Un alumno no puede ver
  ni tocar reservas de otro (`not_found`). Los ids de Stripe no se usan como credenciales ni se muestran.
- **Datos:** la web no ve ni guarda tarjetas. No hay secretos en el repositorio: escaneo automático en
  `tests/test_billing.py`; el servidor de desarrollo usa la sesión del CLI y no maneja claves. El panel vive en una
  hoja privada.
- **Abuso:** campos exactos, cuerpo ≤ 4 KB, trampa para bots, límites por hora de Checkout y de enlaces, bloqueo único.
- **Riesgos residuales:**
  - el permiso `spreadsheets` da acceso a todas las hojas de la cuenta (Apps Script no ofrece uno por hoja);
  - la sesión del alumno queda en `localStorage` (sitio sin scripts de terceros; se borra al cerrar sesión);
  - la reserva de un alumno depende del correo de Checkout: si escribe mal su correo, tendrás que corregirlo en Stripe.

## 14. Costes recurrentes estimados

Tarifas públicas de Stripe en el EEE (comprobar en stripe.com/es/pricing antes de activar): tarjetas europeas estándar
**1,5 % + 0,25 €**; Stripe Billing **0,7 %** del volumen facturado.

| | Por cobro de 148 € | 10 alumnos semanales (130 cobros/año) | 10 alumnos quincenales (65 cobros/año) |
|---|---|---|---|
| Tarjeta | 2,47 € | 321 € | 161 € |
| Billing | 1,04 € | 135 € | 68 € |
| **Total** | **3,51 € (2,4 %)** | **≈ 456 €/año** | **≈ 228 €/año** |

Sin coste: Cloudflare Workers (plan gratuito), Google Apps Script, Sheets y Calendar, y GitHub Pages. Stripe Tax no se
usa. Tarjetas no europeas e internacionales cuestan más.

## 15. Decisiones pendientes

**Tuyas (comerciales):**
1. **Cuenta de Stripe propia**, a tu nombre o al de tu actividad, distinta de Santo Chilaquil.
2. Activar la política de clases perdidas (`CREDIT_POLICY_ENFORCED`). Hasta entonces nadie pierde clases.
3. ¿Se puede reservar una clase para después de la fecha límite de su crédito?
4. Ausencias sin aviso: ¿cuentan como realizadas? (ahora sí, 48 h después, salvo que borres el evento).
5. Una clase cancelada por el alumno después de terminar su ciclo cuenta ahora como trasladada (hasta fin + 30 días).
   ¿Lo mantienes?
6. ¿Imponer la frecuencia (una por semana o cada dos semanas) o dejar libres las 4 clases del ciclo, como ahora?
7. Cambios de plan: desactivados. ¿Quieres permitir pasar de semanal a quincenal y cómo (al renovar, sin prorrateo)?
8. Política de reembolsos (ahora todo es manual).
9. Dirección de las clases (`CLASS_LOCATION`) y si las clases usan franjas propias (`CLASS_AVAILABILITY_CALENDAR_ID`).
10. Tope de cambios de hora por clase (ahora 3, el mismo que la agenda).

**Para tu gestor:**
1. IVA: las clases particulares impartidas por una persona física sobre materias de planes de estudio oficiales suelen
   estar exentas (art. 20.Uno.9.º de la Ley del IVA); confirmar que aplica a tu caso. Los precios están configurados
   como «impuestos incluidos» y el texto dice «precio final»: si hubiera IVA, 148 € ya lo incluiría.
2. Facturas: confirmar si las facturas y recibos de Stripe cumplen el Reglamento de facturación (NIF, numeración,
   mención de la exención) o si hay que emitirlas aparte; impacto de VeriFactu (obligatorio en 2027 según el
   calendario aprobado; confirmar fechas).
3. Alta en Hacienda y epígrafe del IAE de la actividad, y cuenta bancaria del cobro.

**Para un profesional jurídico:**
1. Condiciones generales y información previa obligatoria (TRLGDCU arts. 60 y 97), incluida la identidad del
   prestador (nombre, NIF y dirección, que hoy no aparecen).
2. Desistimiento de 14 días en servicios: el texto y el consentimiento de empezar antes; el cálculo proporcional; el
   formulario de desistimiento.
3. Validez de que las clases no usadas puedan perderse, y del límite de 2 trasladadas y 30 días (riesgo de cláusula
   abusiva); fecha límite de clases ya reservadas.
4. Renovación automática y cancelación «igual de fácil que contratar» (art. 62 TRLGDCU) y posibles nuevas obligaciones
   de atención a la clientela.
5. Alumnos menores: contrata el padre, madre o tutor; consentimiento de datos (LOPDGDD art. 7).
6. Política de privacidad: tratamiento por Stripe (pagos), Google (calendario, correo y hoja) y Cloudflare (relé);
   transferencias internacionales y plazos de conservación.

## 16. Despliegue y reversión

Procedimiento paso a paso en `apps-script/BILLING.md` («Despliegue» y «Reversión»). En resumen:

**Despliegue:**
1. Cuenta real y propia de Stripe, con los precios y el portal creados por el script revisado.
2. Hoja privada.
3. `Billing.gs` y permisos en el Apps Script, como versión nueva con la misma URL (la agenda sigue igual).
4. Worker con sus dos secretos y el endpoint del webhook en Stripe.
5. `SUBSCRIPTIONS.published = True` y merge a `main`.
6. `BILLING_CHECKOUT_ENABLED = true` y una compra real de 148 € con tu tarjeta, reembolsada después.

**Reversión inmediata:**
- Quitar `BILLING_CHECKOUT_ENABLED`: se detienen las contrataciones y los alumnos siguen funcionando.
- `published = False` oculta la web.
- Volver a la versión anterior del Apps Script; Stripe reintenta los webhooks y la conciliación horaria recupera lo
  pendiente.
- No se borra ningún dato.

---

### Archivos

- **Nuevos:** `apps-script/Billing.gs`, `apps-script/BILLING.md`, `workers/stripe-relay/{worker.js,wrangler.toml}`,
  `js/plans.js`, `js/alumnos.js`, `tools/{billing_dev_server.js,stripe_setup.py,stripe_testclock_e2e.py}`,
  `tests/test_billing.py`,
  `tests/support/{billing_env.js,fake_stripe.js,billing_scenarios.js,stripe_relay_scenarios.mjs}`.
- **Modificados:**
  - `apps-script/Code.gs`: 5 líneas de enrutado;
  - `apps-script/appsscript.json`: 3 permisos;
  - `tools/build_formacion.py`: sección de planes, `/alumnos/` y `--preview`;
  - `tools/formacion_content.py`: textos y bandera;
  - `tools/build_site.py`: lista de publicación condicionada;
  - `css/styles.css`: estilos nuevos al final;
  - `tests/test_reservas.py`: permisos esperados.
- **Sin cambios:** reproductor, navegación continua, agenda (página y JS) y páginas generadas de Formación (idénticas
  mientras `published = False`).
