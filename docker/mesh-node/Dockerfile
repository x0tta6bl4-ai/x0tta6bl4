# x0tta6bl4 Mesh Node
# Легковесный контейнер для mesh узла

FROM python:3.12-slim

LABEL maintainer="x0tta6bl4"
LABEL description="x0tta6bl4 Mesh Node with Discovery, Obfuscation, Traffic Shaping"

# Установка зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    iproute2 \
    iputils-ping \
    net-tools \
    tcpdump \
    && rm -rf /var/lib/apt/lists/*

# Рабочая директория
WORKDIR /app

# Копируем requirements
COPY docker/mesh-node/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY src/ ./src/

# Переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Порты
# 5000 - mesh service
# 7777 - multicast discovery
EXPOSE 5000/udp
EXPOSE 7777/udp

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import socket; s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); s.bind(('',0)); print('OK')" || exit 1

# Entrypoint
COPY docker/mesh-node/entrypoint.py /entrypoint.py
ENTRYPOINT ["python3", "/entrypoint.py"]
