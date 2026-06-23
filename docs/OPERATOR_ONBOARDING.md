# x0tta6bl4 Operator Onboarding

## Быстрый старт (1 команда)

```bash
curl -fsSL https://x0tta6bl4.com/install | bash
```

Или вручную:

```bash
# 1. Клонировать репозиторий
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4

# 2. Установить зависимости
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Запустить ноду
python3 scripts/start_mesh_relay_simple.py --port 10809
```

## Что делает нода

1. **Слушает** на TCP порту (по умолчанию 10809)
2. **Подключается** к другим нодам через bootstrap
3. **Ретранслирует** трафик между нодами
4. **Получает rewards** за каждый ретранслированный пакет

## Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `MESH_PORT` | TCP порт | 10809 |
| `MESH_NODE_ID` | ID ноды | auto |
| `MESH_SHARED_KEY` | Ключ шифрования | auto-generated |

### Примеры запуска

```bash
# Базовый запуск
python3 scripts/start_mesh_relay_simple.py --port 10809

# Запуск с подключением к peer
python3 scripts/start_mesh_relay_simple.py --port 10810 --connect 127.0.0.1:10809

# Запуск с переменными окружения
MESH_PORT=10809 MESH_NODE_ID=my-node python3 scripts/start_mesh_relay_simple.py
```

## Монетизация

### Как заработать

1. **Relay Mining** — ретрансляция трафика
   - Ставка: 0.0001 X0T за пакет
   - Автоматически через mesh relay

2. **Staking** — стейкинг X0T токенов
   - Минимум: 100 X0T
   - Rewards: 10,000 X0T за epoch (1 час)

3. **DAO Governance** — голосование за rewards
   - Квадратичное голосование
   - Награды за участие

### Проверка баланса

```bash
python3 -c "
from web3 import Web3
w3 = Web3(Web3.HTTPProvider('https://sepolia.base.org'))
token = w3.eth.contract(address='0xe1F4709A2Cf3F85D88731E4859416cCAdc06190C', abi=[...])
balance = token.functions.balanceOf('YOUR_WALLET').call()
print(f'X0T: {balance}')
"
```

## Контракты

| Контракт | Адрес | Сеть |
|----------|-------|------|
| X0T Token | 0xe1F4709A2Cf3F85D88731E4859416cCAdc06190C | Base Sepolia |
| Mesh Governance | 0x868F54c2f4909690B13b63d406D274A167632025 | Base Sepolia |

## Поддержка

- **GitHub:** https://github.com/x0tta6bl4-ai/x0tta6bl4
- **Discord:** https://discord.gg/x0tta6bl4
- **Twitter:** @x0tta6bl4

## Лицензия

Apache-2.0 — используйте свободно.

---

*Автономное развертывание выполнено через Codex. Проект v4.0 официально вышел в мир.*
