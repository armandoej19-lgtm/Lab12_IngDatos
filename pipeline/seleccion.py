"""Etapa 6: Selección.

Conserva los registros y los atributos necesarios para el proyecto: los
registros sin incumplimientos, con las columnas del diseño. Los demás se
separan con su motivo de rechazo (no se borran en silencio).

Esta etapa no evalúa reglas: decide con el resultado de la validación.
"""

import logging

import pandas as pd

from . import config
from .conversion import fila_excel
from .validacion import Validacion

log = logging.getLogger(__name__)


def seleccion(df: pd.DataFrame, validacion: Validacion,
              df_original: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (df_seleccionado, df_rechazados).

    validacion: resultado de validar este mismo `df` (los datos ya limpios).
    df_original: si se pasa, los rechazados se guardan con los valores tal como
    venían en el Excel, para que sea fácil corregirlos en el origen.
    """
    motivo = validacion.motivos()
    rechazado = motivo.ne("")

    df_sel = df.loc[~rechazado, config.COLUMNAS_SELECCIONADAS].copy()

    fuente = df_original if df_original is not None else df
    df_rechazados = fuente.loc[rechazado].copy()
    df_rechazados.insert(0, "fila_excel", fila_excel(df_rechazados.index))
    df_rechazados["motivo_rechazo"] = motivo[rechazado]
    df_rechazados = df_rechazados.reset_index(drop=True)

    log.info("Selección: %d recibidos | %d aceptados | %d rechazados | %d atributos",
             len(df), len(df_sel), len(df_rechazados), len(df_sel.columns))
    return df_sel, df_rechazados
