#!/bin/sh
# Arranca Ollama y descarga al volumen los modelos que falten.
# Los modelos se toman de la variable MODELOS (separados por espacios).
set -eu

ollama serve &
servidor=$!
trap 'kill "$servidor" 2>/dev/null; wait "$servidor" 2>/dev/null; exit 0' TERM INT

# Espera a que el servidor responda (o termina si se cayó al arrancar)
intentos=0
until ollama list >/dev/null 2>&1; do
    intentos=$((intentos + 1))
    if [ "$intentos" -gt 60 ] || ! kill -0 "$servidor" 2>/dev/null; then
        echo "Ollama no arrancó." >&2
        exit 1
    fi
    sleep 1
done

for modelo in ${MODELOS:-}; do
    if ollama show "$modelo" >/dev/null 2>&1; then
        echo "Modelo disponible: $modelo"
    else
        echo "Descargando $modelo (solo la primera vez)..."
        ollama pull "$modelo"
    fi
done
echo "Listo. Modelos: ${MODELOS:-ninguno}. Puerto 11434."

wait "$servidor"
