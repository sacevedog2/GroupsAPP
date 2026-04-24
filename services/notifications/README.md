# GroupsApp - Notifications Service

Microservicio para notificaciones de GroupsApp.

- Consume eventos de RabbitMQ desde `groupsapp.events`.
- Crea notificaciones no leidas cuando llega `messaging.message.created`.
- Expone REST para que el frontend consulte y marque notificaciones como leidas.

## Endpoints

- `GET /v1/notifications?user_id=<id>&unread_only=true`
- `POST /v1/notifications/read?user_id=<id>`
- `POST /v1/notifications/read?user_id=<id>&scope_type=direct&scope_id=<scope>`
- `GET /healthz`
- `GET /readyz`

## Desarrollo

En Docker Compose el servicio queda en:

- `http://localhost:8083`
