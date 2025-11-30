# ✅ Demo Server Ready!

**Статус**: HTTP сервер запущен ✅

---

## 🌐 Локальный доступ

**Demo URL**: http://localhost:8000/causal-dashboard.html

(Без `/demo/` префикса, так как сервер запущен из директории `web/demo`)

---

## 🚀 Следующий шаг: Ngrok

### В новом терминале:

```bash
# 1. Если authtoken не настроен:
#    Откройте: https://dashboard.ngrok.com/signup
#    Получите authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_AUTHTOKEN

# 2. Запустить tunnel:
ngrok http 8000
```

### Результат:

Ngrok покажет:
```
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8000
```

**Ваш demo URL**: `https://xxxxx.ngrok.io/causal-dashboard.html`

---

## ✅ Проверка

1. Откройте demo URL в браузере
2. Страница должна загрузиться
3. ⚠️ **Note**: "Load Demo" кнопка требует API (FastAPI server)
4. Но dashboard выглядит профессионально для email preview

---

## 📧 Email

Скопируйте URL и вставьте в `EMAIL_TEMPLATE_V3.md`:
```
[DEMO_LINK] → https://xxxxx.ngrok.io/causal-dashboard.html
```

---

## 🆘 Если нужно полный функционал (с API)

```bash
# Установить зависимости
cd /mnt/AC74CC2974CBF3DC
source .venv/bin/activate  # если есть venv
pip install fastapi uvicorn

# Запустить полный сервер
python3 -m src.core.app
```

Затем ngrok как обычно.

---

**Готово!** Запустите `ngrok http 8000` в новом терминале 🚀

