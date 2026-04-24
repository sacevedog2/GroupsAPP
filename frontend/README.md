# Frontend - GroupsApp

Frontend minimalista en tema oscuro para mensajeria directa y grupal:

- registro solo con correo y contrasena
- `user_id` generado automaticamente por backend
- inbox combinado con conversaciones directas y grupos
- inicio de conversaciones escribiendo solo el `user_id` de la otra persona
- creacion de grupos con miembros desde el frontend
- envio de archivos adjuntos en mensajes directos y grupales
- previsualizacion inline de imagenes y descarga de documentos
- ajustes tecnicos escondidos en un panel aparte

## Ejecutar

Desde la raiz del repo:

```powershell
cd frontend
python -m http.server 3000
```

Abre:

- `http://localhost:3000`

## Requisitos

1. Backend levantado por Docker Compose.
2. Puertos activos:
   - Auth: `http://localhost:8082`
   - Messaging: `http://localhost:8080`
   - Groups: `http://localhost:8081`
   - Notifications: `http://localhost:8083`

## Flujo sugerido

1. Crear cuenta solo con correo y contrasena.
2. Guardar tu `@user_id` generado automaticamente.
3. Iniciar sesion.
4. Escribir el `user_id` de otra persona en `Nuevo chat`.
5. O crear un grupo indicando nombre, descripcion y miembros.
6. Enviar mensajes, imagenes o documentos y revisar la bandeja de entrada.
