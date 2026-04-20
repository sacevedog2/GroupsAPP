# GroupsApp - Messaging Service

Primer microservicio de **GroupsApp** enfocado en mensajeria distribuida tipo Telegram:

- Mensajes 1-n (`group` y `channel`) y 1-1 (`direct`).
- Archivos e imagenes.
- Estado de entrega y lectura (doble check).
- Persistencia de historial.
- Publicacion de eventos para desacople.
- Stream interno por gRPC para otros microservicios.

## Arquitectura del servicio

- **REST (FastAPI)**: interfaz externa para clientes/API Gateway.
- **gRPC streaming**: canal interno para que otros servicios consuman eventos de mensajeria en tiempo real.
- **MOM (RabbitMQ)**: publicacion de eventos de dominio (`message.created`, `receipt.updated`, `attachment.uploaded`).
- **BD SQL (SQLite/PostgreSQL)**: almacenamiento persistente de mensajes, adjuntos y receipts.

> Nota: Para desarrollo local el default es SQLite. En produccion se recomienda PostgreSQL particionado por `scope_id` y/o fecha.

## Endpoints REST principales

- `POST /v1/attachments`: subir archivo/imagen.
- `GET /v1/attachments/{attachment_id}`: metadatos.
- `GET /v1/attachments/{attachment_id}/content`: descargar/visualizar archivo.
- `POST /v1/messages`: enviar mensaje.
- `GET /v1/messages`: listar historial por `scope_type + scope_id`.
- `GET /v1/messages/{message_id}`: detalle.
- `POST /v1/messages/{message_id}/receipts`: actualizar estado (`delivered` o `read`).
- `GET /healthz` y `GET /readyz`.

## Contrato gRPC interno

Archivo proto: `app/grpc/proto/messaging.proto`

Servicio:

- `MessagingInternal.StreamEvents(EventSubscriptionRequest) returns (stream MessagingEvent)`

Permite a otros microservicios (notificaciones, analytics, presencia, etc.) suscribirse en tiempo real.

## Ejecutar local

1. Crear entorno e instalar dependencias:

```bash
python -m venv .venv
. .venv/Scripts/Activate.ps1
pip install -r requirements.txt
```

2. Configurar variables:

```bash
copy .env.example .env
```

3. Iniciar servicio:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

4. Probar docs:

- `http://localhost:8080/docs`

## Ejemplos rapidos de uso

Subir un archivo:

```bash
curl -X POST "http://localhost:8080/v1/attachments" \
  -F "uploader_id=user-1" \
  -F "scope_type=group" \
  -F "scope_id=group-123" \
  -F "file=@./foto.png"
```

Enviar mensaje con doble check:

```bash
curl -X POST "http://localhost:8080/v1/messages" \
  -H "Content-Type: application/json" \
  -d '{
    "sender_id":"user-1",
    "scope_type":"group",
    "scope_id":"group-123",
    "body":"Hola equipo",
    "participant_ids":["user-2","user-3"]
  }'
```

Marcar como entregado/leido:

```bash
curl -X POST "http://localhost:8080/v1/messages/<message_id>/receipts" \
  -H "Content-Type: application/json" \
  -d '{"user_id":"user-2","status":"delivered"}'
```

## Integracion con la plataforma distribuida

Este servicio queda listo para integrarse con:

- `auth-service`: validar identidad/JWT.
- `groups-service`: validar membresias, canales y permisos.
- `presence-service`: online/offline y heartbeats.
- `media-service` o S3: almacenamiento distribuido de archivos.

## Roadmap recomendado siguiente

1. Validacion fuerte de membresia/permisos via gRPC con `groups-service`.
2. Outbox pattern para garantizar entrega exacta de eventos.
3. Sharding/particionamiento de mensajes por grupo/canal.
4. Despliegue en Kubernetes (EKS) con HPA + Ingress ALB.
5. Observabilidad: OpenTelemetry + Prometheus + Loki/CloudWatch.

## Kubernetes (EKS)

Manifiestos iniciales en `k8s/`:

- `messaging-configmap.yaml`
- `messaging-secrets.template.yaml`
- `messaging-pvc.yaml`
- `messaging-deployment.yaml`
- `messaging-service.yaml`
- `messaging-hpa.yaml`
- `messaging-ingress-alb.yaml`

Diseno tecnico detallado: `docs/messaging-service-design.md`
