# Provenance & Verification Guide (v1.1 RC1)

Этот документ описывает, как проверить подлинность и происхождение артефактов релиза x0tta6bl4 RC1 с использованием Sigstore/Cosign и Rekor.

## 1. Релизные артефакты

В RC1 подписываются следующие файлы:
- `agent.cdx.json` (SBOM ядра)
- `repo.spdx.json` (SBOM репозитория)
- `RC1_MANIFEST.json` (Официальный манифест релиза)
- `RC1_RELEASE_NOTES.md` (Release Notes с честным PPS базисом)
- `docs/release/RC1_INTEGRITY_NOTE.md` (Документ об очистке данных)

## 2. Верификация через Rekor (Keyless)

Если релиз был подписан в CI через GitHub Actions, он не имеет статических ключей. Проверка осуществляется через OIDC identity.

### Команда для проверки:

```bash
cosign verify-blob \
  --certificate <artifact>.crt \
  --signature <artifact>.sig \
  --certificate-identity "https://github.com/x0tta6bl4/x0tta6bl4/.github/workflows/ci.yml@refs/heads/main" \
  --certificate-oidc-issuer "https://token.actions.githubusercontent.com" \
  <artifact>
```

## 3. Локальная проверка (Mock)

Для разработчиков предусмотрен режим локальной подписи без загрузки в Rekor.

### Генерация локальных подписей:

```bash
# Требует Docker
TOOL_MODE=docker security/sbom/verify-cosign-rekor.sh --mode mock
```

Артефакты подписи будут созданы рядом с файлами: `<artifact>.sig`. Публичный ключ для проверки будет сохранен в `security/sbom/out/mock-cosign.pub`.

## 4. Прослеживаемость (Transparency)

Все подписи в режиме `ci-keyless` попадают в публичный лог прозрачности [Rekor](https://rekor.sigstore.dev). Это гарантирует, что артефакты не были изменены после сборки в доверенном CI-окружении.

---
**Status:** RC1 Provenance Ready.
