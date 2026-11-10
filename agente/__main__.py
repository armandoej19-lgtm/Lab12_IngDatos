"""Chat en la terminal con el agente del programa.

Uso:
    python -m agente                                              # conversación
    python -m agente "¿Qué conferencias hay entre las 10 y las 12?"   # una sola pregunta
"""

import argparse
import logging
import sys

import psycopg
from dotenv import load_dotenv

from pipeline import bd

from . import Agente, Almacen, Modelo, ModeloNoDisponible, SinDatos

SALIR = {"salir", "exit", "quit"}


def _responder(agente: Agente, pregunta: str) -> None:
    respuesta = agente.preguntar(pregunta)
    print(respuesta.completa)
    print(f"\n[Búsqueda: {respuesta.consulta.descripcion()}]")


def conversar(url_bd: str | None = None, pregunta: str | None = None) -> int:
    """Responde `pregunta` o, si no se pasa, abre una conversación. Devuelve el código de salida."""
    sys.stdout.reconfigure(errors="replace")  # el modelo puede escribir símbolos que la consola no tenga
    logging.getLogger("httpx").setLevel(logging.WARNING)  # si no, cada petición a Ollama sale en la consola
    try:
        conn = bd.conectar(url_bd, autocommit=True)
    except (RuntimeError, psycopg.OperationalError) as error:
        print(f"No se pudo conectar a PostgreSQL: {error}", file=sys.stderr)
        return 1

    with conn:
        try:
            modelo = Modelo()
            modelo.verificar()
            agente = Agente(Almacen(conn), modelo)
            print(f"Preparando el agente ({modelo.chat})...")
            nuevos = agente.preparar()
            if nuevos:
                print(f"Se generaron los vectores de {nuevos} eventos ({modelo.embeddings}).")

            if pregunta:
                _responder(agente, pregunta)
                return 0

            print("Pregunta sobre el programa de la Semana de Ingeniería. Escribe 'salir' para terminar.")
            while True:
                try:
                    pregunta = input("\n> ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                if pregunta.lower() in SALIR:
                    break
                if pregunta:
                    _responder(agente, pregunta)
            return 0
        except (ModeloNoDisponible, SinDatos) as error:
            print(f"\n{error}", file=sys.stderr)
            return 1


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m agente",
                                     description="Agente del programa de la Semana de Ingeniería")
    parser.add_argument("pregunta", nargs="?", help="Pregunta a responder (sin ella se abre una conversación)")
    parser.add_argument("--bd", metavar="URL", help="URL de PostgreSQL (por defecto: variable DATABASE_URL)")
    args = parser.parse_args()
    return conversar(args.bd, args.pregunta)


if __name__ == "__main__":
    sys.exit(main())
