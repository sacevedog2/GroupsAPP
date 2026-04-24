# GroupsApp - Messaging Service

Microservicio para mensajes directos, grupales y adjuntos de GroupsApp.

- Guarda mensajes, conversaciones directas, recibos de lectura y archivos adjuntos.
- Permite subir PDFs, documentos, imagenes y otros archivos para asociarlos a mensajes.
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

## Flujo de adjuntos

1. El cliente sube cada archivo con `POST /v1/attachments` usando `multipart/form-data`.
2. El servicio responde con los metadatos del archivo, incluido su `id`.
3. El cliente envia el mensaje con `POST /v1/messages` y agrega esos IDs en `attachment_ids`.
4. El destinatario descarga el archivo desde `GET /v1/attachments/{attachment_id}/content`.
