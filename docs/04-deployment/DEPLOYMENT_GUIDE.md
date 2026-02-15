# docs/DEPLOYMENT_GUIDE.md (ЕДИНСТВЕННЫЙ источник правды)

## Быстрый старт (локальная разработка)
1. Установить зависимости: `pip install -e .[dev]`
2. Запустить Vault: `vault server -dev`
3. Инициализировать секреты: `./scripts/vault-init.sh`
4. Развернуть: `./deploy.sh --mode development --target local --components mesh`

## Production развертывание на VPS
### Предварительные требования
- [ ] Vault запущен и доступен по https://vault.yourdomain.com
- [ ] SSH-ключи настроены для root@89.125.1.107
- [ ] DNS записи: node1.x0tta6bl4.net → 89.125.1.107

### Шаг 1: Vault setup
```bash
export VAULT_ADDR='https://vault.yourdomain.com'
export VAULT_TOKEN='your-root-token'
./scripts/vault-init.sh --cluster production
```

### Шаг 2: Первый узел
```bash
./deploy.sh \
    --mode production \
    --target vps:89.125.1.107 \
    --components mesh,dao,monitoring \
    --vault-token $VAULT_TOKEN \
    --vault-addr $VAULT_ADDR
```

### Шаг 3: Проверка
```bash
ssh root@89.125.1.107 "kubectl get pods -n x0tta6bl4"
curl https://node1.x0tta6bl4.net/health
```