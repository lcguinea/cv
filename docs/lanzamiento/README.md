# Lanzamiento comercial de Formación Musical (Misión 05)

**Estado: técnicamente preparado para producción. NO autorizado para publicar.** Nada está desplegado, publicado ni
cobrado en real. La contratación está bloqueada por tres cierres independientes:
1. `tools/launch_gate.py`: la web no genera los planes sin el checklist completo y firmado.
2. `TERMS_APPROVED_VERSION`: Checkout no se abre sin las condiciones aprobadas.
3. `BILLING_CHECKOUT_ENABLED`: interruptor manual del backend.

| # | Entregable | Archivo |
|---|---|---|
| 1 | Decisiones comerciales cerradas | [01-DECISIONES.md](01-DECISIONES.md) (sección «Cerradas») |
| 2 | Decisiones pendientes | [01-DECISIONES.md](01-DECISIONES.md) (sección «Pendientes») |
| 3 | Consulta para el gestor | [02-CONSULTA-GESTOR.md](02-CONSULTA-GESTOR.md) |
| 4 | Borrador de condiciones generales (revisión jurídica) | [03-CONDICIONES-GENERALES-BORRADOR.md](03-CONDICIONES-GENERALES-BORRADOR.md) |
| 5 | Propuesta de política de privacidad | [04-PRIVACIDAD-PROPUESTA.md](04-PRIVACIDAD-PROPUESTA.md) |
| 6 | Auditoría de seguridad | [05-AUDITORIA-SEGURIDAD.md](05-AUDITORIA-SEGURIDAD.md) |
| 7 | Pruebas adicionales y resultados | [06-PRUEBAS.md](06-PRUEBAS.md) |
| 8 | Configuración de la cuenta real de Stripe | [07-STRIPE-CUENTA-REAL.md](07-STRIPE-CUENTA-REAL.md) |
| 9 | Checklist de lanzamiento (bloqueante) | [CHECKLIST-LANZAMIENTO.md](CHECKLIST-LANZAMIENTO.md) |
| 10 | Plan de despliegue y reversión | [08-DESPLIEGUE-Y-REVERSION.md](08-DESPLIEGUE-Y-REVERSION.md) |

Referencia técnica: [`apps-script/BILLING.md`](../../apps-script/BILLING.md). Misión anterior:
`INFORME-MISION-04-STRIPE-BILLING-20261112.md`.

## Cambios técnicos de esta misión

- **Cambio de plan** semanal ↔ quincenal al renovar, sin prorrateo: se pide y se anula desde el área de alumno.
  Verificado en Stripe real. Además corrige un fallo que dejaba sin clases la factura de cambio de plan.
- **Reembolsos** parciales y totales registrados en el libro de movimientos, sin anular clases automáticamente.
- **Ajustes nuevos:** `justificar` (ausencia justificada: devuelve la clase) y `anonimizar` (supresión de datos
  personales).
- **Conciliación** que recorre también las suscripciones conocidas (verificado ante una caída real simulada).
- **Copia semanal** de la hoja.
- **Doble cierre de Checkout** y bloqueo de publicación por checklist.
- **Área de alumno:** cambio de plan, «Repetir esta hora cada semana / cada dos semanas», explicación con enlace de
  contacto cuando faltan menos de 24 h, y ausencias justificadas visibles.
