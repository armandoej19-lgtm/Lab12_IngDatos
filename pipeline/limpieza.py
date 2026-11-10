"""Etapa 5: Limpieza.

Trata los problemas que identificó la validación (etapa 4). Cada tratamiento
se aplica a los registros que la validación marcó; aquí no se vuelve a evaluar
ninguna regla.

    Problema identificado          Tratamiento
    vacios, espacios_sobrantes     se quitan los espacios de más; el texto vacío pasa a nulo
    actividad_fuera_de_catalogo    nombre de sede -> actividad del catálogo
    salon_fuera_de_catalogo        salón con descripción extra o escrito distinto -> nombre del catálogo
    enlace_invalido                enlace que no es de Teams -> nulo
    maestro_igual_a_ponente        se conserva como ponente; el maestro de ceremonias pasa a nulo

La limpieza corrige solo cuando la corrección es determinística y nunca
elimina registros: lo que no tiene corrección segura lo separa la selección
(etapa 6). Cada celda modificada queda registrada en una bitácora.
"""

import logging

import numpy as np
import pandas as pd

from . import config
from .conversion import columnas_de_texto, fila_excel, normalizar_espacios
from .validacion import Validacion

log = logging.getLogger(__name__)


def _nombre_de_catalogo(salon: pd.Series) -> pd.Series:
    """Deja el salón como aparece en el catálogo: sin descripción extra y con su nombre oficial."""
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
                "fila_excel": fila_excel(idx),
                "columna": col,
                "valor_original": a[idx],
                "valor_limpio": d[idx],
            })
    bitacora = pd.DataFrame(filas, columns=["fila_excel", "columna", "valor_original", "valor_limpio"])
    return bitacora.sort_values("fila_excel", kind="mergesort").reset_index(drop=True)


def limpieza(df: pd.DataFrame, validacion: Validacion) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Devuelve (df_limpio, bitacora). Conserva el índice original de cada registro.

    validacion: resultado de la etapa 4 sobre este mismo `df`.
    """
    marcados = validacion.reglas
    original = df.copy()
    df = df.copy()

    con_espacios = marcados["vacios"] | marcados["espacios_sobrantes"]
    for col in columnas_de_texto(df):
        df.loc[con_espacios, col] = df.loc[con_espacios, col].map(normalizar_espacios)

    actividad = marcados["actividad_fuera_de_catalogo"]
    df.loc[actividad, "Actividad"] = df.loc[actividad, "Actividad"].replace(config.MAPEO_ACTIVIDAD)

    salon = marcados["salon_fuera_de_catalogo"]
    df.loc[salon, "Salón"] = _nombre_de_catalogo(df.loc[salon, "Salón"])

    df.loc[marcados["enlace_invalido"], "Enlace"] = np.nan
    df.loc[marcados["maestro_igual_a_ponente"], "Maestro de ceremonias"] = np.nan

    bitacora = _bitacora(original, df)
    log.info("Limpieza: %d celdas corregidas en %d registros",
             len(bitacora), bitacora["fila_excel"].nunique() if len(bitacora) else 0)
    return df, bitacora
