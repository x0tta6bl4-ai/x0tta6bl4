# x0tta6bl4 Quick Start — Minimal Mesh Node
# Без SPIRE, без внешних зависимостей. Только mesh + validation.

FROM python:3.12-slim

WORKDIR /app

# Копируем только необходимое
COPY src/ /app/src/
COPY mesh_node.py /app/mesh_node.py

ENV PYTHONPATH=/app
ENV HTTP_PROXY=""
ENV HTTPS_PROXY=""
ENV http_proxy=""
ENV https_proxy=""
ENV ALL_PROXY=""
ENV all_proxy=""
ENV NO_PROXY="*"
ENV no_proxy="*"

# Минимальные зависимости
RUN HTTP_PROXY="" HTTPS_PROXY="" http_proxy="" https_proxy="" ALL_PROXY="" all_proxy="" pip install --no-cache-dir prometheus-client aiohttp

EXPOSE 9090 8080

CMD ["python3", "-u", "/app/mesh_node.py"]
