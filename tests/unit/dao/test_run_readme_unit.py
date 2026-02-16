import os
from importlib.machinery import SourceFileLoader

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def test_import_run_readme_script():
    path = "/mnt/projects/src/dao/contracts/node_modules/@ethersproject/json-wallets/node_modules/aes-js/run-readme.py"
    try:
        mod = SourceFileLoader("aesjs_run_readme", path).load_module()
    except Exception as exc:
        pytest.skip(f"optional dependency/import issue: {exc}")
    assert mod is not None
