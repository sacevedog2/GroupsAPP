# Diseno tecnico - Messaging Service (GroupsApp)

## Responsabilidad del servicio

Este servicio es el dueno de:

- Mensajes en `group`, `channel` y `direct`.
- Adjuntos (archivo/imagen/video como archivo).
- Estado por usuario (`sent`, `delivered`, `read`).
- Historial persistente por `scope`.
- Emision de eventos para desacople.

## Modelo de datos

- `messages`: mensaje principal.
- `attachments`: metadatos de archivo en storage.
- `message_attachments`: relacion N:M.
- `message_receipts`: estado por usuario y mensaje (doble check).

Clave de particion recomendada en PostgreSQL/Citus:

- `scope_id` (+ fecha para historial masivo).

## Integracion distribuida

### Entrada (externa)

- REST via API Gateway/Ingress ALB.

### Salida (interna)

- RabbitMQ topic exchange `groupsapp.events`.
- gRPC streaming (`MessagingInternal.StreamEvents`).

## Eventos publicados

- `message.created`
- `receipt.updated`
- `attachment.uploaded`

Todos los eventos contienen:

- `id`, `event_type`, `scope_type`, `scope_id`, `created_at`, `payload`.

## Acoplamientos esperados con otros servicios

- `auth-service`: autenticacion/autorizacion JWT.
- `groups-service`: membresia/permisos de grupo/canal/subgrupo.
- `presence-service`: online/offline y push de cambios de estado.
- `notification-service`: push/email derivados de eventos.
- `media-service` o S3/EFS: almacenamiento distribuido de adjuntos.

## Riesgos tecnicos y mitigacion

- Orden de mensajes entre replicas:
  - Mitigar con IDs temporales + orden por `(created_at, id)`.
- Entrega de evento y persistencia:
  - Implementar outbox para consistencia transaccional.
- Crecimiento de historial:
  - Particionamiento + retencion/archivo por politica.
