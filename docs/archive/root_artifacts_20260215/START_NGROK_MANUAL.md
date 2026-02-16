# 🚀 Запустить Ngrok вручную

**Статус**: ✅ Authtoken настроен

---

## ⚡ Быстрый запуск

**В терминале выполните:**

```bash
ngrok http 8080
```

---

## 📋 Что вы увидите

Ngrok покажет примерно так:

```
ngrok

Session Status: online
Account: your-email@example.com
Version: 3.x.x
Region: United States (us)
Latency: 45ms
Web Interface: http://127.0.0.1:4040
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8080

Connections:
  ttl     opn     rt1     rt5     p50     p90
  0       0       0.00    0.00    0.00    0.00
```

---

## ✅ Скопируйте URL

Из строки "Forwarding" скопируйте:
```
https://xxxxx.ngrok.io
```

**Ваш demo URL**: `https://xxxxx.ngrok.io/causal-dashboard.html`

---

## 📧 Использование

1. Скопируйте URL
2. Откройте `EMAIL_TEMPLATE_V3.md`
3. Замените `[DEMO_LINK]` на ваш URL
4. Готово!

---

## 🌐 Альтернатива: Web Interface

Пока ngrok работает, откройте в браузере:
```
http://localhost:4040
```

Там будет виден URL в секции "Forwarding".

---

**Запустите `ngrok http 8080` в терминале и скопируйте URL!** 🚀

