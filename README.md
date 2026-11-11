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

## Experimentos de carga (datos crudos del informe)

Con Docker Desktop encendido, desde la carpeta del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\medir.ps1
```

Corre todo (unos 30 minutos) y guarda en `carga/resultados/`:

| Experimento | Qué hace | Archivos |
| --- | --- | --- |
| `specs` | Especificaciones de la máquina física y de la VM de Docker | `especificaciones_maquina.txt` |
| `escalado` | 10 usuarios durante 4 min con 1, 2 y 4 CPU | `escalado_cpuN_*` |
| `rampa` | 10 → 25 → 50 → 100 usuarios con 1 CPU, hasta el quiebre | `rampa_cpu1_*` |
| `memoria` | `/subir` con 2 → 16 peticiones simultáneas hasta el OOM killer | `memoria_cpu1_512m_*` |

Por cada corrida quedan tres archivos: `*.json` (resumen de k6), `*_k6.csv` (cada petición) y `*_stats.csv` (`docker stats` cada ~2 s).

Para correr solo uno: `.\medir.ps1 -Solo rampa` (o `specs`, `escalado`, `memoria`).
