# ✅ Готово к Ngrok!

**Статус**: Сервер запущен и работает ✅

**Локальный URL**: http://localhost:8000/demo/causal-dashboard.html

---

## 🚀 Следующий шаг: Запустить Ngrok

### Вариант 1: Автоматический (если authtoken уже настроен)

```bash
ngrok http 8000
```

### Вариант 2: Сначала настроить authtoken

1. **Откройте**: https://dashboard.ngrok.com/signup
2. **Зарегистрируйтесь** (бесплатно)
3. **Получите authtoken**: https://dashboard.ngrok.com/get-started/your-authtoken
4. **Аутентификация**:
   ```bash
   ngrok config add-authtoken YOUR_AUTHTOKEN
   ```
5. **Запустите**:
   ```bash
   ngrok http 8000
   ```

---

## 📋 После запуска ngrok

Ngrok покажет:
```
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8000
```

**Ваш demo URL**: `https://xxxxx.ngrok.io/demo/causal-dashboard.html`

---

## ✅ Проверка

1. Откройте demo URL в браузере
2. Нажмите "🚀 Load Demo Incident"
3. Проверьте animations

---

## 📧 Email Integration

Скопируйте URL и вставьте в `EMAIL_TEMPLATE_V3.md`:
```
[DEMO_LINK] → https://xxxxx.ngrok.io/demo/causal-dashboard.html
```

---

**Готово!** Запустите `ngrok http 8000` и получите live URL 🚀

