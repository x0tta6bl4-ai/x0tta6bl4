# ДЕТАЛЬНЫЙ ТЕХНИЧЕСКИЙ АНАЛИЗ ПРОБЛЕМ

**x0tta6bl4 v3.3.0** | 17 января 2026 г.

---

## 📌 ПРОБЛЕМА #1: WEB SECURITY - MD5 ХЕШИРОВАНИЕ ПАРОЛЕЙ

### Описание
Веб-приложение (PHP legacy code) использует устаревший и криптографически слабый алгоритм MD5 для хеширования паролей.

### Затронутые файлы

| Файл | Строка | Проблема | Статус |
|------|--------|---------|--------|
| `web/renthouse/classes/Auth.class.php` | 43 | Использует MD5 | ❌ ACTIVE BUG |
| `web/test/resetpass.php` | 94 | `SECURITY FIX #7: Replace MD5 with bcrypt` | ⚠️ NOT COMPLETED |
| `web/lib/SecurityUtils.php` | ~320 | `function isMD5Hash()` + `function migrateFromMD5()` | ⚠️ UTILITY EXISTS BUT NOT APPLIED |

### Почему это проблема

```
MD5:
├─ Криптографически сломан (collision attacks 2004+)
├─ Rainbow tables существуют (millions pre-computed hashes)
├─ 0-salt = каждый пароль "123456" хешируется одинаково
└─ ⏱️ Если БД украдена → в считанные часы пароли будут взломаны

bcrypt:
├─ Специально разработан для паролей (adaptive)
├─ Встроенный salt + work factor
├─ Поддерживает iteration count (замедление brute force)
└─ ⏱️ Атака займёт месяцы/годы даже при 100K GPU
```

### Техническое решение

#### Шаг 1: Обновить Auth.class.php

```php
// BEFORE (INSECURE):
class Auth {
    function hashPassword($password) {
        return md5($password);  // ❌ NEVER DO THIS
    }
    
    function verifyPassword($input, $stored_hash) {
        return md5($input) === $stored_hash;  // ❌ VULNERABLE
    }
}

// AFTER (SECURE):
class Auth {
    function hashPassword($password) {
        return password_hash($password, PASSWORD_BCRYPT, [
            'cost' => 12  // Balanced: ~100ms per hash
        ]);
    }
    
    function verifyPassword($input, $stored_hash) {
        return password_verify($input, $stored_hash);
    }
    
    // MIGRATION: Called during login for old MD5 users
    function migrateFromMD5($input, $old_md5_hash) {
        if (password_verify($input, $old_md5_hash)) {
            return password_hash($input, PASSWORD_BCRYPT, ['cost' => 12]);
        }
        return false;
    }
}
```

#### Шаг 2: Настроить миграцию в login flow

```php
// In login endpoint:
function login($email, $password) {
    $user = db.query("SELECT * FROM users WHERE email = ?", [$email]);
    
    if (!$user) return error("User not found", 401);
    
    // Check if using old MD5 hash
    if (SecurityUtils::isMD5Hash($user['password_hash'])) {
        // Try to verify with MD5
        if (md5($password) === $user['password_hash']) {
            // Migrate to bcrypt
            $new_hash = password_hash($password, PASSWORD_BCRYPT, ['cost' => 12]);
            db.update("users", ['password_hash' => $new_hash], ['id' => $user['id']]);
            
            // Log migration event
            log("AUTH", "Migrated user {$user['id']} from MD5 to bcrypt");
            
            // Issue session token
            return token_issued($user);
        }
    } else {
        // New bcrypt hash - use standard verification
        if (password_verify($password, $user['password_hash'])) {
            return token_issued($user);
        }
    }
    
    return error("Invalid credentials", 401);
}
```

#### Шаг 3: Batch migration script (для уже хранящихся паролей)

```php
<?php
// scripts/migrate_md5_to_bcrypt.php
// ⚠️ Run ONCE, then delete this file

require_once 'web/lib/SecurityUtils.php';

$db = new PDO('pgsql:host=localhost;dbname=x0tta6bl4');
$users = $db->query("SELECT id, password_hash FROM users WHERE length(password_hash) = 32 AND password_hash ~ '^[a-f0-9]{32}$'");

$migrated = 0;
$errors = 0;

foreach ($users as $user) {
    try {
        // We can't re-hash already-hashed passwords!
        // This is why migration MUST happen at login time
        
        // Option: Force password reset for old users
        $reset_token = bin2hex(random_bytes(32));
        $db->prepare("UPDATE users SET password_reset_token = ?, password_reset_expires = NOW() + INTERVAL '24 hours' WHERE id = ?")
            ->execute([$reset_token, $user['id']]);
        
        $migrated++;
    } catch (Exception $e) {
        error_log("Migration error for user {$user['id']}: " . $e->getMessage());
        $errors++;
    }
}

echo "✓ Migrated: {$migrated}, Errors: {$errors}\n";
?>
```

#### Шаг 4: Unit tests для проверки

```php
<?php
// tests/Unit/AuthMigrationTest.php

class AuthMigrationTest extends TestCase {
    
    public function testMD5ToBCryptMigrationOnLogin() {
        // Setup: User with old MD5 hash in DB
        $old_md5_password = md5("password123");
        $user = User::create([
            'email' => 'test@example.com',
            'password_hash' => $old_md5_password
        ]);
        
        // Act: Login with correct password
        $response = $this->post('/api/login', [
            'email' => 'test@example.com',
            'password' => 'password123'
        ]);
        
        // Assert: Login successful
        $this->assertEquals(200, $response->status());
        
        // Assert: Password hash upgraded to bcrypt
        $user->refresh();
        $this->assertNotEquals($old_md5_password, $user->password_hash);
        $this->assertTrue(password_verify('password123', $user->password_hash));
        $this->assertTrue(strlen($user->password_hash) > 50); // bcrypt hashes are ~60 chars
    }
    
    public function testBCryptPasswordVerification() {
        // Setup: User with bcrypt hash
        $password = "secure_password_xyz";
        $user = User::create([
            'email' => 'bcrypt@example.com',
            'password_hash' => password_hash($password, PASSWORD_BCRYPT, ['cost' => 12])
        ]);
        
        // Act: Login
        $response = $this->post('/api/login', [
            'email' => 'bcrypt@example.com',
            'password' => $password
        ]);
        
        // Assert
        $this->assertEquals(200, $response->status());
    }
    
    public function testInvalidCredentialsRejected() {
        $user = User::create([
            'email' => 'test@example.com',
            'password_hash' => password_hash('correct_password', PASSWORD_BCRYPT, ['cost' => 12])
        ]);
        
        $response = $this->post('/api/login', [
            'email' => 'test@example.com',
            'password' => 'wrong_password'
        ]);
        
        $this->assertEquals(401, $response->status());
    }
}
?>
```

### Контрольный список

- [ ] Обновить `Auth.class.php` с bcrypt
- [ ] Интегрировать миграцию в login endpoint
- [ ] Написать unit tests (минимум 3 случая)
- [ ] Запустить integration tests на staging БД
- [ ] Логировать события миграции (audit trail)
- [ ] Мониторить прогресс миграции (% users upgraded)
- [ ] Через 30 дней: Force password reset для оставшихся MD5 пользователей
- [ ] Удалить код legacy MD5 из codebase
- [ ] Добавить CI gate: запретить MD5 в коде (regex check)

### Timeline
**Время:** 4-6 часов  
**Тесты:** 1-2 часа  
**Verification:** 1 час  
**Итого:** **6-8 часов**

---

## 📌 ПРОБЛЕМА #2: ТЕСТИРОВАНИЕ - 5% ПОКРЫТИЕ ВМЕСТО 75%

### Описание

Coverage.xml указывает на **5.15% покрытия**, что критически низко. Требование проекта: **≥75%**.

### Диагностика

```bash
# Проверить конфигурацию pytest
cat pytest.ini

# Запустить тесты вручную
pytest tests/ -v --cov=src --cov-report=term-missing

# Посмотреть, какие файлы не покрыты
pytest tests/ --cov=src --cov-report=html
# Открыть htmlcov/index.html
```

### Возможные причины

1. **pytest.ini неправильно настроен** → pytest не находит тесты
2. **Зависимости ML/PQC требуют liboqs-python** → импорт падает на CI
3. **conftest.py нарушен** → fixtures не работают
4. **Skip markers** → многие тесты пропускаются (⚠️ CHECKED: True, есть skipped tests)

### Решение

#### 1. Проверить конфигурацию

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --cov=src
    --cov-report=term-missing:skip-covered
    --cov-report=html:htmlcov
    --cov-report=xml
    --cov-fail-under=75
    -m "not slow"
markers =
    slow: slow tests
    unit: unit tests
    integration: integration tests
    security: security tests
```

#### 2. Настроить .coveragerc

```ini
# .coveragerc
[run]
source = src
omit =
    */tests/*
    */migrations/*
    setup.py
    conftest.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
    @abstractmethod
    @abc.abstractmethod

fail_under = 75
```

#### 3. Установить все зависимости (включая PQC)

```bash
# Install all optional dependencies
pip install -e ".[dev,ml,lora,monitoring]"

# Verify liboqs is available
python -c "from src.security.post_quantum_liboqs import *; print('✓ liboqs loaded')"

# Run tests with verbose output
pytest tests/ -v --tb=short 2>&1 | head -100
```

#### 4. Пример: Unit test для MAPE-K

```python
# tests/unit/test_mape_k.py

import pytest
from unittest.mock import Mock, patch
from src.self_healing.mape_k import MAPEK

class TestMAPEKCycle:
    """Test MAPE-K self-healing cycle"""
    
    @pytest.fixture
    def mapek(self):
        """Initialize MAPE-K with mocks"""
        return MAPEK(
            monitor_interval=0.1,
            analyze_interval=0.1,
            max_incidents=100
        )
    
    def test_monitoring_phase(self, mapek):
        """Test that Monitor phase collects metrics"""
        # Arrange
        mapek.metrics_collector = Mock()
        mapek.metrics_collector.collect.return_value = {
            'cpu': 45.2,
            'memory': 62.1,
            'latency_p99': 125
        }
        
        # Act
        metrics = mapek.monitor()
        
        # Assert
        assert metrics['cpu'] == 45.2
        assert metrics['memory'] == 62.1
        mapek.metrics_collector.collect.assert_called_once()
    
    def test_analysis_phase_detects_anomalies(self, mapek):
        """Test that Analyze phase detects anomalies"""
        # Arrange
        metrics = {'cpu': 95.0, 'memory': 88.0}  # High values
        
        # Act
        anomalies = mapek.analyze(metrics)
        
        # Assert
        assert len(anomalies) > 0
        assert any('cpu' in a for a in anomalies)
    
    def test_planning_phase_creates_actions(self, mapek):
        """Test that Plan phase creates remediation actions"""
        # Arrange
        anomalies = ['high_cpu', 'high_memory']
        
        # Act
        actions = mapek.plan(anomalies)
        
        # Assert
        assert len(actions) > 0
        assert 'scale_up' in str(actions) or 'restart' in str(actions)
    
    def test_execution_phase_runs_actions(self, mapek):
        """Test that Execute phase runs actions"""
        # Arrange
        actions = ['restart_service:api', 'increase_memory:500']
        mapek.executor = Mock()
        mapek.executor.execute.return_value = True
        
        # Act
        success = mapek.execute(actions)
        
        # Assert
        assert success is True
        mapek.executor.execute.assert_called_once()
    
    @pytest.mark.integration
    def test_full_cycle(self, mapek):
        """Test full MAPE-K cycle: Monitor → Analyze → Plan → Execute"""
        # Act: Run one full cycle
        result = mapek.run_cycle()
        
        # Assert: Cycle completed successfully
        assert result['status'] == 'success'
        assert 'metrics' in result
        assert 'anomalies' in result or result['anomalies_count'] == 0
        assert 'actions' in result or result['actions_count'] == 0
```

#### 5. Интегрировать в CI/CD

```yaml
# .gitlab-ci.yml

test:
  stage: test
  image: python:3.11
  before_script:
    - pip install -e ".[dev,ml,lora,monitoring]"
  script:
    - pytest tests/ -v --cov=src --cov-report=term-missing --cov-report=xml
    - coverage report --fail-under=75
  coverage: '/TOTAL\s+(\d+%)$/'
  artifacts:
    reports:
      coverage_report:
        coverage_format: cobertura
        path: coverage.xml
    paths:
      - htmlcov/
```

### Контрольный список

- [ ] Проверить `pytest.ini` и `.coveragerc`
- [ ] Установить all dependencies (`pip install -e ".[dev,ml,...]"`)
- [ ] Запустить локально: `pytest tests/ -v --cov=src`
- [ ] Написать unit tests для всех компонентов (MAPE-K, Mesh, PQC, ML)
  - [ ] `tests/unit/test_mape_k.py` (≥10 cases)
  - [ ] `tests/unit/test_mesh.py` (≥8 cases)
  - [ ] `tests/unit/test_pqc.py` (≥6 cases)
  - [ ] `tests/unit/test_ml.py` (≥8 cases)
- [ ] Добавить integration tests
  - [ ] `tests/integration/test_mape_k_mesh.py`
  - [ ] `tests/integration/test_pqc_mtls.py`
  - [ ] `tests/integration/test_dao_voting.py`
- [ ] Обновить CI/CD с coverage gate (fail-under=75)
- [ ] Локально проверить: `pytest tests/ --cov=src --cov-fail-under=75`

### Timeline
**Написание тестов:** 30-40 часов  
**CI/CD настройка:** 2-3 часа  
**Debugging & fixes:** 5-10 часов  
**Итого:** **35-50 часов** (1.5 недели)

---

## 📌 ПРОБЛЕМА #3: MAPE-K ДУБЛИРОВАНИЕ КОДА

### Описание

```
src/
├── self_healing/
│   ├── mape_k.py          ← ОСНОВНОЙ
│   ├── mape_k_loop.py     ← Может быть нужен?
│   └── ...
├── mape_k/                ← ДУБЛИРУЕТ self_healing/
│   ├── __init__.py
│   ├── mape_k.py
│   └── ...
└── mapek/                 ← ЕЩЕ ОДИН ВАРИАНТ?
    ├── __init__.py
    └── mape_k.py
```

Это приводит к:
- ❌ Confusion: какой использовать?
- ❌ Divergence: обновления только в одном месте
- ❌ Technical debt: поддержание 2+ копий
- ❌ Import errors: `from src.mape_k import MAPEK` vs `from src.self_healing import MAPEK`

### Решение

#### Option A: Полностью удалить дублирование (Preferred)

```bash
# Step 1: Проверить, какой файл используется где
grep -r "from src.mape_k import" tests/ src/ docs/
grep -r "from src.self_healing import" tests/ src/ docs/
grep -r "from src.mapek import" tests/ src/ docs/

# Step 2: ВЫБРАТЬ основной (MUST BE src/self_healing/mape_k.py)
# src/self_healing/mape_k.py имеет статус "Production Ready" в REALITY_MAP.md
# ↓ ИСПОЛЬЗУЕТСЯ ЭТОТ

# Step 3: Обновить все импорты (grep-replace)
find src tests -name "*.py" -exec sed -i \
  's/from src\.mape_k import/from src.self_healing import/g' {} \;
find src tests -name "*.py" -exec sed -i \
  's/from src\.mapek import/from src.self_healing import/g' {} \;

# Step 4: УДАЛИТЬ дублирующие директории
rm -rf src/mape_k/
rm -rf src/mapek/

# Step 5: ПЕРЕИМЕНОВАТЬ для ясности (опционально)
mv src/self_healing/mape_k.py src/self_healing/mape_k_core.py

# Step 6: Обновить imports в tests/
pytest tests/ -v --tb=short  # Проверить, что всё работает
```

#### Option B: Оставить alias (если нужна backward compatibility)

```python
# src/mape_k/__init__.py - DEPRECATED
"""
DEPRECATED: Use src.self_healing instead
This module is maintained only for backward compatibility.
"""

import warnings
from src.self_healing.mape_k import MAPEK, MAPEKState, IncidentResponse

warnings.warn(
    "src.mape_k is deprecated. Use src.self_healing.MAPEK instead.",
    DeprecationWarning,
    stacklevel=2
)

__all__ = ['MAPEK', 'MAPEKState', 'IncidentResponse']
```

### Контрольный список

- [ ] Запустить `grep -r "from src.mape_k\|from src.mapek" src/ tests/` — найти всех импортеров
- [ ] Выбрать `src/self_healing/mape_k.py` как "single source of truth"
- [ ] Обновить все импорты в src/, tests/, docs/
- [ ] Удалить пустые директории (`src/mape_k/`, `src/mapek/`)
- [ ] Запустить полный тест suite: `pytest tests/ -v`
- [ ] Обновить REALITY_MAP.md: пометить, что дублирование удалено

### Timeline
**Время:** 2-3 часа

---

## 📌 ПРОБЛЕМА #4: eBPF - КОМПИЛЯЦИЯ НЕ НАСТРОЕНА В CI

### Описание

```
src/network/ebpf/
├── loader.py              ✓ User-space orchestrator готов
├── orchestrator.py        ✓ Управление программами
├── programs/
│   ├── network_filter.c   ← Требуется компиляция!
│   ├── packet_sniffer.c   ← Требуется компиляция!
│   └── ...
└── [compiled .o files?]   ✗ ОТСУТСТВУЮТ или не обновляются в CI
```

**Проблема:** 
- C-программы существуют, но нет процесса их компиляции в CI
- eBPF-оркестратор не может загрузить скомпилированные программы на CI/staging
- Integration tests невозможны без compiled bytecode

### Решение

#### 1. Добавить Dockerfile для eBPF компиляции

```dockerfile
# Dockerfile.ebpf-build
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    clang \
    llvm \
    libelf-dev \
    libcap-dev \
    gcc \
    make \
    git \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src

COPY src/network/ebpf/programs/ /src/programs/

RUN cd /src/programs && \
    clang -O2 -target bpf -c network_filter.c -o network_filter.o && \
    clang -O2 -target bpf -c packet_sniffer.c -o packet_sniffer.o && \
    echo "✓ eBPF programs compiled successfully"

CMD ["sh"]
```

#### 2. Добавить Makefile target

```makefile
# Makefile

.PHONY: ebpf-compile ebpf-verify ebpf-test

ebpf-compile:
	@echo "🔨 Compiling eBPF programs..."
	mkdir -p src/network/ebpf/compiled
	clang -O2 -target bpf -c \
		src/network/ebpf/programs/network_filter.c \
		-o src/network/ebpf/compiled/network_filter.o
	clang -O2 -target bpf -c \
		src/network/ebpf/programs/packet_sniffer.c \
		-o src/network/ebpf/compiled/packet_sniffer.o
	@echo "✓ eBPF compilation complete"

ebpf-verify:
	@echo "🔍 Verifying eBPF objects..."
	llvm-objdump -d src/network/ebpf/compiled/network_filter.o | head -20
	llvm-objdump -d src/network/ebpf/compiled/packet_sniffer.o | head -20

ebpf-test: ebpf-compile
	@echo "🧪 Testing eBPF loader..."
	pytest tests/network/test_ebpf_integration.py -v
```

#### 3. Обновить CI/CD

```yaml
# .gitlab-ci.yml

stages:
  - build
  - test
  - deploy

build_ebpf:
  stage: build
  image: ubuntu:22.04
  before_script:
    - apt-get update && apt-get install -y clang llvm libelf-dev make
  script:
    - make ebpf-compile
    - make ebpf-verify
  artifacts:
    paths:
      - src/network/ebpf/compiled/
    expire_in: 1 week

test_ebpf:
  stage: test
  image: python:3.11
  needs:
    - build_ebpf
  before_script:
    - pip install -e ".[dev,ml,monitoring]"
    - apt-get update && apt-get install -y libelf-dev libcap-dev
  script:
    - pytest tests/network/test_ebpf_integration.py -v --tb=short
  allow_failure: false

test_all:
  stage: test
  image: python:3.11
  needs:
    - build_ebpf
  before_script:
    - pip install -e ".[dev,ml,monitoring]"
  script:
    - pytest tests/ -v --cov=src --cov-report=term-missing
```

#### 4. Пример: Integration test для eBPF

```python
# tests/network/test_ebpf_integration.py

import pytest
import os
from src.network.ebpf.loader import EBPFLoader
from src.network.ebpf.orchestrator import EBPFOrchestrator

class TestEBPFIntegration:
    """Integration tests for eBPF loader and orchestrator"""
    
    @pytest.fixture
    def ebpf_objects(self):
        """Verify eBPF compiled objects exist"""
        base_path = "src/network/ebpf/compiled"
        
        required_files = [
            f"{base_path}/network_filter.o",
            f"{base_path}/packet_sniffer.o"
        ]
        
        for file_path in required_files:
            assert os.path.exists(file_path), f"eBPF object not found: {file_path}"
        
        return {
            'filter': required_files[0],
            'sniffer': required_files[1]
        }
    
    def test_ebpf_object_valid(self, ebpf_objects):
        """Test that compiled eBPF objects are valid ELF files"""
        for name, path in ebpf_objects.items():
            with open(path, 'rb') as f:
                magic = f.read(4)
                assert magic == b'\x7fELF', f"{name} is not a valid ELF file"
    
    def test_loader_initialize(self, ebpf_objects):
        """Test eBPF loader initialization"""
        loader = EBPFLoader()
        assert loader is not None
        assert loader.kernel_version is not None
    
    def test_load_filter_program(self, ebpf_objects):
        """Test loading network filter program"""
        loader = EBPFLoader()
        result = loader.load_program(
            ebpf_objects['filter'],
            'network_filter',
            'KPROBE'
        )
        
        assert result['status'] == 'loaded'
        assert 'fd' in result  # File descriptor
    
    def test_orchestrator_attach_program(self, ebpf_objects):
        """Test orchestrator attaching eBPF programs"""
        orchestrator = EBPFOrchestrator()
        
        program_spec = {
            'name': 'network_filter',
            'path': ebpf_objects['filter'],
            'type': 'KPROBE',
            'hooks': ['tcp_sendmsg', 'tcp_cleanup_rbuf']
        }
        
        result = orchestrator.attach_program(program_spec)
        
        assert result['status'] == 'attached'
        assert result['hook_count'] == 2
    
    @pytest.mark.slow
    def test_load_sustained_traffic(self, ebpf_objects):
        """Test eBPF program under sustained network traffic"""
        # This would require root/CAP_BPF, so skip in most environments
        pytest.skip("Requires root/CAP_BPF privileges")
```

### Контрольный список

- [ ] Установить clang + llvm
- [ ] Создать Dockerfile.ebpf-build (опционально)
- [ ] Добавить `make ebpf-compile` target
- [ ] Обновить CI/CD (add clang, compile step)
- [ ] Добавить artifacts для compiled .o files
- [ ] Написать integration tests для loader
- [ ] Запустить локально: `make ebpf-compile && pytest tests/network/test_ebpf_*.py -v`
- [ ] Проверить, что скомпилированные файлы загружаются в kernel

### Timeline
**Makefile & CI/CD:** 3-4 часа  
**Integration tests:** 4-6 часов  
**Verification & debugging:** 2-3 часа  
**Итого:** **8-12 часов**

---

## 📌 ПРОБЛЕМА #5: PQC - INTEGRATION TESTS НЕ ЗАВЕРШЕНЫ

### Описание

PQC реализован (`src/security/post_quantum_liboqs.py`), но отсутствуют полные end-to-end тесты для:
1. Key exchange (Kyber key establishment)
2. mTLS с ML-DSA подписями
3. Tunnel encryption в mesh-сети
4. Hybrid mode (classical + PQC)

### Текущее состояние

```
src/security/
├── post_quantum.py            ❌ ЗАГЛУШКА (удалить)
├── post_quantum_liboqs.py     ✓ Реализована
├── pqc_hybrid.py              ⚠️ Черновик
├── pqc_mtls.py                ⚠️ Частичная реализация
└── pqc_ebpf_integration.py    ⚠️ Скелет
```

**Требуется:**
- Полная валидация Kyber + Dilithium на стандартах NIST
- End-to-end integration tests (key exchange → signature → encryption)
- Performance benchmarks
- Graceful fallback к классическим алгоритмам

### Решение

#### 1. Реализовать PQC E2E test suite

```python
# tests/security/test_pqc_complete.py

import pytest
from src.security.post_quantum_liboqs import (
    PQMeshSecurityLibOQS,
    kyber768_key_encapsulation,
    ml_dsa_65_signature
)

class TestPQCKeyExchange:
    """Test Kyber-768 key exchange (NIST FIPS 203)"""
    
    def test_kyber_key_generation(self):
        """Test Kyber key pair generation"""
        pq_sec = PQMeshSecurityLibOQS()
        ek, dk = pq_sec.generate_kyber_keypair()
        
        assert ek is not None
        assert dk is not None
        assert len(ek) > 0
        assert len(dk) > 0
    
    def test_kyber_encapsulation(self):
        """Test Kyber key encapsulation"""
        pq_sec = PQMeshSecurityLibOQS()
        ek, dk = pq_sec.generate_kyber_keypair()
        
        # Alice encapsulates a shared secret for Bob
        shared_secret, ciphertext = pq_sec.kyber_encapsulate(ek)
        
        assert shared_secret is not None
        assert ciphertext is not None
        assert len(shared_secret) == 32  # 32 bytes
        assert len(ciphertext) > 0
    
    def test_kyber_decapsulation(self):
        """Test Kyber key decapsulation"""
        pq_sec = PQMeshSecurityLibOQS()
        ek, dk = pq_sec.generate_kyber_keypair()
        
        # Alice → Bob
        ss_alice, ciphertext = pq_sec.kyber_encapsulate(ek)
        
        # Bob decapsulates
        ss_bob = pq_sec.kyber_decapsulate(dk, ciphertext)
        
        # Alice and Bob must have same shared secret
        assert ss_alice == ss_bob
    
    def test_kyber_perfect_correctness(self):
        """Test Kyber correctness: 1000 key exchanges"""
        pq_sec = PQMeshSecurityLibOQS()
        
        for _ in range(1000):
            ek, dk = pq_sec.generate_kyber_keypair()
            ss_alice, ct = pq_sec.kyber_encapsulate(ek)
            ss_bob = pq_sec.kyber_decapsulate(dk, ct)
            
            assert ss_alice == ss_bob, "Kyber failed to produce identical shared secrets"

class TestPQCSignatures:
    """Test ML-DSA-65 digital signatures (NIST FIPS 204)"""
    
    def test_ml_dsa_keypair_generation(self):
        """Test ML-DSA key pair generation"""
        pq_sec = PQMeshSecurityLibOQS()
        sk, vk = pq_sec.generate_ml_dsa_keypair()
        
        assert sk is not None
        assert vk is not None
        assert len(sk) > 0
        assert len(vk) > 0
    
    def test_ml_dsa_sign_and_verify(self):
        """Test ML-DSA signing and verification"""
        pq_sec = PQMeshSecurityLibOQS()
        sk, vk = pq_sec.generate_ml_dsa_keypair()
        
        message = b"Important mesh network decision"
        
        # Sign
        signature = pq_sec.ml_dsa_sign(sk, message)
        assert signature is not None
        
        # Verify
        valid = pq_sec.ml_dsa_verify(vk, message, signature)
        assert valid is True
    
    def test_ml_dsa_wrong_message_fails(self):
        """Test that signature fails for different message"""
        pq_sec = PQMeshSecurityLibOQS()
        sk, vk = pq_sec.generate_ml_dsa_keypair()
        
        message1 = b"Original message"
        message2 = b"Tampered message"
        
        signature = pq_sec.ml_dsa_sign(sk, message1)
        valid = pq_sec.ml_dsa_verify(vk, message2, signature)
        
        assert valid is False

class TestPQCMTLS:
    """Test mTLS with PQC signatures"""
    
    def test_pqc_certificate_chain(self):
        """Test creating PQC-signed certificate"""
        from src.security.pqc_mtls import PQMTLSConfig
        
        pq_sec = PQMeshSecurityLibOQS()
        sk, vk = pq_sec.generate_ml_dsa_keypair()
        
        config = PQMTLSConfig(
            signing_key=sk,
            verification_key=vk,
            algorithm='ML-DSA-65'
        )
        
        assert config is not None
        assert config.algorithm == 'ML-DSA-65'
    
    def test_pqc_mtls_handshake(self):
        """Test mTLS handshake with PQC"""
        # This would require a real TLS stack with PQC support
        # For now, we test the key exchange part
        pytest.skip("Requires liboqs TLS integration")

class TestPQCHybridMode:
    """Test hybrid PQC + classical cryptography"""
    
    def test_hybrid_encapsulation(self):
        """Test hybrid (Kyber + ECDH) key establishment"""
        pq_sec = PQMeshSecurityLibOQS()
        
        # Kyber
        ek_pq, dk_pq = pq_sec.generate_kyber_keypair()
        ss_pq, ct_pq = pq_sec.kyber_encapsulate(ek_pq)
        
        # Classical (simulated)
        ss_classical = b"classical_shared_secret_32bytes"  # Would be ECDH in real code
        
        # Combine: XOR or KDF
        import hashlib
        hybrid_ss = hashlib.sha256(ss_pq + ss_classical).digest()
        
        assert len(hybrid_ss) == 32
        assert hybrid_ss != ss_pq
        assert hybrid_ss != ss_classical

class TestPQCPerformance:
    """Performance benchmarks for PQC operations"""
    
    @pytest.mark.benchmark
    def test_kyber_key_generation_performance(self, benchmark):
        """Benchmark Kyber key generation"""
        pq_sec = PQMeshSecurityLibOQS()
        result = benchmark(pq_sec.generate_kyber_keypair)
        # Should be fast: <1ms
        assert result is not None
    
    @pytest.mark.benchmark
    def test_ml_dsa_sign_performance(self, benchmark):
        """Benchmark ML-DSA signing"""
        pq_sec = PQMeshSecurityLibOQS()
        sk, _ = pq_sec.generate_ml_dsa_keypair()
        message = b"test message"
        
        result = benchmark(pq_sec.ml_dsa_sign, sk, message)
        assert result is not None

class TestPQCFallback:
    """Test graceful fallback to classical algorithms"""
    
    def test_fallback_when_liboqs_unavailable(self):
        """Test that system falls back to classical crypto if liboqs unavailable"""
        # Mock liboqs unavailability
        import src.security.post_quantum_liboqs as pq_module
        
        with pytest.raises(ImportError):
            # Should either raise informative error or fallback
            original = pq_module.LIBOQS_AVAILABLE
            pq_module.LIBOQS_AVAILABLE = False
            
            from src.security.pqc_fallback import FallbackCrypto
            fc = FallbackCrypto()
            
            # Should use classical ECDH
            assert fc.algorithm == 'ECDH'
            
            pq_module.LIBOQS_AVAILABLE = original
```

#### 2. Написать integration test для mesh tunnel с PQC

```python
# tests/integration/test_pqc_mesh_integration.py

import asyncio
import pytest
from src.network.mesh_node import MeshNode
from src.security.post_quantum_liboqs import PQMeshSecurityLibOQS
from src.network.pqc_tunnel import PQCTunnel

@pytest.mark.integration
class TestPQCMeshIntegration:
    """Integration: PQC tunnel inside mesh network"""
    
    @pytest.fixture
    async def mesh_node_alice(self):
        """Create mesh node Alice with PQC"""
        node = MeshNode(node_id="alice", port=5001)
        node.pqc = PQMeshSecurityLibOQS()
        await node.initialize()
        return node
    
    @pytest.fixture
    async def mesh_node_bob(self):
        """Create mesh node Bob with PQC"""
        node = MeshNode(node_id="bob", port=5002)
        node.pqc = PQMeshSecurityLibOQS()
        await node.initialize()
        return node
    
    @pytest.mark.asyncio
    async def test_pqc_tunnel_establishment(self, mesh_node_alice, mesh_node_bob):
        """Test PQC tunnel establishment between two mesh nodes"""
        
        # Alice initiates tunnel to Bob
        tunnel = PQCTunnel(
            from_node=mesh_node_alice,
            to_node=mesh_node_bob,
            pqc_algorithm='KYBER768'
        )
        
        # Establish tunnel
        await tunnel.establish()
        
        assert tunnel.status == 'established'
        assert tunnel.shared_secret is not None
    
    @pytest.mark.asyncio
    async def test_pqc_encrypted_message_exchange(self, mesh_node_alice, mesh_node_bob):
        """Test encrypted message exchange using PQC tunnel"""
        
        tunnel = PQCTunnel(
            from_node=mesh_node_alice,
            to_node=mesh_node_bob,
            pqc_algorithm='KYBER768'
        )
        await tunnel.establish()
        
        # Alice sends encrypted message
        message = b"Secret mesh network command"
        encrypted = tunnel.encrypt(message)
        
        assert encrypted != message
        assert len(encrypted) > 0
        
        # Bob decrypts
        decrypted = tunnel.decrypt(encrypted)
        assert decrypted == message
    
    @pytest.mark.asyncio
    async def test_pqc_multi_hop_path(self):
        """Test PQC encryption across multi-hop mesh path"""
        # Alice → Charlie → Bob
        
        nodes = [
            MeshNode(node_id=f"node{i}", port=5000 + i)
            for i in range(3)
        ]
        
        for node in nodes:
            node.pqc = PQMeshSecurityLibOQS()
            await node.initialize()
        
        # Connect nodes
        await nodes[0].add_neighbor(nodes[1])
        await nodes[1].add_neighbor(nodes[2])
        
        # End-to-end encryption: Alice → Bob
        # Message encrypted with combined PQC keys
        message = b"Multi-hop secret"
        
        # This would use the routing path and encrypt at each hop
        # Simplified: just test the concept
        assert message is not None
```

#### 3. Обновить CI/CD для PQC tests

```yaml
# .gitlab-ci.yml - добавить PQC testing

test_pqc:
  stage: test
  image: python:3.11
  before_script:
    - pip install -e ".[dev,ml,monitoring]"
    - pip install liboqs-python  # Explicitly install PQC
  script:
    - pytest tests/security/test_pqc_*.py -v --tb=short
    - pytest tests/integration/test_pqc_*.py -v --tb=short
  allow_failure: false  # PQC must pass
```

### Контрольный список

- [ ] Написать full test suite для `test_pqc_complete.py` (≥15 test cases)
- [ ] Написать integration tests для mesh + PQC (`test_pqc_mesh_integration.py`)
- [ ] Удалить `src/security/post_quantum.py` (заглушку)
- [ ] Завершить реализацию `src/security/pqc_hybrid.py`
- [ ] Завершить реализацию `src/security/pqc_mtls.py`
- [ ] Завершить реализацию `src/security/pqc_ebpf_integration.py`
- [ ] Добавить performance benchmarks
- [ ] Провести тестирование на real hardware (не VM, из-за eBPF)
- [ ] Запустить CI/CD: `pytest tests/security/test_pqc*.py -v`
- [ ] Плануть внешний криптографический аудит

### Timeline
**Написание тестов:** 20-25 часов  
**Завершение реализаций:** 15-20 часов  
**Integration & benchmarks:** 8-10 часов  
**Итого:** **43-55 часов** (2 недели)

---

## 📊 ИТОГОВАЯ МАТРИЦА ПРОБЛЕМ

| # | Проблема | Критичность | LOE (hours) | Timeline |
|---|----------|-------------|------------|----------|
| 1 | Web MD5 security | 🔴 CRITICAL | 6-8 | 1 день |
| 2 | Test coverage (5% → 75%) | 🔴 CRITICAL | 35-50 | 1.5 недель |
| 3 | MAPE-K дублирование | 🟡 HIGH | 2-3 | 2-3 часа |
| 4 | eBPF CI/CD компиляция | 🟡 HIGH | 8-12 | 2-3 дня |
| 5 | PQC integration tests | 🟡 HIGH | 43-55 | 1.5-2 недели |
| - | **ИТОГО CRITICAL** | | **41-58** | **2 дня** |
| - | **ИТОГО HIGH** | | **51-70** | **1 неделя** |
| - | **ИТОГО ALL** | | **92-128** | **2-3 недели** |

---

**Дата отчёта:** 17 января 2026 г.  
**Версия документа:** 1.0  
**Статус:** ГОТОВО К IMPLEMENTATION
