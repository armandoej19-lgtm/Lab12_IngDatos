"""Etapa 4: Validación de información.

Identifica y registra los problemas de calidad y los incumplimientos de las
reglas del diccionario de datos. Cada regla se escribe UNA sola vez, como una
máscara booleana por registro (True = el registro la incumple).

El resultado es el único insumo de las etapas siguientes: la limpieza trata
los problemas identificados aquí y la selección conserva los registros que no
tienen ninguno. Ninguna de las dos vuelve a evaluar reglas por su cuenta.
"""

import logging
from dataclasses import dataclass

import pandas as pd

from . import config
from .carga import Diccionario
from .conversion import (a_fecha, a_hora, columnas_de_texto, es_vacio, fila_excel, hora,
                         solo_espacios, texto, tiene_espacios_sobrantes)

log = logging.getLogger(__name__)


@dataclass
class Validacion:
    """Incumplimientos detectados en un conjunto de datos."""
    reglas: dict[str, pd.Series]    # {regla: máscara por registro}, con el índice de los datos validados

    @property
    def reporte(self) -> pd.DataFrame:
        """Resumen: número de registros que incumplen cada regla."""
        return pd.DataFrame({"Validación": list(self.reglas),
                             "Total Errores": [int(mascara.sum()) for mascara in self.reglas.values()]})

    @property
    def incumplimientos(self) -> pd.DataFrame:
        """Registro detallado: un renglón por cada regla que incumple cada fila del Excel."""
        filas = [(fila_excel(indice), regla)
                 for regla, mascara in self.reglas.items() for indice in mascara.index[mascara]]
        detalle = pd.DataFrame(filas, columns=["fila_excel", "regla"])
        return detalle.sort_values("fila_excel", kind="mergesort").reset_index(drop=True)

    def motivos(self) -> pd.Series:
        """Reglas que incumple cada registro, separadas por '; ' (cadena vacía si las cumple todas)."""
        indice = next(iter(self.reglas.values())).index
        motivo = pd.Series("", index=indice, dtype=object)
        for regla, mascara in self.reglas.items():
            motivo[mascara] = motivo[mascara] + regla + "; "
        return motivo.str.rstrip("; ")


def _reglas(df: pd.DataFrame, diccionario: Diccionario) -> dict[str, pd.Series]:
    """{regla: máscara} con True en los registros que la incumplen."""
    f_ini, f_fin = a_fecha(df["Fecha inicio"]), a_fecha(df["Fecha fin"])
    h_ini, h_fin = a_hora(df["Hora inicio"]), a_hora(df["Hora fin"])
    fecha_min, fecha_max = pd.Timestamp(config.FECHA_MIN), pd.Timestamp(config.FECHA_MAX)
    hora_min, hora_max = hora(config.HORA_MIN), hora(config.HORA_MAX)

    tipo = texto(df["Tipo"])
    es_virtual = tipo.eq("virtual").fillna(False)
    es_presencial = tipo.eq("presencial").fillna(False)

    salon = df["Salón"].astype("string").str.strip()
    salon_vacio = es_vacio(df["Salón"]) | salon.eq(config.SIN_SALON).fillna(False)

    enlace = df["Enlace"].astype("string").str.strip()
    ponente, maestro = texto(df["Ponente"]), texto(df["Maestro de ceremonias"])
    de_texto = columnas_de_texto(df)

    def alguna(condicion, columnas):
        return pd.concat([condicion(df[c]) for c in columnas], axis=1).any(axis=1)

    def fuera(serie, minimo, maximo):
        return serie.notna() & ((serie < minimo) | (serie > maximo))

    reglas = {
        # 1. duplicados, nulos y vacíos
        "duplicados": df.duplicated(),
        "nulos": df[config.COLUMNAS_OBLIGATORIAS].isna().any(axis=1),
        "vacios": alguna(solo_espacios, df.columns),
        # 2. catálogos autorizados
        "actividad_fuera_de_catalogo": df["Actividad"].notna() & ~texto(df["Actividad"]).isin(diccionario.actividades),
        "tipo_invalido": df["Tipo"].notna() & ~tipo.isin(config.TIPOS_PERMITIDOS),
        "salon_fuera_de_catalogo": ~salon_vacio & ~salon.isin(diccionario.salones),
        # 3. formatos
        "formato_fecha": (df["Fecha inicio"].notna() & f_ini.isna()) | (df["Fecha fin"].notna() & f_fin.isna()),
        "formato_hora": (df["Hora inicio"].notna() & h_ini.isna()) | (df["Hora fin"].notna() & h_fin.isna()),
        "enlace_invalido": ~es_vacio(df["Enlace"]) & ~enlace.str.match(config.PATRON_TEAMS).fillna(False),
        "espacios_sobrantes": alguna(tiene_espacios_sobrantes, de_texto),
        # 4. rangos
        "fecha_fuera_de_rango": fuera(f_ini, fecha_min, fecha_max) | fuera(f_fin, fecha_min, fecha_max),
        "hora_fuera_de_rango": fuera(h_ini, hora_min, hora_max) | fuera(h_fin, hora_min, hora_max),
        # 5. reglas entre campos
        "fecha_inicio_mayor_a_fin": f_ini > f_fin,
        "hora_inicio_no_menor_a_fin": h_ini >= h_fin,
        "virtual_sin_enlace": es_virtual & es_vacio(df["Enlace"]),
        "presencial_sin_salon": es_presencial & salon_vacio,
        "maestro_igual_a_ponente": ponente.notna() & ponente.eq(maestro).fillna(False),
    }
    return {nombre: mascara.fillna(False).astype(bool) for nombre, mascara in reglas.items()}


def validacion_de_informacion(df: pd.DataFrame, diccionario: Diccionario) -> Validacion:
    """Evalúa todas las reglas sobre `df` y devuelve los incumplimientos detectados."""
    validacion = Validacion(_reglas(df, diccionario))
    con_incumplimientos = int(validacion.motivos().ne("").sum())
    log.info("Registros con al menos un incumplimiento: %d de %d", con_incumplimientos, len(df))
    return validacion
