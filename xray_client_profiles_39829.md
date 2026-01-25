# Xray VLESS+REALITY (Vision) — клиентские профили (порт 39829)

## Параметры сервера
- **Host**: 89.125.1.107
- **Port**: 39829
- **Protocol**: VLESS
- **Security**: reality
- **Flow**: xtls-rprx-vision
- **Transport**: tcp
- **Encryption**: none

## Reality
- **publicKey (pbk)**: xJYKoxof5mzDEbgI8BJYF6Rv2Ef0mGpmFumtZzs2NFg
- **shortIds (sid)**: 6b
- **serverName (sni)**: www.google.com
- **fingerprint (fp)**: chrome
- **spiderX (spx)**: /watch?v=dQw4w9WgXcQ (optional)

## UUIDs
- **Desktop**: f56fb669-32ec-4142-b2fe-8b65c4321102
- **Mobile**:  b02ef223-4558-4cae-b76b-28f58a5e4e57

---

## v2rayN / v2rayNG — ссылки для импорта

- **Desktop**
```
vless://f56fb669-32ec-4142-b2fe-8b65c4321102@89.125.1.107:39829?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.google.com&fp=chrome&pbk=xJYKoxof5mzDEbgI8BJYF6Rv2Ef0mGpmFumtZzs2NFg&sid=6b&spx=%2Fwatch%3Fv%3DdQw4w9WgXcQ&type=tcp#x0tta6bl4_desktop
```

- **Mobile**
```
vless://b02ef223-4558-4cae-b76b-28f58a5e4e57@89.125.1.107:39829?encryption=none&flow=xtls-rprx-vision&security=reality&sni=www.google.com&fp=chrome&pbk=xJYKoxof5mzDEbgI8BJYF6Rv2Ef0mGpmFumtZzs2NFg&sid=6b&spx=%2Fwatch%3Fv%3DdQw4w9WgXcQ&type=tcp#x0tta6bl4_mobile
```

---

## sing-box outbound (JSON)
Вставить в раздел `outbounds` и использовать в маршрутизации тег `vless-reality`.

```json
{
  "type": "vless",
  "tag": "vless-reality",
  "server": "89.125.1.107",
  "server_port": 39829,
  "uuid": "f56fb669-32ec-4142-b2fe-8b65c4321102",
  "flow": "xtls-rprx-vision",
  "packet_encoding": "none",
  "tls": {
    "enabled": true,
    "server_name": "www.google.com",
    "utls": { "enabled": true, "fingerprint": "chrome" },
    "reality": {
      "enabled": true,
      "public_key": "xJYKoxof5mzDEbgI8BJYF6Rv2Ef0mGpmFumtZzs2NFg",
      "short_id": "6b"
    }
  },
  "transport": { "type": "tcp" }
}
```

Пример routing:
```json
{
  "route": {
    "rules": [
      { "outbound": "block", "protocol": ["bittorrent"] }
    ]
  },
  "outbounds": [
    { "type": "block", "tag": "block" },
    { "type": "direct", "tag": "direct" },
    { "type": "selector", "tag": "proxy", "outbounds": ["vless-reality", "direct"] },
    { "type": "vless", "tag": "vless-reality", "server": "89.125.1.107", "server_port": 39829, "uuid": "f56fb669-32ec-4142-b2fe-8b65c4321102", "flow": "xtls-rprx-vision", "packet_encoding": "none", "tls": { "enabled": true, "server_name": "www.google.com", "utls": { "enabled": true, "fingerprint": "chrome" }, "reality": { "enabled": true, "public_key": "xJYKoxof5mzDEbgI8BJYF6Rv2Ef0mGpmFumtZzs2NFg", "short_id": "6b" } }, "transport": { "type": "tcp" } }
  ]
}
```

---

## Быстрый тест
- Включить профиль и проверить:
```
curl -s --socks5 127.0.0.1:10808 https://ipinfo.io/ip
```
Должен показать IP сервера: 89.125.1.107

## Важно
- Удалить старые узлы: любые на 628/443 и все panel/api/server/status
- Параметры должны точно совпадать: security=reality, flow=xtls-rprx-vision, sni=www.google.com, pbk как выше, sid=6b, fp=chrome
