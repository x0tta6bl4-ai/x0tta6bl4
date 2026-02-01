# x0tta6bl4 Xray VPS

Производственная VPN-инфраструктура с анти-геолокационной защитой и multi-vector обнаружением утечек.

## Архитектура

### Сетевой уровень (Network Layer)

| Компонент | Описание | Файл |
|-----------|----------|------|
| VPN Chain Manager | Управление цепочками VPN (WARP + Xray) | [`vpn-chain-manager.py`](network-layer/vpn-chain-manager.py) |
| VPN Config | Конфигурация цепочек VPN | [`vpn-chain-config.yaml`](network-layer/vpn-chain-config.yaml) |
| Kill Switch | Блокировка траффика при отключении VPN | [`killswitch.sh`](network-layer/killswitch.sh) |

### Транспортный уровень (Transport Layer)

| Компонент | Описание | Файл |
|-----------|----------|------|
| DNS Proxy | DNS-over-HTTPS прокси | [`dns-proxy.sh`](transport-layer/dns-proxy.sh) |
| Traffic Shaper | Шейпинг траффика для маскировки | [`traffic-shaper.sh`](transport-layer/traffic-shaper.sh) |

### Уровень приложения (Application Layer)

| Компонент | Описание | Файл |
|-----------|----------|------|
| Firefox Hardening | User.js для Firefox | [`firefox-hardening.js`](application-layer/firefox-hardening.js) |
| Chrome Hardening | Скрипт харднинга Chrome | [`chrome-hardening.sh`](application-layer/chrome-hardening.sh) |

## Установка

```bash
# Полная установка
sudo ./deployment/install.sh

# Проверка установки
sudo ./deployment/verify.sh
```

## Использование Kill Switch

```bash
# Включить защиту
sudo ./network-layer/killswitch.sh enable

# Проверить статус
./network-layer/killswitch.sh status

# Тест на утечки
./network-layer/killswitch.sh test

# Выключить
sudo ./network-layer/killswitch.sh disable
```

## Развёртывание Xray VPS

См. [x0tta6bl4-xray-vps/docs/xray-setup-guide.md](x0tta6bl4-xray-vps/docs/xray-setup-guide.md)

## Лицензия

PRIVATE - Для использования в проекте x0tta6bl4
