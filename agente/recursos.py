"""Recursos que consume la aplicación completa, en una sola vista de consola.

Reúne los procesos de la página web y el agente, de Ollama (instalado en el
sistema o en contenedor) y de PostgreSQL, y muestra de cada uno procesador,
memoria y swap, además de los modelos cargados y lo que ocupan los datos en disco.

    python -m agente.recursos               una vez
    python -m agente.recursos --seguir      en tiempo real: se actualiza cada segundo
    python -m agente.recursos --seguir 0.5  lo mismo, cada medio segundo
    python -m agente.recursos --procesos    añade el detalle proceso por proceso

Lee /proc, así que solo funciona en Linux.
"""

import argparse
import json
import os
import socket
import sys
import time as reloj
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

PAGINA = "Página web y agente"
OLLAMA = "Ollama (sistema)"
OLLAMA_CONTENEDOR = "Ollama (contenedor)"
POSTGRES = "PostgreSQL"
ORDEN = (PAGINA, OLLAMA, OLLAMA_CONTENEDOR, POSTGRES)

TICS = os.sysconf("SC_CLK_TCK")
NUCLEOS = os.cpu_count() or 1
COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def pintar(texto: str, codigo: str) -> str:
    return f"\033[{codigo}m{texto}\033[0m" if COLOR else texto


def tamano(en_bytes: float) -> str:
    if en_bytes >= 1024 ** 3:
        return f"{en_bytes / 1024 ** 3:.2f} GiB"
    return f"{en_bytes / 1024 ** 2:.0f} MiB"


def barra(fraccion: float, ancho: int = 12) -> str:
    fraccion = max(0.0, min(1.0, fraccion))
    llenos = round(fraccion * ancho)
    if fraccion > 0 and llenos == 0:
        llenos = 1
    codigo = "32" if fraccion < 0.6 else "33" if fraccion < 0.85 else "31"
    return pintar("█" * llenos, codigo) + pintar("░" * (ancho - llenos), "2")


# --------------------------------------------------------------------------
# Procesos
# --------------------------------------------------------------------------
def componente(pid: Path) -> tuple[str, str] | None:
    """Componente de la aplicación al que pertenece el proceso, y su descripción."""
    orden = (pid / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
    nombre = (pid / "comm").read_text().strip()
    if "agente.servidor" in orden and nombre.startswith("python"):
        return PAGINA, "servidor web (python -m agente.servidor)"
    if nombre.startswith(("ollama", "llama-server")):
        grupo = (pid / "cgroup").read_text()
        en_contenedor = any(marca in grupo for marca in ("docker", "libpod", "containerd"))
        papel = "modelo en ejecución" if " runner" in orden else "servidor de modelos"
        return (OLLAMA_CONTENEDOR if en_contenedor else OLLAMA), papel
    if nombre.startswith("postgres"):
        return POSTGRES, orden.removeprefix("postgres: ") if orden.startswith("postgres: ") else "servidor principal"
    return None


def leer_procesos() -> dict[int, dict]:
    procesos = {}
    for pid in Path("/proc").iterdir():
        if not pid.name.isdigit():
            continue
        try:
            encontrado = componente(pid)
            if not encontrado:
                continue
            estado = dict(linea.split(":", 1) for linea in (pid / "status").read_text().splitlines())
            campos = (pid / "stat").read_text().rsplit(")", 1)[1].split()
            kb = lambda clave: int(estado.get(clave, "0 kB").split()[0]) * 1024
            procesos[int(pid.name)] = {
                "componente": encontrado[0], "papel": encontrado[1],
                "hilos": int(estado.get("Threads", "1")),
                "anonima": kb("RssAnon"), "archivos": kb("RssFile"), "compartida": kb("RssShmem"),
                "swap": kb("VmSwap"),
                "tics": int(campos[11]) + int(campos[12]),   # utime + stime
            }
        except (OSError, ValueError, IndexError):
            continue   # el proceso terminó mientras se leía, o no se puede leer
    return procesos


def con_procesador(antes: dict[int, dict], ahora: dict[int, dict], segundos: float) -> dict[int, dict]:
    """Añade a cada proceso el procesador que usó entre las dos lecturas."""
    for pid, proceso in ahora.items():
        gastados = proceso["tics"] - antes.get(pid, proceso)["tics"]
        proceso["cpu"] = 100 * gastados / TICS / max(segundos, 0.01) / NUCLEOS   # % de toda la máquina
    return ahora


def resumir(procesos: list[dict]) -> dict:
    # La memoria compartida (la de PostgreSQL, sobre todo) es la misma para todos
    # los procesos del grupo: se cuenta una vez, no una por proceso.
    return {
        "procesos": len(procesos),
        "hilos": sum(p["hilos"] for p in procesos),
        "cpu": sum(p["cpu"] for p in procesos),
        "ram": sum(p["anonima"] + p["archivos"] for p in procesos) + max((p["compartida"] for p in procesos), default=0),
        "swap": sum(p["swap"] for p in procesos),
    }


# --------------------------------------------------------------------------
# Servicios, modelos y datos
# --------------------------------------------------------------------------
def direccion_ollama() -> str:
    valor = os.environ.get("OLLAMA_HOST", "").strip() or "localhost:11434"
    return valor if "://" in valor else f"http://{valor}"


def puerto_abierto(puerto: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", puerto), timeout=0.5):
            return True
    except OSError:
        return False


def pedir_a_ollama(ruta: str) -> dict | None:
    try:
        with urllib.request.urlopen(direccion_ollama() + ruta, timeout=2) as respuesta:
            return json.load(respuesta)
    except (OSError, ValueError):
        return None


def modelos_cargados() -> list[str] | None:
    datos = pedir_a_ollama("/api/ps")
    if datos is None:
        return None
    lineas = []
    for modelo in datos.get("models", []):
        texto = f"{modelo['name']:<16} {tamano(modelo.get('size', 0)):>9} en memoria"
        try:
            vence = datetime.fromisoformat(modelo["expires_at"].replace("Z", "+00:00"))
            segundos = (vence - datetime.now(timezone.utc)).total_seconds()
            if segundos > 0:
                texto += f" · se libera en {segundos / 60:.0f} min si no se usa"
        except (KeyError, ValueError):
            pass
        lineas.append(texto)
    return lineas


_disco: tuple[float, list] = (0.0, [])


def datos_en_disco() -> list[tuple[str, str]]:
    """Cambian poco: en la vista en tiempo real se consultan cada 30 segundos."""
    global _disco
    if _disco[1] and reloj.monotonic() - _disco[0] < 30:
        return _disco[1]
    _disco = (reloj.monotonic(), _consultar_disco())
    return _disco[1]


def _consultar_disco() -> list[tuple[str, str]]:
    filas = []
    etiquetas = pedir_a_ollama("/api/tags")
    if etiquetas is not None:
        modelos = etiquetas.get("models", [])
        filas.append(("Modelos de Ollama", f"{tamano(sum(m.get('size', 0) for m in modelos))} ({len(modelos)} modelos)"))
    try:
        import psycopg
        from dotenv import load_dotenv
        load_dotenv()
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=2) as conn:
            base, ocupa = conn.execute("SELECT current_database(), pg_database_size(current_database())").fetchone()
        filas.append(("Base de datos", f"{tamano(ocupa)} ({base})"))
    except Exception:
        filas.append(("Base de datos", "sin conexión: revisa DATABASE_URL en .env"))
    return filas


def memoria_del_sistema() -> dict:
    valores = {}
    for linea in Path("/proc/meminfo").read_text().splitlines():
        clave, valor = linea.split(":", 1)
        valores[clave] = int(valor.split()[0]) * 1024
    return valores


# --------------------------------------------------------------------------
# Vista
# --------------------------------------------------------------------------
def dibujar(procesos: dict[int, dict], con_procesos: bool) -> str:
    sistema = memoria_del_sistema()
    ram_total = sistema["MemTotal"]
    grupos = {nombre: [p for p in procesos.values() if p["componente"] == nombre] for nombre in ORDEN}

    titulo = f"Recursos de la aplicación · {datetime.now():%Y-%m-%d %H:%M:%S}"
    salida = [pintar(titulo, "1"), "═" * len(titulo), ""]

    def seccion(nombre: str) -> None:
        salida.append(pintar(nombre, "1;36"))

    def estado(nombre: str, activo: bool, detalle: str) -> None:
        punto = pintar("●", "32") if activo else pintar("○", "31")
        salida.append(f"  {punto} {nombre:<22} {detalle if activo else pintar('detenido', '31')}")

    seccion("SERVICIOS")
    estado(PAGINA, bool(grupos[PAGINA]), "en marcha · http://localhost:8000" if puerto_abierto(8000) else "en marcha")
    estado(OLLAMA, bool(grupos[OLLAMA]), f"en marcha · {direccion_ollama()}")
    if grupos[OLLAMA_CONTENEDOR]:
        estado(OLLAMA_CONTENEDOR, True, "en marcha")
    estado(POSTGRES, bool(grupos[POSTGRES]), "en marcha · puerto 5432" if puerto_abierto(5432) else "en marcha")
    salida.append("")

    seccion("CONSUMO")
    salida.append(pintar(f"  {'Componente':<22} {'Proc':>4} {'Hilos':>5}   {'Procesador':<20}  {'Memoria RAM':<23} {'Swap':>9}", "2"))

    def fila(nombre: str, r: dict) -> str:
        return (f"  {nombre:<22} {r['procesos']:>4} {r['hilos']:>5}   {barra(r['cpu'] / 100)} {r['cpu']:>5.1f} %"
                 f"  {barra(r['ram'] / ram_total)} {tamano(r['ram']):>10} {tamano(r['swap']):>9}")

    for nombre in ORDEN:
        if not grupos[nombre]:
            continue
        salida.append(fila(nombre, resumir(grupos[nombre])))
        if con_procesos:
            for pid, p in sorted(procesos.items(), key=lambda par: -(par[1]["anonima"] + par[1]["archivos"])):
                if p["componente"] == nombre:
                    propia = p["anonima"] + p["archivos"]
                    salida.append(pintar(f"      {pid:>7}  {p['papel'][:34]:<34} {p['cpu']:>5.1f} %  {tamano(propia):>10}"
                                         f"  {p['hilos']} {'hilo' if p['hilos'] == 1 else 'hilos'}", "2"))
    total = resumir(list(procesos.values()))
    total["ram"] = sum(resumir(g)["ram"] for g in grupos.values())
    salida.append("  " + "─" * 90)
    salida.append(fila(pintar("Toda la aplicación", "1") + " " * 4, total))
    salida.append("")

    seccion("MODELOS EN MEMORIA")
    cargados = modelos_cargados()
    if cargados is None:
        salida.append("  Ollama no responde")
    elif not cargados:
        salida.append("  Ninguno: el modelo se carga al hacer una pregunta (y ocupa unos 2.5 GiB)")
    else:
        salida.extend(f"  {linea}" for linea in cargados)
    salida.append("")

    seccion("DATOS EN DISCO")
    salida.extend(f"  {nombre:<22} {valor}" for nombre, valor in datos_en_disco())
    salida.append("")

    seccion("EQUIPO")
    en_uso = ram_total - sistema["MemAvailable"]
    swap_total, swap_uso = sistema["SwapTotal"], sistema["SwapTotal"] - sistema["SwapFree"]
    salida.append(f"  {'Memoria RAM':<22} {barra(en_uso / ram_total, 24)} {tamano(en_uso)} de {tamano(ram_total)}"
                  f" ({100 * en_uso / ram_total:.0f} %) · la aplicación usa {100 * total['ram'] / ram_total:.0f} %")
    if swap_total:
        salida.append(f"  {'Swap':<22} {barra(swap_uso / swap_total, 24)} {tamano(swap_uso)} de {tamano(swap_total)}"
                      f" ({100 * swap_uso / swap_total:.0f} %) · la aplicación usa {tamano(total['swap'])}")
    carga = os.getloadavg()[0]
    salida.append(f"  {'Procesador':<22} {barra(carga / NUCLEOS, 24)} carga de {carga:.2f} en {NUCLEOS} núcleos")
    return "\n".join(salida)


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m agente.recursos", description=__doc__.split("\n")[0])
    parser.add_argument("--seguir", type=float, nargs="?", const=1, metavar="SEGUNDOS",
                        help="vista en tiempo real: se actualiza cada tantos segundos (1 si no se indica) "
                             "hasta pulsar Ctrl+C")
    parser.add_argument("--procesos", action="store_true", help="añade el detalle de cada proceso")
    args = parser.parse_args()
    if not Path("/proc/meminfo").exists():
        print("Esta vista lee /proc y solo funciona en Linux.", file=sys.stderr)
        return 1

    intervalo = max(0.2, args.seguir) if args.seguir else 1.0
    antes, momento = leer_procesos(), reloj.monotonic()
    if not args.seguir:
        reloj.sleep(intervalo)
        print(dibujar(con_procesador(antes, leer_procesos(), reloj.monotonic() - momento), args.procesos))
        return 0

    # Pantalla alterna y cursor oculto: cada cuadro se escribe encima del anterior,
    # sin borrar antes, para que la vista no parpadee.
    sys.stdout.write("\033[?1049h\033[?25l")
    try:
        while True:
            reloj.sleep(intervalo)
            ahora, instante = leer_procesos(), reloj.monotonic()
            vista = dibujar(con_procesador(antes, ahora, instante - momento), args.procesos)
            antes, momento = ahora, instante
            pie = pintar(f"En tiempo real, cada {intervalo:g} s · Ctrl+C para salir", "2")
            lineas = (vista + "\n\n" + pie).split("\n")
            sys.stdout.write("\033[H" + "".join(linea + "\033[K\n" for linea in lineas) + "\033[J")
            sys.stdout.flush()
    except KeyboardInterrupt:
        return 0
    finally:
        sys.stdout.write("\033[?25h\033[?1049l")
        sys.stdout.flush()


if __name__ == "__main__":
    sys.exit(main())
