# eBPF Extended Features Guide

**Версия:** x0tta6bl4 v3.0  
**Дата:** $(date)

---

## Обзор

Расширенные функции для eBPF валидации и загрузки, включая детекцию бесконечных циклов и улучшенную верификацию attachment.

---

## Новые функции

### 1. Enhanced Loop Detection (`src/network/ebpf/validator.py`)

#### Backward Jump Detection
Обнаруживает backward jumps (потенциальные бесконечные циклы):

```python
from src.network.ebpf.validator import EBPFValidator

validator = EBPFValidator()
result = validator.validate_bytecode(bytecode)

# Проверка предупреждений
if result.warnings:
    for warning in result.warnings:
        if "backward jump" in warning.lower():
            print(f"⚠️ Potential loop detected: {warning}")
```

#### Nested Loop Detection
Обнаруживает множественные jumps к одной инструкции (nested loops):

```python
# Метаданные содержат информацию о loops
metadata = result.metadata
print(f"Loop analysis: {metadata['loop_analysis']}")
print(f"Loop warnings: {metadata['loop_warnings_count']}")
```

---

### 2. Enhanced Attachment Verification (`src/network/ebpf/loader.py`)

#### bpftool Verification
Улучшенная проверка attachment через `bpftool`:

```python
from src.network.ebpf.loader import EBPFLoader, EBPFProgramType

loader = EBPFLoader()
program_id = loader.load_program("program.o", EBPFProgramType.XDP)

# Attachment с автоматической верификацией
loader.attach_program(
    program_id,
    "eth0",
    EBPFProgramType.XDP
)

# Верификация проверяет:
# 1. Программа загружена
# 2. Attachment тип корректен (XDP/TC/etc)
# 3. Программа действительно attached
```

---

## Использование

### Loop Detection

```python
from src.network.ebpf.validator import EBPFValidator

validator = EBPFValidator()

# Валидация bytecode
result = validator.validate_bytecode(bytecode)

if not result.is_valid:
    print("❌ Validation failed:")
    for error in result.errors:
        print(f"  - {error}")

# Проверка предупреждений о loops
if result.metadata.get("loop_analysis") == "basic":
    warnings = result.warnings
    loop_warnings = [w for w in warnings if "loop" in w.lower() or "jump" in w.lower()]
    if loop_warnings:
        print("⚠️ Potential loops detected:")
        for warning in loop_warnings:
            print(f"  - {warning}")
```

### Attachment Verification

```python
from src.network.ebpf.loader import EBPFLoader, EBPFProgramType

loader = EBPFLoader()

# Загрузка программы
program_id = loader.load_program("xdp_counter.o", EBPFProgramType.XDP)

# Attachment с верификацией
try:
    loader.attach_program(program_id, "eth0", EBPFProgramType.XDP)
    print("✅ Program attached and verified")
except Exception as e:
    print(f"❌ Attachment failed: {e}")
```

---

## Метаданные

### Validation Result Metadata

```python
metadata = result.metadata

# Loop analysis
print(f"Loop analysis: {metadata['loop_analysis']}")  # "basic" | "none_detected"
print(f"Loop warnings: {metadata['loop_warnings_count']}")

# Register analysis
print(f"Register usage: {metadata['register_usage']}")
print(f"Registers used: {metadata['registers_used']}")

# Instruction count
print(f"Instructions: {metadata['instruction_count']}")
```

---

## Тестирование

```bash
# Запустить тесты extended features
pytest tests/unit/network/ebpf/test_validator_extended.py
pytest tests/unit/network/ebpf/test_loader_extended.py
```

---

## Ограничения

### Loop Detection
- **Текущий уровень:** Базовая детекция (backward jumps, nested loops)
- **Будущее:** Полный control flow analysis (требует больше времени)

### Attachment Verification
- Требует `bpftool` в системе
- Проверяет только наличие программы, не детальную конфигурацию

---

## Best Practices

1. **Всегда валидируйте** eBPF программы перед загрузкой
2. **Проверяйте предупреждения** о потенциальных loops
3. **Используйте верификацию** attachment для production
4. **Мониторьте метаданные** для анализа качества программ

---

**Последнее обновление:** $(date)


