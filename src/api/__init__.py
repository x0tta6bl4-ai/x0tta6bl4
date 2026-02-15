# Expose common API submodules for easy patching/import in tests
# Import submodules lazily and guard imports to avoid heavy startup failures
try:
    from . import users  # noqa: F401
except Exception:
    users = None

try:
    from . import billing  # noqa: F401
except Exception:
    billing = None

try:
    from . import vpn  # noqa: F401
except Exception:
    vpn = None
