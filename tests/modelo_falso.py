"""Modelo simulado para las pruebas del agente y de su servicio web."""

from agente.consulta import sin_acentos


class ModeloFalso:
    """Devuelve filtros fijos y vectores que solo dependen de unas palabras clave.

    filtros: lo que "interpreta" de cualquier pregunta.
    afines:  números de los candidatos que "elige" cuando se le pide filtrar por tema.
    """
    chat = "modelo-falso"
    embeddings = "embeddings-falsos"
    PALABRAS = ["sensor", "circuito", "programacion", "torneo", "industria"]

    def __init__(self, filtros: dict | None = None, afines: list[int] | None = None):
        self.filtros = filtros or {}
        self.afines = afines or []
        self.candidatos = None      # lista que recibió para filtrar por tema
        self.datos_recibidos = None  # datos que recibió para redactar

    def verificar(self):
        pass

    def interpretar(self, sistema, usuario, esquema):
        if "relacionados" in esquema["properties"]:
            self.candidatos = usuario
            return {"relacionados": self.afines}
        return self.filtros

    def redactar(self, sistema, usuario):
        self.datos_recibidos = usuario
        return "Respuesta de prueba."

    def vectorizar(self, textos):
        return [[float(palabra in sin_acentos(texto)) for palabra in self.PALABRAS] for texto in textos]
