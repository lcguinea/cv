# Checklist de lanzamiento: contratación de clases

> **Este archivo bloquea la publicación.** `tools/launch_gate.py` lo lee y `tools/build_formacion.py` se niega a
> generar la sección de planes con `SUBSCRIPTIONS["published"] = True` si queda alguna casilla sin marcar o falta la
> autorización final. Además, el backend no abre Checkout sin `BILLING_CHECKOUT_ENABLED=true` y sin
> `TERMS_APPROVED_VERSION`.
>
> Dos estados cerrados, distintos a propósito:
> - `[x]` **cumplido y verificado**: la nota dice cómo y cuándo.
> - `[~]` **dispensado por Luis**: no se ha hecho; Luis decidió lanzar igualmente (autorización de la Misión 06). La
>   línea dice «Dispensado» y el motivo. `launch_gate.py` lo acepta pero lo lista siempre como no verificado.
>   A1 nunca se puede dispensar.

Estado a 2026-11-13. Verificación: Claude. Decisiones y dispensas: Luis (Misión 06 y su revisión del 2026-11-13).

## Legal

- [~] L1 Un profesional jurídico ha revisado y aprobado las condiciones generales (03) y la política de privacidad (04). Dispensado por Luis: no hay revisión jurídica previa. Él aprobó el texto («Autorizo publicar las condiciones comerciales acordadas, pero no habilitar cláusulas contrarias a la normativa aplicable»); `TERMS_APPROVED_VERSION=2026-11-12-v1` registra su aprobación, no la de un abogado. Abierto: revisión jurídica.
- [x] L2 Los datos del prestador están completos en las condiciones (nombre fiscal, NIF y domicilio) y no queda ningún `[PENDIENTE]`. (2026-11-13: NIF, domicilio y lugar de las clases facilitados por Luis; comprobado en /formacion/condiciones/.)
- [~] L3 Las condiciones y la privacidad aprobadas están publicadas en luisguinea.com y enlazadas desde la sección de planes y desde Stripe (Public details). Dispensado por Luis en cuanto a Stripe, como consecuencia de usar la cuenta de Santo Chilaquil (S1): los «Public details» siguen siendo los del restaurante. Las condiciones se publican en /formacion/condiciones/ y se enlazan desde los planes, y Checkout muestra una nota con el titular.
- [x] L4 Los textos de la web (sección de planes, área de alumno y correos) coinciden con las condiciones aprobadas. (Revisados en la vista previa y en los correos reales del 2026-11-13.)
- [~] L5 La regla de ausencias y la de clases no utilizadas tienen la redacción aprobada. `CREDIT_POLICY_ENFORCED` solo se activa si el informe jurídico lo permite. Dispensado por Luis en cuanto a la aprobación jurídica (L1). `CREDIT_POLICY_ENFORCED` sigue sin definir: no hay caducidad automática.
- [x] L6 Está resuelto el tratamiento de los alumnos menores de edad. (Decisión 10 de Luis: contrata el representante legal; lo recogen la casilla de aceptación y el apartado 12.)

## Fiscal

- [~] F1 El gestor ha respondido a la consulta (02): alta, IAE, IVA por materia, facturas, VeriFactu y cobros anticipados. Dispensado por Luis: «mi gestor ya tiene dada de alta mi actividad» y «No quiero … consultar nuevamente a mi gestor como condición previa». La consulta (02) no se ha enviado.
- [~] F2 El precio final (148 €) es correcto con el tratamiento fiscal confirmado. Dispensado por Luis: el precio final de 148 € es decisión suya; el tratamiento de IVA no lo ha confirmado el gestor (F1).
- [~] F3 Las facturas o recibos cumplen lo indicado por el gestor (emisor, numeración y mención fiscal). Dispensado por Luis (F1): de momento solo hay los recibos de Stripe.

## Stripe

- [~] S1 La cuenta propia de la actividad musical está activada y verificada (07). No es la de Santo Chilaquil. Dispensado por Luis: «utilizar mi cuenta actual de Santo Chilaquil» y «No quiero crear otra cuenta de Stripe». Comprobado: es una cuenta de persona física, con producto propio y descriptor LUISGUINEA CLASES en el cargo real.
- [x] S2 `tools/stripe_testclock_e2e.py` pasa en el sandbox de la cuenta nueva. (Pasa en el sandbox «Luis Guinea Formacion (pruebas)», Misión 05; no existe cuenta nueva por S1.)
- [x] S3 Están creados en real el producto, los 2 precios (14 800 EUR, `week` × 4 y × 8) y el portal (sin cambios de plan, cancelación al final del periodo), y `checkBillingSetup` dice `ok`. (2026-11-13.)
- [x] S4 La clave es restringida, con los permisos mínimos de 07, y solo está en Script Properties. (Subscriptions en escritura porque Stripe incluye ahí los Subscription Schedules.)
- [x] S5 El webhook real apunta al Worker con los 12 eventos, y el secreto `whsec_` está en Cloudflare.
- [~] S6 Recibos, Smart Retries y correos de pago fallido están configurados, y el correo de cancelación de Stripe está desactivado. Dispensado por Luis como consecuencia de S1: no se cambian los correos de Stripe porque afectan a toda la cuenta del restaurante. En su lugar el backend envía su propio aviso de renovación y de pago fallido (cubierto por los tests).

## Técnico

- [x] T1 La hoja privada «Clases luisguinea.com» está creada, sin compartir y con la pestaña `movimientos` protegida. (2026-11-13: «Private only to me»; `movimientos` protegida con aviso al editar.)
- [x] T2 El Apps Script está actualizado: versión nueva de la implementación, permisos aceptados, `checkBillingSetup` en `ok`, `installBillingTriggers` ejecutado y la agenda general probada después. (Versión @10; activadores `billingHourly` y `billingWeeklyBackup`; agenda probada.)
- [x] T3 El Worker está desplegado con `STRIPE_MODE=live`, `APPS_SCRIPT_URL` y los dos secretos, y un evento de prueba enviado desde Stripe devuelve 200. (Eventos reales entregados con `pending_webhooks=0`; firma falsa rechazada con 400.)
- [x] T4 `python3 -m unittest discover -s tests` está en verde, salvo fallos previos documentados. (Solo falla `test_site_navigation_i18n`, ya fallaba en `main`.)
- [x] T5 La previsualización (`build_formacion.py --preview`) está revisada en escritorio y móvil con la URL real `/exec`. (2026-11-13.)

## Seguridad

- [x] X1 La cuenta de Google y la de Stripe tienen la verificación en dos pasos activa. (Comprobado el 2026-11-13: Google, activa desde el 27-11-2024; Stripe, app de autenticación desde el 18-10-2024.)
- [x] X2 Ningún secreto está en el repositorio (`tests/test_billing.py` en verde) y el proyecto de Apps Script no tiene otros editores. (Comprobado el 2026-11-13: proyecto «Private only to me».)
- [x] X3 Está probado el procedimiento de reversión: quitar `BILLING_CHECKOUT_ENABLED` cierra la contratación. (2026-11-13: respuesta `not_available`.)

## Compra controlada (en real, con la contratación aún cerrada al público)

- [~] R1 Compra real de 148 € con tarjeta propia (activando `BILLING_CHECKOUT_ENABLED` solo durante la prueba), con 4 clases concedidas. Dispensado por Luis en cuanto al importe: la compra real fue de **0,50 €**, no de 148 €, con un precio temporal (archivado) y una versión temporal del backend (revertida). Se concedieron 4 clases una sola vez y el duplicado de `invoice.paid` no concedió nada. El cobro de 148 € solo se ha probado en el sandbox.
- [~] R2 Llegaron el correo de acceso, la invitación de Calendar y los avisos a Luis (nueva suscripción y reserva). Dispensado por Luis en cuanto a la invitación: llegaron el correo de acceso y todos los avisos, pero no hubo invitación de Calendar porque el alumno de prueba era el propio organizador. La invitación a un tercero solo se ha probado en el sandbox y en los tests.
- [x] R3 Reserva, cambio y cancelación de una clase desde el área de alumno. (En real, el 2026-11-13: reserva, cambio de las 19:00 a las 22:00 y cancelación con recuperación del crédito.)
- [x] R4 Cancelación desde el portal: tus clases se conservan y llegan los avisos.
- [x] R5 Reembolso de la compra en Stripe: queda registrado e incidencia abierta; anulación de sus clases con un ajuste. (Reembolso de 0,50 € registrado e incidencia abierta; los 4 créditos anulados con ajustes `anular` en estado `hecho`.)

## Autorización final

- [x] A1 Luis autoriza el lanzamiento público tras revisar todo lo anterior. («Tienes mi autorización para ejecutar el lanzamiento completo», Misión 06; reiterada tras revisar este checklist el 2026-11-13.)

Autorizado por: Luis Carlos Guinea Moctezuma (autorización escrita de la Misión 06) Fecha: 2026-11-13
