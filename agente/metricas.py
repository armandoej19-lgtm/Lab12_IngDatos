"""Vista en consola de las métricas de los modelos del agente.

Muestra la ficha de cada modelo (parámetros, arquitectura, contexto, tamaño),
la memoria que ocupan ahora y los tokens que ha consumido el agente.

Uso:
    python -m agente.metricas               # una vez
    python -m agente.metricas --medir       # además mide la velocidad con una generación corta
    python -m agente.metricas --seguir 5    # se actualiza cada 5 segundos (Ctrl+C para salir)
"""

import argparse
import csv
import ctypes
import io
import os
import subprocess
import sys
import time as reloj
from datetime import datetime, timezone
from pathlib import Path

import ollama
import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

from pipeline import bd

from . import config
from .almacen import Almacen
from .modelo import Modelo

Seccion = tuple[str, list[tuple[str, str]]]     # (título, [(etiqueta, valor)])

PROCESOS_DE_OLLAMA = ("ollama", "llama-server")
PREGUNTA_DE_MEDICION = "Cuenta del uno al veinte, con palabras."


# --------------------------------------------------------------------------
# Formato
# --------------------------------------------------------------------------
def numero(valor) -> str:
    """Entero con separador de miles: 4,022,468,096."""
    return f"{int(valor):,}"


def tamano(en_bytes) -> str:
    """Tamaño en unidades binarias: 2.33 GiB, 563 MiB."""
    if en_bytes >= 1024 ** 3:
        return f"{en_bytes / 1024 ** 3:.2f} GiB"
    return f"{en_bytes / 1024 ** 2:.0f} MiB"


def _con_etiqueta(nombre: str) -> str:
    """Nombre del modelo con su etiqueta: 'bge-m3' es 'bge-m3:latest'."""
    return nombre if ":" in nombre else f"{nombre}:latest"


def _del_modelo(modelos, nombre: str):
    """El elemento de una lista de Ollama que corresponde al modelo, o None."""
    return next((m for m in modelos if _con_etiqueta(m.model) == _con_etiqueta(nombre)), None)


# --------------------------------------------------------------------------
# Modelos
# --------------------------------------------------------------------------
def ficha_modelo(cliente, nombre: str, titulo: str, contexto_en_uso: int | None = None) -> Seccion:
    """Datos fijos del modelo: cuántos parámetros tiene, cómo está construido y cuánto ocupa."""
    info = cliente.show(nombre)
    datos = info.modelinfo or {}
    capacidades = info.capabilities or []
    arquitectura = datos.get("general.architecture") or info.details.family
    filas = []

    parametros = datos.get("general.parameter_count")
    filas.append(("Parámetros", f"{numero(parametros)} ({info.details.parameter_size})" if parametros
                  else str(info.details.parameter_size)))

    capas = datos.get(f"{arquitectura}.block_count")
    filas.append(("Arquitectura", arquitectura + (f", {capas} capas" if capas else "")
                  + f", cuantización {info.details.quantization_level} ({info.details.format})"))

    maximo = datos.get(f"{arquitectura}.context_length")
    if contexto_en_uso:
        filas.append(("Contexto", f"{numero(contexto_en_uso)} tokens por petición"
                      + (f" (el modelo admite hasta {numero(maximo)})" if maximo else "")))
    elif maximo:
        filas.append(("Contexto", f"hasta {numero(maximo)} tokens por texto"))

    dimension = datos.get(f"{arquitectura}.embedding_length")
    if "embedding" in capacidades and dimension:
        filas.append(("Dimensión", f"{numero(dimension)} valores por vector"))

    en_disco = _del_modelo(cliente.list().models, nombre)
    if en_disco:
        filas.append(("Tamaño en disco", tamano(en_disco.size)))
    if capacidades:
        filas.append(("Capacidades", ", ".join(capacidades)))
    if datos.get("general.license"):
        filas.append(("Licencia", str(datos["general.license"])))
    return f"{titulo} · {nombre}", filas


def medir(cliente, nombre: str) -> Seccion:
    """Velocidad del modelo de chat, medida con una generación corta."""
    capacidades = cliente.show(nombre).capabilities or []
    respuesta = cliente.chat(
        model=nombre, think=False if "thinking" in capacidades else None,
        messages=[{"role": "user", "content": PREGUNTA_DE_MEDICION}],
        options={"temperature": 0, "num_ctx": config.TOKENS_CONTEXTO, "num_predict": 64})

    def por_segundo(tokens, nanosegundos) -> str:
        return f"{tokens / (nanosegundos / 1e9):.1f} tokens/s" if tokens and nanosegundos else "sin dato"

    return f"VELOCIDAD · {nombre}", [
        ("Carga del modelo", f"{(respuesta.load_duration or 0) / 1e9:.1f} s"),
        ("Lectura", f"{por_segundo(respuesta.prompt_eval_count, respuesta.prompt_eval_duration)}"
                    f" ({numero(respuesta.prompt_eval_count or 0)} tokens)"),
        ("Generación", f"{por_segundo(respuesta.eval_count, respuesta.eval_duration)}"
                       f" ({numero(respuesta.eval_count or 0)} tokens)"),
        ("Tiempo total", f"{(respuesta.total_duration or 0) / 1e9:.1f} s"),
    ]


# --------------------------------------------------------------------------
# Memoria
# --------------------------------------------------------------------------
def memoria_del_sistema() -> tuple[int, int] | None:
    """(RAM total, RAM disponible) en bytes, o None si no se puede saber."""
    try:
        if sys.platform == "win32":
            class Estado(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            estado = Estado()
            estado.dwLength = ctypes.sizeof(estado)
            if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
                return None
            return estado.ullTotalPhys, estado.ullAvailPhys

        campos = {}
        for linea in Path("/proc/meminfo").read_text().splitlines():
            clave, valor = linea.split(":", 1)
            campos[clave] = int(valor.split()[0]) * 1024
        return campos["MemTotal"], campos["MemAvailable"]
    except (OSError, KeyError, ValueError, AttributeError):
        return None


def memoria_de_ollama() -> int | None:
    """RAM que ocupan los procesos de Ollama en esta máquina, en bytes (None si no hay o no se puede saber).

    Es lo que mide el sistema operativo; puede ser más de lo que Ollama reporta
    como «en RAM», porque incluye el propio servidor y los archivos en caché.
    """
    try:
        total = 0
        if sys.platform == "win32":
            salida = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True,
                                    errors="replace", timeout=10).stdout
            for fila in csv.reader(io.StringIO(salida)):
                if len(fila) >= 5 and fila[0].lower().startswith(PROCESOS_DE_OLLAMA):
                    total += int("".join(c for c in fila[4] if c.isdigit())) * 1024
            return total or None

        for proceso in Path("/proc").iterdir():
            if not proceso.name.isdigit():
                continue
            try:
                if not (proceso / "comm").read_text().strip().startswith(PROCESOS_DE_OLLAMA):
                    continue
                for linea in (proceso / "status").read_text().splitlines():
                    if linea.startswith("VmRSS:"):
                        total += int(linea.split()[1]) * 1024
            except OSError:     # el proceso terminó mientras se leía
                continue
        return total or None
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _cargado(modelo) -> str:
    """Memoria de un modelo cargado y cuándo se libera."""
    total, en_gpu = modelo.size or 0, modelo.size_vram or 0
    en_ram = total - en_gpu
    if en_ram <= 0:
        reparto = "todo en GPU"
    elif not en_gpu:
        reparto = "todo en RAM"
    else:
        reparto = f"{tamano(en_ram)} en RAM y {tamano(en_gpu)} en GPU"
    partes = [f"{tamano(total)} ({reparto})"]
    if getattr(modelo, "context_length", None):
        partes.append(f"contexto de {numero(modelo.context_length)}")
    if modelo.expires_at:
        segundos = (modelo.expires_at - datetime.now(timezone.utc)).total_seconds()
        partes.append("se libera en menos de 1 min" if segundos < 60 else f"se libera en {segundos / 60:.0f} min")
    return " · ".join(partes)


def seccion_memoria(cliente, nombres: list[str]) -> Seccion:
    """Memoria que ocupan los modelos ahora mismo y estado de la RAM de la máquina."""
    cargados = cliente.ps().models if cliente else []
    filas = []
    for nombre in nombres:
        modelo = _del_modelo(cargados, nombre)
        filas.append((nombre, _cargado(modelo) if modelo else "no está cargado (se carga al usarlo)"))
    filas += filas_del_sistema()
    return "MEMORIA", filas


def filas_del_sistema() -> list[tuple[str, str]]:
    filas = []
    procesos = memoria_de_ollama()
    if procesos:
        filas.append(("Procesos de Ollama", f"{tamano(procesos)} de RAM"))
    sistema = memoria_del_sistema()
    if sistema:
        total, disponible = sistema
        filas.append(("RAM del sistema", f"{tamano(total)} · {tamano(disponible)} libres "
                                         f"({(total - disponible) / total:.0%} en uso)"))
    return filas


# --------------------------------------------------------------------------
# Uso
# --------------------------------------------------------------------------
def uso_del_agente(conn) -> Seccion:
    """Preguntas atendidas y tokens consumidos, según el historial de `agente_interacciones`."""
    Almacen(conn).asegurar_esquema()
    with conn.cursor(row_factory=dict_row) as cur:
        total = cur.execute(
            "SELECT count(*) AS preguntas, count(DISTINCT sesion) AS conversaciones, "
            "count(*) FILTER (WHERE creado_en >= date_trunc('day', now())) AS hoy, "
            "count(tokens_entrada) AS con_tokens, "
            "coalesce(sum(tokens_entrada), 0) AS entrada, coalesce(sum(tokens_salida), 0) AS salida, "
            "percentile_cont(0.5) WITHIN GROUP (ORDER BY duracion_ms) AS mediana_ms, avg(duracion_ms) AS promedio_ms "
            "FROM agente_interacciones").fetchone()
        ultimas = cur.execute(
            "SELECT creado_en, duracion_ms, tokens_entrada, tokens_salida, pregunta "
            "FROM agente_interacciones ORDER BY id_interaccion DESC LIMIT 5").fetchall()

    titulo = "USO DEL AGENTE"
    if not total["preguntas"]:
        return titulo, [("Preguntas", "ninguna todavía")]

    conversaciones = "1 conversación" if total["conversaciones"] == 1 else f"{numero(total['conversaciones'])} conversaciones"
    filas = [("Preguntas", f"{numero(total['preguntas'])} en {conversaciones} (hoy: {numero(total['hoy'])})")]
    medidas = total["con_tokens"]
    if medidas:
        filas.append(("Tokens leídos", f"{numero(total['entrada'])} (promedio de {numero(total['entrada'] / medidas)} por pregunta)"))
        filas.append(("Tokens generados", f"{numero(total['salida'])} (promedio de {numero(total['salida'] / medidas)} por pregunta)"))
    if medidas < total["preguntas"]:
        filas.append(("Tokens", f"registrados en {numero(medidas)} de {numero(total['preguntas'])} preguntas "
                                "(las anteriores no los guardaban)"))
    filas.append(("Tiempo por pregunta", f"mediana de {total['mediana_ms'] / 1000:.1f} s · "
                                         f"promedio de {float(total['promedio_ms']) / 1000:.1f} s"))
    for fila in ultimas:
        tokens = (f"{numero(fila['tokens_entrada'])} leídos, {numero(fila['tokens_salida'])} generados"
                  if fila["tokens_entrada"] is not None else "tokens sin registrar")
        pregunta = fila["pregunta"] if len(fila["pregunta"]) <= 48 else fila["pregunta"][:47] + "…"
        filas.append((f"{fila['creado_en'].astimezone():%d/%m %H:%M}",
                      f"{fila['duracion_ms'] / 1000:.1f} s · {tokens} · {pregunta}"))
    return titulo, filas


# --------------------------------------------------------------------------
# Vista
# --------------------------------------------------------------------------
def reunir(cliente, chat: str, embeddings: str, conn, con_medicion: bool = False) -> list[Seccion]:
    """Todas las secciones. Si Ollama o PostgreSQL no responden, su sección lo dice y las demás se muestran."""
    secciones = []
    try:
        secciones.append(ficha_modelo(cliente, chat, "MODELO DE CHAT", config.TOKENS_CONTEXTO))
        secciones.append(ficha_modelo(cliente, embeddings, "MODELO DE EMBEDDINGS"))
        if con_medicion:
            secciones.append(medir(cliente, chat))
        secciones.append(seccion_memoria(cliente, [chat, embeddings]))
    except ConnectionError:
        secciones.append(("MODELOS", [("Ollama", "no responde: inícialo y vuelve a intentar")]))
        secciones.append(("MEMORIA", filas_del_sistema()))
    except ollama.ResponseError as error:
        secciones.append(("MODELOS", [("Ollama", f"{error.error}. ¿Falta descargar el modelo con «ollama pull»?")]))
        secciones.append(("MEMORIA", filas_del_sistema()))

    if conn is None:
        secciones.append(("USO DEL AGENTE", [("PostgreSQL", "sin conexión: revisa DATABASE_URL en .env")]))
    else:
        try:
            secciones.append(uso_del_agente(conn))
        except psycopg.errors.UndefinedTable:
            secciones.append(("USO DEL AGENTE", [("PostgreSQL", "sin tablas: ejecuta primero el pipeline (python main.py)")]))
    return secciones


def dibujar(secciones: list[Seccion], titulo: str) -> str:
    """Las secciones como texto alineado para la consola."""
    ancho = max((len(etiqueta) for _, filas in secciones for etiqueta, _ in filas), default=0) + 2
    lineas = [titulo, "=" * len(titulo)]
    for nombre, filas in secciones:
        lineas += ["", nombre, *(f"  {etiqueta:<{ancho}}{valor}" for etiqueta, valor in filas)]
    return "\n".join(lineas)


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(prog="python -m agente.metricas",
                                     description="Métricas de los modelos del agente")
    parser.add_argument("--medir", action="store_true",
                        help="Mide la velocidad con una generación corta (carga el modelo en memoria)")
    parser.add_argument("--seguir", type=float, nargs="?", const=5, metavar="SEGUNDOS",
                        help="Actualiza la vista cada tantos segundos (por defecto 5) hasta pulsar Ctrl+C")
    parser.add_argument("--bd", metavar="URL", help="URL de PostgreSQL (por defecto: variable DATABASE_URL)")
    args = parser.parse_args()
    sys.stdout.reconfigure(errors="replace")

    modelos = Modelo()
    cliente = ollama.Client()
    try:
        conn = bd.conectar(args.bd, autocommit=True, connect_timeout=5)
    except (RuntimeError, psycopg.OperationalError):
        conn = None

    try:
        while True:
            secciones = reunir(cliente, modelos.chat, modelos.embeddings, conn, args.medir)
            vista = dibujar(secciones, f"Métricas del agente · {datetime.now():%Y-%m-%d %H:%M:%S}")
            if args.seguir is None:
                print(vista)
                return 0
            os.system("cls" if os.name == "nt" else "clear")
            print(vista + f"\n\nSe actualiza cada {args.seguir:g} s. Ctrl+C para salir.")
            reloj.sleep(args.seguir)
    except KeyboardInterrupt:
        return 0
    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    sys.exit(main())
