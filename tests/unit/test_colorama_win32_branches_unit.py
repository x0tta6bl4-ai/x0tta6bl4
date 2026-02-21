from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest


os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


class _Fn:
    def __init__(self, return_value=True, side_effect=None):
        self.return_value = return_value
        self.side_effect = side_effect
        self.argtypes = None
        self.restype = None
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if self.side_effect is not None:
            return self.side_effect(*args)
        return self.return_value


class _Value:
    def __init__(self, value=0):
        self.value = value


class _COORD:
    def __init__(self, x=0, y=0):
        self.X = x
        self.Y = y


class _SMALL_RECT:
    def __init__(self, top=0, left=0, bottom=0, right=0):
        self.Top = top
        self.Left = left
        self.Bottom = bottom
        self.Right = right


class _Structure:
    _fields_ = []

    def __init__(self):
        for name, field_type in self._fields_:
            try:
                setattr(self, name, field_type())
            except Exception:
                setattr(self, name, 0)


class _CChar:
    def __init__(self, value=b""):
        self.value = value


def _load_win32_with_fake_ctypes(monkeypatch: pytest.MonkeyPatch, module_name: str):
    def _populate_csbi(_handle, csbi):
        csbi.dwSize = _COORD(80, 25)
        csbi.dwCursorPosition = _COORD(2, 3)
        csbi.wAttributes = 7
        csbi.srWindow = _SMALL_RECT(10, 20, 30, 40)
        csbi.dwMaximumWindowSize = _COORD(120, 60)
        return True

    def _fill_chars(_handle, _char, length, _start, num_written):
        num_written.value = length.value
        return True

    get_std_handle = _Fn(side_effect=lambda stream_id: stream_id)
    get_console_screen_buffer_info = _Fn(side_effect=_populate_csbi)
    set_console_text_attribute = _Fn(return_value=True)
    set_console_cursor_position = _Fn(return_value=True)
    fill_console_output_character = _Fn(side_effect=_fill_chars)
    fill_console_output_attribute = _Fn(return_value=True)
    set_console_title = _Fn(return_value=True)
    get_console_mode = _Fn(side_effect=lambda _handle, mode: setattr(mode, "value", 8) or True)
    set_console_mode = _Fn(return_value=True)

    kernel32 = types.SimpleNamespace(
        GetStdHandle=get_std_handle,
        GetConsoleScreenBufferInfo=get_console_screen_buffer_info,
        SetConsoleTextAttribute=set_console_text_attribute,
        SetConsoleCursorPosition=set_console_cursor_position,
        FillConsoleOutputCharacterA=fill_console_output_character,
        FillConsoleOutputAttribute=fill_console_output_attribute,
        SetConsoleTitleW=set_console_title,
        GetConsoleMode=get_console_mode,
        SetConsoleMode=set_console_mode,
    )

    class _LibraryLoader:
        def __init__(self, _dll):
            self.kernel32 = kernel32

    wintypes = types.SimpleNamespace(
        _COORD=_COORD,
        WORD=_Value,
        SMALL_RECT=_SMALL_RECT,
        DWORD=_Value,
        HANDLE=_Value,
        BOOL=_Value,
        LPCWSTR=str,
    )

    fake_ctypes = types.ModuleType("ctypes")
    fake_ctypes.LibraryLoader = _LibraryLoader
    fake_ctypes.WinDLL = object
    fake_ctypes.wintypes = wintypes
    fake_ctypes.byref = lambda obj: obj
    fake_ctypes.Structure = _Structure
    fake_ctypes.c_char = _CChar
    fake_ctypes.POINTER = lambda obj: obj
    fake_ctypes.WinError = lambda: RuntimeError("win error")

    monkeypatch.setitem(sys.modules, "ctypes", fake_ctypes)

    module_path = Path("/usr/lib/python3/dist-packages/colorama/win32.py")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module, kernel32


def test_colorama_win32_windows_branch_success(monkeypatch: pytest.MonkeyPatch):
    mod, kernel32 = _load_win32_with_fake_ctypes(
        monkeypatch, "_colorama_win32_windows_branch_success_cov"
    )

    assert mod.windll is not None
    assert mod._winapi_test(mod.STDOUT) is True
    assert mod.winapi_test() is True

    csbi = mod.GetConsoleScreenBufferInfo(mod.STDOUT)
    assert "80" in str(csbi)
    assert mod.SetConsoleTextAttribute(mod.STDOUT, 7) is True

    assert mod.SetConsoleCursorPosition(mod.STDOUT, (0, 0)) is None
    assert mod.SetConsoleCursorPosition(mod.STDOUT, (2, 3), adjust=False) is True
    assert mod.SetConsoleCursorPosition(mod.STDOUT, (2, 3), adjust=True) is True

    assert mod.FillConsoleOutputCharacter(mod.STDOUT, "A", 5, mod.COORD(1, 1)) == 5
    assert mod.FillConsoleOutputAttribute(mod.STDOUT, 7, 5, mod.COORD(1, 1)) is True
    assert mod.SetConsoleTitle("demo") is True

    assert mod.GetConsoleMode(1) == 8
    assert mod.SetConsoleMode(1, mod.ENABLE_VIRTUAL_TERMINAL_PROCESSING) is None

    assert kernel32.GetConsoleMode.calls
    assert kernel32.SetConsoleMode.calls


def test_colorama_win32_mode_errors_and_false_winapi(monkeypatch: pytest.MonkeyPatch):
    mod, kernel32 = _load_win32_with_fake_ctypes(
        monkeypatch, "_colorama_win32_windows_branch_errors_cov"
    )

    kernel32.GetConsoleScreenBufferInfo.side_effect = lambda *_args: False
    assert mod._winapi_test(mod.STDOUT) is False

    kernel32.GetConsoleMode.side_effect = lambda *_args: False
    with pytest.raises(RuntimeError, match="win error"):
        mod.GetConsoleMode(1)

    kernel32.GetConsoleMode.side_effect = lambda _handle, mode: setattr(mode, "value", 12) or True
    kernel32.SetConsoleMode.return_value = False
    with pytest.raises(RuntimeError, match="win error"):
        mod.SetConsoleMode(1, mod.ENABLE_VIRTUAL_TERMINAL_PROCESSING)
