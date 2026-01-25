# ✅ Готово к Ngrok!

**Статус**: Demo сервер запущен ✅

**Локальный URL**: http://localhost:8080/causal-dashboard.html

---

## 🚀 Запустить Ngrok (2 команды)

### 1. Настроить authtoken (если еще не настроен)

```bash
# Получите authtoken: https://dashboard.ngrok.com/get-started/your-authtoken
ngrok config add-authtoken YOUR_AUTHTOKEN
```

### 2. Запустить tunnel

```bash
ngrok http 8080
```

**Важно**: Используйте порт **8080**, не 8000!

---

## 📋 Результат

Ngrok покажет:
```
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8080
```

**Ваш demo URL**: `https://xxxxx.ngrok.io/causal-dashboard.html`

---

## ✅ Проверка

1. Откройте demo URL
2. Dashboard должен загрузиться
3. Страница выглядит профессионально

⚠️ **Note**: "Load Demo" кнопка требует API (можно добавить позже).
Для email preview достаточно статичного dashboard.

---

## 📧 Email

Скопируйте URL в `EMAIL_TEMPLATE_V3.md`:
```
[DEMO_LINK] → https://xxxxx.ngrok.io/causal-dashboard.html
```

---

**Готово!** Запустите `ngrok http 8080` 🚀

