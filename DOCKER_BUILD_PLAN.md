# 🐳 Docker Build Plan для x0tta6bl4 v3.4.0

**Дата:** 2026-01-05  
**Статус:** 🟢 READY TO BUILD  
**Версия:** 3.4.0

---

## 📋 Prerequisites Check

### ✅ Проверено
- [x] Dockerfile обновлён до версии 3.4.0
- [x] requirements.txt существует
- [x] .dockerignore настроен
- [x] Docker установлен (версия 29.1.3)
- [x] Диск: 6.6G свободно (94% занято, но достаточно для build)

### ⚠️ Предупреждения
- Диск заполнен на 94% - рекомендуется освободить место перед build
- Docker использует 20.4GB (можно освободить 4.278GB)
- Build может занять 15-30 минут в зависимости от зависимостей

---

## 🚀 Build Process

### Step 1: Подготовка (Jan 5)

**Очистка Docker (опционально, если нужно место):**
```bash
# Удалить dangling images
docker image prune -f

# Удалить неиспользуемые build cache (осторожно!)
docker builder prune -f --filter "until=24h"
```

**Проверка готовности:**
```bash
# Проверить Dockerfile
cat Dockerfile | head -10

# Проверить requirements.txt
wc -l requirements.txt

# Проверить .dockerignore
cat .dockerignore
```

### Step 2: Build Image

**Вариант A: Использовать скрипт (рекомендуется)**
```bash
cd /mnt/AC74CC2974CBF3DC
./scripts/build_docker_image.sh 3.4.0
```

**Вариант B: Прямой build**
```bash
cd /mnt/AC74CC2974CBF3DC
docker build \
  --tag x0tta6bl4:3.4.0 \
  --tag x0tta6bl4:latest \
  --file Dockerfile \
  --progress=plain \
  .
```

**Ожидаемое время:** 15-30 минут (зависит от зависимостей и скорости сети)

### Step 3: Verify Build

**Проверка образа:**
```bash
# Проверить, что image создан
docker images x0tta6bl4:3.4.0

# Проверить размер
docker images x0tta6bl4:3.4.0 --format "{{.Size}}"

# Проверить метаданные
docker inspect x0tta6bl4:3.4.0 | grep -A 5 Labels
```

**Тест образа (опционально):**
```bash
# Запустить контейнер для теста
docker run --rm -it \
  -p 8080:8080 \
  -e ENVIRONMENT=development \
  x0tta6bl4:3.4.0 \
  python -m src.core.app

# Проверить health endpoint
curl http://localhost:8080/health
```

### Step 4: Load в kind Cluster

**После успешного build:**
```bash
# Load image в staging cluster
kind load docker-image x0tta6bl4:3.4.0 --name x0tta6bl4-staging

# Verify image loaded
docker exec -it x0tta6bl4-staging-control-plane crictl images | grep x0tta6bl4
```

---

## 🔍 Troubleshooting

### Проблема: Build fails на requirements.txt

**Решение:**
```bash
# Проверить зависимости
pip install -r requirements.txt --dry-run

# Проверить конфликты версий
pip check
```

### Проблема: Недостаточно места на диске

**Решение:**
```bash
# Очистить Docker
docker system prune -a --volumes

# Удалить старые images
docker image prune -a --filter "until=7d"
```

### Проблема: Build слишком долгий

**Решение:**
- Использовать Docker BuildKit для кэширования
- Проверить сеть (pip install может быть медленным)
- Использовать multi-stage build для оптимизации

---

## ✅ Success Criteria

- [ ] Docker image `x0tta6bl4:3.4.0` создан
- [ ] Image имеет правильные метаданные (version: 3.4.0)
- [ ] Image загружен в kind cluster
- [ ] Image может быть использован в Helm deployment

---

## 📝 Next Steps After Build

1. Load image в kind: `kind load docker-image x0tta6bl4:3.4.0 --name x0tta6bl4-staging`
2. Deploy via Helm: `helm upgrade --install x0tta6bl4-staging ./helm/x0tta6bl4 -f values-staging.yaml`
3. Verify deployment: `kubectl get pods -n x0tta6bl4-staging`

---

**Версия:** 1.0  
**Создано:** Jan 5, 00:30 CET  
**Статус:** 🟢 READY TO BUILD

