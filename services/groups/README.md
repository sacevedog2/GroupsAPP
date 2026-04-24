# GroupsApp - Groups Service

Microservicio para grupos, miembros, canales y contactos de GroupsApp.

- Crea y lista grupos del usuario autenticado.
- Administra miembros y canales de cada grupo.
- Publica eventos en RabbitMQ desde `groupsapp.events`.

## Endpoints

- `GET /v1/groups/`
- `POST /v1/groups/`
- `GET /v1/groups/{group_id}`
- `POST /v1/groups/{group_id}/members`
- `GET /v1/groups/{group_id}/members`
- `POST /v1/groups/{group_id}/channels`
- `POST /v1/contacts/`
- `GET /v1/contacts/`
- `GET /healthz`
- `GET /readyz`

## Desarrollo

En Docker Compose el servicio queda en:

- `http://localhost:8081`
