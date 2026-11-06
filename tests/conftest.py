import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from generar_datos_muestra import escribir  # noqa: E402

from pipeline import cargar_datos, cargar_diccionario  # noqa: E402


@pytest.fixture
def rutas_muestra(tmp_path):
    return escribir(tmp_path / "sample")


@pytest.fixture
def df(rutas_muestra):
    return cargar_datos(rutas_muestra[0])


@pytest.fixture
def diccionario(rutas_muestra):
    return cargar_diccionario(rutas_muestra[1])
