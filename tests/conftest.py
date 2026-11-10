import os
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from dotenv import load_dotenv
from psycopg.conninfo import make_conninfo

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from generar_datos_muestra import escribir  # noqa: E402

from pipeline import cargar_datos, cargar_diccionario  # noqa: E402
from pipeline.config import VAR_URL_BD  # noqa: E402

load_dotenv(RAIZ / ".env")


@pytest.fixture
def rutas_muestra(tmp_path):
    return escribir(tmp_path / "sample")


@pytest.fixture
def df(rutas_muestra):
    return cargar_datos(rutas_muestra[0])


@pytest.fixture
def diccionario(rutas_muestra):
    return cargar_diccionario(rutas_muestra[1])


@pytest.fixture
def url_bd():
    """URL de PostgreSQL que apunta a un esquema temporal.

    Las pruebas nunca tocan las tablas reales: trabajan en un esquema propio
    que se borra al terminar. Si no hay base de datos, la prueba se omite.
    """
    base = os.getenv(VAR_URL_BD)
    if not base:
        pytest.skip(f"{VAR_URL_BD} no está definida")
    try:
        conn = psycopg.connect(base, autocommit=True, connect_timeout=3)
    except psycopg.OperationalError as error:
        pytest.skip(f"PostgreSQL no disponible: {error}")

    esquema = f"pruebas_{uuid4().hex[:12]}"
    with conn:
        conn.execute(f'CREATE SCHEMA "{esquema}"')
        try:
            yield make_conninfo(base, options=f"-c search_path={esquema}")
        finally:
            conn.execute(f'DROP SCHEMA "{esquema}" CASCADE')


@pytest.fixture
def bd_con_muestra(rutas_muestra, tmp_path, url_bd):
    """URL de una base con los datos de muestra ya cargados por el pipeline completo."""
    from main import ejecutar

    assert ejecutar(*rutas_muestra, tmp_path / "out", url_bd) == 0
    return url_bd
