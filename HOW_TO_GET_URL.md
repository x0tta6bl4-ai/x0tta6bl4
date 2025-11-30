# 🔍 Как получить Ngrok URL

**Статус**: ✅ Authtoken настроен, ngrok запущен

---

## 🚀 Способ 1: Через Ngrok Web Interface (самый простой)

1. **Откройте в браузере**: http://localhost:4040

2. **Найдите секцию "Forwarding"**

3. **Скопируйте URL** типа: `https://xxxxx.ngrok.io`

4. **Ваш demo URL**: `https://xxxxx.ngrok.io/causal-dashboard.html`

---

## 🚀 Способ 2: Через терминал (если ngrok запущен в foreground)

Если вы запустили `ngrok http 8080` в терминале, URL будет виден в выводе:

```
Session Status: online
Forwarding: https://xxxxx.ngrok.io -> http://localhost:8080
```

Скопируйте: `https://xxxxx.ngrok.io/causal-dashboard.html`

---

## 🚀 Способ 3: Через API (автоматически)

```bash
cd /mnt/AC74CC2974CBF3DC
./GET_NGROK_URL.sh
```

Или вручную:
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

1. **Скопируйте URL**: `https://xxxxx.ngrok.io/causal-dashboard.html`

2. **Откройте** `EMAIL_TEMPLATE_V3.md`

3. **Замените**: `[DEMO_LINK]` → ваш ngrok URL

4. **Готово к отправке email wave 3-4!**

---

## 🆘 Если URL не получается

**Проверьте что ngrok работает**:
```bash
# Проверить процесс
ps aux | grep ngrok

# Проверить API
curl http://localhost:4040/api/tunnels

# Перезапустить если нужно
pkill ngrok
ngrok http 8080
```

---

**Самый простой способ**: Откройте http://localhost:4040 в браузере 🚀

