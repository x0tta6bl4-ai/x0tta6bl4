"""Shared runtime helpers for importing liboqs without noisy version warnings."""

from __future__ import annotations

import os
import warnings


def prepare_oqs_runtime() -> None:
    """Apply process-wide settings before importing ``oqs``.

    The local machine currently has a working liboqs runtime with a minor
    version mismatch between the native library and the Python bindings.
    That mismatch emits a noisy ``UserWarning`` on every import even when the
    runtime functions correctly. We suppress only that warning class/module and
    keep the actual import/operation failures visible.
    """

    os.environ.setdefault("OQS_DISABLE_AUTO_INSTALL", "1")
    warnings.filterwarnings("ignore", category=UserWarning, module="oqs")


prepare_oqs_runtime()
