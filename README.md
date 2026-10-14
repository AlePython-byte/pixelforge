# PixelForge

API pequeña (FastAPI + Pillow + PostgreSQL) para pruebas de carga en Arquitectura Computacional.

## Levantar

```powershell
docker compose up --build
```

Probar:

```powershell
curl.exe http://localhost:8000/salud
# {"ok":true}
```

Docs interactivas: http://localhost:8000/docs

## Límites de recursos del servicio `api`

Por defecto 1 CPU y 512 MB. Se cambian con variables de entorno:

```powershell
$env:API_CPUS="0.5"; $env:API_MEM_LIMIT="256m"; docker compose up --build
```

O en un archivo `.env` junto al `docker-compose.yml`:

```
API_CPUS=0.5
API_MEM_LIMIT=256m
```

Verificar los límites aplicados: `docker stats`.

## Detener

```powershell
docker compose down        # conserva datos
docker compose down -v     # borra también el volumen de la BD
```
