# 01 · Decisiones comerciales

Estado a 13 de noviembre de 2026. «Cerrada» significa aprobada por Luis en la Misión 05 e implementada o preparada en
la rama `feat/formacion-suscripciones-stripe`. Nada de esto está publicado.

## Cerradas

| # | Decisión | Cómo queda en el sistema | Dónde |
|---|---|---|---|
| C1 | Plan semanal: 148 € cada 28 días, 4 clases individuales presenciales de 60 min | Precio `week × 4`, 14 800 céntimos, impuestos incluidos (pendiente de confirmación fiscal, ver P1) | `tools/stripe_setup.py` |
| C2 | Plan quincenal: 148 € cada 56 días, mismas 4 clases | Precio `week × 8` | ídem |
| C3 | Hasta 2 clases sin usar pasan al ciclo siguiente, con 30 días adicionales | `CARRY_MAX=2`, `CARRY_DAYS=30`; queda anotado al cerrar cada ciclo | `Billing.gs` `rollover_` |
| C4 | Se usan primero las clases con fecha límite más próxima | Asignación automática al reservar | `sortCredits_` |
| C5 | Las clases de recuperación no desplazan reservas ajenas | Solo se reserva tiempo libre; nunca se mueve ni cancela otra reserva | probado: `make_up_classes_never_displace_other_bookings` |
| C6 | Si Luis cancela, el alumno conserva la clase íntegra | Borrar el evento en Google Calendar devuelve la clase **sin fecha límite** y avisa al alumno | `classesMaintenance_` |
| C7 | Cambiar o cancelar sin penalización con ≥ 24 h | `STUDENT_CHANGE_HOURS=24` | `cancelClass_`, `moveClass_` |
| C8 | Fuera de plazo: información clara, sin penalización automática | El área explica las condiciones y ofrece escribir a Luis; ningún crédito se elimina por ello | `js/alumnos.js` |
| C9 | Ausencia sin aviso puede contar como clase realizada si se informó y aceptó; con excepciones justificadas | La clase cuenta como realizada 48 h después de terminar. Luis la devuelve con el ajuste `justificar`. **La regla solo debe anunciarse cuando las condiciones estén aprobadas (P3)** | `processAdjustments_` |
| C10 | La frecuencia define el calendario habitual, con flexibilidad para recuperar | Botón «Repetir esta hora cada semana / cada dos semanas»; las 4 clases del ciclo se pueden mover libremente con disponibilidad | `js/alumnos.js` |
| C11 | Cambio de plan solo al terminar el ciclo pagado, sin prorrateo | Programación de Stripe con `proration_behavior=none`. **Verificado con Test Clocks**: no se cobra nada al pedirlo y el día de la renovación hay una sola factura de 148 € | `changePlan_` |
| C12 | El alumno detiene las renovaciones desde el Customer Portal; las clases pagadas se conservan | Portal con cancelación al final del periodo. Verificado también con un cambio de plan pendiente: Stripe lo anula y las clases se conservan | `stripe_setup.py` |
| C13 | Reembolsos en revisión manual, sin denegaciones automáticas, registrados | Cada reembolso (parcial o total) queda en `movimientos` y abre una incidencia; las clases solo se anulan si Luis lo decide (`anular`) | `recordRefund_` |
| C14 | Máximo 3 cambios de hora por reserva, sin bloquear derechos | `MAX_RESCHEDULES=3` solo cuenta los cambios del alumno. Una clase cancelada por Luis vuelve como clase nueva, con sus 3 cambios | probado: `reschedule_limit_never_blocks_a_class_luis_cancelled` |
| C15 | `CREDIT_POLICY_ENFORCED` sigue desactivado | Las fechas límite se muestran como orientativas («Pensada para usar antes del…»); nadie pierde clases | propiedad sin definir |

## Pendientes (requieren intervención)

| # | Decisión | Quién | Opción recomendada y motivo |
|---|---|---|---|
| P1 | IVA y precio final | Gestor | Mantener 148 € como precio final, IVA incluido si lo hubiera. Si las clases tributan al 21 %, el ingreso neto sería 122,31 €: decidir si se mantiene o se sube el precio **antes** de publicar |
| P2 | Caducidad definitiva de clases (activar `CREDIT_POLICY_ENFORCED`) | Abogado → Luis | No activar hasta el informe jurídico. Mientras tanto, las clases vencidas siguen reservables y aparecen en el panel |
| P3 | Texto de la regla de ausencias y su aceptación | Abogado | Incluirla en las condiciones aceptadas en el pago (casilla actual) y en el recordatorio de 24 h |
| P4 | Si una clase puede programarse después de la fecha límite de su crédito | Luis tras P2 | Permitirlo si se reservó antes de que venciera: es lo más defendible ante un consumidor |
| P5 | Clase cancelada por el alumno ya terminado su ciclo | Luis | Mantener lo actual (cuenta como trasladada, 30 días). Es favorable al alumno y sencillo |
| P6 | Datos del prestador (nombre fiscal, NIF, domicilio profesional, teléfono) | Luis | Imprescindibles para las condiciones, Stripe y las facturas. No se han inventado: figuran como `[PENDIENTE]` |
| P7 | Dirección de las clases (`CLASS_LOCATION`) y franjas propias para clases (`CLASS_AVAILABILITY_CALENDAR_ID`) | Luis | Crear un calendario «Clases» con las franjas que quieres dar, separado de la agenda general |
| P8 | Menores de edad | Abogado → Luis | Contrata el progenitor o tutor; el alumno menor no tiene acceso propio. Añadir casilla «Contrato como progenitor/tutor de un menor» si se aprueba |
| P9 | Cuenta propia de Stripe | Luis | Ver `07-STRIPE-CUENTA-REAL.md` |
| P10 | Política de reembolso ante un desistimiento con clases ya recibidas | Abogado + gestor | Reembolso proporcional: 37 € por clase recibida descontada de los 148 € |
