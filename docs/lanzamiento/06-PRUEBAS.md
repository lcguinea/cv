# 06 · Pruebas adicionales y resultados

Tres niveles, que **no** deben confundirse:

- **A. Automáticas (simuladas):** el código real de `Code.gs` y `Billing.gs` con Google y Stripe simulados
  (`tests/support/billing_scenarios.js`). Rápidas y repetibles, pero no prueban a Stripe ni a Google.
- **B. Integración real en modo de pruebas:** el mismo código en local contra la **API real de Stripe**, en el sandbox
  «Luis Guinea Formacion (pruebas)», con webhooks reales firmados y Test Clocks. Google sigue simulado.
- **C. Producción:** **ninguna**. No hay nada desplegado ni se ha cobrado nada real.

## A. Automáticas: 45 de 45

`python3 -m unittest tests/test_billing.py` incluye los escenarios, 9 pruebas del relé y comprobaciones estáticas.

| Pedido en la misión | Escenario |
|---|---|
| Traslado de hasta dos clases | `one_or_two_unused_credits_carry_over_for_thirty_days`, `at_most_two_credits_carry_over` |
| Vencimiento de recuperación | `recovery_deadline_with_policy_on_blocks_booking_and_luis_can_extend` (con la política activada solo en la prueba) |
| Cancelación con clases pendientes | `cancellation_at_period_end_keeps_paid_credits_and_stops_renewals`, `immediate_cancellation_keeps_paid_credits_bookable` |
| Reprogramación fuera de plazo | `changes_inside_twenty_four_hours_are_refused` |
| Ausencias justificadas | `justified_absence_gives_the_class_back` |
| Cambio de plan al renovar | `plan_change_weekly_to_biweekly_happens_at_renewal_without_extra_charges`, `plan_change_biweekly_to_weekly_and_undo`, `plan_change_is_refused_when_cancelling_or_inactive` |
| Reembolso parcial y total | `partial_and_total_refunds_are_recorded_and_change_no_credit` |
| Clases canceladas por el profesor | `teacher_cancellation_in_calendar_restores_the_class_without_deadline`, `reschedule_limit_never_blocks_a_class_luis_cancelled` |
| Imposibilidad de ofrecer horarios | `no_available_times_is_reported_and_luis_can_extend_or_grant` |
| Recuperación de eventos perdidos | `lost_webhooks_are_recovered_by_the_hourly_reconciliation`, `temporary_backend_failure_is_retried_without_side_effects` |
| Acceso tras cancelar | `student_keeps_access_and_classes_after_the_subscription_ends` |
| Otros | `make_up_classes_never_displace_other_bookings`, `anonymising_a_student_keeps_the_ledger`, `checkout_stays_closed_until_the_terms_are_approved` |

**Prueba de que las pruebas detectan fallos:** al quitar la corrección de las facturas de cambio de plan, los dos
escenarios de cambio de plan fallan (el alumno se quedaba sin sus clases).

## B. Integración real con Stripe en modo de pruebas

Script: `tools/stripe_testclock_e2e.py` (requiere `tools/billing_dev_server.js` y `stripe listen`). Los relojes de
prueba se borran al terminar.

| Escenario | Resultado observado |
|---|---|
| Renovación semanal (+28 días) | 8 clases; dos periodos de exactamente 28,0 días |
| Reenvío del webhook de la renovación | Siguen 8 |
| Renovación quincenal | 4 clases el día 28, 8 el día 56; periodos de 56,0 días |
| Renovación con tarjeta que falla | Siguen 4, suscripción `past_due`, un aviso a Luis |
| **Cambio de plan desde el área** (semanal → quincenal) | Ninguna factura nueva al pedirlo (vista previa de Stripe: 148 €); el día 28, **una** factura de 148 € (`subscription_update`, sin líneas de prorrateo); nuevo ciclo de 56 días con 4 clases; 0 incidencias |
| **Reembolso parcial (37 €) y total** | Registrados `[3700, parcial]` y `[14800, total]`; ninguna clase anulada |
| **Caída del backend durante una renovación** | 4 clases durante la caída, 8 tras la conciliación horaria. Primero falló: la conciliación no veía suscripciones con Test Clock; ahora recorre también las ya conocidas |
| **Cancelación en el portal con cambio de plan pendiente** (Chrome) | Permitida; Stripe libera la programación; el área muestra «termina el 10 de diciembre», sin cambio pendiente y con las 4 clases |
| Interfaz de cambio de plan y repetición semanal (Chrome) | Confirmación en lenguaje claro; «Repetir esta hora cada semana» elige 16/11, 23/11, 30/11 y 7/12 a las 10:00 |
| Misión 04 (repetidas) | Checkout semanal, rechazo de tarjeta, alta, reservas, cambios, portal, navegación continua y vista móvil |

## Sin verificar (requiere producción o Google real)

- `MailApp`, `Calendar` y `LockService` reales, el activador horario, la copia semanal (`Spreadsheet.copy`) y los
  permisos reales: solo se pueden comprobar con el despliegue, en el paso de compra controlada del checklist.
- El Worker en Cloudflare: probado en Node con el mismo código, no desplegado.
- Cuenta real de Stripe y facturas reales.
