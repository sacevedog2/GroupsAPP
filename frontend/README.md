# Frontend - GroupsApp

- registro solo con correo y contraseña
- `user_id` generado automáticamente por backend
- inbox combinado con conversaciones directas y grupos
- inicio de conversaciones escribiendo solo el `user_id` de la otra persona
- creación de grupos con miembros desde el frontend
- envío de archivos adjuntos en mensajes directos y grupales
- previsualización inline de imágenes y descarga de documentos
- ajustes técnicos escondidos en un panel aparte

## Ejecutar

Desde la raíz del repo:

```powershell
docker compose up --build
```

O solo el frontend:

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

1. Crear cuenta solo con correo y contraseña.
2. Guardar tu `@user_id` generado automáticamente.
3. Iniciar sesión.
4. Escribir el `user_id` de otra persona en `Nuevo chat`.
5. O crear un grupo indicando nombre, descripción y miembros.
6. Enviar mensajes, imágenes o documentos y revisar la bandeja de entrada.
