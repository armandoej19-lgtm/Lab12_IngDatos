"""Etapa 6: Selección.

Conserva los registros que cumplen TODAS las reglas del diccionario y los
atributos necesarios para el proyecto. Los registros que no las cumplen se
separan con su motivo de rechazo (no se borran en silencio).
"""

import logging

import pandas as pd

from . import config
from .carga import Diccionario
from .validacion import reglas_por_registro

log = logging.getLogger(__name__)


def seleccion(df: pd.DataFrame, diccionario: Diccionario,
              df_original: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (df_seleccionado, df_rechazados).

    df_original: si se pasa, los rechazados se guardan con los valores tal como
    venían en el Excel, para que sea fácil corregirlos en el origen.
    """
    reglas = reglas_por_registro(df, diccionario)

    motivo = pd.Series("", index=df.index, dtype=object)
    for nombre, mascara in reglas.items():
        motivo[mascara] = motivo[mascara] + nombre + "; "
    rechazado = motivo.ne("")

    df_sel = df.loc[~rechazado, config.COLUMNAS_SELECCIONADAS].copy()

    fuente = df_original if df_original is not None else df
    df_rechazados = fuente.loc[rechazado].copy()
    df_rechazados.insert(0, "fila_excel", df_rechazados.index + 2)
    df_rechazados["motivo_rechazo"] = motivo[rechazado].str.rstrip("; ")
    df_rechazados = df_rechazados.reset_index(drop=True)

    log.info("Selección: %d recibidos | %d aceptados | %d rechazados | %d atributos",
             len(df), len(df_sel), len(df_rechazados), len(df_sel.columns))
    return df_sel, df_rechazados
