# 🎯 QUICK START — Copy & Paste Commands

## ✅ VERIFY EVERYTHING IS WORKING (30 seconds)

```bash
cd /mnt/AC74CC2974CBF3DC
docker compose -f staging/docker-compose.quick.yml ps
```

**Expected output**: All 5 services should show `Up` or `Healthy`

---

## 🌐 OPEN IN BROWSER (Instant Access)

### Option 1: Interactive API Docs (Recommended)
```
http://localhost:8000/docs
```
- Swagger UI with all endpoints
- Try out endpoints directly
- See request/response examples

### Option 2: Alternative API Docs
```
http://localhost:8000/redoc
```
- ReDoc format (cleaner layout)
- Same endpoints, different view

### Option 3: Monitoring Dashboard
```
http://localhost:3000
```
- Grafana dashboards
- Login: `admin` / `admin`
- View system metrics

### Option 4: Prometheus Metrics
```
http://localhost:9090
```
- Raw metrics storage
- Query builder
- Scrape targets

---

## 🧪 TEST API FROM COMMAND LINE

### Health Check
```bash
curl http://localhost:8000/health | python -m json.tool
```

**Expected**: 200 OK with JSON response

### List Endpoints
```bash
curl http://localhost:8000/docs
```

### Get Mesh Status
```bash
curl http://localhost:8000/api/mesh/status | python -m json.tool
```

### Export Metrics
```bash
curl http://localhost:8000/metrics
```

---

## 🛑 STOP & START SERVICES

### Stop all services
```bash
docker compose -f staging/docker-compose.quick.yml down
```

### Start all services (background)
```bash
docker compose -f staging/docker-compose.quick.yml up -d
```

### Start and watch logs
```bash
docker compose -f staging/docker-compose.quick.yml up
```
(Press Ctrl+C to stop)

### View logs for specific service
```bash
# API logs
docker logs -f x0tta6bl4-api

# Database logs
docker logs -f x0tta6bl4-db

# Redis logs
docker logs -f x0tta6bl4-redis
```

---

## 🔧 REBUILD AFTER CODE CHANGES

### Rebuild just the API image
```bash
docker compose -f staging/docker-compose.quick.yml build api
docker compose -f staging/docker-compose.quick.yml up -d api
```

### Full rebuild (all services)
```bash
docker compose -f staging/docker-compose.quick.yml build --no-cache
docker compose -f staging/docker-compose.quick.yml up -d
```

---

## 💾 DATABASE ACCESS

### Connect to PostgreSQL
```bash
docker exec -it x0tta6bl4-db psql -U x0tta6bl4 -d x0tta6bl4_db
```

### Run SQL queries
```bash
docker exec x0tta6bl4-db psql -U x0tta6bl4 -d x0tta6bl4_db -c "SELECT * FROM users LIMIT 5;"
```

---

## 💾 REDIS ACCESS

### Connect to Redis CLI
```bash
docker exec -it x0tta6bl4-redis redis-cli
```

### Run Redis commands
```bash
docker exec x0tta6bl4-redis redis-cli PING
docker exec x0tta6bl4-redis redis-cli KEYS "*"
docker exec x0tta6bl4-redis redis-cli DBSIZE
```

---

## 📊 SYSTEM HEALTH CHECK

```bash
# Check all containers
docker compose -f staging/docker-compose.quick.yml ps

# Check container resource usage
docker stats

# View network
docker network ls

# Check volumes
docker volume ls
```

---

## 🔍 TROUBLESHOOTING

### API crashing?
```bash
# Check error
docker logs x0tta6bl4-api | tail -50

# Check specific error
docker logs x0tta6bl4-api | grep -i error

# Restart API
docker compose -f staging/docker-compose.quick.yml restart api
```

### Port already in use?
```bash
# Find what's using the port
lsof -i :8000

# Kill the process
pkill -f uvicorn

# Or use Docker compose down
docker compose -f staging/docker-compose.quick.yml down
```

### Database won't connect?
```bash
# Check database logs
docker logs x0tta6bl4-db

# Check if database is running
docker exec x0tta6bl4-db pg_isready

# Restart database
docker compose -f staging/docker-compose.quick.yml restart db
```

---

## 📈 PERFORMANCE CHECK

```bash
# Response time
time curl -s http://localhost:8000/health > /dev/null

# Container memory usage
docker stats --no-stream

# Disk usage
docker system df
```

---

## 🚀 DEPLOY TO CLOUD (Next Phase)

### Using Docker Hub
```bash
docker tag staging-api username/x0tta6bl4-api:latest
docker push username/x0tta6bl4-api:latest
```

### Using Kubernetes
```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

### Using Docker Swarm
```bash
docker swarm init
docker stack deploy -c staging/docker-compose.quick.yml x0tta6bl4
```

---

## 📝 COMMON CURL COMMANDS

```bash
# Get health
curl http://localhost:8000/health

# Get API docs JSON
curl http://localhost:8000/openapi.json

# Get metrics
curl http://localhost:8000/metrics

# Test endpoint with JSON
curl -X POST http://localhost:8000/api/endpoint \
  -H "Content-Type: application/json" \
  -d '{"key": "value"}'

# Follow redirect
curl -L http://localhost:8000/docs

# Show headers
curl -i http://localhost:8000/health

# Verbose output
curl -v http://localhost:8000/health
```

---

## ✨ SUCCESS INDICATORS

You'll know everything is working when:

✅ `docker compose ps` shows 5 containers with `Up` status  
✅ http://localhost:8000/health returns JSON  
✅ http://localhost:8000/docs loads in browser  
✅ http://localhost:3000 shows Grafana dashboard  
✅ No errors in `docker logs`  

---

## 🎓 WHAT'S RUNNING

| Service | Port | Tech |
|---------|------|------|
| FastAPI | 8000 | Python + Uvicorn |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Cache |
| Prometheus | 9090 | Metrics |
| Grafana | 3000 | Dashboards |

---

**You're all set! Pick any browser link above and start exploring. 🚀**
