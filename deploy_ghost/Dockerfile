FROM projects-ghost-vpn-server:latest
WORKDIR /app
COPY ghost_pulse_vpn.py .
COPY src/network/transport/ghost_pulse_transport.py ./src/network/transport/
ENTRYPOINT ["python3", "ghost_pulse_vpn.py"]
CMD ["server"]
