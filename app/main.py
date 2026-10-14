import io
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse
from PIL import Image, ImageFilter
from sqlalchemy import select
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.orm import Session

from app.db import Registro, engine, iniciar_db, registrar


@asynccontextmanager
async def lifespan(_: FastAPI):
    iniciar_db()
    yield


app = FastAPI(title="PixelForge", lifespan=lifespan)

# Anchos objetivo del redimensionado y pasadas de blur (más pasadas = más CPU).
TAMANOS = (1920, 1024, 256)
PASADAS_BLUR = 3
RADIO_BLUR = 25


@app.get("/salud")
def salud():
    return {"ok": True}


# --- /procesar --------------------------------------------------------------
# Componente estresado: CPU.
# Redimensionar con LANCZOS y aplicar GaussianBlur son operaciones de cálculo
# puro sobre cada píxel; no esperan disco ni red. La imagen se decodifica una
# sola vez y por cada tamaño se hace resize + varias pasadas de blur, así que
# el tiempo crece con los píxeles y con las peticiones concurrentes hasta
# saturar los núcleos asignados (cpus). Es "def" y no "async def" para que
# FastAPI lo ejecute en un hilo y varias peticiones usen varios núcleos
# (Pillow libera el GIL en estas operaciones).
@app.post("/procesar")
def procesar(archivo: UploadFile = File(...)):
    t0 = time.perf_counter()
    img = Image.open(archivo.file).convert("RGB")
    ancho, alto = img.size

    salidas = []
    for objetivo in TAMANOS:
        nuevo_alto = max(1, round(alto * objetivo / ancho))
        copia = img.resize((objetivo, nuevo_alto), Image.LANCZOS)
        for _ in range(PASADAS_BLUR):
            copia = copia.filter(ImageFilter.GaussianBlur(RADIO_BLUR))
        salidas.append({"ancho": objetivo, "alto": nuevo_alto})

    ms = round((time.perf_counter() - t0) * 1000, 1)
    guardado = registrar("procesar", archivo.filename or "", ancho, alto, ms)
    return {
        "endpoint": "procesar",
        "original": {"ancho": ancho, "alto": alto},
        "salidas": salidas,
        "ms": ms,
        "registrado": guardado,
    }


# --- /subir -----------------------------------------------------------------
# Componente estresado: MEMORIA RAM.
# Se lee el archivo completo a bytes, se decodifica a RGB y se convierte a
# RGBA sin comprimir (4 bytes por píxel: 8000x8000 = 256 MB solo el RGBA).
# Todas las copias se mantienen vivas mientras se calcula el histograma, así
# que cada petición ocupa varias veces el tamaño del archivo. Con varias
# peticiones grandes a la vez se supera mem_limit y el kernel mata el
# contenedor (OOM killer, código de salida 137).
@app.post("/subir")
def subir(archivo: UploadFile = File(...)):
    t0 = time.perf_counter()
    datos = archivo.file.read()  # archivo completo en memoria (comprimido)
    img = Image.open(io.BytesIO(datos))
    img.load()  # decodifica a RGB sin comprimir
    rgba = img.convert("RGBA")  # segunda copia, 4 bytes/píxel
    # Trabajo mientras todo sigue en memoria (img, rgba y datos referenciados).
    histograma = rgba.histogram()
    bytes_rgba = rgba.width * rgba.height * 4
    ms = round((time.perf_counter() - t0) * 1000, 1)

    guardado = registrar("subir", archivo.filename or "", rgba.width, rgba.height, ms)
    return {
        "endpoint": "subir",
        "ancho": rgba.width,
        "alto": rgba.height,
        "bytes_archivo": len(datos),
        "bytes_rgba_en_memoria": bytes_rgba,
        "canales_histograma": len(histograma),
        "ms": ms,
        "registrado": guardado,
    }


# --- /historial -------------------------------------------------------------
# Componente estresado: BASE DE DATOS (disco + pool de conexiones).
# La consulta ordena por creado_en, que no tiene índice, sobre ~1M de filas:
# Postgres debe leer toda la tabla (E/S de disco/caché) y ordenarla en cada
# petición. Como el pool tiene solo 5 conexiones y cada consulta es lenta,
# bajo carga las peticiones esperan conexión y, tras 5 s, fallan con 503.
@app.get("/historial")
def historial():
    t0 = time.perf_counter()
    try:
        with Session(engine) as s:
            filas = s.scalars(
                select(Registro).order_by(Registro.creado_en.desc()).limit(50)
            ).all()
    except PoolTimeout:
        ms = round((time.perf_counter() - t0) * 1000, 1)
        return JSONResponse(
            status_code=503,
            content={"error": "pool de conexiones agotado", "ms": ms},
        )

    ms = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "endpoint": "historial",
        "total": len(filas),
        "registros": [
            {
                "id": r.id,
                "endpoint": r.endpoint,
                "archivo": r.archivo,
                "ancho": r.ancho,
                "alto": r.alto,
                "ms": r.ms,
                "creado_en": r.creado_en.isoformat(),
            }
            for r in filas
        ],
        "ms": ms,
    }
