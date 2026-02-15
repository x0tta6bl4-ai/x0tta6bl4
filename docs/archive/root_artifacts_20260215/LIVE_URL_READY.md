# ✅ Ngrok настроен и запущен!

**Статус**: ✅ Authtoken настроен, ngrok запущен

---

## 🌐 Получить Live URL

### Способ 1: Web Interface (самый простой)

1. **Откройте в браузере**: http://localhost:4040

2. **Найдите секцию "Forwarding"**

3. **Скопируйте URL**: `https://xxxxx.ngrok.io`

4. **Ваш demo URL**: `https://xxxxx.ngrok.io/causal-dashboard.html`

---

### Способ 2: Через терминал

Если ngrok запущен в терминале, URL виден в выводе:

```
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8080
```

---

### Способ 3: Через API

```bash
curl -s http://localhost:4040/api/tunnels | python3 -c "
import sys, json
data = json.load(sys.stdin)
tunnels = data.get('tunnels', [])
if tunnels:
    print(tunnels[0]['public_url'] + '/causal-dashboard.html')
"
```

---

## ✅ После получения URL

1. **Скопируйте**: `https://xxxxx.ngrok.io/causal-dashboard.html`

2. **Откройте**: `EMAIL_TEMPLATE_V3.md`

3. **Замените**: `[DEMO_LINK]` → ваш ngrok URL

4. **Готово к отправке email wave 3-4!**

---

## 🎯 Быстрый способ

**Просто откройте**: http://localhost:4040

Там будет виден ваш live URL! 🚀

