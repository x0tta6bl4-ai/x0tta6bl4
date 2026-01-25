#!/bin/bash
echo "=== Docker Networking Diagnostics ==="

echo -e "\n1. Container Status:"
docker compose ps

echo -e "\n2. Port Mappings:"
docker port node-a
docker port node-b
docker port node-c

echo -e "\n3. Host Listening Ports:"
netstat -tuln 2>/dev/null | grep -E '8000|8001|8002' || ss -tuln | grep -E '8000|8001|8002'

echo -e "\n4. Container IPs:"
docker inspect -f '{{.Name}} - {{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' node-a node-b node-c

echo -e "\n5. Internal curl (from inside container):"
docker exec node-a curl -s -o /dev/null -w "node-a internal: %{http_code}\n" http://localhost:8000/health

echo -e "\n6. External curl (from host):"
curl -s -o /dev/null -w "node-a external: %{http_code}\n" http://localhost:8000/health || echo "External curl failed with exit code $?"

echo -e "\n7. Process inside container:"
docker exec node-a ps aux | grep -E 'python|uvicorn|yggdrasil'

echo -e "\n8. Network listening inside container:"
docker exec node-a netstat -tuln 2>/dev/null | grep -E '8000|9090' || docker exec node-a ss -tuln | grep -E '8000|9090'

echo -e "\n9. Docker network inspect:"
docker network inspect ac74cc2974cbf3dc_mesh 2>/dev/null | grep -A 20 '"Containers"' || echo "Network inspection failed"

echo -e "\n10. Firewall rules (if Linux):"
if command -v iptables &> /dev/null; then
  sudo iptables -L -n 2>/dev/null | grep -E '8000|8001|8002' || echo "No firewall rules found for ports 8000-8002"
fi

echo -e "\n11. Docker version info:"
docker version | head -n 10

echo -e "\n12. Docker daemon settings:"
docker info | grep -E "Operating System|OSType|Architecture|CPUs|Total Memory"
