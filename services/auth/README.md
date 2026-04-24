# GroupsApp - Auth Service

Microservicio para autenticacion y usuarios de GroupsApp.

- Registra usuarios con correo y contrasena.
- Genera y valida tokens Bearer.
- Expone perfiles publicos y presencia online/offline.

## Endpoints

- `POST /v1/auth/register`
- `POST /v1/auth/login`
- `GET /v1/auth/me`
- `GET /v1/auth/users/{user_id}`
- `POST /v1/auth/introspect`
- `POST /v1/auth/presence`
- `GET /healthz`
- `GET /readyz`

## Desarrollo

En Docker Compose el servicio queda en:

- `http://localhost:8082`
