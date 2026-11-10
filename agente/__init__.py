"""Agente que responde preguntas sobre el programa de la Semana de Ingeniería.

Usa modelos locales de Ollama y lee de PostgreSQL lo que guardó el pipeline.

    consulta   Consulta: filtros que el modelo extrae de la pregunta
    almacen    Almacen: SQL de búsqueda, vectores e interacciones
    modelo     Modelo: cliente de Ollama
    agente     Agente: interpretar -> recuperar -> redactar -> registrar
"""

from .agente import Agente, Respuesta
from .almacen import Almacen, SinDatos
from .consulta import Consulta
from .modelo import Modelo, ModeloNoDisponible

__all__ = ["Agente", "Respuesta", "Almacen", "SinDatos", "Consulta", "Modelo", "ModeloNoDisponible"]
