# ⚡ Быстрое исправление: Ngrok Authtoken

**Проблема**: `ERR_NGROK_4018 - authentication failed`

**Решение**: Настроить authtoken (2 минуты)

---

## 🚀 3 команды для запуска

### 1. Получить authtoken

Откройте: **https://dashboard.ngrok.com/get-started/your-authtoken**

(Если нет аккаунта: https://dashboard.ngrok.com/signup)

### 2. Настроить

```bash
ngrok config add-authtoken ВАШ_ТОКЕН
```

### 3. Запустить

```bash
ngrok http 8080
```

---

## ✅ После этого

Ngrok покажет URL: `https://xxxxx.ngrok.io`

**Demo URL**: `https://xxxxx.ngrok.io/causal-dashboard.html`

---

**Готово!** После настройки authtoken, ngrok заработает 🚀

