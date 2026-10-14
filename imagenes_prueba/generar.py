"""Genera las imágenes de prueba (pequena, mediana, grande) como JPEG.

Se ejecuta dentro del contenedor de la api:
    docker compose exec api python imagenes_prueba/generar.py

La carpeta está montada como volumen, así que los archivos aparecen también
en Windows. El contenido es ruido suavizado: pesa poco como archivo pero se
decodifica al tamaño completo en memoria, que es lo que interesa probar.
"""
import os
from pathlib import Path

from PIL import Image

DESTINO = Path(__file__).resolve().parent
TAMANOS = {
    "pequena": (800, 600),
    "mediana": (3000, 2000),
    "grande": (8000, 8000),
}

for nombre, (ancho, alto) in TAMANOS.items():
    # Ruido en baja resolución ampliado: variación real sin un archivo gigante.
    bw, bh = max(1, ancho // 50), max(1, alto // 50)
    base = Image.frombytes("RGB", (bw, bh), os.urandom(bw * bh * 3))
    img = base.resize((ancho, alto), Image.BICUBIC)
    ruta = DESTINO / f"{nombre}.jpg"
    img.save(ruta, "JPEG", quality=90)
    print(f"{ruta.name}: {ancho}x{alto}, {ruta.stat().st_size / 1e6:.1f} MB")
