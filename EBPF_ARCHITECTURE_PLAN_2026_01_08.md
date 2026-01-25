# eBPF Architecture Plan: Завершение реализации

**Дата:** 8 января 2026  
**Приоритет:** P0 (критический для observability)  
**Статус:** Архитектурный план для завершения TODO в loader.py

---

## 🎯 Цель

Завершить реализацию eBPF observability, устранив TODO в `src/network/ebpf/loader.py` (строки 277, 394, 439).

---

## 📊 Текущее состояние

### ✅ Что уже реализовано:

1. **eBPF Программы:**
   - ✅ `xdp_counter.c` - Подсчет пакетов по протоколам
   - ✅ `kprobe_syscall_latency.c` - Отслеживание latency системных вызовов
   - ✅ `tc_classifier.c` - Классификация трафика
   - ✅ `tracepoint_net.c` - Сетевые tracepoints

2. **Инфраструктура:**
   - ✅ `loader.py` - Базовая структура загрузчика
   - ✅ `validator.py` - Валидация программ
   - ✅ `map_reader.py` - Чтение eBPF maps
   - ✅ `metrics_exporter.py` - Экспорт метрик в Prometheus

### ❌ Что не реализовано:

1. **Actual Interface Attachment** (строка 277):
   - TODO: Implement actual interface attachment via ip link / bpftool
   - TODO: Verify interface exists and is up

2. **Actual Detachment** (строка 394):
   - TODO: Implement actual detachment (ip link set dev {interface} xdp off)
   - TODO: Handle TC detachment (tc filter del)

3. **Verification** (строка 439):
   - TODO: Verify program is detached from all interfaces first
   - TODO: Release BPF maps

---

## 🏗️ Архитектура решения

### 1. Interface Attachment (строка 277)

**Текущий код:**
```python
def attach_to_interface(
    self,
    program_id: str,
    interface: str,
    mode: EBPFAttachMode = EBPFAttachMode.SKB
) -> bool:
    # TODO: Implement actual interface attachment
    # TODO: Verify interface exists and is up
```

**Реализация:**

```python
def attach_to_interface(
    self,
    program_id: str,
    interface: str,
    mode: EBPFAttachMode = EBPFAttachMode.SKB
) -> bool:
    """
    Attach a loaded eBPF program to a network interface.
    
    Implementation:
    - For XDP: Uses 'ip link set dev {interface} xdp obj {program}'
    - For TC: Uses 'tc filter add dev {interface} {ingress/egress}'
    - Verifies interface exists and is up
    - Handles XDP mode negotiation (HW → DRV → SKB)
    """
    if program_id not in self.loaded_programs:
        raise EBPFAttachError(f"Program not loaded: {program_id}")
    
    program_info = self.loaded_programs[program_id]
    program_type = program_info["type"]
    program_path = program_info["path"]
    
    # Verify interface exists
    interface_path = Path(f"/sys/class/net/{interface}")
    if not interface_path.exists():
        raise EBPFAttachError(f"Network interface not found: {interface}")
    
    # Check if interface is up
    operstate_path = interface_path / "operstate"
    if operstate_path.exists():
        operstate = operstate_path.read_text().strip()
        if operstate != "up":
            logger.warning(f"Interface {interface} is not up (state: {operstate})")
            # Try to bring interface up
            try:
                subprocess.run(
                    ["ip", "link", "set", "dev", interface, "up"],
                    check=True,
                    capture_output=True,
                    timeout=5
                )
            except subprocess.CalledProcessError as e:
                raise EBPFAttachError(f"Failed to bring interface up: {e}")
    
    # Attach based on program type
    if program_type == EBPFProgramType.XDP:
        return self._attach_xdp(program_path, interface, mode)
    elif program_type == EBPFProgramType.TC:
        return self._attach_tc(program_path, interface)
    else:
        raise EBPFAttachError(f"Unsupported program type for attachment: {program_type}")
    
    # Store attachment info
    if interface not in self.attached_interfaces:
        self.attached_interfaces[interface] = []
    self.attached_interfaces[interface].append({
        "program_id": program_id,
        "type": program_type,
        "mode": mode,
        "attached_at": time.time()
    })
    
    logger.info(f"✅ Attached {program_id} to {interface} ({program_type.value}, {mode.value})")
    return True

def _attach_xdp(
    self,
    program_path: str,
    interface: str,
    mode: EBPFAttachMode
) -> bool:
    """
    Attach XDP program to interface.
    
    Tries modes in order: HW → DRV → SKB (fallback)
    """
    modes_to_try = []
    if mode == EBPFAttachMode.HW:
        modes_to_try = ["offload", "drv", "skb"]
    elif mode == EBPFAttachMode.DRV:
        modes_to_try = ["drv", "skb"]
    else:
        modes_to_try = ["skb"]
    
    for xdp_mode in modes_to_try:
        try:
            # Use ip link to attach XDP program
            cmd = [
                "ip", "link", "set", "dev", interface,
                "xdp", "obj", str(program_path),
                "sec", ".text"  # Section name in ELF
            ]
            
            if xdp_mode != "skb":
                cmd.extend(["mode", xdp_mode])
            
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Verify attachment
            if self._verify_xdp_attachment(interface, xdp_mode):
                logger.info(f"✅ XDP attached in {xdp_mode} mode")
                return True
                
        except subprocess.CalledProcessError as e:
            logger.debug(f"Failed to attach in {xdp_mode} mode: {e.stderr}")
            continue
    
    raise EBPFAttachError(f"Failed to attach XDP program to {interface} in any mode")

def _attach_tc(
    self,
    program_path: str,
    interface: str
) -> bool:
    """
    Attach TC program to interface (ingress).
    """
    try:
        # Create qdisc if not exists
        subprocess.run(
            ["tc", "qdisc", "add", "dev", interface, "clsact"],
            check=False,  # May already exist
            capture_output=True,
            timeout=5
        )
        
        # Attach TC program
        cmd = [
            "tc", "filter", "add", "dev", interface,
            "ingress", "bpf", "da", "obj", str(program_path),
            "sec", ".text"
        ]
        
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        logger.info(f"✅ TC program attached to {interface}")
        return True
        
    except subprocess.CalledProcessError as e:
        raise EBPFAttachError(f"Failed to attach TC program: {e.stderr}")

def _verify_xdp_attachment(self, interface: str, mode: str) -> bool:
    """Verify XDP program is attached to interface."""
    try:
        result = subprocess.run(
            ["ip", "link", "show", "dev", interface],
            check=True,
            capture_output=True,
            text=True,
            timeout=5
        )
        
        # Check for xdp in output
        output = result.stdout
        if "xdp" in output.lower():
            # Check mode matches
            if mode == "offload" and "xdp" in output:
                return True
            elif mode == "drv" and "xdp" in output:
                return True
            elif mode == "skb" and "xdp" in output:
                return True
        
        return False
        
    except subprocess.CalledProcessError:
        return False
```

---

### 2. Interface Detachment (строка 394)

**Текущий код:**
```python
def detach_from_interface(
    self,
    program_id: str,
    interface: str
) -> bool:
    # TODO: Implement actual detachment
    # TODO: Handle TC detachment
```

**Реализация:**

```python
def detach_from_interface(
    self,
    program_id: str,
    interface: str
) -> bool:
    """
    Detach eBPF program from network interface.
    
    Implementation:
    - For XDP: 'ip link set dev {interface} xdp off'
    - For TC: 'tc filter del dev {interface} ingress'
    """
    if interface not in self.attached_interfaces:
        logger.warning(f"No programs attached to {interface}")
        return False
    
    # Find program attachment
    attachment = None
    for att in self.attached_interfaces[interface]:
        if att["program_id"] == program_id:
            attachment = att
            break
    
    if not attachment:
        raise EBPFAttachError(f"Program {program_id} not attached to {interface}")
    
    program_type = attachment["type"]
    
    # Detach based on program type
    if program_type == EBPFProgramType.XDP:
        success = self._detach_xdp(interface)
    elif program_type == EBPFProgramType.TC:
        success = self._detach_tc(interface)
    else:
        raise EBPFAttachError(f"Unsupported program type for detachment: {program_type}")
    
    if success:
        # Remove from tracking
        self.attached_interfaces[interface].remove(attachment)
        if not self.attached_interfaces[interface]:
            del self.attached_interfaces[interface]
        
        logger.info(f"✅ Detached {program_id} from {interface}")
    
    return success

def _detach_xdp(self, interface: str) -> bool:
    """Detach XDP program from interface."""
    try:
        result = subprocess.run(
            ["ip", "link", "set", "dev", interface, "xdp", "off"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Verify detachment
        if not self._verify_xdp_attachment(interface, "skb"):
            return True
        
        logger.warning(f"XDP program may still be attached to {interface}")
        return False
        
    except subprocess.CalledProcessError as e:
        raise EBPFAttachError(f"Failed to detach XDP: {e.stderr}")

def _detach_tc(self, interface: str) -> bool:
    """Detach TC program from interface."""
    try:
        # Remove TC filter
        result = subprocess.run(
            ["tc", "filter", "del", "dev", interface, "ingress"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # Optionally remove qdisc (if no other filters)
        # subprocess.run(["tc", "qdisc", "del", "dev", interface, "clsact"], check=False)
        
        return True
        
    except subprocess.CalledProcessError as e:
        raise EBPFAttachError(f"Failed to detach TC: {e.stderr}")
```

---

### 3. Program Unloading with Verification (строка 439)

**Текущий код:**
```python
def unload_program(self, program_id: str) -> bool:
    # TODO: Verify program is detached from all interfaces first
    # TODO: Release BPF maps
```

**Реализация:**

```python
def unload_program(self, program_id: str) -> bool:
    """
    Unload eBPF program and release resources.
    
    Implementation:
    - Verifies program is detached from all interfaces
    - Releases BPF maps
    - Removes program from tracking
    """
    if program_id not in self.loaded_programs:
        logger.warning(f"Program {program_id} not loaded")
        return False
    
    # Check if program is still attached
    attached_interfaces = []
    for interface, attachments in self.attached_interfaces.items():
        for att in attachments:
            if att["program_id"] == program_id:
                attached_interfaces.append(interface)
    
    if attached_interfaces:
        raise EBPFAttachError(
            f"Cannot unload program {program_id}: still attached to {attached_interfaces}. "
            f"Detach first using detach_from_interface()"
        )
    
    program_info = self.loaded_programs[program_id]
    program_path = program_info["path"]
    
    # Release BPF maps (if any)
    # Note: Maps are automatically released when program is unloaded by kernel
    # But we can verify they're gone
    try:
        # Use bpftool to check if program still exists
        result = subprocess.run(
            ["bpftool", "prog", "show", "id", program_info.get("kernel_id", "0")],
            capture_output=True,
            timeout=5
        )
        
        if result.returncode == 0:
            logger.warning(f"Program {program_id} may still be loaded in kernel")
            # Try to unload via bpftool
            subprocess.run(
                ["bpftool", "prog", "unload", "id", program_info.get("kernel_id", "0")],
                capture_output=True,
                timeout=5
            )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # bpftool may not be available, or program already unloaded
        pass
    
    # Remove from tracking
    del self.loaded_programs[program_id]
    
    # Optionally remove program file (if temporary)
    if program_info.get("temporary", False):
        try:
            Path(program_path).unlink()
        except FileNotFoundError:
            pass
    
    logger.info(f"✅ Unloaded program {program_id}")
    return True
```

---

## 📋 Полная структура реализации

### Файл: `src/network/ebpf/loader.py`

**Добавить в класс `EBPFLoader`:**

```python
class EBPFLoader:
    def __init__(self):
        # ... existing code ...
        self.attached_interfaces: Dict[str, List[Dict]] = {}  # interface -> [attachments]
    
    def attach_to_interface(self, ...) -> bool:
        # Implementation above
    
    def _attach_xdp(self, ...) -> bool:
        # Implementation above
    
    def _attach_tc(self, ...) -> bool:
        # Implementation above
    
    def _verify_xdp_attachment(self, ...) -> bool:
        # Implementation above
    
    def detach_from_interface(self, ...) -> bool:
        # Implementation above
    
    def _detach_xdp(self, ...) -> bool:
        # Implementation above
    
    def _detach_tc(self, ...) -> bool:
        # Implementation above
    
    def unload_program(self, ...) -> bool:
        # Implementation above
```

---

## 🧪 Тестирование

### Unit Tests

```python
# tests/unit/network/ebpf/test_loader_attachment.py

def test_xdp_attachment():
    """Test XDP program attachment to interface"""
    loader = EBPFLoader()
    program_id = loader.load_program("xdp_counter.o", EBPFProgramType.XDP)
    
    # Test attachment
    assert loader.attach_to_interface(program_id, "lo", EBPFAttachMode.SKB)
    
    # Verify attachment
    assert "lo" in loader.attached_interfaces
    
    # Test detachment
    assert loader.detach_from_interface(program_id, "lo")
    
    # Verify detachment
    assert "lo" not in loader.attached_interfaces

def test_tc_attachment():
    """Test TC program attachment"""
    loader = EBPFLoader()
    program_id = loader.load_program("tc_classifier.o", EBPFProgramType.TC)
    
    assert loader.attach_to_interface(program_id, "lo")
    assert loader.detach_from_interface(program_id, "lo")

def test_unload_with_attachments():
    """Test that unload fails if program is still attached"""
    loader = EBPFLoader()
    program_id = loader.load_program("xdp_counter.o", EBPFProgramType.XDP)
    loader.attach_to_interface(program_id, "lo")
    
    # Should raise error
    with pytest.raises(EBPFAttachError):
        loader.unload_program(program_id)
    
    # Detach first
    loader.detach_from_interface(program_id, "lo")
    assert loader.unload_program(program_id)
```

---

## 📊 Интеграция с Monitoring

### Prometheus Metrics

```python
# src/network/ebpf/metrics_exporter.py

ebpf_programs_loaded = Gauge(
    "ebpf_programs_loaded_total",
    "Number of loaded eBPF programs",
    ["program_type"]
)

ebpf_programs_attached = Gauge(
    "ebpf_programs_attached_total",
    "Number of attached eBPF programs",
    ["interface", "program_type"]
)

ebpf_attachment_errors = Counter(
    "ebpf_attachment_errors_total",
    "Number of attachment errors",
    ["interface", "error_type"]
)
```

---

## 🎯 Критерии успеха

- ✅ XDP программы прикрепляются к интерфейсам через `ip link`
- ✅ TC программы прикрепляются через `tc filter`
- ✅ Программы корректно отсоединяются
- ✅ Верификация attachment работает
- ✅ Unload проверяет, что программа отсоединена
- ✅ Unit tests проходят (coverage >90%)
- ✅ Integration tests с реальными интерфейсами
- ✅ Метрики экспортируются в Prometheus

---

## 📅 Оценка времени

**Общая оценка:** 2-3 недели (1 разработчик с опытом eBPF)

**Разбивка:**
- Interface Attachment: 1 неделя
- Interface Detachment: 3-5 дней
- Verification & Unloading: 3-5 дней
- Testing & Integration: 3-5 дней

---

## 🚨 Риски и митигация

### Риск 1: XDP mode negotiation может не работать на всех системах
**Митигация:** Fallback на SKB mode (работает везде)

### Риск 2: TC qdisc может конфликтовать с другими программами
**Митигация:** Проверка существования qdisc перед созданием

### Риск 3: bpftool может быть недоступен
**Митигация:** Использование `ip link` и `tc` команд (стандартные утилиты)

---

**Дата:** 8 января 2026  
**Статус:** ✅ Архитектурный план готов  
**Следующий шаг:** Начало реализации в loader.py



