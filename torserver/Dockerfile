FROM debian:bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl ffmpeg \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/torrserver \
    && curl -fsSL \
      -o /opt/torrserver/TorrServer-linux-amd64 \
      https://github.com/YouROK/TorrServer/releases/latest/download/TorrServer-linux-amd64 \
    && chmod +x /opt/torrserver/TorrServer-linux-amd64

EXPOSE 8090
VOLUME ["/opt/ts"]

ENTRYPOINT ["/opt/torrserver/TorrServer-linux-amd64"]
CMD ["--port", "8090", "--path", "/opt/ts"]
