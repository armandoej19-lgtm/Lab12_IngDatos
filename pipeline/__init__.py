"""Pipeline de datos del programa de la Semana de Ingeniería.

Etapas:
    1-2  carga           cargar_datos, cargar_diccionario, validar_carga
    3    layout          validar_layout
    4    validacion      validacion_de_informacion, reglas_por_registro
    5    limpieza        limpieza
    6    seleccion       seleccion
    7    transformacion  transformacion
    8    almacenamiento  almacenamiento
"""

from .almacenamiento import almacenamiento
from .carga import cargar_datos, cargar_diccionario, validar_carga
from .layout import validar_layout
from .limpieza import limpieza
from .seleccion import seleccion
from .transformacion import transformacion
from .validacion import reglas_por_registro, validacion_de_informacion

__all__ = [
    "cargar_datos", "cargar_diccionario", "validar_carga", "validar_layout",
    "validacion_de_informacion", "reglas_por_registro", "limpieza",
    "seleccion", "transformacion", "almacenamiento",
]
__version__ = "1.0.0"
