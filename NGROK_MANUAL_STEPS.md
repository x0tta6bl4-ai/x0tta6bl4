# Ngrok Manual Setup - Пошаговая инструкция

**Статус**: Сервер запущен на http://localhost:8000 ✅

**Следующий шаг**: Настроить ngrok tunnel

---

## 🔐 Шаг 1: Получить Ngrok Authtoken (2 минуты)

1. **Откройте**: https://dashboard.ngrok.com/signup
2. **Зарегистрируйтесь** (бесплатно, 30 секунд)
3. **Получите authtoken**: https://dashboard.ngrok.com/get-started/your-authtoken
4. **Скопируйте токен**

---

## 🚀 Шаг 2: Аутентификация Ngrok

```bash
ngrok config add-authtoken YOUR_AUTHTOKEN
```

Замените `YOUR_AUTHTOKEN` на токен из шага 1.

---

## 🌐 Шаг 3: Запустить Ngrok Tunnel

**В новом терминале:**

```bash
ngrok http 8000
```

Вы увидите:
```
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8000
```

**Ваш demo URL**: `https://xxxxx.ngrok.io/demo/causal-dashboard.html`

---

## ✅ Шаг 4: Проверка

1. Откройте demo URL в браузере
2. Нажмите "🚀 Load Demo Incident"
3. Проверьте что всё работает

---

## 📧 Шаг 5: Использование в Email

Скопируйте demo URL и вставьте в `EMAIL_TEMPLATE_V3.md`:

```
[DEMO_LINK] → https://xxxxx.ngrok.io/demo/causal-dashboard.html
```

---

## 🆘 Если что-то не работает

**Проверьте что сервер работает:**
```bash
curl http://localhost:8000/health
```

**Проверьте ngrok:**
```bash
curl http://localhost:4040/api/tunnels
```

**Остановить процессы:**
```bash
pkill -f "src.core.app"
pkill ngrok
```

---

**Готово!** После получения authtoken, запустите `ngrok http 8000` 🚀

