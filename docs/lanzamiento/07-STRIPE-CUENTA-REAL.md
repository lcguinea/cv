# 07 · Cuenta real de Stripe para la actividad musical

## Por qué una cuenta nueva

La única cuenta actual es la de **Santo Chilaquil**. Según la documentación de Stripe («Multiple separate accounts»),
cada negocio con distinto titular o NIF debe tener **su propia cuenta**: el titular fiscal, el descriptor del extracto
bancario y la información pública van ligados a la cuenta. Cobrar las clases desde la cuenta del restaurante haría que
el alumno viera «Santo Chilaquil» en su extracto y en sus recibos.

No se reutiliza nada del restaurante: ni productos, ni clientes, ni claves, ni el sandbox de pruebas actual (que
cuelga de la organización del restaurante y solo ha servido para el desarrollo).

## Pasos (los hace Luis; no se ha creado nada)

1. Entra en dashboard.stripe.com con tu usuario.
2. Abre el selector de cuenta (arriba a la izquierda) → **New account** (Nueva cuenta).
   - Nombre: p. ej. «Luis Guinea · Clases de música».
   - País: **España**. No se puede cambiar después de activar la cuenta.
   - No copies la configuración de otra cuenta.
3. Activa la autenticación en dos pasos con llave de acceso (*passkey*) o llave de seguridad.
4. **Verificar el negocio** (*Activate payments*). Stripe pedirá, para una persona física o autónomo:

| Dato | Valor previsto | Estado |
|---|---|---|
| Tipo de negocio | Persona física / autónomo | Confirmar con el gestor |
| Nombre legal, fecha de nacimiento, dirección y teléfono | Los tuyos | **[PENDIENTE]** |
| NIF/DNI y documento de identidad para verificación | — | **[PENDIENTE]** |
| Sector / descripción | Clases particulares de música (servicios educativos) | Propuesto |
| Web | https://luisguinea.com/formacion/ | Propuesto |
| Cuenta bancaria (IBAN) para las transferencias | La que use la actividad | **[PENDIENTE]** |
| Información pública: nombre comercial, correo y teléfono de soporte | «Luis Guinea» · correo de contacto | **[PENDIENTE]** |
| Descriptor del extracto | `LUISGUINEA CLASES` | Propuesto |

5. Aceptarás el contrato de servicios de Stripe al activar. **Eso solo lo haces tú.**
6. **Billing → Configuración de suscripciones y correos:**
   - Activar recibos por correo de pagos correctos y de reembolsos.
   - Correos de pago fallido y reintentos inteligentes (*Smart Retries*); tras el último reintento, «cancelar la
     suscripción» o «dejar impagada» (decisión pendiente, ver condiciones §13).
   - **No** activar el correo de cancelación de Stripe: lo envía el sistema.
7. **Facturas:** datos fiscales, numeración y pie con la mención fiscal **solo tras la respuesta del gestor**. Stripe
   Tax queda desactivado.
8. **Public details:** URL de las condiciones y de la privacidad, cuando estén aprobadas y publicadas.

## Configuración técnica (la hace Claude con tu autorización, tras los pasos anteriores)

1. Primero en el **sandbox de la nueva cuenta**:
   - `stripe login` eligiendo la cuenta nueva;
   - `python3 tools/stripe_setup.py`;
   - repetir `tools/stripe_testclock_e2e.py`.
2. En modo real: el mismo script, revisado, con su bloqueo de `--live` levantado solo para esa ejecución. Crea el
   producto, los 2 precios y el portal sin duplicados.
3. **Clave restringida** (*Developers → API keys → Create restricted key*), con estos permisos:
   - Lectura: Customers, Subscriptions, Invoices, Charges, Events, Prices, Products y Subscription schedules.
   - Escritura: Checkout Sessions, Customer portal y Subscription schedules (cambio de plan).
   - Todo lo demás, sin acceso.
4. **Webhook** (*Developers → Webhooks → Add endpoint*):
   - URL: `https://<worker>.workers.dev/stripe/webhook`.
   - Versión de API: la de la cuenta (el backend fija la suya en cada llamada).
   - Eventos: los 12 listados en `apps-script/BILLING.md`.

## ¿Funciona el sistema con la cuenta nueva?

Sí, sin cambios de código. Todo lo específico de la cuenta va en propiedades:
- `STRIPE_SECRET_KEY` y `STRIPE_MODE`;
- `STRIPE_PRICE_WEEKLY`, `STRIPE_PRICE_BIWEEKLY` y `STRIPE_PORTAL_CONFIG`;
- el secreto `whsec_…` del Worker.

El backend se niega a arrancar si la clave no coincide con el modo, y la conciliación ignora cualquier producto que no
sea uno de los dos precios configurados. Se ha comprobado en el sandbox actual; en la cuenta nueva se comprobará con el
paso 1 de esta sección.
