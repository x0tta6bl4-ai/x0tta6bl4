# Ngrok Quick Start - 5 минут до Live Demo

**Цель**: Получить live HTTPS URL для email wave 3-4

---

## 🚀 Автоматический запуск (рекомендуется)

```bash
cd /mnt/AC74CC2974CBF3DC
./QUICK_NGROK_SETUP.sh
```

Скрипт сделает всё автоматически:
- Установит ngrok (если нет)
- Настроит аутентификацию
- Запустит сервер
- Создаст tunnel
- Покажет demo URL

---

## 📋 Ручной запуск (если скрипт не работает)

### Шаг 1: Установка ngrok (2 минуты)

```bash
# Linux x86_64
curl -L https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -o ngrok.tgz
tar -xzf ngrok.tgz
sudo mv ngrok /usr/local/bin/

# Или Linux ARM64
curl -L https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz -o ngrok.tgz
tar -xzf ngrok.tgz
sudo mv ngrok /usr/local/bin/

# Проверка
ngrok version
```

### Шаг 2: Регистрация (1 минута)

1. Откройте: https://dashboard.ngrok.com/signup
2. Зарегистрируйтесь (бесплатно)
3. Получите authtoken: https://dashboard.ngrok.com/get-started/your-authtoken

### Шаг 3: Аутентификация

```bash
ngrok config add-authtoken YOUR_AUTHTOKEN
```

### Шаг 4: Запуск (2 минуты)

**Терминал 1: Запустить сервер**
```bash
cd /mnt/AC74CC2974CBF3DC
python3 -m src.core.app
```

**Терминал 2: Запустить ngrok**
```bash
ngrok http 8000
```

### Шаг 5: Получить URL

Ngrok покажет:
```
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8000
```

**Ваш demo URL**: `https://xxxxx.ngrok.io/demo/causal-dashboard.html`

---

## ✅ Проверка

1. Откройте demo URL в браузере
2. Нажмите "🚀 Load Demo Incident"
3. Проверьте:
   - [ ] Timeline анимируется
   - [ ] Dependency graph отображается
   - [ ] Root causes показываются
   - [ ] Metrics обновляются

---

## 📧 Использование в Email

Скопируйте demo URL и вставьте в `EMAIL_TEMPLATE_V3.md`:

```
[DEMO_LINK] → https://xxxxx.ngrok.io/demo/causal-dashboard.html
```

---

## ⚠️ Важные замечания

### Ограничения Free Tier:

- ✅ URL работает 24 часа
- ✅ HTTPS автоматически
- ✅ Работает через VPN
- ⚠️ URL меняется после перезапуска
- ⚠️ Rate limits (но достаточно для demo)

### Для Production:

После email wave 3-4 переключитесь на VPS:
```bash
./scripts/deploy_vps.sh
```

---

## 🆘 Troubleshooting

**Проблема**: "ngrok: command not found"
```bash
# Проверьте PATH
echo $PATH

# Добавьте в PATH (если установлен в ~/.local/bin)
export PATH="$HOME/.local/bin:$PATH"
```

**Проблема**: "authtoken invalid"
```bash
# Получите новый token
# https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken NEW_TOKEN
```

**Проблема**: "Port 8000 already in use"
```bash
# Найти процесс
lsof -i :8000

# Остановить
kill -9 PID
```

**Проблема**: "Connection refused"
```bash
# Проверить что сервер запущен
curl http://localhost:8000/health

# Если не работает, запустите вручную
python3 -m src.core.app
```

---

## 🎯 Альтернатива: GitHub Pages (если ngrok не работает)

Если ngrok не работает, используйте статичный вариант:

```bash
./scripts/deploy_demo.sh github-pages
```

⚠️ Но "Load Demo" кнопка не будет работать полностью (нет API)

---

## 📊 Мониторинг

**Ngrok Dashboard** (локально):
```
http://localhost:4040
```

Показывает:
- Requests
- Response times
- Errors

---

**Готово!** У вас есть live demo URL за 5 минут 🚀

