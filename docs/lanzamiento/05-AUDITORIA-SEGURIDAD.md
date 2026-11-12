# 05 · Auditoría de seguridad y privacidad

Revisión del código de la rama a 13 de noviembre de 2026. Nada está desplegado: los riesgos «en producción» son
previstos, no observados.

| Área | Estado | Riesgo residual | Acción |
|---|---|---|---|
| **Sesiones** | Token de 256 bits en `localStorage` (`lg-student-session`), 30 días, revocable (`stu_logout`, ajuste `revocar`, `anonimizar`). En servidor solo su SHA-256 | Robo por XSS. El sitio no carga scripts de terceros y el área no usa `innerHTML`. Un ordenador compartido conserva la sesión | Aceptable. Opción: bajar `SESSION_DAYS` a 7 |
| **Enlaces de acceso** | Un solo uso, 72 h, en el fragmento `#` (no llega a servidores ni registros), se borra de la barra antes de usarse; también con `hashchange` | Reenvío del correo a terceros antes de usarlo | Aceptable; `LINK_HOURS` configurable |
| **Enumeración de alumnos** | `stu_link` responde igual exista o no el correo | — | — |
| **Permisos de Google** | `spreadsheets` (todas las hojas de la cuenta), `calendar`, `send_mail`, `external_request`, `scriptapp` | `spreadsheets` es más amplio de lo necesario (Apps Script independiente no ofrece permiso por hoja) | Ejecutar como la cuenta de Luis; nadie más edita el proyecto. Opción futura: script vinculado a la hoja (`spreadsheets.currentonly`) |
| **Acceso a datos de alumnos** | Cada operación comprueba la sesión y la propiedad de la reserva (`not_found` si es de otro). La vista del alumno no incluye correos ajenos ni ids de Stripe | — | Probado: `nobody_reaches_another_students_data` |
| **Hoja privada** | No compartida; solo la cuenta de Luis | Compartirla por error expone todo | Checklist: comprobar «Acceso restringido» |
| **Secretos** | Clave restringida de Stripe y `RELAY_SECRET` en Script Properties; `STRIPE_WEBHOOK_SECRET` y `RELAY_SECRET` como secretos de Cloudflare. Ninguno en el repositorio (escaneo en `tests/test_billing.py`). El servidor local usa la sesión del CLI | Script Properties las ve cualquier editor del proyecto | Proyecto sin otros editores; rotar claves si eso cambia |
| **Clave de Stripe** | Restringida y con modo comprobado (`sk_live` nunca corre en `test` ni al revés) | — | Permisos mínimos listados en `08-DESPLIEGUE-Y-REVERSION.md` |
| **Webhooks** | Firma `v1` verificada en tiempo constante con 300 s de tolerancia; relé autenticado con HMAC y marca de tiempo; el evento se vuelve a descargar de Stripe; idempotencia por id | Caída de Cloudflare o de Apps Script | La conciliación horaria recupera lo perdido (probado con Stripe real) |
| **Abuso** | Campos exactos, ≤ 4 KB, trampa para bots, 30 checkouts por hora, 3 enlaces por correo y hora, 30 enlaces por hora en total, bloqueo único | Agotar el cupo de correo con muchas direcciones | Aceptable; límites configurables |
| **Concurrencia** | Todo lo que escribe va dentro de `LockService` (compartido con la agenda) | Respuestas `busy` en picos | Probado: dos reservas simultáneas |
| **Copias de seguridad** | Historial de versiones de Sheets y copia semanal (`billingWeeklyBackup`); Stripe conserva pagos y suscripciones | Las copias no se borran solas (sin permiso de Drive) | Borrar copias antiguas a mano cada año |
| **Recuperación ante errores** | Reserva todo o nada (compensación si Calendar falla); webhooks reintentados por Stripe; conciliación horaria; interruptor `BILLING_CHECKOUT_ENABLED` | — | Ver reversión |
| **Registro económico** | `movimientos` solo crece: concesiones por factura, reservas, consumos, traslados, ajustes, **reembolsos** (con importe y factura). Saldos recalculados, nunca editados | Edición manual de la hoja | Proteger la pestaña `movimientos` (Datos → Proteger hojas) |
| **Conservación y supresión** | Ajuste `anonimizar`; enlaces y sesiones caducan; la conservación contable se mantiene con un id seudónimo | Supresión en Stripe manual | Procedimiento en `04-PRIVACIDAD-PROPUESTA.md` |
| **Checkout** | Doble cierre: `BILLING_CHECKOUT_ENABLED=true` y `TERMS_APPROVED_VERSION` igual a la versión aprobada. La web no se genera con planes si el checklist no está completo (`tools/launch_gate.py`) | — | Probado: `checkout_stays_closed_until_the_terms_are_approved`, `test_launch_gate.py` |

**Servicios nuevos:** ninguno respecto a la Misión 04 (Cloudflare Workers, plan gratuito, ya justificado).
