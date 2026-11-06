"""Etapa 4: Validación de información.

Cada regla del diccionario se expresa UNA sola vez como una máscara booleana
por registro (True = el registro incumple la regla). La misma función sirve
para el reporte de esta etapa y para decidir rechazos en la etapa 6.
"""

import logging

import pandas as pd

from . import config
from .carga import Diccionario
from .conversion import a_fecha, a_hora, es_vacio, hora, solo_espacios, texto

log = logging.getLogger(__name__)


def reglas_por_registro(df: pd.DataFrame, diccionario: Diccionario) -> dict[str, pd.Series]:
    """Devuelve {nombre_regla: máscara} con True en los registros que la incumplen."""
    f_ini, f_fin = a_fecha(df["Fecha inicio"]), a_fecha(df["Fecha fin"])
    h_ini, h_fin = a_hora(df["Hora inicio"]), a_hora(df["Hora fin"])
    fecha_min, fecha_max = pd.Timestamp(config.FECHA_MIN), pd.Timestamp(config.FECHA_MAX)
    hora_min, hora_max = hora(config.HORA_MIN), hora(config.HORA_MAX)

    tipo = texto(df["Tipo"])
    es_virtual = tipo.eq("virtual").fillna(False)
    es_presencial = tipo.eq("presencial").fillna(False)

    salon = df["Salón"].astype("string").str.strip()
    salon_vacio = es_vacio(df["Salón"]) | salon.eq(config.SIN_SALON).fillna(False)

    ponente, maestro = texto(df["Ponente"]), texto(df["Maestro de ceremonias"])

    def fuera(serie, minimo, maximo):
        return serie.notna() & ((serie < minimo) | (serie > maximo))

    reglas = {
        # 1. duplicados, nulos y vacíos
        "duplicados": df.duplicated(),
        "nulos": df[config.COLUMNAS_OBLIGATORIAS].isna().any(axis=1),
        "vacios": pd.concat([solo_espacios(df[c]) for c in df.columns], axis=1).any(axis=1),
        # 2. catálogos autorizados
        "actividad_fuera_de_catalogo": df["Actividad"].notna() & ~texto(df["Actividad"]).isin(diccionario.actividades),
        "tipo_invalido": df["Tipo"].notna() & ~tipo.isin(config.TIPOS_PERMITIDOS),
        "salon_fuera_de_catalogo": ~salon_vacio & ~salon.isin(diccionario.salones),
        # 3. formatos
        "formato_fecha": (df["Fecha inicio"].notna() & f_ini.isna()) | (df["Fecha fin"].notna() & f_fin.isna()),
        "formato_hora": (df["Hora inicio"].notna() & h_ini.isna()) | (df["Hora fin"].notna() & h_fin.isna()),
        "enlace_invalido": df["Enlace"].notna() & ~df["Enlace"].astype("string").str.match(config.PATRON_TEAMS).fillna(False),
        # 4. rangos
        "fecha_fuera_de_rango": fuera(f_ini, fecha_min, fecha_max) | fuera(f_fin, fecha_min, fecha_max),
        "hora_fuera_de_rango": fuera(h_ini, hora_min, hora_max) | fuera(h_fin, hora_min, hora_max),
        # 5. reglas entre campos
        "fecha_inicio_mayor_a_fin": f_ini > f_fin,
        "hora_inicio_no_menor_a_fin": h_ini >= h_fin,
        "virtual_sin_enlace": es_virtual & es_vacio(df["Enlace"]),
        "presencial_sin_salon": es_presencial & salon_vacio,
        "titulo_vacio": es_vacio(df["Título"]),
        "maestro_igual_a_ponente": ponente.notna() & ponente.eq(maestro).fillna(False),
        "empresa_vacia": solo_espacios(df["Empresa / Institución"]),
    }
    return {nombre: mascara.fillna(False).astype(bool) for nombre, mascara in reglas.items()}


def validacion_de_informacion(df: pd.DataFrame, diccionario: Diccionario) -> pd.DataFrame:
    """Reporte con el número de registros que incumplen cada regla."""
    reglas = reglas_por_registro(df, diccionario)
    reporte = pd.DataFrame(
        {"Validación": list(reglas), "Total Errores": [int(m.sum()) for m in reglas.values()]}
    )
    total = int(pd.concat(reglas.values(), axis=1).any(axis=1).sum())
    log.info("Registros con al menos un incumplimiento: %d de %d", total, len(df))
    return reporte
