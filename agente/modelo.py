"""Cliente de los modelos locales de Ollama: interpretar (JSON), redactar y vectorizar."""

import json
import os
import re
from collections.abc import Callable

import ollama

from . import config

ESQUEMA_TEXTO = {"type": "object", "properties": {"respuesta": {"type": "string"}}, "required": ["respuesta"]}


class ModeloNoDisponible(RuntimeError):
    """Ollama no responde o falta descargar alguno de los modelos."""


class Modelo:
    def __init__(self, chat: str | None = None, embeddings: str | None = None, host: str | None = None):
        self.chat = chat or os.getenv(config.VAR_MODELO) or config.MODELO
        self.embeddings = embeddings or os.getenv(config.VAR_MODELO_EMBEDDINGS) or config.MODELO_EMBEDDINGS
        self._cliente = ollama.Client(host=host)  # sin host usa OLLAMA_HOST o http://localhost:11434
        self._opciones = {"temperature": config.TEMPERATURA, "num_ctx": config.TOKENS_CONTEXTO}
        self._pensar = None  # se define en verificar()

    def _llamar(self, funcion: Callable, **argumentos):
        try:
            return funcion(**argumentos)
        except ConnectionError as error:
            raise ModeloNoDisponible("No se pudo conectar con Ollama. Inícialo y vuelve a intentar "
                                     "(https://ollama.com/download).") from error
        except ollama.ResponseError as error:
            modelo = argumentos.get("model")
            if error.status_code == 404:
                raise ModeloNoDisponible(f"Falta el modelo '{modelo}'. Descárgalo con: ollama pull {modelo}") from error
            raise ModeloNoDisponible(f"Ollama devolvió un error con '{modelo}': {error.error}") from error

    def verificar(self) -> None:
        """Comprueba que Ollama responde y que los dos modelos están descargados."""
        capacidades = self._llamar(self._cliente.show, model=self.chat).capabilities or []
        # Los modelos que razonan antes de contestar tardan mucho más: aquí no hace falta
        self._pensar = False if "thinking" in capacidades else None
        self._llamar(self._cliente.show, model=self.embeddings)

    def _conversar(self, sistema: str, usuario: str, **extra):
        return self._llamar(
            self._cliente.chat, model=self.chat, think=self._pensar,
            messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            **extra)

    def interpretar(self, sistema: str, usuario: str, esquema: dict) -> dict:
        """Respuesta en JSON restringida por `esquema`."""
        respuesta = self._conversar(sistema, usuario, format=esquema, options=self._opciones)
        try:
            datos = json.loads(respuesta.message.content)
        except json.JSONDecodeError:
            return {}
        return datos if isinstance(datos, dict) else {}

    def redactar(self, sistema: str, usuario: str) -> str:
        """Respuesta en texto (cadena vacía si el modelo no devolvió nada útil).

        El texto se pide dentro de un JSON: con la salida restringida, un modelo
        que razona antes de contestar no escribe su razonamiento como respuesta.
        """
        opciones = {**self._opciones, "num_predict": config.TOKENS_RESPUESTA}
        contenido = self._conversar(sistema, usuario, format=ESQUEMA_TEXTO, options=opciones).message.content
        try:
            texto = json.loads(contenido)["respuesta"]
        except (json.JSONDecodeError, KeyError, TypeError):
            # respuesta cortada por el límite de tokens: se aprovechan las frases que alcanzó a terminar
            parcial = re.search(r'"respuesta"\s*:\s*"(.*)', contenido, re.DOTALL)
            texto = parcial[1].replace('\\n', "\n").replace('\\"', '"') if parcial else ""
            texto = texto[:texto.rfind(".") + 1]
        return str(texto).strip()

    def vectorizar(self, textos: list[str]) -> list[list[float]]:
        """Un vector (embedding) por cada texto."""
        respuesta = self._llamar(self._cliente.embed, model=self.embeddings, input=textos)
        return [list(vector) for vector in respuesta.embeddings]
