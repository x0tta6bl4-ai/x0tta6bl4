"""
Conftest для API тестов.

Мокирует optional dependencies перед импортом src модулей.
"""
import sys
from unittest.mock import MagicMock

# Mock optional dependencies before any src imports
_hvac_mock = MagicMock()
_hvac_mock.exceptions = MagicMock()
_hvac_mock.api = MagicMock()
_hvac_mock.api.auth_methods = MagicMock()
_hvac_mock.api.auth_methods.Kubernetes = MagicMock()

_torch_mock = MagicMock()
_torch_nn_mock = MagicMock()

_mocked_modules = {
    'hvac': _hvac_mock,
    'hvac.exceptions': _hvac_mock.exceptions,
    'hvac.api': _hvac_mock.api,
    'hvac.api.auth_methods': _hvac_mock.api.auth_methods,
    'torch': _torch_mock,
    'torch.nn': _torch_nn_mock,
}

for mod_name, mock_obj in _mocked_modules.items():
    if mod_name not in sys.modules:
        sys.modules[mod_name] = mock_obj

import pytest
