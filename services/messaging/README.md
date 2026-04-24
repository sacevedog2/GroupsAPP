# GroupsApp - Messaging Service

Microservicio para mensajes directos, grupales y adjuntos de GroupsApp.

- Guarda mensajes, conversaciones directas, recibos de lectura y archivos adjuntos.
- Publica eventos en RabbitMQ desde `groupsapp.events`.
- Expone REST para que el frontend envie mensajes, consulte historial y marque recibos.

## Endpoints

- `POST /v1/messages`
- `GET /v1/messages?scope_type=<type>&scope_id=<id>`
- `GET /v1/messages/{message_id}`
- `POST /v1/messages/{message_id}/receipts`
- `POST /v1/direct-conversations`
- `GET /v1/direct-conversations?user_id=<id>`
- `POST /v1/attachments`
- `GET /v1/attachments/{attachment_id}`
- `GET /v1/attachments/{attachment_id}/content`
- `GET /healthz`
- `GET /readyz`

## Desarrollo

En Docker Compose el servicio queda en:

- `http://localhost:8080`
