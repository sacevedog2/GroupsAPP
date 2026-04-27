# GroupsApp Kubernetes Deployment

Manifiestos de produccion para EKS con EKS Auto Mode.

## Aplicar

```bash
kubectl apply -f k8s/
```

## Secrets requeridos

Se crean fuera del repo para no versionar credenciales:

- `auth-db-secret`
- `groups-db-secret`
- `messaging-db-secret`
- `notifications-db-secret`
- `rabbitmq-secret`
- `auth-jwt-secret`

Las URLs de PostgreSQL usan SSL:

- Servicios async (`auth`, `messaging`, `notifications`): `?ssl=require`
- Servicio sync (`groups`): `?sslmode=require`

## Entrada publica

El Ingress `groupsapp-alb` usa `IngressClassParams` de EKS Auto Mode y crea un ALB publico.
El ALB apunta al servicio interno `groupsapp-api-gateway`, donde corre NGINX.

El gateway enruta:

- `/api/auth/` -> `groupsapp-auth`
- `/api/groups/` -> `groupsapp-groups`
- `/api/messaging/` -> `groupsapp-messaging`
- `/api/notifications/` -> `groupsapp-notifications`
- `/` -> `groupsapp-frontend`

## Replicas

Los servicios de aplicacion quedan con 2 replicas:

- `groupsapp-auth`
- `groupsapp-groups`
- `groupsapp-messaging`
- `groupsapp-notifications`
- `groupsapp-frontend`
- `groupsapp-api-gateway`

`groupsapp-rabbitmq` queda con 1 replica porque no esta configurado como cluster StatefulSet.
