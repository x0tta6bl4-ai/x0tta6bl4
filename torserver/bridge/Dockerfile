FROM python:3.12-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY lampa_parser_bridge.py /app/lampa_parser_bridge.py
EXPOSE 8090
CMD ["python", "/app/lampa_parser_bridge.py"]
