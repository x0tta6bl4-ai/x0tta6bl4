# 🔧 eBPF Setup Guide для x0tta6bl4 (Jan 17, 2026)

## 📋 Цель

Подготовить окружение на **192.168.0.101** для:
1. Компиляции eBPF программ (clang → .o)
2. Загрузки и прикрепления к network interfaces (XDP, TC)
3. Валидации eBPF observability компонентов

---

## ✅ Требования

### Система
- **Linux kernel >= 5.4** (с eBPF support)
- **x86_64 architecture** (ARM также поддерживается)

### Инструменты
| Инструмент | Минимум | Статус | Установка |
|-----------|---------|--------|-----------|
| **clang** | >= 10 | REQUIRED | `apt install clang` |
| **llvm** | >= 10 | REQUIRED | `apt install llvm` |
| **linux-headers** | current kernel | REQUIRED | `apt install linux-headers-$(uname -r)` |
| **build-essential** | - | REQUIRED | `apt install build-essential` |
| **bpftool** | - | OPTIONAL | `apt install linux-tools-$(uname -r)` |
| **pahole** | - | OPTIONAL | `apt install dwarves` (CO-RE support) |

---

## 🚀 Быстрая установка (для Ubuntu/Debian)

### Вариант 1: Автоматическая установка (рекомендуется)

```bash
# 1. Clone или скачать скрипт
cd /tmp
wget https://raw.githubusercontent.com/x0tta6bl4/x0tta6bl4/main/scripts/setup_ebpf_environment.sh
chmod +x setup_ebpf_environment.sh

# 2. Проверить что нужно установить (без root)
./setup_ebpf_environment.sh --check-only

# 3. Сухой запуск (покажет что будет установлено)
sudo ./setup_ebpf_environment.sh --dry-run

# 4. Полная установка
sudo ./setup_ebpf_environment.sh
```

### Вариант 2: Ручная установка

```bash
# Обновить пакеты
sudo apt-get update

# Установить зависимости
sudo apt-get install -y \
    clang \
    llvm \
    build-essential \
    linux-headers-$(uname -r) \
    bpftool \
    pahole \
    python3-dev \
    git \
    bc \
    vim

# Проверить версии
clang --version
llvm-config --version
uname -r
```

---

## 🔍 Проверка окружения

### Шаг 1: Проверить kernel версию

```bash
uname -r
# Ожидаемый результат: >= 5.4
```

### Шаг 2: Проверить eBPF support

```bash
# Проверить конфиг kernel
grep CONFIG_BPF /boot/config-$(uname -r)
# Ожидаемый результат: CONFIG_BPF=y

# Проверить доступность трейсинга
[ -d /sys/kernel/debug/tracing ] && echo "Tracing: OK" || echo "Tracing: MISSING"
```

### Шаг 3: Проверить инструменты

```bash
# Проверить clang
clang --version

# Проверить kernel headers
ls -d /usr/src/linux-headers-$(uname -r)

# Проверить bpftool (optional)
bpftool --version
```

---

## 📝 Компиляция eBPF программ

### Структура проекта

```
src/network/ebpf/
├── programs/           # eBPF C программы
│   ├── xdp_counter.c
│   ├── xdp_firewall.c
│   └── Makefile        # Компиляция
├── loader.py          # Python loader для eBPF programs
└── unsupervised_detector.py
```

### Компиляция вручную

```bash
cd /path/to/x0tta6bl4/src/network/ebpf/programs

# Вариант 1: Использовать Makefile
make clean
make all

# Вариант 2: Ручная компиляция clang
clang -O2 -g -target bpf \
    -I/usr/src/linux-headers-$(uname -r)/include \
    -c xdp_counter.c -o xdp_counter.o

# Проверить результат
file xdp_counter.o
# Ожидаемый результат: ELF 64-bit LSB relocatable, eBPF, version 1
```

### Использование скрипта сборки проекта

```bash
cd /path/to/x0tta6bl4

# Полная сборка и валидация
./scripts/build_ebpf.sh

# Только проверка (без изменений)
./scripts/build_ebpf.sh --info

# Сухой запуск
./scripts/build_ebpf.sh --test
```

---

## 🧪 Валидация eBPF компонентов

### Вариант 1: Используя валидационный скрипт

```bash
cd /path/to/x0tta6bl4

# Запустить валидацию
python3 scripts/validate_ebpf_observability.py

# Ожидаемые результаты:
# ✅ clang found
# ✅ bpftool found
# ✅ eBPF program compiled successfully
# ✅ eBPF program loaded successfully
# ✅ eBPF program attached to interface lo
```

### Вариант 2: Ручная валидация

```bash
# 1. Проверить что компилируется
cd src/network/ebpf/programs
clang -O2 -target bpf -c xdp_counter.c -o xdp_counter.o
file xdp_counter.o  # Should be: eBPF

# 2. Загрузить программу (требует root)
sudo ip link set lo xdp obj xdp_counter.o sec .text

# 3. Проверить что загружено
sudo ip link show lo
# Ожидаемый результат: xdp/id:123

# 4. Снять программу
sudo ip link set lo xdp off
```

---

## 🛠️ Troubleshooting

### Проблема: `clang: command not found`

```bash
# Решение:
sudo apt-get install clang
```

### Проблема: `linux-headers-X.X.X not found`

```bash
# Показать что установлено
dpkg -l | grep linux-headers

# Установить текущий версии
sudo apt-get install linux-headers-$(uname -r)

# Если не работает, установить от репы
sudo apt-get update
sudo apt-get install linux-headers-generic
```

### Проблема: `error: invalid -mllvm option`

Это means kernel headers несовместимы. Решение:
```bash
# Обновить kernel
sudo apt-get install linux-image-generic
sudo reboot

# После перезагрузки
uname -r  # Check new version
```

### Проблема: `Operation not permitted` при загрузке eBPF

```bash
# Решение: Требуется root
sudo su -

# Или используйте sudo
sudo ip link set lo xdp obj xdp_counter.o sec .text
```

### Проблема: `BTF not available`

```bash
# This is OK, CO-RE support limited but программы работают
# Решение для полного CO-RE:
sudo apt-get install pahole  # Needs kernel with BTF support
```

---

## 📊 Проверочный список перед валидацией

- [ ] Kernel >= 5.4 (проверить: `uname -r`)
- [ ] clang установлен (проверить: `clang --version`)
- [ ] llvm установлен (проверить: `llvm-config --version`)
- [ ] linux-headers установлены (проверить: `ls /usr/src/linux-headers-*`)
- [ ] build-essential установлен (проверить: `which make gcc`)
- [ ] eBPF программы компилируются (проверить: `./scripts/build_ebpf.sh`)
- [ ] bpftool доступен (проверить: `bpftool --version`)
- [ ] Можно загружать eBPF (проверить: запустить валидацию как root)

---

## 🔗 Что дальше

После успешной подготовки окружения:

1. **Запустить P0 валидацию:**
   ```bash
   python3 scripts/validate_ebpf_observability.py
   ```

2. **Интегрировать в staging:**
   ```bash
   kubectl apply -f k8s/x0tta6bl4-ebpf-daemonset.yaml
   ```

3. **Мониторить метрики:**
   ```bash
   curl http://localhost:8080/metrics | grep ebpf
   ```

---

## 📞 Поддержка

Если возникают проблемы:

1. Проверить logs:
   ```bash
   dmesg | tail -20  # kernel logs
   journalctl -e     # systemd logs
   ```

2. Запустить диагностику:
   ```bash
   ./scripts/setup_ebpf_environment.sh --check-only --verbose
   ```

3. Связаться с командой:
   - Email: contact@x0tta6bl4.com
   - Slack: [invite]

---

**Версия:** 1.0 (Jan 17, 2026)  
**Статус:** Ready for staging deployment
