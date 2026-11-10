"""Crea el rol y la base de datos del proyecto en PostgreSQL.

Lee de .env la conexión que usará el proyecto (DATABASE_URL) y la clave del
superusuario con la que se crean (POSTGRES_PASSWORD; el usuario es `postgres`
salvo que se defina POSTGRES_USER). Se puede ejecutar varias veces: lo que ya
existe se conserva y la clave del rol se iguala a la de DATABASE_URL.

Uso:
    python scripts/crear_bd.py
"""

import os
import sys
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict

RAIZ = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv(RAIZ / ".env")
    url, clave_admin = os.getenv("DATABASE_URL"), os.getenv("POSTGRES_PASSWORD")
    if not url or not clave_admin:
        print("Define DATABASE_URL y POSTGRES_PASSWORD en .env (ver .env.example).", file=sys.stderr)
        return 1

    destino = conninfo_to_dict(url)
    rol, clave, base = destino.get("user"), destino.get("password"), destino.get("dbname")
    if not (rol and clave and base):
        print("DATABASE_URL debe incluir usuario, clave y base de datos.", file=sys.stderr)
        return 1

    admin = {"host": destino.get("host", "localhost"), "port": destino.get("port", "5432"),
             "user": os.getenv("POSTGRES_USER", "postgres"), "password": clave_admin, "dbname": "postgres"}
    try:
        conn = psycopg.connect(**admin, autocommit=True, connect_timeout=5)
    except psycopg.OperationalError as error:
        print(f"No se pudo conectar como superusuario: {error}", file=sys.stderr)
        return 1

    with conn:
        existe_rol = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", [rol]).fetchone()
        accion = sql.SQL("ALTER" if existe_rol else "CREATE")
        conn.execute(sql.SQL("{} ROLE {} LOGIN PASSWORD {}").format(accion, sql.Identifier(rol), sql.Literal(clave)))

        existe_base = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", [base]).fetchone()
        if not existe_base:
            conn.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(base), sql.Identifier(rol)))

    print(f"Rol '{rol}' {'actualizado' if existe_rol else 'creado'}; "
          f"base de datos '{base}' {'ya existía' if existe_base else 'creada'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
