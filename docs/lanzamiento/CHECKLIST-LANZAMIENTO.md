# Checklist de lanzamiento: contratación de clases

> **Este archivo bloquea la publicación.** `tools/launch_gate.py` lo lee y `tools/build_formacion.py` se niega a
> generar la sección de planes con `SUBSCRIPTIONS["published"] = True` si queda alguna casilla sin marcar o falta la
> autorización final. Marca cada casilla (`[x]`) solo cuando la condición se haya cumplido **de verdad**, y anota la
> fecha. Además, el backend no abre Checkout sin `BILLING_CHECKOUT_ENABLED=true` y sin `TERMS_APPROVED_VERSION`.

## Legal

- [ ] L1 Un profesional jurídico ha revisado y aprobado las condiciones generales (03) y la política de privacidad (04).
- [ ] L2 Los datos del prestador están completos en las condiciones (nombre fiscal, NIF y domicilio) y no queda ningún `[PENDIENTE]`.
- [ ] L3 Las condiciones y la privacidad aprobadas están publicadas en luisguinea.com y enlazadas desde la sección de planes y desde Stripe (Public details).
- [ ] L4 Los textos de la web (sección de planes, área de alumno y correos) coinciden con las condiciones aprobadas.
- [ ] L5 La regla de ausencias y la de clases no utilizadas tienen la redacción aprobada. `CREDIT_POLICY_ENFORCED` solo se activa si el informe jurídico lo permite.
- [ ] L6 Está resuelto el tratamiento de los alumnos menores de edad.

## Fiscal

- [ ] F1 El gestor ha respondido a la consulta (02): alta, IAE, IVA por materia, facturas, VeriFactu y cobros anticipados.
- [ ] F2 El precio final (148 €) es correcto con el tratamiento fiscal confirmado.
- [ ] F3 Las facturas o recibos cumplen lo indicado por el gestor (emisor, numeración y mención fiscal).

## Stripe

- [ ] S1 La cuenta propia de la actividad musical está activada y verificada (07). No es la de Santo Chilaquil.
- [ ] S2 `tools/stripe_testclock_e2e.py` pasa en el sandbox de la cuenta nueva.
- [ ] S3 Están creados en real el producto, los 2 precios (14 800 EUR, `week` × 4 y × 8) y el portal (sin cambios de plan, cancelación al final del periodo), y `checkBillingSetup` dice `ok`.
- [ ] S4 La clave es restringida, con los permisos mínimos de 07, y solo está en Script Properties.
- [ ] S5 El webhook real apunta al Worker con los 12 eventos, y el secreto `whsec_` está en Cloudflare.
- [ ] S6 Recibos, Smart Retries y correos de pago fallido están configurados, y el correo de cancelación de Stripe está desactivado.

## Técnico

- [ ] T1 La hoja privada «Clases luisguinea.com» está creada, sin compartir y con la pestaña `movimientos` protegida.
- [ ] T2 El Apps Script está actualizado: versión nueva de la implementación, permisos aceptados, `checkBillingSetup` en `ok`, `installBillingTriggers` ejecutado y la agenda general probada después.
- [ ] T3 El Worker está desplegado con `STRIPE_MODE=live`, `APPS_SCRIPT_URL` y los dos secretos, y un evento de prueba enviado desde Stripe devuelve 200.
- [ ] T4 `python3 -m unittest discover -s tests` está en verde, salvo fallos previos documentados.
- [ ] T5 La previsualización (`build_formacion.py --preview`) está revisada en escritorio y móvil con la URL real `/exec`.

## Seguridad

- [ ] X1 La cuenta de Google y la de Stripe tienen la verificación en dos pasos activa.
- [ ] X2 Ningún secreto está en el repositorio (`tests/test_billing.py` en verde) y el proyecto de Apps Script no tiene otros editores.
- [ ] X3 Está probado el procedimiento de reversión: quitar `BILLING_CHECKOUT_ENABLED` cierra la contratación.

## Compra controlada (en real, con la contratación aún cerrada al público)

- [ ] R1 Compra real de 148 € con tarjeta propia (activando `BILLING_CHECKOUT_ENABLED` solo durante la prueba), con 4 clases concedidas.
- [ ] R2 Llegaron el correo de acceso, la invitación de Calendar y los avisos a Luis (nueva suscripción y reserva).
- [ ] R3 Reserva, cambio y cancelación de una clase desde el área de alumno.
- [ ] R4 Cancelación desde el portal: tus clases se conservan y llegan los avisos.
- [ ] R5 Reembolso de la compra en Stripe: queda registrado e incidencia abierta; anulación de sus clases con un ajuste.

## Autorización final

- [ ] A1 Luis autoriza el lanzamiento público tras revisar todo lo anterior.

Autorizado por: ______________________ Fecha: __________
