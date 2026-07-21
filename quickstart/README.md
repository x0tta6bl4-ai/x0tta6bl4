# x0tta6bl4

Self-healing Mesh + VPN с встроенным Validation Framework.

## Quick Start

```bash
git clone <repo>
cd x0tta6bl4/quickstart
docker compose up -d
./demo.sh
```

## Что вы увидите

```
✓ Mesh Connected
✓ PQC Handshake Established
✓ Validation Passed
✓ HTML Report Generated
```

## Команды

| Команда | Описание |
|:--------|:---------|
| `docker compose up -d` | Запуск 2 mesh-нод |
| `./demo.sh` | Полный demo (5-10 мин) |
| `docker compose down` | Остановка |

## Документация

- [Quick Start](quickstart/README.md)
- [Architecture](docs/architecture/)
- [Validation Framework](validation/)
- [Production Deploy](deploy/)
