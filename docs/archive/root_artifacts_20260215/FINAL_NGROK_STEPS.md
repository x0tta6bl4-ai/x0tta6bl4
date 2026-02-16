# 🚀 Финальные шаги: Получить Live Demo URL

**Статус**: ✅ HTTP сервер запущен на порту 8000

---

## ✅ Текущий статус

- **Локальный URL**: http://localhost:8000/causal-dashboard.html
- **Сервер**: Python HTTP Server (статичные файлы)
- **Готово для**: Ngrok tunnel

---

## 🌐 Шаг 1: Настроить Ngrok (если еще не настроен)

### Получить Authtoken:

1. **Откройте**: https://dashboard.ngrok.com/signup
2. **Зарегистрируйтесь** (бесплатно, 30 секунд)
3. **Получите authtoken**: https://dashboard.ngrok.com/get-started/your-authtoken
4. **Скопируйте токен**

### Аутентификация:

```bash
ngrok config add-authtoken ВАШ_ТОКЕН_ЗДЕСЬ
```

---

## 🚀 Шаг 2: Запустить Ngrok Tunnel

**В новом терминале** (сервер уже работает в фоне):

```bash
ngrok http 8000
```

---

## 📋 Шаг 3: Получить Demo URL

Ngrok покажет:
```
Session Status: online
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8000
```

**Ваш demo URL**: `https://xxxxx.ngrok.io/causal-dashboard.html`

---

## ✅ Шаг 4: Проверка

1. Откройте demo URL в браузере
2. Страница должна загрузиться
3. Dashboard должен отображаться

⚠️ **Note**: "Load Demo Incident" кнопка требует API endpoints (FastAPI).
Для email preview достаточно статичного dashboard.

---

## 📧 Шаг 5: Email Integration

1. **Скопируйте demo URL**
   ```
   https://xxxxx.ngrok.io/causal-dashboard.html
   ```

2. **Откройте** `EMAIL_TEMPLATE_V3.md`

3. **Замените**:
   - `[DEMO_LINK]` → ваш ngrok URL
   - `[Name]` → имя получателя

4. **Готово к отправке!**

---

## 🆘 Troubleshooting

**Проблема**: "Port 8000 already in use"
```bash
lsof -ti:8000 | xargs kill -9
```

**Проблема**: "ngrok: command not found"
```bash
# Установка (если нужно)
curl -L https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz | tar xz
sudo mv ngrok /usr/local/bin/
```

**Проблема**: "authentication failed"
```bash
# Получите новый token
ngrok config add-authtoken YOUR_NEW_TOKEN
```

---

## 🎯 Альтернатива: Если ngrok не работает

### Вариант A: Скриншоты локального demo

```bash
# Сервер уже работает
# Откройте: http://localhost:8000/causal-dashboard.html
# Сделайте скриншоты/GIF
# В email: "Live demo coming soon"
```

### Вариант B: GitHub Pages

```bash
./scripts/deploy_demo.sh github-pages
```

---

**Готово!** Запустите `ngrok http 8000` и получите live URL 🚀

