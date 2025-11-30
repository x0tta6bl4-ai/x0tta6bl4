# 🔧 Исправление: Неверный Authtoken

**Ошибка**: `ERR_NGROK_107 - authtoken is invalid`

**Причина**: Использован API key вместо authtoken, или токен был сброшен

---

## ⚡ Быстрое исправление

### Важно: Authtoken ≠ API Key

Ngrok использует **authtoken**, а не API key.

---

## 🚀 Правильные шаги

### Шаг 1: Получить Authtoken (не API key)

1. **Откройте**: https://dashboard.ngrok.com/get-started/your-authtoken
2. **Найдите секцию "Your Authtoken"** (не API Keys!)
3. **Скопируйте authtoken** (длинная строка)

**Важно**: Authtoken выглядит примерно так:
```
2abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
```

---

### Шаг 2: Настроить правильный Authtoken

```bash
ngrok config add-authtoken ВАШ_ПРАВИЛЬНЫЙ_AUTHTOKEN
```

---

### Шаг 3: Запустить Ngrok

```bash
ngrok http 8080
```

---

## 🔍 Как отличить Authtoken от API Key

**Authtoken**:
- Используется для: `ngrok config add-authtoken`
- Находится: https://dashboard.ngrok.com/get-started/your-authtoken
- Начинается обычно с цифры или буквы

**API Key**:
- Используется для: API вызовов
- Находится: https://dashboard.ngrok.com/api-keys
- Не используется для `ngrok config add-authtoken`

---

## ✅ После правильной настройки

Ngrok покажет:
```
Session Status: online
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8080
```

**Demo URL**: `https://xxxxx.ngrok.io/causal-dashboard.html`

---

**Получите правильный authtoken и настройте снова!** 🚀

