# Planes de clases con Stripe Billing

Suscripciones de las clases particulares presenciales de `https://luisguinea.com/formacion/` (misión 04). Mismo
proyecto de Apps Script que la agenda (`Code.gs`); este archivo describe `Billing.gs`, el relé
`workers/stripe-relay/` y las páginas `formacion/#planes` y `alumnos/`.

**Estado:** implementado y probado en modo de pruebas. **Nada está publicado ni activado en real**:
`SUBSCRIPTIONS["published"]` es `False` en `tools/formacion_content.py`, `BILLING_CHECKOUT_ENABLED` no existe en las
propiedades de producción y no hay webhook ni clave real configurados.

## Arquitectura

```
                         ┌──────────────── GitHub Pages (estático) ────────────────┐
 alumno ── navegador ──▶ │ /formacion/#planes  (js/plans.js)   /alumnos/ (js/alumnos.js) │
                         └───────────────┬───────────────────────────────┬─────────┘
             POST text/plain {op: checkout|checkout_status|stu_*}        │ redirección
                                         ▼                               ▼
 ┌─────────────── Apps Script web app (Code.gs + Billing.gs) ───────────┐   Stripe Checkout
 │ LockService (un solo bloqueo para agenda, clases y webhooks)         │   Stripe Customer Portal
 │ UrlFetchApp ──▶ API de Stripe (clave restringida en Script Properties)│        │
 │ Calendar ─────▶ calendario de reservas (clases = eventos con invitado)│        │ eventos
 │ SpreadsheetApp ▶ hoja privada "Clases luisguinea.com" (registro)      │        ▼
 │ MailApp ──────▶ avisos al alumno y a Luis                             │   Cloudflare Worker
 └──────────────────────────────▲───────────────────────────────────────┘   (relé de webhooks)
                                └──── POST {op: stripe_event, id, ts, sig} ──────┘
```

- **Stripe es la fuente de verdad de pagos y suscripciones.** El backend nunca usa los datos que trae un webhook ni lo
  que diga el navegador: descarga el evento (`GET /v1/events/:id`) y la factura, suscripción o sesión de Checkout
  correspondiente antes de cambiar nada. Por eso los eventos repetidos o desordenados no alteran los saldos.
- **El registro de clases es propio** (pestaña `movimientos`, solo se añaden filas): cada movimiento tiene un id único
  (`grant:<factura>:<n>`, `reserve:<reserva>`, `release:…`, `consume:…`, `rollover:…`, `move:…`, `void:…`, `extend:…`).
  Créditos, reservas y saldos se recalculan siempre a partir de los movimientos (`deriveLedger_`). No hay contador
  editable. Una factura no puede conceder créditos dos veces.
- **Concurrencia:** todo lo que escribe pasa por el bloqueo de `Code.gs` (`withLock_`), compartido con la agenda. Dos
  peticiones simultáneas no pueden usar el mismo crédito ni la misma hora; la segunda recibe `busy` y no escribe nada.
- **Agenda intacta:** las clases se crean en el calendario de reservas, así que bloquean la agenda general (Freebusy) y
  viceversa. El contrato de la agenda no cambia.

### Por qué un relé (Cloudflare Worker) y no solo Apps Script

Apps Script no puede validar webhooks de Stripe: `doPost` no recibe cabeceras (no hay `Stripe-Signature`) y responde a
cada POST con un 302, que Stripe cuenta como entrega fallida (reintentos durante días y desactivación del endpoint).
El relé (`workers/stripe-relay/worker.js`, ~120 líneas, sin dependencias):

1. verifica la firma `v1` (HMAC-SHA256 de `t.cuerpo` con `whsec_…`, comparación en tiempo constante, 5 min de tolerancia);
2. reenvía solo `{id, type}` con su propia firma HMAC (`RELAY_SECRET`, compartido solo con Apps Script);
3. responde 200 solo si Apps Script lo procesó; si no, 5xx y Stripe reintenta.

| Alternativa | Por qué se descarta |
|---|---|
| Solo Apps Script | No puede verificar la firma ni devolver 200 (ver arriba) |
| Vercel (plan Hobby) | Sus condiciones prohíben el uso comercial; Pro cuesta 20 $/mes |
| Supabase / servidor propio | Base de datos y servicio nuevos que mantener, cuando el registro cabe en una hoja privada |
| Stripe Pricing Table / Payment Links sin backend | No permiten créditos, reservas ni recuperación; seguiría haciendo falta el backend |

Coste del relé: 0 € (plan gratuito de Workers: 100.000 peticiones/día; aquí habrá unas decenas al mes).

### Registro (Google Sheet privada)

Pestañas (se crean solas con `checkBillingSetup`): `movimientos`, `alumnos`, `suscripciones` (copia del estado en
Stripe), `eventos` (eventos ya procesados), `accesos` (solo hashes), `avisos` (idempotencia de correos),
`incidencias`, `ajustes` (escribe Luis) y `panel` (se regenera; no editar).

**Panel administrativo = pestaña `panel`**: alumnos con plan, estado y próxima renovación; créditos disponibles,
reservados y fuera de plazo; próximas clases; incidencias abiertas (pagos fallidos, reembolsos, facturas inesperadas).
No hay otro panel que mantener. La hoja no se comparte con nadie.

**Ajustes manuales** (una fila por ajuste en `ajustes`; se aplican en la siguiente ejecución horaria y la columna
`estado` dice `hecho` o el error):

| tipo | columnas | efecto |
|---|---|---|
| `anular` | `credito` | Anula un crédito sin usar (p. ej. tras un reembolso) |
| `ampliar` | `credito`, `valor` = `aaaa-mm-dd` | Nueva fecha límite |
| `conceder` | `alumno` (correo), `valor` = 1 a 8 | Clases extra sin fecha límite |
| `revocar` | `alumno` (correo) | Cierra todas las sesiones de ese alumno |
| `justificar` | `credito` (ver «CLASES RECIENTES» en el panel) | Ausencia justificada: la clase realizada vuelve al saldo, sin fecha límite |
| `anonimizar` | `alumno` (correo) | Supresión: borra nombre y correo de la hoja y cierra sesiones; el registro contable queda con el id seudónimo |

**Cancelar una clase como profesor:** borra el evento en Google Calendar. En menos de una hora el alumno recupera la
clase **sin fecha límite** y recibe un correo. Mover el evento en Calendar también se refleja en su área.

## Operaciones (POST `text/plain`, campos exactos)

| op | campos | qué hace |
|---|---|---|
| `checkout` | `plan`, `lang`, `requestId`, `acceptTerms: true`, `earlyStart: true`, `website` | Crea la sesión de Checkout (idempotente por `requestId`) |
| `checkout_status` | `session` | Estado del pago (`open`, `processing`, `ready`, `expired`). Si Stripe ya lo cobró, concede las clases aquí mismo (idempotente) sin esperar al webhook. No devuelve datos personales |
| `stu_link` | `email`, `lang`, `website` | Envía un enlace de acceso de un solo uso (72 h). Misma respuesta exista o no el alumno |
| `stu_login` | `token` (del enlace) | Lo canjea por una sesión de 30 días |
| `stu_view` / `stu_slots` | `token` | Plan, clases, reservas y política / horarios de 60 min |
| `stu_book` | `token`, `requestId`, `starts[]` (1 a 4) | Reserva todo o nada; crédito más antiguo primero; reintento seguro |
| `stu_cancel` | `token`, `booking`, `confirm: true` | Hasta 24 h antes: borra el evento y devuelve el crédito |
| `stu_move` | `token`, `booking`, `start` | Hasta 24 h antes: mueve el mismo evento (máx. `MAX_RESCHEDULES`) |
| `stu_portal` | `token` | URL del Customer Portal de Stripe |
| `stu_logout` | `token` | Revoca la sesión |
| `stu_plan` | `token`, `plan`, `confirm: true` | Programa el cambio semanal ↔ quincenal para la próxima renovación (Subscription Schedule, sin prorrateo). Nada se cobra ahora |
| `stu_plan_undo` | `token` | Anula el cambio programado |
| `stripe_event` | `id`, `type`, `ts`, `sig` | Solo desde el relé |

Acceso de alumnos: enlace mágico por correo (prueba que controla el buzón), de un solo uso, canjeado por una sesión
revocable. Los tokens se guardan solo como SHA-256. Conocer el correo de otro alumno no da acceso; los ids de
Stripe no son credenciales; un alumno no puede ver ni tocar reservas de otro (`not_found`).

## Reglas de créditos implementadas

- Cada factura pagada de alta o renovación (`subscription_create`, `subscription_cycle`) concede 4 créditos con el
  periodo de la factura. Facturas pendientes, fallidas o de otro tipo no conceden nada (las raras abren incidencia).
- Reservar bloquea un crédito (el de fecha límite más próxima). Cancelar con ≥ 24 h lo libera. La clase pasa a
  realizada 48 h después de terminar (`CONSUME_GRACE_HOURS`) si el evento sigue en Calendar.
- Al terminar cada ciclo se registra qué créditos sin usar se trasladan (máx. 2, fecha límite = fin + 30 días) y
  cuáles no. **Ningún crédito se borra nunca.**
- `CREDIT_POLICY_ENFORCED` (por defecto **desactivado**): mientras no se apruebe la política, las fechas límite son
  informativas y nada deja de poder reservarse. Activado: un crédito vencido no se puede reservar por cuenta propia
  (queda "en revisión", visible para Luis, recuperable con `ampliar`), una clase no puede programarse después de la
  fecha límite de su crédito, y el alumno recibe un aviso 7 días antes.
- Cancelar la suscripción (al final del periodo o inmediata) no toca los créditos pagados.
- **Cambio de plan:** programado para el final del ciclo pagado. Stripe cobra entonces una factura `subscription_update`
  de 148 € sin prorrateo (verificado con Test Clocks), que concede las 4 clases del nuevo ciclo. Una factura
  `subscription_update` con prorrateo o con otro importe no concede nada y abre incidencia. Cancelar en el portal con un
  cambio pendiente anula el cambio.
- **Reembolsos:** cada `charge.refunded` deja un movimiento `refund` (importe, factura, parcial o total) y una incidencia;
  no se anula ninguna clase sin un ajuste `anular`.
- **Conciliación horaria:** revisa las suscripciones que lista Stripe **y** las ya conocidas por el registro.
- **Copia de seguridad:** `billingWeeklyBackup` (activador semanal) duplica la hoja en el mismo Drive.

## Propiedades de la secuencia de comandos (nuevas)

| Propiedad | Valor |
|---|---|
| `STRIPE_MODE` | `test` o `live` (debe coincidir con la clave) |
| `STRIPE_SECRET_KEY` | Clave **restringida** (`rk_…`): lectura de Customers, Subscriptions, Invoices, Events, Prices, Checkout Sessions; escritura de Checkout Sessions y Customer portal |
| `STRIPE_PRICE_WEEKLY` / `STRIPE_PRICE_BIWEEKLY` | ids de `tools/stripe_setup.py` |
| `STRIPE_PORTAL_CONFIG` | `bpc_…` de `tools/stripe_setup.py` |
| `RELAY_SECRET` | 64 hex aleatorios, el mismo que en el Worker |
| `LEDGER_SPREADSHEET_ID` | id de la hoja privada nueva |
| `BILLING_CHECKOUT_ENABLED` | `true` para permitir contratar (interruptor de emergencia) |
| `TERMS_APPROVED_VERSION` | Debe ser igual a `TERMS_VERSION` de `Billing.gs` (versión de las condiciones revisada por el abogado); si no, Checkout sigue cerrado |
| `CREDIT_POLICY_ENFORCED` | `false` hasta aprobar la política |
| `CLASS_LOCATION` | Dirección que aparece en la invitación (opcional) |
| `CLASS_AVAILABILITY_CALENDAR_ID` | Calendario de franjas solo para clases (opcional; si no, el de la agenda) |
| `STUDENT_CHANGE_HOURS`, `CONSUME_GRACE_HOURS`, `CARRY_MAX`, `CARRY_DAYS`, `LINK_HOURS`, `SESSION_DAYS`, `REMIND_HOURS`, `EXPIRY_WARN_DAYS` | 24, 48, 2, 30, 72, 30, 24, 7 por defecto |

Permisos nuevos del manifiesto (pedirán reautorizar): `spreadsheets` (la hoja; Apps Script no ofrece un permiso
limitado a una hoja en proyectos independientes), `script.external_request` (API de Stripe) y `script.scriptapp`
(activador horario).

## Pruebas

```
python3 -m unittest tests/test_billing.py      # 34 escenarios del backend + 9 del relé + comprobaciones estáticas
python3 -m unittest tests/test_reservas.py     # la agenda general sigue igual
```

De extremo a extremo contra la API real de Stripe en modo de pruebas (sandbox "Luis Guinea Formacion (pruebas)"):

```
stripe login                                    # elegir el sandbox de pruebas
python3 tools/stripe_setup.py                   # productos, precios y portal (idempotente)
python3 tools/build_formacion.py --preview http://127.0.0.1:8792/exec --out "$TMPDIR/preview"
STRIPE_PRICE_WEEKLY=price_… STRIPE_PRICE_BIWEEKLY=price_… STRIPE_PORTAL_CONFIG=bpc_… \
  node tools/billing_dev_server.js --preview "$TMPDIR/preview" --state "$TMPDIR/billing-state.json"
stripe listen --forward-to http://127.0.0.1:8792/stripe/webhook
open http://127.0.0.1:8792/formacion/#planes    # tarjeta 4242 4242 4242 4242; rechazo: 4000 0000 0000 0002
```

## Despliegue (cuando Luis lo apruebe; nada de esto está hecho)

> Procedimiento vigente y verificable: `docs/lanzamiento/08-DESPLIEGUE-Y-REVERSION.md` y el checklist bloqueante
> `docs/lanzamiento/CHECKLIST-LANZAMIENTO.md`. Lo que sigue es el resumen original de la Misión 04.

Orden pensado para que en ningún momento haya un botón de pago que no funcione:

1. **Stripe (modo real, cuenta propia de Luis, no la de Santo Chilaquil):** completar la activación de la cuenta y
   los datos fiscales; en *Settings → Billing → Subscriptions and emails* activar recibos, correos de pago fallido y
   Smart Retries, y **no** activar el correo de cancelación (lo envía el backend); en *Public details* poner la URL de
   condiciones. Ejecutar `tools/stripe_setup.py` adaptado a real (quitar el bloqueo de `--live` solo para esa
   ejecución, revisada). Crear la clave restringida.
2. **Hoja:** crear "Clases luisguinea.com" (privada) y copiar su id.
3. **Apps Script:** añadir `Billing.gs`, pegar el `appsscript.json` nuevo, poner las propiedades (sin
   `BILLING_CHECKOUT_ENABLED`), ejecutar `checkBillingSetup` (debe decir `ok` en los dos precios) e
   `installBillingTriggers`, aceptar los permisos y crear una **versión nueva** de la implementación (misma URL).
   La agenda sigue funcionando igual.
4. **Relé:** `npx wrangler deploy` en `workers/stripe-relay` con `APPS_SCRIPT_URL` y `STRIPE_MODE = "live"`;
   `wrangler secret put RELAY_SECRET` y, tras crear en Stripe el endpoint
   `https://<worker>/stripe/webhook` con los eventos de abajo, `wrangler secret put STRIPE_WEBHOOK_SECRET`.
5. **Web:** en `tools/formacion_content.py`, `SUBSCRIPTIONS = {"published": True, "endpoint": "<URL /exec>"}`;
   `python3 tools/build_formacion.py`; actualizar `tests/test_billing.py` (clase `NotPublishedUntilApproved`);
   PR y merge a `main` (publica GitHub Pages).
6. Poner `BILLING_CHECKOUT_ENABLED = true` y hacer una contratación real de 148 € con una tarjeta propia; comprobar
   créditos, reserva, cancelación desde el portal y reembolsarla desde Stripe (abre incidencia; anular sus créditos
   con un ajuste).

Eventos del webhook: `checkout.session.completed`, `checkout.session.async_payment_succeeded`, `invoice.paid`,
`invoice.payment_failed`, `customer.subscription.created`, `customer.subscription.updated`,
`customer.subscription.deleted`, `charge.refunded`, `charge.dispute.created`, `credit_note.created`,
`invoice.voided`, `invoice.marked_uncollectible`.

## Reversión

- **Parar contrataciones al instante:** borrar `BILLING_CHECKOUT_ENABLED` (la web muestra "no disponible"). Los
  alumnos actuales siguen reservando y Stripe sigue renovando.
- **Ocultar la web:** `SUBSCRIPTIONS["published"] = False`, regenerar y publicar.
- **Volver a la agenda anterior:** gestionar implementaciones → versión anterior. Los webhooks fallarán y Stripe los
  reintentará hasta 3 días; al volver a la versión nueva, la conciliación horaria recupera cualquier pago perdido.
- **Detener cobros:** cancelar las suscripciones en Stripe (los créditos pagados se conservan en la hoja).
- Nada de lo anterior borra datos: el registro solo crece.
