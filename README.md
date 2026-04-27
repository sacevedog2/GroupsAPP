# GroupsApp

Este es nuestro proyecto #1 de la materia de Sistemas Distribuidos para el 2026-1. Desarrollamos una aplicacion de mensajeria basada en grupos, canales y chats directos. La version de este repositorio implementa la arquitectura de microservicios; la version monolitica y parte del despliegue se encuentran en el otro repositorio adjunto en la entrega.

## Integrantes

- Sebastian Acevedo
- Sebastian Acosta
- Alejandro Carmona
- Miguel A. Gomez

## Funcionalidades

- Registro, inicio de sesion y autenticacion con JWT.
- Creacion y administracion de grupos.
- Canales dentro de grupos.
- Mensajes directos con solicitud de aceptacion.
- Mensajeria en grupos/canales.
- Notificaciones.
- Detalles de grupos, miembros y estado de usuarios.

## Tecnologias

- Frontend: HTML, CSS, JavaScript y NGINX.
- Backend: Python, FastAPI y gRPC.
- Bases de datos: PostgreSQL en local/produccion segun servicio.
- Mensajeria asincrona: RabbitMQ.
- Contenedores: Docker y Docker Compose.
- Despliegue: Kubernetes en Amazon EKS, ALB, ECR y RDS.

## Estructura

```text
frontend/              Interfaz web
services/auth/         Autenticacion y usuarios
services/groups/       Grupos, miembros y canales
services/messaging/    Mensajes, chats y adjuntos
services/notifications/ Notificaciones
k8s/                   Manifiestos para EKS
docker-compose.yml     Ejecucion local
```

## Probar en local

Requisitos: Docker y Docker Compose.

```bash
docker compose up --build
```

Luego abre:

```text
http://localhost:3000
```

Servicios principales en local:

- Frontend: `http://localhost:3000`
- Messaging: `http://localhost:8080`
- Groups: `http://localhost:8081`
- Auth: `http://localhost:8082`
- Notifications: `http://localhost:8083`
- RabbitMQ UI: `http://localhost:15672`

Para detener:

```bash
docker compose down
```

## Despliegue

Los manifiestos de Kubernetes estan en `k8s/`. La aplicacion esta preparada para EKS con:

- 2 replicas en los microservicios y frontend/gateway.
- NGINX como API Gateway interno.
- ALB como entrada publica.
- Secrets de Kubernetes para credenciales.
- PostgreSQL en RDS con SSL.
- Imagenes publicadas en Amazon ECR.

Aplicar manifiestos:

```bash
kubectl apply -f k8s/
```
