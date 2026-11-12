# 08 · Plan de despliegue y reversión

Cada paso tiene una **verificación** y nada queda abierto al público hasta el paso 12. Los pasos 1 a 11 pueden
hacerse con la contratación cerrada: la web publicada no muestra los planes y el backend rechaza Checkout.

| # | Paso | Quién | Verificación |
|---|---|---|---|
| 1 | **Cuenta real de Stripe**: crear, verificar, banco, 2FA y Billing (07) | Luis | Dashboard sin avisos de verificación; checklist S1 y S6 |
| 2 | **Productos y precios**: `stripe login` en la cuenta nueva, primero en su sandbox (`stripe_setup.py` + `stripe_testclock_e2e.py`) y después en real (`stripe_setup.py` revisado) | Claude, con autorización | Script en `ok` y sin duplicados al repetirlo; S2 y S3 |
| 3 | **Customer Portal**: lo crea el mismo script (sin cambio de plan, cancelación al final del periodo, sin edición del cliente) | Claude | Abrir el portal de un cliente de prueba en el sandbox de la cuenta nueva |
| 4 | **Hoja privada**: crear «Clases luisguinea.com» y copiar su id | Luis | Acceso restringido; T1 |
| 5 | **Apps Script**: pegar `Billing.gs` y el `Code.gs` y `appsscript.json` de la rama; propiedades de la tabla siguiente, **sin** `BILLING_CHECKOUT_ENABLED` ni `TERMS_APPROVED_VERSION`; ejecutar `checkBillingSetup` e `installBillingTriggers`; aceptar los permisos; *Gestionar implementaciones → Editar → Versión nueva* (misma URL) | Luis, guiado | `checkBillingSetup` en `ok`; la agenda general reserva y cancela bien; T2 |
| 6 | **Secretos**: `RELAY_SECRET` (64 hex, el mismo en Apps Script y Cloudflare), clave restringida (07) y `whsec_` | Luis | Ningún secreto en el repo ni en mensajes; X2 |
| 7 | **Cloudflare Worker**: `npx wrangler deploy` en `workers/stripe-relay` con `APPS_SCRIPT_URL` y `STRIPE_MODE=live`; `wrangler secret put RELAY_SECRET` | Luis, guiado | `GET /stripe/webhook` → 405 |
| 8 | **Webhook** en Stripe → `https://<worker>/stripe/webhook` con los 12 eventos; `wrangler secret put STRIPE_WEBHOOK_SECRET` | Luis | «Enviar evento de prueba» → 200; pestaña `eventos` de la hoja con `invalid_event` o `ignored` (los eventos de prueba no existen en la API); T3 |
| 9 | **Frontend en vista previa**: `build_formacion.py --preview <URL /exec real> --out <tmp>` y servidor local | Claude | Revisión en escritorio y móvil; T5 |
| 10 | **Compra controlada**: poner `TERMS_APPROVED_VERSION` (si L1 está hecho) y `BILLING_CHECKOUT_ENABLED=true`; comprar desde la vista previa con tarjeta propia; probar reservas, portal y reembolso; **volver a quitar** `BILLING_CHECKOUT_ENABLED` | Luis + Claude | R1 a R5 |
| 11 | **Notificaciones**: confirmar la recepción real de todos los correos (alumno y Luis) y su aspecto en el móvil | Luis | R2 |
| 12 | **Activación pública**: completar y firmar el checklist; `SUBSCRIPTIONS = {"published": True, "endpoint": "<URL /exec>"}`; `python3 tools/build_formacion.py` (el bloqueo se abre); actualizar `NotPublishedUntilApproved` en `tests/test_billing.py`; PR a `main`; **después** de publicar, `BILLING_CHECKOUT_ENABLED=true` | Luis autoriza; Claude prepara el PR | Sección visible en luisguinea.com/formacion/#planes; A1 |
| 13 | **Monitorización inicial (2 semanas)**: revisar a diario la pestaña `panel` (incidencias), el Dashboard de Stripe (pagos, webhooks fallidos) y los registros de ejecución de Apps Script; comprobar que se ejecuta `billingHourly` y que existe la copia semanal | Luis | Sin incidencias abiertas sin explicar; entregas de webhook al 100 % |

### Propiedades de producción (Apps Script)

`STRIPE_MODE=live`, `STRIPE_SECRET_KEY` (rk_live restringida), `STRIPE_PRICE_WEEKLY`, `STRIPE_PRICE_BIWEEKLY`,
`STRIPE_PORTAL_CONFIG`, `RELAY_SECRET`, `LEDGER_SPREADSHEET_ID`, `CLASS_LOCATION`,
`CLASS_AVAILABILITY_CALENDAR_ID` (opcional) y, al final, `TERMS_APPROVED_VERSION` y `BILLING_CHECKOUT_ENABLED`.
`CREDIT_POLICY_ENFORCED` **no se define** hasta el informe jurídico.

## 14. Reversión

| Situación | Acción | Efecto |
|---|---|---|
| Hay que parar las contrataciones ya | Borrar `BILLING_CHECKOUT_ENABLED` en Apps Script | Inmediato: el botón muestra «no disponible». Los alumnos siguen reservando y Stripe sigue renovando |
| Error en las condiciones | Borrar `TERMS_APPROVED_VERSION` | Igual que lo anterior |
| Ocultar la sección de la web | `SUBSCRIPTIONS["published"] = False`, regenerar y publicar | La web vuelve a ser la anterior |
| Fallo del backend nuevo | *Gestionar implementaciones* → versión anterior | La agenda vuelve a la versión previa; los webhooks fallan y Stripe los reintenta 3 días; al volver, la conciliación recupera lo pendiente |
| Fallo del Worker | `npx wrangler rollback` o desactivar el endpoint en Stripe | Los eventos se acumulan en Stripe; la conciliación horaria concede igualmente las clases pagadas |
| Detener todos los cobros | Cancelar las suscripciones en Stripe (al final del periodo) | Las clases pagadas se conservan en la hoja |
| Datos dañados en la hoja | Restaurar desde el historial de versiones o la última copia semanal | El registro solo crece: comparar `movimientos` con Stripe |

Nada de lo anterior borra pagos ni movimientos.
