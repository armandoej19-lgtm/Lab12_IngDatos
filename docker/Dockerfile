# Modelos del agente en Fedora, con el menor consumo de recursos posible.
#
# Ejecuta Ollama solo con procesador y con ajustes de bajo consumo. Los modelos
# no van dentro de la imagen: se descargan una sola vez a un volumen, así la
# imagen pesa poco y reconstruirla no obliga a bajarlos de nuevo.
#
#   docker build -t semana-modelo docker
#   docker run -d --name semana-modelo -p 127.0.0.1:11434:11434 \
#       -v semana-modelos:/ollama --memory 5g --cpus 4 semana-modelo
#
# En Fedora funciona igual con podman en lugar de docker. El proyecto se conecta
# sin cambios: usa http://localhost:11434, que es el puerto que se publica.

ARG VERSION_OLLAMA=0.40.16
ARG VERSION_FEDORA=latest

# --------------------------------------------------------------------------
# Etapa 1: Ollama oficial, sin las bibliotecas de GPU (CUDA, ROCm y Vulkan
# ocupan más de 3 GB y un contenedor sin tarjeta gráfica no las usa).
# --------------------------------------------------------------------------
FROM docker.io/ollama/ollama:${VERSION_OLLAMA} AS ollama
RUN rm -rf /usr/lib/ollama/cuda_* /usr/lib/ollama/rocm_* /usr/lib/ollama/vulkan /usr/lib/ollama/mlx_*

# --------------------------------------------------------------------------
# Etapa 2: imagen final sobre Fedora mínima
# --------------------------------------------------------------------------
FROM registry.fedoraproject.org/fedora-minimal:${VERSION_FEDORA}

RUN microdnf install -y libstdc++ libgomp ca-certificates \
    && microdnf clean all \
    && mkdir -p /ollama \
    && chown 1000:0 /ollama \
    && chmod g=u /ollama

COPY --from=ollama /usr/bin/ollama /usr/bin/ollama
COPY --from=ollama /usr/lib/ollama /usr/lib/ollama
COPY --chmod=755 iniciar.sh /usr/local/bin/iniciar-modelos

# Modelos que usa el agente. Para gastar menos memoria se puede cambiar el de chat
# por uno más pequeño (por ejemplo qwen3:1.7b) y definir AGENTE_MODELO en el .env.
ENV MODELOS="qwen3:4b bge-m3"

# Ajustes de bajo consumo:
#   OLLAMA_MAX_LOADED_MODELS  un solo modelo en memoria; el de chat y el de vectores se turnan
#   OLLAMA_NUM_PARALLEL       una petición a la vez: la memoria de contexto no se multiplica
#   OLLAMA_KEEP_ALIVE         libera la memoria a los 2 minutos sin uso (por defecto son 5)
#   OLLAMA_CONTEXT_LENGTH     contexto por defecto igual al que pide el agente
#   OLLAMA_KV_CACHE_TYPE      contexto en 8 bits: cerca de la mitad de memoria que en 16
#   OLLAMA_FLASH_ATTENTION    lo necesita el ajuste anterior y reduce el cómputo
#   OLLAMA_MAX_QUEUE          cola corta: si se satura rechaza en vez de acumular
ENV OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_MODELS=/ollama/models \
    HOME=/ollama \
    OLLAMA_MAX_LOADED_MODELS=1 \
    OLLAMA_NUM_PARALLEL=1 \
    OLLAMA_KEEP_ALIVE=2m \
    OLLAMA_CONTEXT_LENGTH=4096 \
    OLLAMA_KV_CACHE_TYPE=q8_0 \
    OLLAMA_FLASH_ATTENTION=1 \
    OLLAMA_MAX_QUEUE=16

# Sin privilegios de administrador dentro del contenedor
USER 1000
VOLUME /ollama
EXPOSE 11434

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ollama list >/dev/null || exit 1

ENTRYPOINT ["/usr/local/bin/iniciar-modelos"]
