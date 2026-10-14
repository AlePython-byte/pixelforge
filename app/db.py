import os
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, create_engine, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

# SQLAlchemy necesita el driver explícito (psycopg 3).
DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://pixelforge:pixelforge@db:5432/pixelforge"
).replace("postgresql://", "postgresql+psycopg://", 1)

# Filas de relleno para que el ORDER BY sin índice sea realmente lento.
FILAS_SEMILLA = int(os.environ.get("HISTORIAL_FILAS_SEMILLA", "1000000"))

# --- Componente estresado: POOL DE CONEXIONES / BASE DE DATOS ---
# El pool es pequeño a propósito: solo 5 conexiones simultáneas, sin overflow
# y con 5 s de espera. Cuando llegan más de 5 peticiones concurrentes a
# /historial, las demás esperan una conexión y, pasados 5 s, fallan con
# TimeoutError. Así se ve el agotamiento del pool, no un límite de CPU.
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=0,
    pool_timeout=5,
)


class Base(DeclarativeBase):
    pass


class Registro(Base):
    __tablename__ = "registros"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    endpoint: Mapped[str] = mapped_column(String(20))
    archivo: Mapped[str] = mapped_column(String(255))
    ancho: Mapped[int] = mapped_column(Integer)
    alto: Mapped[int] = mapped_column(Integer)
    ms: Mapped[float] = mapped_column(Float)
    # OJO: sin índice a propósito. /historial ordena por esta columna, lo que
    # obliga a Postgres a recorrer y ordenar toda la tabla en cada consulta.
    creado_en: Mapped[datetime] = mapped_column(DateTime(timezone=True))


def iniciar_db() -> None:
    """Crea la tabla y la rellena con filas de semilla la primera vez."""
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        hay_datos = s.execute(text("SELECT 1 FROM registros LIMIT 1")).first()
        if hay_datos:
            return
        s.execute(
            text(
                """
                INSERT INTO registros (endpoint, archivo, ancho, alto, ms, creado_en)
                SELECT 'semilla', md5(g::text), 800, 600, random() * 1000,
                       now() - random() * interval '365 days'
                FROM generate_series(1, :n) AS g
                """
            ),
            {"n": FILAS_SEMILLA},
        )
        s.commit()


def registrar(endpoint: str, archivo: str, ancho: int, alto: int, ms: float) -> bool:
    """Guarda una operación. Devuelve False si no pudo (p. ej. pool agotado)
    para que un fallo de BD no tumbe los endpoints de CPU y memoria."""
    try:
        with Session(engine) as s:
            s.add(
                Registro(
                    endpoint=endpoint,
                    archivo=archivo,
                    ancho=ancho,
                    alto=alto,
                    ms=ms,
                    creado_en=datetime.now(timezone.utc),
                )
            )
            s.commit()
        return True
    except Exception:
        return False
