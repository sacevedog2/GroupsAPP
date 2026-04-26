# GroupsApp Kubernetes Deployment

Manifiestos de producción para EKS.

## Aplicar

```bash
kubectl apply -f k8s/
```

## Secrets requeridos

Ya se crean fuera del repo para no versionar credenciales:

- `auth-db-secret`
- `groups-db-secret`
- `messaging-db-secret`
- `notifications-db-secret`
- `rabbitmq-secret`
- `auth-jwt-secret`

Las URLs de PostgreSQL usan SSL:

- Servicios async (`auth`, `messaging`, `notifications`): `?ssl=require`
- Servicio sync (`groups`): `?sslmode=require`

## Entrada pública

El Ingress `groupsapp-alb` apunta al pod NGINX `groupsapp-api-gateway`.
El gateway enruta:

- `/api/auth/` -> `groupsapp-auth`
- `/api/groups/` -> `groupsapp-groups`
- `/api/messaging/` -> `groupsapp-messaging`
- `/api/notifications/` -> `groupsapp-notifications`
- `/` -> `groupsapp-frontend`
