"""Etapa 1 (Carga) y Etapa 2 (Validación de carga)."""

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import config

log = logging.getLogger(__name__)

EXTENSIONES_EXCEL = {".xlsx", ".xls"}


@dataclass
class Diccionario:
    """Contenido del diccionario de datos usado como referencia."""
    tipos_esperados: dict      # {campo: tipo esperado}
    actividades: list          # catálogo de actividades (en minúsculas)
    salones: list              # catálogo de salones / lugares


def _validar_ruta(ruta) -> Path:
    ruta = Path(ruta)
    if not ruta.exists():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    if ruta.suffix.lower() not in EXTENSIONES_EXCEL:
        raise ValueError(f"El archivo debe tener formato Excel: {ruta.name}")
    return ruta


# --------------------------------------------------------------------------
# ETAPA 1: CARGA
# --------------------------------------------------------------------------
def cargar_datos(ruta) -> pd.DataFrame | None:
    """Lee el programa de actividades desde Excel. Devuelve None si falla."""
    try:
        ruta = _validar_ruta(ruta)
        df = pd.read_excel(ruta)
        log.info("Archivo cargado: %s", ruta.name)
        return df
    except Exception as error:
        log.error("Error durante la carga: %s", error)
        return None


def cargar_diccionario(ruta) -> Diccionario:
    """Lee las hojas del diccionario de datos (layout y catálogos)."""
    ruta = _validar_ruta(ruta)
    hojas = pd.read_excel(
        ruta,
        sheet_name=[config.HOJA_DICCIONARIO, config.HOJA_ACTIVIDADES, config.HOJA_SALONES],
    )
    dicc = hojas[config.HOJA_DICCIONARIO]
    act = hojas[config.HOJA_ACTIVIDADES]
    sal = hojas[config.HOJA_SALONES]

    diccionario = Diccionario(
        tipos_esperados=dict(zip(dicc[config.COL_CAMPO], dicc[config.COL_TIPO_ESPERADO])),
        actividades=act[config.COL_ACTIVIDAD_PERMITIDA].dropna().astype(str).str.strip().str.lower().tolist(),
        salones=sal[config.COL_LUGAR].dropna().astype(str).str.strip().tolist(),
    )
    log.info("Diccionario cargado: %d campos, %d actividades, %d salones",
             len(diccionario.tipos_esperados), len(diccionario.actividades), len(diccionario.salones))
    return diccionario


# --------------------------------------------------------------------------
# ETAPA 2: VALIDACIÓN DE CARGA
# --------------------------------------------------------------------------
def validar_carga(df: pd.DataFrame | None) -> bool:
    """Comprueba que el archivo se haya leído y que no esté vacío."""
    if df is None:
        log.error("No se pudieron cargar los datos.")
        return False
    if len(df.columns) == 0:
        log.error("El archivo no contiene columnas.")
        return False
    if df.empty:
        log.error("El archivo no contiene registros.")
        return False

    log.info("Validación de carga exitosa: %d registros, %d columnas", *df.shape)
    return True
