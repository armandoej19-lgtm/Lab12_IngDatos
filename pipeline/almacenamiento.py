"""Etapa 8: Almacenamiento.

Guarda por separado los datos procesados y los registros rechazados (más la
bitácora de limpieza y el reporte de validación) y verifica la escritura
releyendo cada archivo.
"""

import logging
from pathlib import Path

import pandas as pd

from . import config

log = logging.getLogger(__name__)


def _guardar_y_verificar(df: pd.DataFrame, ruta: Path) -> Path:
    df.to_excel(ruta, index=False)
    leido = pd.read_excel(ruta)
    if leido.shape != df.shape or list(leido.columns) != [str(c) for c in df.columns]:
        raise IOError(f"Verificación fallida en {ruta.name}: "
                      f"se esperaba {df.shape}, se leyó {leido.shape}")
    log.info("Guardado y verificado: %s (%d registros)", ruta.name, len(df))
    return ruta


def almacenamiento(df_procesados: pd.DataFrame, df_rechazados: pd.DataFrame,
                   directorio, df_bitacora: pd.DataFrame | None = None,
                   reportes: dict[str, pd.DataFrame] | None = None) -> dict[str, Path]:
    """Escribe las salidas en `directorio` y devuelve las rutas verificadas.

    El archivo de rechazados se escribe aunque esté vacío, para dejar
    constancia de que la etapa se ejecutó.
    """
    directorio = Path(directorio)
    directorio.mkdir(parents=True, exist_ok=True)

    rutas = {
        "procesados": _guardar_y_verificar(df_procesados, directorio / config.ARCHIVO_PROCESADOS),
        "rechazados": _guardar_y_verificar(df_rechazados, directorio / config.ARCHIVO_RECHAZADOS),
    }
    if df_bitacora is not None:
        rutas["bitacora"] = _guardar_y_verificar(df_bitacora, directorio / config.ARCHIVO_BITACORA)

    if reportes:
        ruta = directorio / config.ARCHIVO_REPORTE
        with pd.ExcelWriter(ruta) as writer:
            for hoja, reporte in reportes.items():
                reporte.to_excel(writer, sheet_name=hoja, index=False)
        if set(pd.ExcelFile(ruta).sheet_names) != set(reportes):
            raise IOError(f"Verificación fallida en {ruta.name}")
        log.info("Guardado y verificado: %s", ruta.name)
        rutas["reporte"] = ruta

    return rutas
