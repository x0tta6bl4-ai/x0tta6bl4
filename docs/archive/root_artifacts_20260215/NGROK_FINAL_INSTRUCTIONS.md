# 🚀 Финальные инструкции: Получить Live Demo URL

**Статус**: ✅ Готово к запуску

---

## ⚡ Быстрый способ (2 команды)

### Шаг 1: Запустить простой сервер

```bash
cd /mnt/AC74CC2974CBF3DC
./START_DEMO_SERVER.sh
```

Или вручную:
```bash
cd /mnt/AC74CC2974CBF3DC/web/demo
python3 -m http.server 8000
```

**Локальный URL**: http://localhost:8000/causal-dashboard.html

---

### Шаг 2: Запустить Ngrok (в новом терминале)

```bash
# Если authtoken не настроен:
# 1. https://dashboard.ngrok.com/signup
# 2. Получите authtoken
ngrok config add-authtoken YOUR_TOKEN

# Запустить tunnel:
ngrok http 8000
```

**Результат**: Скопируйте URL из вывода ngrok
```
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8000
```

**Ваш demo URL**: `https://xxxxx.ngrok.io/causal-dashboard.html`

---

## ✅ Проверка

1. Откройте demo URL в браузере
2. Нажмите "🚀 Load Demo Incident"
3. ⚠️ **Note**: API endpoints не будут работать (только статика)
4. Но dashboard отображается и выглядит профессионально

---

## 📧 Email Integration

Скопируйте URL и вставьте в `EMAIL_TEMPLATE_V3.md`:
```
[DEMO_LINK] → https://xxxxx.ngrok.io/causal-dashboard.html
```

**В email укажите**: "Interactive dashboard (API endpoints require full server deployment)"

---

## 🎯 Альтернатива: Полный сервер с API

Если нужны API endpoints (для "Load Demo" кнопки):

```bash
# Установить зависимости
cd /mnt/AC74CC2974CBF3DC
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn

# Запустить полный сервер
python3 -m src.core.app
```

Затем ngrok как обычно.

---

## 🆘 Troubleshooting

**Проблема**: Port 8000 занят
```bash
pkill -f "http.server"
```

**Проблема**: Ngrok требует authtoken
```bash
# Получите здесь: https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_TOKEN
```

---

**Готово!** Запустите `./START_DEMO_SERVER.sh` и затем `ngrok http 8000` 🚀

