from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import src.network.ebpf.ebpf_loader as mod


class _Hook:
    def __init__(self):
        self.opened = 0
        self.attached = []

    def open_perf_buffer(self, perf_cb=None):
        self.opened += 1

    def attach(self, *args):
        self.attached.append(args)


class _FakeBPF:
    SCHED_CLS = "sched_cls"

    def __init__(self, text=None, cflags=None):
        self.text = text
        self.cflags = cflags
        self.cleaned = False
        self.hooks = {}
        self.loaded_funcs = []

    def __getitem__(self, key):
        if key not in self.hooks:
            self.hooks[key] = _Hook()
        return self.hooks[key]

    def __dir__(self):
        return ["['map1']", "['map2']"]

    def load_func(self, name, mode):
        fn = _Hook()
        self.loaded_funcs.append((name, mode, fn))
        return fn

    def cleanup(self):
        self.cleaned = True


def _program(name: str, bpf=None, loaded=True):
    return mod.EBPFProgram(name=name, bpf=bpf, program_path=f"{name}.c", loaded=loaded)


def test_load_program_stub_when_bcc_missing(monkeypatch):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", False)

    loader = mod.EBPFLoader()
    program = loader.load_program("/tmp/test_prog.c")

    assert program.name == "test_prog"
    assert program.bpf is None
    assert program.loaded is False


def test_load_program_bcc_success_and_default_cflags(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)
    monkeypatch.setattr(mod, "BPF", _FakeBPF)

    src = tmp_path / "prog_a.c"
    src.write_text("int main() { return 0; }")

    loader = mod.EBPFLoader()
    program = loader.load_program(str(src))

    assert program.loaded is True
    assert program.name == "prog_a"
    assert program.name in loader.loaded_programs
    stats = loader.program_stats[program.name]
    assert "loaded_at" in stats
    assert stats["maps"] == ["map1", "map2"]
    assert stats["events"] == 0


def test_load_program_bcc_failure_raises_runtime_error(monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)

    class _BrokenBPF:
        def __init__(self, **_kwargs):
            raise RuntimeError("compile fail")

    monkeypatch.setattr(mod, "BPF", _BrokenBPF)

    src = tmp_path / "prog_b.c"
    src.write_text("int main() { return 0; }")

    loader = mod.EBPFLoader()
    with pytest.raises(RuntimeError, match="Failed to load eBPF program"):
        loader.load_program(str(src))


def test_attach_hook_bcc_unavailable_or_program_not_loaded(monkeypatch):
    loader = mod.EBPFLoader()
    program = _program("stub", bpf=None, loaded=False)

    monkeypatch.setattr(mod, "BCC_AVAILABLE", False)
    assert loader.attach_hook(program, "sched_switch") is False

    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)
    assert loader.attach_hook(program, "sched_switch") is False


def test_attach_hook_supported_types_unknown_and_exception(monkeypatch):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)
    monkeypatch.setattr(mod, "BPF", _FakeBPF)

    loader = mod.EBPFLoader()
    fake_bpf = _FakeBPF(text="x", cflags=[])
    program = _program("prog_attach", bpf=fake_bpf)
    loader.program_stats[program.name] = {"attached_hooks": [], "events": 0}

    hooks = [
        "sched_switch",
        "tc",
        "sys_connect",
        "sys_enter_execve",
        "kmem_cache_alloc",
        "kfree_skb",
        "security_inode_permission",
        "sched_process_exec",
        "sched_process_exit",
        "tcp_retransmit_skb",
        "inet_sock_set_state",
        "security_prepare_creds",
        "tcp_connect",
        "block_rq_insert",
    ]

    for hook in hooks:
        assert loader.attach_hook(program, hook, interface="eth1", direction="egress")

    assert loader.attach_hook(program, "unknown_hook") is False
    assert len(program.attached_hooks) == len(hooks)
    assert len(loader.program_stats[program.name]["attached_hooks"]) == len(hooks)

    class _BrokenBPF(_FakeBPF):
        def __getitem__(self, _key):
            raise RuntimeError("hook fail")

    broken_program = _program("broken", bpf=_BrokenBPF(text="x", cflags=[]))
    loader.program_stats[broken_program.name] = {"attached_hooks": []}
    assert loader.attach_hook(broken_program, "sched_switch") is False


def test_detach_hook_paths(monkeypatch):
    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)

    loader = mod.EBPFLoader()
    program = _program("prog_detach", bpf=_FakeBPF())
    program.attached_hooks = ["tc", "sched_switch"]
    loader.program_stats[program.name] = {"attached_hooks": ["tc", "sched_switch"]}

    assert loader.detach_hook(program, "tc") is True
    assert loader.detach_hook(program, "sched_switch") is True
    assert loader.detach_hook(program, "unknown") is False

    broken = _program("broken_detach", bpf=_FakeBPF())
    broken.attached_hooks = None
    loader.program_stats[broken.name] = {"attached_hooks": ["sched_switch"]}
    assert loader.detach_hook(broken, "sched_switch") is False


def test_unload_program_paths(monkeypatch):
    loader = mod.EBPFLoader()

    monkeypatch.setattr(mod, "BCC_AVAILABLE", False)
    assert loader.unload_program(_program("stub", bpf=None, loaded=False)) is False

    monkeypatch.setattr(mod, "BCC_AVAILABLE", True)
    program = _program("prog_unload", bpf=_FakeBPF())
    program.attached_hooks = ["tc", "sched_switch"]
    loader.loaded_programs[program.name] = program

    detached = []

    def _detach(p, hook):
        detached.append((p.name, hook))
        return True

    monkeypatch.setattr(loader, "detach_hook", _detach)

    assert loader.unload_program(program) is True
    assert program.loaded is False
    assert program.name not in loader.loaded_programs
    assert detached == [("prog_unload", "tc"), ("prog_unload", "sched_switch")]

    class _BrokenCleanupBPF(_FakeBPF):
        def cleanup(self):
            raise RuntimeError("cleanup fail")

    broken_program = _program("prog_broken", bpf=_BrokenCleanupBPF())
    assert loader.unload_program(broken_program) is False


def test_stats_maps_timestamp_perf_callback_and_context_manager(monkeypatch):
    loader = mod.EBPFLoader()

    missing_stats = loader.get_program_stats(_program("none", bpf=None, loaded=False))
    assert missing_stats == {}

    loader.program_stats["p1"] = {"loaded_at": 10, "attached_hooks": [], "events": 1}
    monkeypatch.setattr(loader, "_get_timestamp", lambda: 25)
    stats = loader.get_program_stats(_program("p1", bpf=None, loaded=False))
    assert stats["current_time"] == 25
    assert stats["uptime_ns"] == 15

    loader._perf_event_cb(0, b"x", 1)
    assert loader.program_stats["p1"]["events"] == 2

    assert "p1" in loader.get_all_stats()

    class _NoGetItem:
        pass

    assert loader._get_program_maps(_NoGetItem()) == []
    assert loader._get_program_maps(_FakeBPF()) == ["map1", "map2"]

    assert isinstance(loader._get_timestamp(), int)

    p1 = _program("ctx1", bpf=_FakeBPF())
    p2 = _program("ctx2", bpf=_FakeBPF())
    loader.loaded_programs = {"ctx1": p1, "ctx2": p2}

    unloaded = []

    def _unload(program):
        unloaded.append(program.name)
        return True

    monkeypatch.setattr(loader, "unload_program", _unload)

    with loader as ctx:
        assert ctx is loader

    assert sorted(unloaded) == ["ctx1", "ctx2"]


def test_stub_map_and_create_stub_program():
    stub = mod.StubEBPFProgram("stub_program")
    stub_map = stub["flows"]

    stub_map["k1"] = "v1"
    assert stub_map["k1"] == "v1"
    assert stub_map.get("k1") == "v1"
    assert list(stub_map.items()) == [("k1", "v1")]
    assert list(stub_map.keys()) == ["k1"]
    assert list(stub_map.values()) == ["v1"]

    created = mod.create_stub_program("/tmp/example_prog.c")
    assert created.name == "example_prog"
    assert created.loaded is False
    assert isinstance(created.bpf, mod.StubEBPFProgram)
