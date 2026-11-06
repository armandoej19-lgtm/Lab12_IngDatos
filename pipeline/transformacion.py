"""Etapa 7: Transformación.

Aplica el esquema de salida del diseño: nombres estándar, tipos correctos y
atributos derivados que facilitan el uso del programa del evento.
"""

import logging

import numpy as np
import pandas as pd

from . import config
from .conversion import a_fecha, a_hora

log = logging.getLogger(__name__)


def transformacion(df: pd.DataFrame) -> pd.DataFrame:
    """Devuelve el DataFrame final listo para almacenarse."""
    df_t = df.rename(columns=config.RENOMBRAR).copy()

    # 1. Tipos: fechas -> datetime, horas -> texto HH:MM
    df_t["fecha_inicio"] = a_fecha(df_t["fecha_inicio"])
    df_t["fecha_fin"] = a_fecha(df_t["fecha_fin"])
    h_ini, h_fin = a_hora(df_t["hora_inicio"]), a_hora(df_t["hora_fin"])
    df_t["hora_inicio"] = h_ini.dt.strftime("%H:%M")
    df_t["hora_fin"] = h_fin.dt.strftime("%H:%M")

    # 2. Eventos virtuales: el marcador '—' en salón pasa a nulo
    df_t.loc[df_t["salon"].astype("string").str.strip().eq(config.SIN_SALON).fillna(False), "salon"] = np.nan

    # 3. Atributos derivados
    df_t["duracion_horas"] = ((h_fin - h_ini).dt.total_seconds() / 3600).round(2)
    df_t["num_dias"] = (df_t["fecha_fin"] - df_t["fecha_inicio"]).dt.days + 1
    df_t["dia_semana"] = df_t["fecha_inicio"].dt.dayofweek.map(config.DIAS_ES)

    # 4. Orden cronológico e identificador
    df_t = df_t.sort_values(["fecha_inicio", "hora_inicio"], kind="mergesort").reset_index(drop=True)
    df_t.insert(0, "id_evento", range(1, len(df_t) + 1))

    log.info("Transformación: %d registros, %d columnas", *df_t.shape)
    return df_t
