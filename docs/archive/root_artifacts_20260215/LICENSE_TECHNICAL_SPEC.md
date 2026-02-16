# 🔐 ТЕХНИЧЕСКАЯ СПЕЦИФИКАЦИЯ: ЛИЦЕНЗИРОВАНИЕ

**Версия:** 1.0.0  
**Дата:** 30 ноября 2025  
**Цель:** Zero-Trust лицензирование через Node Identity Binding

---

## 🎯 ОБЗОР

### Проблема:
- Обычный DRM ломают за 2 дня
- Реверс-инжиниринг
- Копирование файлов

### Решение:
- **Hardware Binding:** Привязка к устройству
- **Network Enforcement:** Сеть отвергает невалидные ноды
- **Post-Quantum Signing:** Подпись через PQ-Manager

---

## 🔒 АРХИТЕКТУРА ЗАЩИТЫ

### Компоненты:

1. **Device Fingerprint Generator**
   - Собирает уникальные идентификаторы железа
   - Генерирует хэш-отпечаток

2. **Activation Server**
   - Принимает Fingerprint + Token
   - Подписывает через Master Private Key
   - Выдает Signed Certificate

3. **License Validator**
   - Проверяет Certificate при запуске
   - Валидирует Fingerprint
   - Проверяет срок действия

4. **Network Enforcement**
   - Mesh-ноды проверяют Certificate при подключении
   - Отвергают невалидные соединения
   - DAO-consensus для бана

---

## 📋 ПРОТОКОЛ АКТИВАЦИИ

### Шаг 1: Генерация Device Fingerprint

```python
# device_fingerprint.py

import hashlib
import platform
import subprocess
import uuid

class DeviceFingerprint:
    def __init__(self):
        self.components = {}
    
    def collect_cpu_id(self):
        """Собрать CPU ID"""
        try:
            if platform.system() == "Linux":
                # /proc/cpuinfo
                with open('/proc/cpuinfo', 'r') as f:
                    for line in f:
                        if 'Serial' in line:
                            return line.split(':')[1].strip()
            elif platform.system() == "Darwin":
                # sysctl machdep.cpu.brand_string
                result = subprocess.run(
                    ['sysctl', '-n', 'machdep.cpu.brand_string'],
                    capture_output=True, text=True
                )
                return result.stdout.strip()
        except:
            return None
    
    def collect_mac_address(self):
        """Собрать MAC адрес"""
        try:
            mac = ':'.join(['{:02x}'.format((uuid.getnode() >> i) & 0xff) 
                           for i in range(0,8*6,8)][::-1])
            return mac
        except:
            return None
    
    def collect_motherboard_serial(self):
        """Собрать серийный номер материнской платы"""
        try:
            if platform.system() == "Linux":
                # dmidecode или /sys/class/dmi/id
                result = subprocess.run(
                    ['dmidecode', '-s', 'baseboard-serial-number'],
                    capture_output=True, text=True
                )
                return result.stdout.strip()
            elif platform.system() == "Darwin":
                # system_profiler SPHardwareDataType
                result = subprocess.run(
                    ['system_profiler', 'SPHardwareDataType'],
                    capture_output=True, text=True
                )
                # Парсинг вывода
                return self._parse_mac_serial(result.stdout)
        except:
            return None
    
    def generate_fingerprint(self):
        """Генерация финального отпечатка"""
        components = {
            'cpu_id': self.collect_cpu_id(),
            'mac': self.collect_mac_address(),
            'motherboard': self.collect_motherboard_serial(),
            'platform': platform.system(),
            'machine': platform.machine(),
        }
        
        # Убрать None значения
        components = {k: v for k, v in components.items() if v}
        
        # Создать строку для хэширования
        fingerprint_string = '|'.join([f"{k}:{v}" for k, v in sorted(components.items())])
        
        # SHA-256 хэш
        fingerprint_hash = hashlib.sha256(fingerprint_string.encode()).hexdigest()
        
        return {
            'fingerprint': fingerprint_hash,
            'components': components,
            'timestamp': datetime.now().isoformat()
        }
```

### Шаг 2: Запрос активации

```python
# activation_client.py

import requests
import json

class ActivationClient:
    def __init__(self, activation_token, auth_server_url):
        self.token = activation_token
        self.server_url = auth_server_url
        self.fingerprint_gen = DeviceFingerprint()
    
    def request_activation(self):
        """Запросить активацию у сервера"""
        # Генерация fingerprint
        fingerprint_data = self.fingerprint_gen.generate_fingerprint()
        
        # Запрос к серверу
        payload = {
            'activation_token': self.token,
            'device_fingerprint': fingerprint_data['fingerprint'],
            'device_info': fingerprint_data['components']
        }
        
        response = requests.post(
            f"{self.server_url}/api/activate",
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'certificate': data['certificate'],
                'expires_at': data['expires_at']
            }
        else:
            return {
                'success': False,
                'error': response.json().get('error', 'Unknown error')
            }
```

### Шаг 3: Серверная обработка

```python
# activation_server.py

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
import json
import base64
from datetime import datetime, timedelta

class ActivationServer:
    def __init__(self, master_private_key_path):
        # Загрузка Master Private Key (PQ-Manager)
        with open(master_private_key_path, 'rb') as f:
            self.master_key = serialization.load_pem_private_key(
                f.read(),
                password=None,
                backend=default_backend()
            )
    
    def validate_token(self, activation_token):
        """Проверка Activation Token в БД"""
        # Проверка в purchases таблице
        # Проверка что token не использован
        # Проверка срока действия
        pass
    
    def sign_certificate(self, activation_token, device_fingerprint):
        """Подписать сертификат"""
        # Создать payload
        payload = {
            'activation_token': activation_token,
            'device_fingerprint': device_fingerprint,
            'issued_at': datetime.now().isoformat(),
            'expires_at': (datetime.now() + timedelta(days=365*10)).isoformat(),  # 10 лет
            'version': '1.0.0'
        }
        
        # Сериализация
        payload_json = json.dumps(payload, sort_keys=True)
        payload_bytes = payload_json.encode('utf-8')
        
        # Подпись через Master Private Key
        signature = self.master_key.sign(
            payload_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Создать сертификат
        certificate = {
            'payload': payload,
            'signature': base64.b64encode(signature).decode('utf-8'),
            'algorithm': 'RSA-PSS-SHA256'  # Или Post-Quantum алгоритм
        }
        
        return certificate
    
    def handle_activation_request(self, request_data):
        """Обработка запроса активации"""
        activation_token = request_data['activation_token']
        device_fingerprint = request_data['device_fingerprint']
        
        # Валидация token
        if not self.validate_token(activation_token):
            return {'error': 'Invalid or expired activation token'}
        
        # Проверка на double-spending
        if self.is_fingerprint_already_used(device_fingerprint):
            return {'error': 'Device fingerprint already activated'}
        
        # Подпись сертификата
        certificate = self.sign_certificate(activation_token, device_fingerprint)
        
        # Сохранение в БД
        self.save_activation(activation_token, device_fingerprint, certificate)
        
        return {
            'success': True,
            'certificate': certificate,
            'expires_at': certificate['payload']['expires_at']
        }
```

### Шаг 4: Валидация при запуске

```python
# license_validator.py

import json
import base64
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend
from datetime import datetime

class LicenseValidator:
    def __init__(self, master_public_key_path, certificate_path):
        # Загрузка Master Public Key
        with open(master_public_key_path, 'rb') as f:
            self.master_public_key = serialization.load_pem_public_key(
                f.read(),
                backend=default_backend()
            )
        
        # Загрузка сертификата
        with open(certificate_path, 'r') as f:
            self.certificate = json.load(f)
    
    def validate_certificate(self):
        """Валидация сертификата"""
        # Проверка срока действия
        expires_at = datetime.fromisoformat(
            self.certificate['payload']['expires_at']
        )
        if datetime.now() > expires_at:
            return {'valid': False, 'error': 'Certificate expired'}
        
        # Проверка подписи
        payload_json = json.dumps(
            self.certificate['payload'],
            sort_keys=True
        )
        payload_bytes = payload_json.encode('utf-8')
        
        signature = base64.b64decode(
            self.certificate['signature']
        )
        
        try:
            self.master_public_key.verify(
                signature,
                payload_bytes,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        except:
            return {'valid': False, 'error': 'Invalid signature'}
        
        # Проверка Device Fingerprint
        current_fingerprint = DeviceFingerprint().generate_fingerprint()
        if current_fingerprint['fingerprint'] != self.certificate['payload']['device_fingerprint']:
            return {'valid': False, 'error': 'Device fingerprint mismatch'}
        
        return {'valid': True}
```

---

## 🌐 NETWORK-LEVEL ENFORCEMENT

### Проверка при подключении к mesh:

```python
# mesh_node_license_check.py

class MeshNodeLicenseCheck:
    def __init__(self, license_validator):
        self.validator = license_validator
    
    def on_peer_connect(self, peer_info):
        """Проверка лицензии при подключении пира"""
        # Пир отправляет свой Certificate
        peer_certificate = peer_info.get('certificate')
        
        if not peer_certificate:
            # Нет сертификата = отклонение
            return {'allowed': False, 'reason': 'No certificate'}
        
        # Валидация сертификата
        validation_result = self.validator.validate_certificate(peer_certificate)
        
        if not validation_result['valid']:
            # Невалидный сертификат = отклонение
            return {'allowed': False, 'reason': validation_result['error']}
        
        # Проверка на double-spending (DAO-consensus)
        if self.detect_double_spending(peer_certificate):
            # Две ноды с одним ID = бан обеих
            self.ban_node(peer_certificate['payload']['device_fingerprint'])
            return {'allowed': False, 'reason': 'Double spending detected'}
        
        return {'allowed': True}
    
    def detect_double_spending(self, certificate):
        """Обнаружение double-spending через DAO-consensus"""
        # Проверка в mesh-сети: есть ли другая активная нода с таким же fingerprint?
        # Если да - это double-spending
        pass
```

---

## 🔐 POST-QUANTUM КРИПТОГРАФИЯ

### Интеграция с PQ-Manager:

```python
# pq_license_signing.py

from src.security.post_quantum import PQManager

class PQLicenseSigning:
    def __init__(self):
        self.pq_manager = PQManager()
    
    def sign_with_pq(self, payload):
        """Подпись через Post-Quantum алгоритм"""
        # Использование Dilithium-3 или другого PQ алгоритма
        signature = self.pq_manager.sign(payload)
        return signature
    
    def verify_pq_signature(self, payload, signature):
        """Верификация PQ подписи"""
        return self.pq_manager.verify(payload, signature)
```

---

## 📊 БАЗА ДАННЫХ

### Схема:

```sql
-- Таблица активаций
CREATE TABLE activations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    purchase_id INTEGER NOT NULL,
    activation_token TEXT NOT NULL,
    device_fingerprint TEXT NOT NULL UNIQUE,
    certificate TEXT NOT NULL,  -- JSON
    status TEXT DEFAULT 'active',  -- 'active', 'banned', 'expired'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    FOREIGN KEY (purchase_id) REFERENCES purchases(id)
);

-- Таблица банов (для double-spending)
CREATE TABLE banned_fingerprints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_fingerprint TEXT NOT NULL UNIQUE,
    reason TEXT,
    banned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Индекс для быстрого поиска
CREATE INDEX idx_fingerprint ON activations(device_fingerprint);
CREATE INDEX idx_token ON activations(activation_token);
```

---

## 🧪 ТЕСТИРОВАНИЕ

### Тест-кейсы:

1. **Успешная активация:**
   - Генерация fingerprint
   - Запрос активации
   - Получение сертификата
   - Валидация при запуске

2. **Невалидный token:**
   - Запрос с несуществующим token
   - Ожидается ошибка

3. **Double-spending:**
   - Активация на двух устройствах с одним token
   - Ожидается бан обеих нод

4. **Копирование файла:**
   - Копирование на другое устройство
   - Ожидается несовпадение fingerprint
   - Ожидается отклонение сетью

---

## 🚀 ДЕПЛОЙ

### Требования:

- Python 3.8+
- PostgreSQL или SQLite
- Master Private Key (хранить в секрете!)
- HTTPS для Activation Server

### Безопасность:

- Master Private Key в отдельном файле
- Не коммитить ключи в Git
- Использовать environment variables
- Rate limiting на Activation Server
- Логирование всех активаций

---

## 📝 TODO

- [ ] Реализовать DeviceFingerprint
- [ ] Реализовать ActivationServer
- [ ] Реализовать LicenseValidator
- [ ] Интеграция с Mesh Node
- [ ] Post-Quantum подпись
- [ ] Double-spending detection
- [ ] Тестирование
- [ ] Документация

---

**Готов к реализации!** 🔐

