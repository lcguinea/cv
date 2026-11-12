# 04 · Propuesta de política de privacidad: contratación de clases

> **Propuesta para revisión jurídica. No publicar.** Complementa la información de privacidad actual del sitio
> (agenda y formularios). Datos marcados **[PENDIENTE]** a completar por el responsable.

## Responsable

Luis Carlos Guinea Moctezuma, NIF **[PENDIENTE]**, domicilio **[PENDIENTE]**, contacto lguinea@berklee.edu.

## Qué datos tratamos y para qué

| Finalidad | Datos | Base jurídica | Conservación |
|---|---|---|---|
| Contratar y prestar las clases (reservas, recordatorios, cambios) | Nombre, correo, fechas y horas de las clases, clases disponibles y usadas | Ejecución del contrato (art. 6.1.b RGPD) | Mientras dure la relación y, después, el tiempo de prescripción de acciones **[REVISAR]** |
| Cobro de la suscripción | Correo, nombre, país, NIF si se aporta; los datos de tarjeta los trata Stripe | Ejecución del contrato | Facturas: 6 años (art. 30 C. de Comercio) y 4 años a efectos fiscales **[REVISAR]** |
| Obligaciones fiscales y contables | Facturas, cobros, reembolsos | Obligación legal (art. 6.1.c) | Plazos legales anteriores |
| Acceso seguro al área privada | Correo, enlaces y sesiones cifrados (solo se guarda su huella) | Ejecución del contrato e interés legítimo en la seguridad | Enlaces: 72 h; sesiones: 30 días |
| Avisos del servicio (confirmación, recordatorio, cancelación) | Correo | Ejecución del contrato | Igual que la primera fila |

No se usan los datos para publicidad ni para decisiones automatizadas con efectos jurídicos. El sitio no usa cookies de
analítica ni de publicidad; el área privada guarda en el navegador solo el token de sesión (almacenamiento local),
necesario para el servicio.

## Menores

Si el alumno es menor de 14 años, los datos los facilita y gestiona su madre, padre o tutor legal (art. 7 LOPDGDD).
**[REVISAR]**

## Encargados y destinatarios

| Proveedor | Para qué | Ubicación y garantías |
|---|---|---|
| Stripe Payments Europe, Ltd. (Irlanda) | Pagos, suscripciones, facturas y portal de facturación | UE. Stripe actúa también como responsable independiente para sus fines de prevención del fraude y cumplimiento normativo. **[REVISAR: rol exacto según su DPA]** |
| Google Ireland Ltd. (Google Workspace / cuenta de Google) | Calendario de clases, correo de avisos, hoja de registro privada | UE/EE. UU.; cláusulas contractuales tipo y Marco de Privacidad de Datos UE-EE. UU. **[REVISAR]** |
| Cloudflare, Inc. | Reenvío seguro de los avisos técnicos de Stripe (no guarda datos personales; solo identificadores de eventos) | EE. UU.; DPA de Cloudflare y Marco de Privacidad de Datos **[REVISAR]** |
| GitHub, Inc. | Alojamiento de la web estática (registros técnicos de acceso) | EE. UU.; DPA de GitHub **[REVISAR]** |

## Derechos

Acceso, rectificación, supresión, oposición, limitación y portabilidad: escribiendo al correo de contacto. Derecho a
reclamar ante la Agencia Española de Protección de Datos (aepd.es). La supresión se ejecuta con el ajuste `anonimizar`
(borra nombre y correo del registro y cierra las sesiones) y borrando el cliente en Stripe, salvo los datos que deban
conservarse por obligación legal.

## Seguridad

Pagos en Stripe (PCI DSS); enlaces de acceso de un solo uso; tokens guardados solo como huella SHA-256; registro privado
con acceso exclusivo del responsable; copia de seguridad semanal privada.
