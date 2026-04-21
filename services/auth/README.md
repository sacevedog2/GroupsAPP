# GroupsApp - Auth Service

Microservicio de autenticacion para **GroupsApp** que cubre el primer requisito funcional:

- Registro de usuarios.
- `user_id` unico (nombre de usuario) para agregar/interactuar con otros usuarios.
- Login por credenciales.
- Emision/validacion de token de acceso.
- Publicacion de eventos de autenticacion.

## Arquitectura del servicio

- **REST (FastAPI)**: interfaz externa para clientes/API Gateway.
- **gRPC interno**: validacion de token y consulta de usuario para otros servicios.
- **MOM (RabbitMQ)**: publicacion de eventos de dominio (`user.registered`, `user.logged_in`).
- **BD SQL (PostgreSQL)**: persistencia de usuarios.

## Endpoints REST principales

- `POST /v1/auth/register`: crea usuario y retorna token.
- `POST /v1/auth/login`: autentica usuario y retorna token.
- `GET /v1/auth/me`: perfil autenticado (Bearer token).
- `POST /v1/auth/introspect`: valida token recibido por Bearer.
- `GET /healthz` y `GET /readyz`.

## Contrato gRPC interno

Archivo proto: `app/grpc/proto/auth.proto`

Servicio:

- `AuthInternal.ValidateToken(TokenValidationRequest) returns (TokenValidationResponse)`
- `AuthInternal.GetUser(UserLookupRequest) returns (UserProfile)`
- `AuthInternal.StreamEvents(EventSubscriptionRequest) returns (stream AuthEvent)`

## Ejecutar local

1. Crear entorno e instalar dependencias:

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
```

2. Configurar variables:

```bash
cp .env.example .env
```

3. Levantar PostgreSQL + RabbitMQ + auth:

```bash
docker compose -f docker-compose.auth.yml up --build
```

4. Si quieres correr solo la API local (sin Docker para `auth`), usa:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8081
```

5. Probar docs:

- `http://localhost:8081/docs`

## Ejemplos rapidos

Registrar usuario:

```bash
curl -X POST "http://localhost:8081/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "ana.dev",
    "email": "ana@example.com",
    "password": "AnaPass2026",
    "display_name": "Ana"
  }'
```

Login:

```bash
curl -X POST "http://localhost:8081/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "identifier": "ana.dev",
    "password": "AnaPass2026"
  }'
```

Perfil autenticado:

```bash
curl -X GET "http://localhost:8081/v1/auth/me" \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## Integracion recomendada con la plataforma

- `messaging-service` debe llamar `ValidateToken` por gRPC para validar identidad.
- `groups-service` debe consultar `GetUser` por gRPC para resolver datos de usuario.
- Servicios de notificaciones/analytics pueden suscribirse a eventos de RabbitMQ.

## Kubernetes (EKS)

Manifiestos iniciales en `k8s/`:

- `auth-configmap.yaml`
- `auth-secrets.template.yaml`
- `auth-deployment.yaml`
- `auth-service.yaml`
- `auth-hpa.yaml`
- `auth-ingress-alb.yaml`

Diseno tecnico detallado: `docs/auth-service-design.md`
