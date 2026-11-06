"""Etapa 3: Validación del layout contra el diccionario de datos."""

import logging
from dataclasses import dataclass, field

import pandas as pd

from .carga import Diccionario
from .conversion import a_fecha, a_hora

log = logging.getLogger(__name__)


@dataclass
class ResultadoLayout:
    columnas_faltantes: list = field(default_factory=list)
    columnas_adicionales: list = field(default_factory=list)
    errores_tipos: dict = field(default_factory=dict)   # {columna: valores incorrectos}

    @property
    def estructura_valida(self) -> bool:
        """Todas las columnas requeridas están presentes."""
        return not self.columnas_faltantes

    @property
    def valido(self) -> bool:
        """Estructura correcta y tipos compatibles."""
        return self.estructura_valida and not self.errores_tipos


def _valores_incorrectos(valores: pd.Series, tipo: str) -> int | None:
    """Cuenta los valores que no corresponden al tipo esperado (None si el tipo no se reconoce)."""
    tipo = str(tipo).strip().lower()
    if tipo == "str":
        return int((~valores.map(lambda v: isinstance(v, str))).sum())
    if tipo == "date":
        return int(a_fecha(valores).isna().sum())
    if tipo == "time":
        return int(a_hora(valores).isna().sum())
    return None


def validar_layout(df: pd.DataFrame, diccionario: Diccionario) -> ResultadoLayout:
    """Verifica nombres de columnas, columnas requeridas y tipos de datos."""
    esperadas = list(diccionario.tipos_esperados)
    reales = df.columns.tolist()

    resultado = ResultadoLayout(
        columnas_faltantes=[c for c in esperadas if c not in reales],
        columnas_adicionales=[c for c in reales if c not in esperadas],
    )

    for col in esperadas:
        if col not in reales:
            continue
        tipo = diccionario.tipos_esperados[col]
        incorrectos = _valores_incorrectos(df[col].dropna(), tipo)  # los nulos se revisan en la etapa 4
        if incorrectos is None:
            log.warning("Tipo esperado no reconocido para '%s': %s", col, tipo)
        elif incorrectos > 0:
            resultado.errores_tipos[col] = incorrectos

    log.info("Columnas esperadas: %d | encontradas: %d", len(esperadas), len(reales))
    for col in resultado.columnas_faltantes:
        log.error("Columna faltante: %s", col)
    for col in resultado.columnas_adicionales:
        log.warning("Columna adicional: %s", col)
    for col, n in resultado.errores_tipos.items():
        log.warning("Tipo/formato incorrecto en '%s': %d valores", col, n)

    if resultado.valido:
        log.info("Validación de layout exitosa.")
    elif resultado.estructura_valida:
        log.warning("Layout con errores de tipo: se tratarán en validación, limpieza y selección.")
    else:
        log.error("Layout inválido: faltan columnas requeridas.")
    return resultado
