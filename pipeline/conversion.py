"""Conversión tolerante de fechas, horas y textos.

Excel puede entregar una fecha como texto ("2026-09-20") o como Timestamp,
y una hora como texto ("10:00") o como datetime.time. Estas funciones
aceptan ambos casos y devuelven NaT cuando el valor no es válido.
"""

import pandas as pd


def a_fecha(serie: pd.Series) -> pd.Series:
    """Convierte a datetime64 con formato YYYY-MM-DD; inválidos -> NaT."""
    if pd.api.types.is_datetime64_any_dtype(serie):
        return serie.dt.normalize()
    texto = serie.astype("string").str.strip().str[:10]
    return pd.to_datetime(texto, format="%Y-%m-%d", errors="coerce")


def a_hora(serie: pd.Series) -> pd.Series:
    """Convierte a datetime64 (fecha base 1900-01-01) con formato HH:MM; inválidos -> NaT."""
    texto = serie.map(lambda v: v.strftime("%H:%M") if hasattr(v, "strftime") else v)
    texto = texto.astype("string").str.strip().str[:5]
    return pd.to_datetime(texto, format="%H:%M", errors="coerce")


def hora(valor: str) -> pd.Timestamp:
    """Convierte una constante 'HH:MM' al mismo formato que a_hora."""
    return pd.to_datetime(valor, format="%H:%M")


def texto(serie: pd.Series) -> pd.Series:
    """Texto normalizado para comparar: sin espacios extremos y en minúsculas."""
    return serie.astype("string").str.strip().str.lower()


def es_vacio(serie: pd.Series) -> pd.Series:
    """True si el valor es nulo o solo contiene espacios."""
    solo_espacios = serie.astype("string").str.strip().eq("").fillna(False)
    return (serie.isna() | solo_espacios).astype(bool)


def solo_espacios(serie: pd.Series) -> pd.Series:
    """True si el valor es texto vacío o solo espacios (no cuenta los nulos)."""
    return serie.notna() & serie.astype("string").str.strip().eq("").fillna(False).astype(bool)
