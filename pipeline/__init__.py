"""Pipeline de datos del programa de la Semana de Ingeniería.

Cada etapa hace una sola cosa y entrega su resultado a la siguiente:

    1    carga           cargar_datos, cargar_diccionario   lee los Excel
    2    carga           validar_carga                      se leyó sin errores y no está vacío
    3    layout          validar_layout                     columnas y tipos de datos esperados
    4    validacion      validacion_de_informacion          identifica y registra incumplimientos
    5    limpieza        limpieza                           trata los problemas que marcó la etapa 4
    6    seleccion       seleccion                          conserva registros y atributos necesarios
    7    transformacion  transformacion                     aplica el esquema del diseño
    8    almacenamiento  almacenamiento                     guarda procesados y rechazados, y verifica
"""

from .almacenamiento import almacenamiento
from .carga import cargar_datos, cargar_diccionario, validar_carga
from .layout import validar_layout
from .limpieza import limpieza
from .seleccion import seleccion
from .transformacion import transformacion
from .validacion import Validacion, validacion_de_informacion

__all__ = [
    "cargar_datos", "cargar_diccionario", "validar_carga", "validar_layout",
    "validacion_de_informacion", "Validacion", "limpieza",
    "seleccion", "transformacion", "almacenamiento",
]
__version__ = "1.1.0"
