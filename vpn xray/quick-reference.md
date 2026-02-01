# 🚀 x0tta6bl4: WARP + Xray Quick Reference Guide

## 📋 Быстрые Команды для Решения Проблем

### 🔧 SSH Connection (Спасение)
```bash
# SSH на сервер
SSH_PASS="lH7SEcWM812blV50sz"
SSH_USER="root"
SSH_HOST="89.125.1.107"

# Быстрое подключение
sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no $SSH_USER@$SSH_HOST

# Или используй алиас
alias x0tta='sshpass -p "lH7SEcWM812blV50sz" ssh -o StrictHostKeyChecking=no root@89.125.1.107'
x0tta  # просто так
```

---

## 🔍 ДИАГНОСТИКА

### WARP Status
```bash
# Проверить статус WARP
warp-cli --accept-tos status

# Проверить режим
warp-cli --accept-tos mode

# Проверить proxy port
ss -tulnp | grep warp
ss -tulnp | grep 40000

# Подробная информация
warp-cli --accept-tos show-config

# Логи WARP
journalctl -u warp-svc -f
```

### Xray Status
```bash
# Проверить контейнер
docker ps | grep x0t-node
docker stats x0t-node

# Проверить если слушает на порту
ss -tulnp | grep 10809

# Проверить конфиг
cat /usr/local/etc/xray/config.json | jq .

# Тест конфига
docker exec x0t-node xray test -c /etc/xray/config.json

# Логи (последние 50 строк)
docker logs x0t-node --tail 50

# Логи в реальном времени
docker logs x0t-node -f

# Логи с ошибками
docker logs x0t-node --tail 100 | grep -i error
```

### iptables Rules
```bash
# Показать все правила
sudo iptables -t mangle -L -v

# Показать только XRAY_WARP цепь
sudo iptables -t mangle -L XRAY_WARP -v

# Показать правила с номерами (для удаления)
sudo iptables -t mangle -L --line-numbers

# Проверить GID
getent group xray_warp

# Проверить marked packets
sudo iptables -t mangle -L -v -x | grep MARK
```

### DNS Check
```bash
# Текущие nameservers
cat /etc/resolv.conf

# Тест разрешения
dig google.com
dig @1.1.1.1 google.com
dig @8.8.8.8 google.com

# Проверить утечки DNS
nslookup google.com
nslookup google.com 1.1.1.1
nslookup google.com 8.8.8.8
```

### Network Connectivity
```bash
# Проверить слушащие порты
ss -tlnp

# Активные соединения
ss -anp | grep ESTABLISHED

# Трафик на WARP порт
tcpdump -i lo -n 'port 40000' -A | head -50

# Трафик на Xray порт
tcpdump -i lo -n 'port 10809' -A | head -50

# Проверить доступность WARP SOCKS5
curl -v --socks5 127.0.0.1:40000 https://google.com

# Проверить IP через WARP
curl --socks5 127.0.0.1:40000 https://ifconfig.me
```

---

## 🔨 ИСПРАВЛЕНИЯ

### Проблема: Google Блокирует

**Признак:**
```
curl: (56) Received HTTP/0.9 when not allowed, or
403 Forbidden, или
HTTP/0.0 400 Bad Request
```

**Решение 1: Проверить WARP**
```bash
# WARP должен быть в proxy mode
warp-cli --accept-tos mode proxy

# Убедиться что WARP connected
warp-cli --accept-tos connect

# Проверить listening
ss -tulnp | grep 40000

# Если не слушает - перезагрузить WARP
systemctl restart warp-svc
```

**Решение 2: Проверить Xray routing**
```bash
# Убедиться что Google domains есть в routing rules
cat /usr/local/etc/xray/config.json | jq '.routing.rules[] | select(.domain | strings | select(test("goog|google|youtube")))'

# Должно вывести что-то вроде:
# {
#   "type": "field",
#   "outboundTag": "warp-google",
#   "domain": ["goog", "googleapis.com", "google.com", ...]
# }

# Если нет - добавить правило (см. файл warp-xray-integration.md)
```

**Решение 3: Перезагрузить Xray**
```bash
docker restart x0t-node
sleep 3
docker logs x0t-node --tail 20
```

---

### Проблема: DNS Не Работает

**Признак:**
```
nslookup: can't resolve 'google.com'
```

**Решение:**
```bash
# Установить правильные nameservers
echo "nameserver 1.1.1.1" | sudo tee /etc/resolv.conf
echo "nameserver 8.8.8.8" | sudo tee -a /etc/resolv.conf

# Сделать immutable
sudo chattr +i /etc/resolv.conf

# Проверить
cat /etc/resolv.conf
dig google.com
```

---

### Проблема: WARP Не Подключается

**Признак:**
```
Status: Disconnected
```

**Решение:**
```bash
# Переключить в proxy mode
warp-cli --accept-tos mode proxy

# Подключиться
warp-cli --accept-tos connect

# Проверить статус
warp-cli --accept-tos status

# Если не работает - перезагрузить сервис
systemctl restart warp-svc

# Или перезагрузить контейнер
docker restart warp-svc  # если в контейнере

# Проверить логи
journalctl -u warp-svc -n 50
```

---

### Проблема: Xray Не Запускается

**Признак:**
```
docker: Error response from daemon: Container x0t-node is not running
```

**Решение:**
```bash
# Проверить логи
docker logs x0t-node --tail 50

# Проверить конфиг JSON
docker exec x0t-node xray test -c /etc/xray/config.json

# Если JSON ошибка - исправить конфиг
cat /usr/local/etc/xray/config.json | jq .

# Если нужно полностью пересоздать контейнер
docker stop x0t-node
docker rm x0t-node
docker run -d --name x0t-node \
  -v /usr/local/etc/xray:/etc/xray \
  -p 10809:10809 \
  x0tta6bl4-app:staging

# Проверить
docker ps | grep x0t-node
docker logs x0t-node
```

---

### Проблема: iptables Rules Не Работают

**Признак:**
```
iptables -t mangle -L XRAY_WARP
# Table 'mangle' does not exist
```

**Решение:**
```bash
# Создать правила заново
GID=$(getent group xray_warp | cut -d: -f3 || echo "23333")

# Создать цепь
sudo iptables -t mangle -N XRAY_WARP 2>/dev/null || true

# Добавить правила
sudo iptables -t mangle -A XRAY_WARP -m owner --gid-owner $GID -j RETURN
sudo iptables -t mangle -A XRAY_WARP -p tcp --dport 40000 -j MARK --set-mark 0x1
sudo iptables -t mangle -A XRAY_WARP -p udp --dport 40000 -j MARK --set-mark 0x1

# Сохранить
sudo iptables-save | sudo tee /etc/iptables/rules.v4

# Проверить
sudo iptables -t mangle -L XRAY_WARP -v
```

---

## 🧪 ТЕСТИРОВАНИЕ

### Тест 1: Базовая Connectivity
```bash
# Тест WARP SOCKS5 прокси
curl -v --socks5 127.0.0.1:40000 https://google.com 2>&1 | head -20

# Тест IP адреса через WARP
curl --socks5 127.0.0.1:40000 https://ifconfig.me

# Должно вывести IP Cloudflare, НЕ 89.125.1.107
```

### Тест 2: Google Доступность
```bash
# Прямой тест
curl -I https://google.com

# Через WARP прокси
curl -I --socks5 127.0.0.1:40000 https://google.com

# Должно быть 200 или 301/302, а не 403
```

### Тест 3: DNS Утечки
```bash
# Тест резолюции
dig google.com

# Тест через конкретный DNS
dig @1.1.1.1 google.com

# Проверить IP утечки
curl https://ipleak.net
curl --socks5 127.0.0.1:40000 https://ipleak.net
```

### Тест 4: Xray Configuration
```bash
# Проверить что конфиг валиден
docker exec x0t-node xray test -c /etc/xray/config.json

# Вывод должен быть:
# configuration ok
```

### Тест 5: End-to-End (От Клиента)
```bash
# На клиенте (из Крыма) через VLESS:
# 1. Подключиться к серверу через VLESS+Reality
# 2. Проверить Google:
curl -I https://google.com
# Должно быть 200 OK (не 403)

# 3. Проверить IP:
curl https://ifconfig.me
# Должно показать Cloudflare IP (WARP), не 89.125.1.107

# 4. Проверить DNS leak:
curl https://ipleak.net
# Должно показать "No DNS leaks detected"
```

---

## 📊 МОНИТОРИНГ В РЕАЛЬНОМ ВРЕМЕНИ

### Все сразу (Dashboard)
```bash
# Terminal 1: Xray логи
docker logs x0t-node -f

# Terminal 2: Сетевой трафик
sudo watch -n 1 'ss -tnp | grep -E "(10809|40000)"'

# Terminal 3: iptables hits
sudo watch -n 1 'iptables -t mangle -L XRAY_WARP -v'

# Terminal 4: DNS резолюции
watch -n 5 'dig google.com @1.1.1.1 +short'
```

### CPU/Memory Xray
```bash
docker stats x0t-node --no-stream

# Или в реальном времени
docker stats x0t-node
```

### Активные соединения
```bash
# Посмотреть кто к нам подключается
watch -n 1 'ss -tnp | grep ESTABLISHED | tail -20'

# На порту 10809
watch -n 1 'ss -tnp | grep 10809'

# На порту 40000
watch -n 1 'ss -tnp | grep 40000'
```

---

## 🔐 SECURITY CHECK

### Firewall Ports
```bash
# Какие порты открыты наружу?
sudo ufw status

# Должны быть открыты только:
# 22 (SSH)
# 443 (VLESS Reality)
# 80 (HTTP redirect если нужно)

# Остальные внутренние:
# 10809 (Xray) - только localhost
# 40000 (WARP) - только localhost
# 3000 (Grafana)
# 9091 (Prometheus)
```

### Fail2ban Status
```bash
# Проверить бан лист
sudo fail2ban-client status sshd

# Посмотреть заблокированные IP
sudo fail2ban-client set sshd unbanip YOUR_IP  # разблокировать если нужно
```

### SSL Сертификаты
```bash
# Проверить Reality сертификаты
ls -la /usr/local/etc/xray/

# Если нужны новые:
docker exec x0t-node xray-cert -cn "*.microsoft.com" -ca
```

---

## 📝 КОНФИГУРАЦИЯ

### Где находятся файлы?

```bash
# Xray конфиг
/usr/local/etc/xray/config.json

# WARP конфиг
~/.config/Cloudflare-WARP/  (или /etc/warp-plus/)

# iptables rules
/etc/iptables/rules.v4

# DNS
/etc/resolv.conf

# Логи Xray
docker logs x0t-node

# Логи WARP
journalctl -u warp-svc
```

### Как редактировать Xray конфиг?

```bash
# Отредактировать локально
vim /tmp/config.json

# Или через SCP
scp /tmp/config.json root@89.125.1.107:/usr/local/etc/xray/config.json

# Проверить синтаксис
jq . /usr/local/etc/xray/config.json

# Перезагрузить
docker restart x0t-node
```

---

## 🚨 EMERGENCY COMMANDS

### Если всё сломалось
```bash
# 1. SSH на сервер
sshpass -p "lH7SEcWM812blV50sz" ssh -o StrictHostKeyChecking=no root@89.125.1.107

# 2. Убедиться что WARP running
warp-cli --accept-tos connect

# 3. Перезагрузить Xray
docker restart x0t-node

# 4. Проверить логи
docker logs x0t-node --tail 50

# 5. Если не помогает - восстановить backup
cp /usr/local/etc/xray/config.json.backup.TIMESTAMP /usr/local/etc/xray/config.json
docker restart x0t-node
```

### Полный reset
```bash
# Если нужно всё пересоздать:

# 1. Остановить контейнер
docker stop x0t-node

# 2. Удалить контейнер
docker rm x0t-node

# 3. Пересоздать контейнер
docker-compose -f /path/to/docker-compose.yml up -d x0t-node

# 4. Проверить
docker logs x0t-node

# Если всё совсем плохо - перезагрузить сервер
reboot
```

---

## 📞 SUPPORT MATRIX

| Problem | Command | Expected Output |
|---------|---------|-----------------|
| WARP не подключен | `warp-cli --accept-tos status` | Connected ✓ |
| Xray не запущен | `docker ps \| grep x0t-node` | x0t-node Running |
| DNS не работает | `dig @1.1.1.1 google.com +short` | IP address |
| Ports не слушают | `ss -tulnp \| grep 10809` | tcp LISTEN |
| Google блокирует | `curl -I https://google.com` | HTTP/1.1 200 OK |
| iptables сломаны | `iptables -t mangle -L` | мало ошибок |

---

## 🎓 TUTORIAL: Решение Типичной Проблемы

### Сценарий: Google Возвращает 403

```bash
# ШАГ 1: Диагностировать проблему
$ docker logs x0t-node --tail 20 | grep error
# Ищите сообщения об ошибках

# ШАГ 2: Проверить WARP
$ warp-cli --accept-tos status
# Должно показать "Connected"

# ШАГ 3: Проверить routing в config
$ cat /usr/local/etc/xray/config.json | jq '.routing.rules[] | select(.domain)'
# Должны быть Google domains

# ШАГ 4: Проверить outbounds
$ cat /usr/local/etc/xray/config.json | jq '.outbounds[] | select(.tag | contains("warp"))'
# Должны быть warp-google, warp-meta и т.д.

# ШАГ 5: Если всё конфигурировано правильно
# Перезагрузить Xray
$ docker restart x0t-node
$ sleep 3
$ docker logs x0t-node --tail 10

# ШАГ 6: Тестировать
$ curl -v --socks5 127.0.0.1:40000 https://google.com | head -20
# Должно быть 200 OK
```

---

**Дата обновления:** 2025-01-31  
**Версия:** 1.0  
**Для:** x0tta6bl4 mesh-архитектура
