"""Etapa 5: Limpieza.

La limpieza CORRIGE valores cuando la corrección es determinística y nunca
elimina registros: lo que no se puede corregir lo rechaza la etapa 6.
Cada celda modificada queda registrada en una bitácora.
"""

import logging
import re

import numpy as np
import pandas as pd

from . import config

log = logging.getLogger(__name__)


def _normalizar_texto(valor):
    """Quita espacios extremos y dobles; los textos vacíos pasan a nulo."""
    if isinstance(valor, str):
        limpio = re.sub(r"\s+", " ", valor).strip()
        return limpio if limpio else np.nan
    return valor


def _limpiar_salon(salon: pd.Series) -> pd.Series:
    salon = salon.copy()
    con_valor = salon.notna()
    salon[con_valor] = salon[con_valor].astype(str).str.replace(config.PATRON_SALON, r"\1", regex=True)
    for contiene, nombre in config.MAPEO_SALON:
        salon[salon.astype("string").str.contains(contiene, case=False, regex=False).fillna(False)] = nombre
    return salon


def _bitacora(antes: pd.DataFrame, despues: pd.DataFrame) -> pd.DataFrame:
    """Lista de celdas modificadas: fila de Excel, columna, valor original y valor limpio."""
    filas = []
    for col in despues.columns:
        a, d = antes[col], despues[col]
        cambio = ~((a == d) | (a.isna() & d.isna()))
        for idx in cambio[cambio].index:
            filas.append({
                "fila_excel": idx + 2,  # +1 por el encabezado y +1 porque Excel cuenta desde 1
                "columna": col,
                "valor_original": a[idx],
                "valor_limpio": d[idx],
            })
    bitacora = pd.DataFrame(filas, columns=["fila_excel", "columna", "valor_original", "valor_limpio"])
    return bitacora.sort_values("fila_excel", kind="mergesort").reset_index(drop=True)


def limpieza(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (df_limpio, bitacora). Conserva el índice original de cada registro."""
    original = df.copy()
    df = df.copy()

    # 1. Espacios extremos/dobles y textos vacíos -> nulo (incluye empresa vacía)
    for col in df.columns:
        if pd.api.types.is_object_dtype(df[col]) or pd.api.types.is_string_dtype(df[col]):
            df[col] = df[col].map(_normalizar_texto)

    # 2. Actividades con nombre de sede -> actividad del catálogo
    df["Actividad"] = df["Actividad"].replace(config.MAPEO_ACTIVIDAD)

    # 3. Tipo en minúsculas (presencial / virtual)
    df["Tipo"] = df["Tipo"].astype("string").str.lower().astype(object).where(df["Tipo"].notna(), np.nan)

    # 4. Salones con descripción extra -> nombre del catálogo
    df["Salón"] = _limpiar_salon(df["Salón"])

    # 5. Enlaces que no son de Teams -> nulo
    enlace_invalido = df["Enlace"].notna() & ~df["Enlace"].astype("string").str.match(config.PATRON_TEAMS).fillna(False)
    df.loc[enlace_invalido, "Enlace"] = np.nan

    # 6. Maestro de ceremonias repetido como ponente -> nulo
    ponente = df["Ponente"].astype("string").str.strip().str.lower()
    maestro = df["Maestro de ceremonias"].astype("string").str.strip().str.lower()
    repetido = ponente.notna() & ponente.eq(maestro).fillna(False)
    df.loc[repetido, "Maestro de ceremonias"] = np.nan

    bitacora = _bitacora(original, df)
    log.info("Limpieza: %d celdas corregidas en %d registros",
             len(bitacora), bitacora["fila_excel"].nunique() if len(bitacora) else 0)
    return df, bitacora
