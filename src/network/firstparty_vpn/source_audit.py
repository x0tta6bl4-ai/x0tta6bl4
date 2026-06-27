"""First-party source dependency audit for production VPN readiness."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import sys
from typing import Iterable

from .ops import assert_privacy_safe, hash_identifier


FORBIDDEN_IMPORT_PREFIXES = frozenset(
    {
        "cryptography",
        "liboqs",
        "nacl",
        "oqs",
        "OpenSSL",
        "pywireguard",
        "wireguard",
    }
)
FORBIDDEN_STRING_MARKERS = frozenset(
    {
        "liboqs",
        "oqs.",
        "wireguard",
        "wg-quick",
        "openvpn",
        "openconnect",
        "strongswan",
        "ipsec",
        "xray",
        "v2ray",
        "shadowsocks",
        "tailscale",
        "zerotier",
    }
)
FORBIDDEN_NATIVE_LIBRARY_MARKERS = frozenset(
    {
        "crypto",
        "libcrypto",
        "liboqs",
        "libssl",
        "libsodium",
        "libwireguard",
        "nacl",
        "openssl",
        "oqs",
        "sodium",
        "ssl",
        "wireguard",
    }
)
ALLOWED_FIRSTPARTY_IMPORT_PREFIXES = frozenset({"src.network.firstparty_vpn"})
DEPENDENCY_FILE_NAMES = frozenset(
    {
        "Pipfile",
        "Pipfile.lock",
        "package-lock.json",
        "package.json",
        "pnpm-lock.yaml",
        "poetry.lock",
        "pyproject.toml",
        "requirements-dev.txt",
        "requirements-staging.txt",
        "requirements.txt",
        "setup.cfg",
        "setup.py",
        "uv.lock",
        "yarn.lock",
    }
)
DEPENDENCY_FILE_SUFFIXES = (".requirements.txt",)
RUNTIME_ARTIFACT_FILE_NAMES = frozenset(
    {
        "Dockerfile",
        "Containerfile",
    }
)
RUNTIME_ARTIFACT_FILE_SUFFIXES = (
    ".conf",
    ".env",
    ".ini",
    ".json",
    ".service",
    ".sh",
    ".socket",
    ".timer",
    ".toml",
    ".yaml",
    ".yml",
)
FOREIGN_BACKEND_ARTIFACT_FILE_SUFFIXES = (
    ".a",
    ".bin",
    ".dll",
    ".dylib",
    ".exe",
    ".ko",
    ".lib",
    ".node",
    ".o",
    ".pyd",
    ".so",
    ".tar",
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
    ".tgz",
    ".whl",
    ".zip",
)


class FirstPartySourceAuditError(ValueError):
    """Raised when first-party source audit input is invalid."""


@dataclass(frozen=True)
class FirstPartySourceAuditEvidence:
    """Privacy-safe evidence that first-party VPN source has no foreign backend."""

    root_hash: str
    source_tree_hash: str
    scanned_files: int
    captured_at: int = 0
    forbidden_imports: tuple[str, ...] = ()
    external_imports: tuple[str, ...] = ()
    forbidden_markers: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _assert_sha256_hex(self.root_hash, "root_hash")
        _assert_sha256_hex(self.source_tree_hash, "source_tree_hash")
        if self.scanned_files < 1:
            raise FirstPartySourceAuditError("first-party source audit scanned no files")
        if self.captured_at < 0:
            raise FirstPartySourceAuditError("first-party source audit time is invalid")

    @property
    def passed(self) -> bool:
        return not (
            self.forbidden_imports
            or self.external_imports
            or self.forbidden_markers
        )

    @property
    def reasons(self) -> tuple[str, ...]:
        reasons: list[str] = []
        if self.forbidden_imports:
            reasons.append("firstparty_forbidden_import_detected")
        if self.external_imports:
            reasons.append("firstparty_external_import_detected")
        if self.forbidden_markers:
            reasons.append("firstparty_foreign_protocol_marker_detected")
        return tuple(reasons)

    def evidence_hash(self) -> str:
        return hashlib.sha256(_canonical_json(self.to_json_dict())).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "allowed": self.passed,
            "captured_at": self.captured_at,
            "external_import_hashes": _hash_many(
                self.external_imports,
                namespace="firstparty-source-external-import",
            ),
            "forbidden_import_hashes": _hash_many(
                self.forbidden_imports,
                namespace="firstparty-source-forbidden-import",
            ),
            "forbidden_marker_hashes": _hash_many(
                self.forbidden_markers,
                namespace="firstparty-source-forbidden-marker",
            ),
            "reasons": list(self.reasons),
            "root_hash": self.root_hash,
            "scanned_files": self.scanned_files,
            "source_tree_hash": self.source_tree_hash,
            "version": 1,
        }
        assert_privacy_safe(payload)
        return payload


def audit_firstparty_source_tree(
    root: Path | str,
    *,
    captured_at: int | None = None,
) -> FirstPartySourceAuditEvidence:
    """Audit a first-party VPN source tree for foreign VPN/PQC dependencies."""

    root_path = Path(root)
    collected_at = _utc_now() if captured_at is None else captured_at
    if collected_at < 0:
        raise FirstPartySourceAuditError("first-party source audit time is invalid")
    if not root_path.exists():
        raise FirstPartySourceAuditError("first-party source audit root is missing")
    if not root_path.is_dir():
        raise FirstPartySourceAuditError("first-party source audit root must be a directory")

    python_files = tuple(
        sorted(path for path in root_path.rglob("*.py") if path.is_file())
    )
    if not python_files:
        raise FirstPartySourceAuditError("first-party source audit found no Python files")
    dependency_files = _dependency_manifest_files(root_path)
    runtime_artifact_files = _runtime_artifact_files(root_path)
    foreign_artifact_files = _foreign_backend_artifact_files(root_path)
    files = tuple(
        sorted(
            {
                *python_files,
                *dependency_files,
                *runtime_artifact_files,
                *foreign_artifact_files,
            }
        )
    )

    forbidden_imports: list[str] = []
    external_imports: list[str] = []
    forbidden_markers: list[str] = []
    file_hashes: list[str] = []
    root_resolved = root_path.resolve()

    for path in files:
        relative = path.relative_to(root_path).as_posix()
        if path in foreign_artifact_files and path not in (
            *python_files,
            *dependency_files,
            *runtime_artifact_files,
        ):
            content = path.read_bytes()
            file_hashes.append(_file_bytes_hash(relative, content))
            forbidden_markers.extend(
                f"{relative}:{marker}"
                for marker in _forbidden_artifact_name_markers(relative)
            )
            continue

        source = path.read_text(encoding="utf-8")
        file_hashes.append(_file_hash(relative, source))
        if path.suffix == ".py":
            try:
                tree = ast.parse(source, filename=str(path))
            except SyntaxError as exc:
                raise FirstPartySourceAuditError(
                    f"first-party source audit cannot parse {relative}"
                ) from exc

            forbidden_imports.extend(
                f"{relative}:{module}"
                for module in _forbidden_imports(tree, relative_path=relative)
            )
            external_imports.extend(
                f"{relative}:{module}"
                for module in _external_imports(tree, relative_path=relative)
            )
            if path.name != "source_audit.py":
                forbidden_markers.extend(
                    f"{relative}:{marker}"
                    for marker in _forbidden_string_markers(tree)
                )
        elif path in dependency_files or path in runtime_artifact_files:
            forbidden_markers.extend(
                f"{relative}:{marker}"
                for marker in _forbidden_dependency_markers(source)
            )
        if path in foreign_artifact_files:
            forbidden_markers.extend(
                f"{relative}:{marker}"
                for marker in _forbidden_artifact_name_markers(relative)
            )

    return FirstPartySourceAuditEvidence(
        root_hash=hash_identifier(
            root_resolved.as_posix(),
            namespace="firstparty-source-root",
        ),
        source_tree_hash=hashlib.sha256(
            _canonical_json(sorted(file_hashes))
        ).hexdigest(),
        scanned_files=len(files),
        captured_at=collected_at,
        forbidden_imports=tuple(sorted(set(forbidden_imports))),
        external_imports=tuple(sorted(set(external_imports))),
        forbidden_markers=tuple(sorted(set(forbidden_markers))),
    )


def _dependency_manifest_files(root_path: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        if path.name in DEPENDENCY_FILE_NAMES or path.name.endswith(
            DEPENDENCY_FILE_SUFFIXES
        ):
            files.append(path)
    return tuple(sorted(files))


def _runtime_artifact_files(root_path: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        if path.name in RUNTIME_ARTIFACT_FILE_NAMES or path.name.endswith(
            RUNTIME_ARTIFACT_FILE_SUFFIXES
        ):
            files.append(path)
    return tuple(sorted(files))


def _foreign_backend_artifact_files(root_path: Path) -> tuple[Path, ...]:
    files: list[Path] = []
    for path in root_path.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root_path).as_posix()
        if not path.name.lower().endswith(FOREIGN_BACKEND_ARTIFACT_FILE_SUFFIXES):
            continue
        if _forbidden_artifact_name_markers(relative):
            files.append(path)
    return tuple(sorted(files))


def _forbidden_imports(tree: ast.AST, *, relative_path: str) -> tuple[str, ...]:
    return tuple(
        module
        for module in _imported_modules(tree, relative_path=relative_path)
        if _matches_prefix(module, FORBIDDEN_IMPORT_PREFIXES)
    )


def _external_imports(tree: ast.AST, *, relative_path: str) -> tuple[str, ...]:
    external: list[str] = []
    for module in _imported_modules(tree, relative_path=relative_path):
        root = module.split(".", 1)[0]
        if _matches_prefix(module, ALLOWED_FIRSTPARTY_IMPORT_PREFIXES):
            continue
        if root in sys.stdlib_module_names:
            continue
        external.append(module)
    return tuple(external)


def _imported_modules(tree: ast.AST, *, relative_path: str) -> tuple[str, ...]:
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                modules.extend(_relative_import_modules(node, relative_path=relative_path))
            elif node.module:
                modules.append(node.module)
    modules.extend(_dynamic_imported_modules(tree))
    modules.extend(_python_module_process_modules(tree, relative_path=relative_path))
    modules.extend(_importlib_loader_modules(tree))
    modules.extend(_importlib_resources_modules(tree))
    modules.extend(_stdlib_module_resolution_modules(tree))
    modules.extend(
        _literal_runtime_code_imported_modules(tree, relative_path=relative_path)
    )
    return tuple(modules)


def _relative_import_modules(
    node: ast.ImportFrom,
    *,
    relative_path: str,
) -> tuple[str, ...]:
    base = _relative_import_base(relative_path, level=node.level)
    if base is None:
        return (f"__outside_firstparty_source__.{node.module or '*'}",)
    if node.module:
        return (f"{base}.{node.module}",)
    return tuple(
        f"{base}.{alias.name}"
        for alias in node.names
        if alias.name != "*"
    ) or (base,)


def _relative_import_base(relative_path: str, *, level: int) -> str | None:
    package_parts = ["src", "network", "firstparty_vpn"]
    path = Path(relative_path)
    if path.name == "__init__.py":
        package_parts.extend(path.parent.parts)
    else:
        package_parts.extend(path.parent.parts)
    trim = level - 1
    if trim > len(package_parts):
        return None
    if trim:
        package_parts = package_parts[:-trim]
    return ".".join(package_parts)


def _dynamic_imported_modules(tree: ast.AST) -> tuple[str, ...]:
    builtins_aliases = {"builtins", "__builtins__"}
    importlib_aliases = {"importlib"}
    dynamic_import_callables = {"__import__"}
    constants = _constant_string_assignments(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "builtins":
                    builtins_aliases.add(alias.asname or alias.name)
                if alias.name == "importlib":
                    importlib_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "builtins":
                for alias in node.names:
                    if alias.name == "__import__":
                        dynamic_import_callables.add(alias.asname or alias.name)
            elif node.module == "importlib":
                for alias in node.names:
                    if alias.name == "*":
                        dynamic_import_callables.add("import_module")
                    elif alias.name == "import_module":
                        dynamic_import_callables.add(alias.asname or alias.name)
    dynamic_import_callables.update(
        _dynamic_import_callable_assignments(
            tree,
            builtins_aliases=builtins_aliases,
            importlib_aliases=importlib_aliases,
            constants=constants,
            known_callables=dynamic_import_callables,
        )
    )

    modules: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        imported_modules = _dynamic_import_module_names(node, constants=constants)
        if not imported_modules:
            continue
        if isinstance(node.func, ast.Name):
            if node.func.id in dynamic_import_callables:
                modules.extend(imported_modules)
        elif _is_dynamic_import_callable(
            node.func,
            builtins_aliases=builtins_aliases,
            importlib_aliases=importlib_aliases,
            constants=constants,
            known_callables=dynamic_import_callables,
        ):
            modules.extend(imported_modules)
    return tuple(modules)


def _dynamic_import_module_names(
    node: ast.Call,
    *,
    constants: dict[str, str],
) -> tuple[str, ...]:
    name_node: ast.AST | None = None
    if node.args:
        name_node = node.args[0]
    else:
        for keyword in node.keywords:
            if keyword.arg == "name":
                name_node = keyword.value
                break
    if name_node is None:
        return ()

    raw_name = _literal_string_value(name_node, constants=constants)
    if raw_name is None:
        return ()
    name = raw_name.strip()
    if not name:
        return ()

    modules: list[str] = []
    if not name.startswith("."):
        modules.append(name)

    package = _dynamic_import_package_name(node, constants=constants)
    if package is not None and name.startswith("."):
        resolved = _resolve_relative_module_name(name, package=package)
        if resolved is not None:
            modules.append(resolved)
    return tuple(modules)


def _dynamic_import_package_name(
    node: ast.Call,
    *,
    constants: dict[str, str],
) -> str | None:
    if len(node.args) >= 2:
        return _literal_module_name(node.args[1], constants=constants)
    for keyword in node.keywords:
        if keyword.arg == "package":
            return _literal_module_name(keyword.value, constants=constants)
    return None


def _resolve_relative_module_name(name: str, *, package: str) -> str | None:
    stripped_name = name.strip()
    stripped_package = package.strip()
    if not stripped_name.startswith(".") or not stripped_package:
        return None

    level = len(stripped_name) - len(stripped_name.lstrip("."))
    suffix = stripped_name[level:]
    package_parts = stripped_package.split(".")
    base_size = len(package_parts) - level + 1
    if base_size < 1:
        return None
    parts = package_parts[:base_size]
    if suffix:
        parts.append(suffix)
    return ".".join(parts)


_PYTHON_PROCESS_LAUNCH_FUNCTIONS = frozenset(
    {
        "call",
        "check_call",
        "check_output",
        "Popen",
        "run",
    }
)
_PYTHON_SHELL_LAUNCH_FUNCTIONS = frozenset(
    {
        "popen",
        "system",
    }
)
_PYTHON_OS_PROCESS_LAUNCH_FUNCTIONS = frozenset(
    {
        "execl",
        "execle",
        "execlp",
        "execlpe",
        "execv",
        "execve",
        "execvp",
        "execvpe",
        "spawnl",
        "spawnle",
        "spawnlp",
        "spawnlpe",
        "spawnv",
        "spawnve",
        "spawnvp",
        "spawnvpe",
    }
)
_PACKAGE_INSTALL_COMMANDS = frozenset(
    {
        "add",
        "get",
        "install",
    }
)
_PACKAGE_MANAGER_COMMANDS = frozenset(
    {
        "apk",
        "apt",
        "apt-get",
        "brew",
        "dnf",
        "go",
        "npm",
        "pip",
        "pip3",
        "pnpm",
        "poetry",
        "uv",
        "yarn",
        "yum",
    }
)
_DOWNLOADER_COMMANDS = frozenset(
    {
        "aria2c",
        "curl",
        "fetch",
        "wget",
    }
)
_VCS_COMMANDS = frozenset(
    {
        "gh",
        "git",
        "hg",
        "svn",
    }
)


def _python_module_process_modules(
    tree: ast.AST,
    *,
    relative_path: str,
) -> tuple[str, ...]:
    constants = _constant_string_assignments(tree)
    subprocess_aliases = {"subprocess"}
    os_aliases = {"os"}
    sys_aliases = {"sys"}
    sys_executable_names: set[str] = set()
    process_callables: set[str] = set()
    os_process_callables: set[str] = set()
    shell_callables: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                if alias.name == "subprocess":
                    subprocess_aliases.add(bound)
                elif alias.name == "os":
                    os_aliases.add(bound)
                elif alias.name == "sys":
                    sys_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "subprocess":
                for alias in node.names:
                    if alias.name == "*":
                        process_callables.update(_PYTHON_PROCESS_LAUNCH_FUNCTIONS)
                    elif alias.name in _PYTHON_PROCESS_LAUNCH_FUNCTIONS:
                        process_callables.add(alias.asname or alias.name)
            elif node.module == "os":
                for alias in node.names:
                    if alias.name == "*":
                        shell_callables.update(_PYTHON_SHELL_LAUNCH_FUNCTIONS)
                        os_process_callables.update(_PYTHON_OS_PROCESS_LAUNCH_FUNCTIONS)
                    elif alias.name in _PYTHON_SHELL_LAUNCH_FUNCTIONS:
                        shell_callables.add(alias.asname or alias.name)
                    elif alias.name in _PYTHON_OS_PROCESS_LAUNCH_FUNCTIONS:
                        os_process_callables.add(alias.asname or alias.name)
            elif node.module == "sys":
                for alias in node.names:
                    if alias.name == "executable":
                        sys_executable_names.add(alias.asname or alias.name)

    (
        new_process_callables,
        new_os_process_callables,
        new_shell_callables,
    ) = _python_process_callable_assignments(
        tree,
        subprocess_aliases=subprocess_aliases,
        os_aliases=os_aliases,
        constants=constants,
        known_process_callables=process_callables,
        known_os_process_callables=os_process_callables,
        known_shell_callables=shell_callables,
    )
    process_callables.update(new_process_callables)
    os_process_callables.update(new_os_process_callables)
    shell_callables.update(new_shell_callables)

    modules: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_python_process_launch_callable(
            node.func,
            subprocess_aliases=subprocess_aliases,
            constants=constants,
            known_callables=process_callables,
        ):
            modules.extend(
                _python_modules_from_process_call(
                    node,
                    constants=constants,
                    relative_path=relative_path,
                    sys_aliases=sys_aliases,
                    sys_executable_names=sys_executable_names,
                )
            )
        elif _is_python_os_process_launch_callable(
            node.func,
            os_aliases=os_aliases,
            constants=constants,
            known_callables=os_process_callables,
        ):
            modules.extend(
                _python_modules_from_os_process_call(
                    node,
                    constants=constants,
                    relative_path=relative_path,
                    sys_aliases=sys_aliases,
                    sys_executable_names=sys_executable_names,
                )
            )
        elif _is_python_shell_launch_callable(
            node.func,
            os_aliases=os_aliases,
            constants=constants,
            known_callables=shell_callables,
        ):
            modules.extend(
                _python_modules_from_shell_call(
                    node,
                    constants=constants,
                    relative_path=relative_path,
                )
            )
    return tuple(modules)


def _python_process_callable_assignments(
    tree: ast.AST,
    *,
    subprocess_aliases: set[str],
    os_aliases: set[str],
    constants: dict[str, str],
    known_process_callables: set[str],
    known_os_process_callables: set[str],
    known_shell_callables: set[str],
) -> tuple[set[str], set[str], set[str]]:
    process_aliases = set(known_process_callables)
    os_process_aliases = set(known_os_process_callables)
    shell_aliases = set(known_shell_callables)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            value: ast.AST | None = None
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = [node.target]
                value = node.value
            if value is None:
                continue

            is_process_callable = _is_python_process_launch_callable(
                value,
                subprocess_aliases=subprocess_aliases,
                constants=constants,
                known_callables=process_aliases,
            )
            is_os_process_callable = _is_python_os_process_launch_callable(
                value,
                os_aliases=os_aliases,
                constants=constants,
                known_callables=os_process_aliases,
            )
            is_shell_callable = _is_python_shell_launch_callable(
                value,
                os_aliases=os_aliases,
                constants=constants,
                known_callables=shell_aliases,
            )
            if (
                not is_process_callable
                and not is_os_process_callable
                and not is_shell_callable
            ):
                continue
            for target in targets:
                if not isinstance(target, ast.Name):
                    continue
                if is_process_callable and target.id not in process_aliases:
                    process_aliases.add(target.id)
                    changed = True
                if is_os_process_callable and target.id not in os_process_aliases:
                    os_process_aliases.add(target.id)
                    changed = True
                if is_shell_callable and target.id not in shell_aliases:
                    shell_aliases.add(target.id)
                    changed = True
    return (
        process_aliases - known_process_callables,
        os_process_aliases - known_os_process_callables,
        shell_aliases - known_shell_callables,
    )


def _is_python_process_launch_callable(
    node: ast.AST,
    *,
    subprocess_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in known_callables
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return (
            node.attr in _PYTHON_PROCESS_LAUNCH_FUNCTIONS
            and node.value.id in subprocess_aliases
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Name)
    ):
        attribute = _literal_string_value(node.args[1], constants=constants)
        return (
            attribute in _PYTHON_PROCESS_LAUNCH_FUNCTIONS
            and node.args[0].id in subprocess_aliases
        )
    lookup = _module_dictionary_lookup(
        node,
        module_aliases=subprocess_aliases,
        constants=constants,
    )
    if lookup is not None:
        _, attribute = lookup
        return attribute in _PYTHON_PROCESS_LAUNCH_FUNCTIONS
    return False


def _is_python_shell_launch_callable(
    node: ast.AST,
    *,
    os_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in known_callables
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return (
            node.attr in _PYTHON_SHELL_LAUNCH_FUNCTIONS
            and node.value.id in os_aliases
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Name)
    ):
        attribute = _literal_string_value(node.args[1], constants=constants)
        return (
            attribute in _PYTHON_SHELL_LAUNCH_FUNCTIONS
            and node.args[0].id in os_aliases
        )
    lookup = _module_dictionary_lookup(
        node,
        module_aliases=os_aliases,
        constants=constants,
    )
    if lookup is not None:
        _, attribute = lookup
        return attribute in _PYTHON_SHELL_LAUNCH_FUNCTIONS
    return False


def _is_python_os_process_launch_callable(
    node: ast.AST,
    *,
    os_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in known_callables
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return (
            node.attr in _PYTHON_OS_PROCESS_LAUNCH_FUNCTIONS
            and node.value.id in os_aliases
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Name)
    ):
        attribute = _literal_string_value(node.args[1], constants=constants)
        return (
            attribute in _PYTHON_OS_PROCESS_LAUNCH_FUNCTIONS
            and node.args[0].id in os_aliases
        )
    lookup = _module_dictionary_lookup(
        node,
        module_aliases=os_aliases,
        constants=constants,
    )
    if lookup is not None:
        _, attribute = lookup
        return attribute in _PYTHON_OS_PROCESS_LAUNCH_FUNCTIONS
    return False


def _python_modules_from_process_call(
    node: ast.Call,
    *,
    constants: dict[str, str],
    relative_path: str,
    sys_aliases: set[str],
    sys_executable_names: set[str],
) -> tuple[str, ...]:
    command_node = _first_call_argument(node, keyword_names={"args"})
    if command_node is None:
        return ()
    tokens = _literal_command_tokens(
        command_node,
        constants=constants,
        sys_aliases=sys_aliases,
        sys_executable_names=sys_executable_names,
    )
    return _python_modules_from_command_tokens(tokens, relative_path=relative_path)


def _python_modules_from_os_process_call(
    node: ast.Call,
    *,
    constants: dict[str, str],
    relative_path: str,
    sys_aliases: set[str],
    sys_executable_names: set[str],
) -> tuple[str, ...]:
    modules: list[str] = []
    if len(node.args) >= 2:
        modules.extend(
            _python_modules_from_command_tokens(
                _literal_command_tokens(
                    node.args[1],
                    constants=constants,
                    sys_aliases=sys_aliases,
                    sys_executable_names=sys_executable_names,
                ),
                relative_path=relative_path,
            )
        )
        modules.extend(
            _python_modules_from_command_tokens(
                _literal_command_tokens_from_elements(
                    node.args[1:],
                    constants=constants,
                    sys_aliases=sys_aliases,
                    sys_executable_names=sys_executable_names,
                ),
                relative_path=relative_path,
            )
        )
    if len(node.args) >= 3:
        modules.extend(
            _python_modules_from_command_tokens(
                _literal_command_tokens(
                    node.args[2],
                    constants=constants,
                    sys_aliases=sys_aliases,
                    sys_executable_names=sys_executable_names,
                ),
                relative_path=relative_path,
            )
        )
        modules.extend(
            _python_modules_from_command_tokens(
                _literal_command_tokens_from_elements(
                    node.args[2:],
                    constants=constants,
                    sys_aliases=sys_aliases,
                    sys_executable_names=sys_executable_names,
                ),
                relative_path=relative_path,
            )
        )
    return tuple(modules)


def _python_modules_from_shell_call(
    node: ast.Call,
    *,
    constants: dict[str, str],
    relative_path: str,
) -> tuple[str, ...]:
    command_node = _first_call_argument(node, keyword_names={"cmd", "command"})
    if command_node is None:
        return ()
    command = _literal_string_value(command_node, constants=constants)
    if command is None:
        return ()
    return _python_modules_from_command_tokens(
        _shell_command_tokens(command),
        relative_path=relative_path,
    )


def _first_call_argument(
    node: ast.Call,
    *,
    keyword_names: set[str],
) -> ast.AST | None:
    if node.args:
        return node.args[0]
    for keyword in node.keywords:
        if keyword.arg in keyword_names:
            return keyword.value
    return None


def _literal_command_tokens(
    node: ast.AST,
    *,
    constants: dict[str, str],
    sys_aliases: set[str],
    sys_executable_names: set[str],
) -> tuple[str, ...]:
    if isinstance(node, ast.List | ast.Tuple):
        tokens: list[str] = []
        for element in node.elts:
            token = _literal_command_token(
                element,
                constants=constants,
                sys_aliases=sys_aliases,
                sys_executable_names=sys_executable_names,
            )
            if token is None:
                return ()
            tokens.append(token)
        return tuple(tokens)

    command = _literal_string_value(node, constants=constants)
    if command is not None:
        return _shell_command_tokens(command)
    return ()


def _literal_command_tokens_from_elements(
    elements: list[ast.expr],
    *,
    constants: dict[str, str],
    sys_aliases: set[str],
    sys_executable_names: set[str],
) -> tuple[str, ...]:
    tokens: list[str] = []
    for element in elements:
        if isinstance(element, ast.Dict):
            break
        token = _literal_command_token(
            element,
            constants=constants,
            sys_aliases=sys_aliases,
            sys_executable_names=sys_executable_names,
        )
        if token is None:
            return ()
        tokens.append(token)
    return tuple(tokens)


def _literal_command_token(
    node: ast.AST,
    *,
    constants: dict[str, str],
    sys_aliases: set[str],
    sys_executable_names: set[str],
) -> str | None:
    value = _literal_string_value(node, constants=constants)
    if value is not None:
        return value
    if isinstance(node, ast.Name) and node.id in sys_executable_names:
        return "python"
    if (
        isinstance(node, ast.Attribute)
        and node.attr == "executable"
        and isinstance(node.value, ast.Name)
        and node.value.id in sys_aliases
    ):
        return "python"
    return None


def _shell_command_tokens(command: str) -> tuple[str, ...]:
    try:
        return tuple(shlex.split(command))
    except ValueError:
        return ()


def _python_modules_from_command_tokens(
    tokens: tuple[str, ...],
    *,
    relative_path: str,
) -> tuple[str, ...]:
    modules: list[str] = []
    for index, token in enumerate(tokens):
        if not _is_python_executable_token(token):
            continue
        modules.extend(
            _python_modules_after_flags(
                tokens,
                start=index + 1,
                relative_path=relative_path,
            )
        )
    return tuple(modules)


def _python_modules_after_flags(
    tokens: tuple[str, ...],
    *,
    start: int,
    relative_path: str,
) -> tuple[str, ...]:
    for index in range(start, len(tokens) - 1):
        token = tokens[index]
        if token == "-c":
            return _python_modules_from_inline_code(
                tokens[index + 1],
                relative_path=relative_path,
            )
        if token == "-m":
            module = _module_name_from_command_token(tokens[index + 1])
            if module is None:
                return ()
            return (module,)
    return ()


def _python_modules_from_inline_code(
    source: str,
    *,
    relative_path: str,
) -> tuple[str, ...]:
    return _imported_modules(
        _parse_runtime_code_source(
            source,
            relative_path=relative_path,
            function_name="python-c",
        ),
        relative_path=relative_path,
    )


def _is_python_executable_token(token: str) -> bool:
    name = Path(token).name
    return name == "python" or name.startswith("python3") or name.startswith("pypy")


def _module_name_from_command_token(token: str) -> str | None:
    module = token.strip()
    if module and not module.startswith((".", "-")):
        return module
    return None


def _importlib_loader_modules(tree: ast.AST) -> tuple[str, ...]:
    constants = _constant_string_assignments(tree)
    importlib_aliases = {"importlib"}
    util_aliases: set[str] = set()
    machinery_aliases: set[str] = set()
    util_callables: set[str] = set()
    machinery_callables: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                if alias.name == "importlib":
                    importlib_aliases.add(bound)
                elif alias.name == "importlib.util":
                    if alias.asname:
                        util_aliases.add(alias.asname)
                    else:
                        importlib_aliases.add(bound)
                elif alias.name == "importlib.machinery":
                    if alias.asname:
                        machinery_aliases.add(alias.asname)
                    else:
                        importlib_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "importlib":
                for alias in node.names:
                    if alias.name == "util":
                        util_aliases.add(alias.asname or alias.name)
                    elif alias.name == "machinery":
                        machinery_aliases.add(alias.asname or alias.name)
            elif node.module == "importlib.util":
                for alias in node.names:
                    if alias.name in {"spec_from_file_location", "spec_from_loader"}:
                        util_callables.add(alias.asname or alias.name)
            elif node.module == "importlib.machinery":
                for alias in node.names:
                    if alias.name in {
                        "ExtensionFileLoader",
                        "SourcelessFileLoader",
                        "SourceFileLoader",
                    }:
                        machinery_callables.add(alias.asname or alias.name)
    loader_callables = util_callables | machinery_callables
    loader_callables.update(
        _importlib_loader_callable_assignments(
            tree,
            importlib_aliases=importlib_aliases,
            util_aliases=util_aliases,
            machinery_aliases=machinery_aliases,
            constants=constants,
            known_callables=loader_callables,
        )
    )

    modules: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_importlib_loader_callable(
            node.func,
            importlib_aliases=importlib_aliases,
            util_aliases=util_aliases,
            machinery_aliases=machinery_aliases,
            constants=constants,
            known_callables=loader_callables,
        ):
            module = _loader_module_name(node, constants=constants)
            if module is not None:
                modules.append(module)
    return tuple(modules)


def _importlib_loader_callable_assignments(
    tree: ast.AST,
    *,
    importlib_aliases: set[str],
    util_aliases: set[str],
    machinery_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> set[str]:
    aliases = set(known_callables)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if not _is_importlib_loader_callable(
                    node.value,
                    importlib_aliases=importlib_aliases,
                    util_aliases=util_aliases,
                    machinery_aliases=machinery_aliases,
                    constants=constants,
                    known_callables=aliases,
                ):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in aliases:
                        aliases.add(target.id)
                        changed = True
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.value is None:
                    continue
                if _is_importlib_loader_callable(
                    node.value,
                    importlib_aliases=importlib_aliases,
                    util_aliases=util_aliases,
                    machinery_aliases=machinery_aliases,
                    constants=constants,
                    known_callables=aliases,
                ) and node.target.id not in aliases:
                    aliases.add(node.target.id)
                    changed = True
    return aliases - known_callables


def _is_importlib_loader_callable(
    node: ast.AST,
    *,
    importlib_aliases: set[str],
    util_aliases: set[str],
    machinery_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> bool:
    util_functions = {"spec_from_file_location", "spec_from_loader"}
    machinery_functions = {
        "ExtensionFileLoader",
        "SourcelessFileLoader",
        "SourceFileLoader",
    }
    if isinstance(node, ast.Name):
        return node.id in known_callables
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name):
            return (
                node.attr in util_functions
                and node.value.id in util_aliases
            ) or (
                node.attr in machinery_functions
                and node.value.id in machinery_aliases
            )
        return (
            node.attr in util_functions
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "util"
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id in importlib_aliases
        ) or (
            node.attr in machinery_functions
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "machinery"
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id in importlib_aliases
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
    ):
        attribute = _literal_string_value(node.args[1], constants=constants)
        if attribute is None:
            return False
        owner = _importlib_loader_owner(
            node.args[0],
            importlib_aliases=importlib_aliases,
            util_aliases=util_aliases,
            machinery_aliases=machinery_aliases,
        )
        return (
            attribute in util_functions
            and owner == "util"
        ) or (
            attribute in machinery_functions
            and owner == "machinery"
        )
    lookup = _importlib_loader_dictionary_lookup(
        node,
        importlib_aliases=importlib_aliases,
        util_aliases=util_aliases,
        machinery_aliases=machinery_aliases,
        constants=constants,
    )
    if lookup is not None:
        owner, attribute = lookup
        return (
            attribute in util_functions
            and owner == "util"
        ) or (
            attribute in machinery_functions
            and owner == "machinery"
        )
    return False


def _importlib_loader_owner(
    node: ast.AST,
    *,
    importlib_aliases: set[str],
    util_aliases: set[str],
    machinery_aliases: set[str],
) -> str | None:
    if isinstance(node, ast.Name):
        if node.id in util_aliases:
            return "util"
        if node.id in machinery_aliases:
            return "machinery"
    if (
        isinstance(node, ast.Attribute)
        and node.attr in {"util", "machinery"}
        and isinstance(node.value, ast.Name)
        and node.value.id in importlib_aliases
    ):
        return node.attr
    return None


def _importlib_loader_dictionary_lookup(
    node: ast.AST,
    *,
    importlib_aliases: set[str],
    util_aliases: set[str],
    machinery_aliases: set[str],
    constants: dict[str, str],
) -> tuple[str, str] | None:
    if not isinstance(node, ast.Subscript):
        return None
    key = _literal_string_value(node.slice, constants=constants)
    if key is None:
        return None
    owner_node: ast.AST | None = None
    if isinstance(node.value, ast.Attribute) and node.value.attr == "__dict__":
        owner_node = node.value.value
    elif (
        isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "vars"
        and node.value.args
    ):
        owner_node = node.value.args[0]
    if owner_node is None:
        return None
    owner = _importlib_loader_owner(
        owner_node,
        importlib_aliases=importlib_aliases,
        util_aliases=util_aliases,
        machinery_aliases=machinery_aliases,
    )
    if owner is None:
        return None
    return owner, key


def _loader_module_name(
    node: ast.Call,
    *,
    constants: dict[str, str],
) -> str | None:
    if node.args:
        return _literal_module_name(node.args[0], constants=constants)
    for keyword in node.keywords:
        if keyword.arg in {"fullname", "name"}:
            return _literal_module_name(keyword.value, constants=constants)
    return None


def _importlib_resources_modules(tree: ast.AST) -> tuple[str, ...]:
    constants = _constant_string_assignments(tree)
    importlib_aliases = {"importlib"}
    resources_aliases: set[str] = set()
    resources_callables: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                if alias.name == "importlib":
                    importlib_aliases.add(bound)
                elif alias.name == "importlib.resources":
                    if alias.asname:
                        resources_aliases.add(alias.asname)
                    else:
                        importlib_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "importlib":
                for alias in node.names:
                    if alias.name == "resources":
                        resources_aliases.add(alias.asname or alias.name)
            elif node.module == "importlib.resources":
                for alias in node.names:
                    if alias.name == "*":
                        resources_callables.update(_IMPORTLIB_RESOURCES_FUNCTIONS)
                    elif alias.name in _IMPORTLIB_RESOURCES_FUNCTIONS:
                        resources_callables.add(alias.asname or alias.name)
    resources_callables.update(
        _importlib_resources_callable_assignments(
            tree,
            importlib_aliases=importlib_aliases,
            resources_aliases=resources_aliases,
            constants=constants,
            known_callables=resources_callables,
        )
    )

    modules: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_importlib_resources_callable(
            node.func,
            importlib_aliases=importlib_aliases,
            resources_aliases=resources_aliases,
            constants=constants,
            known_callables=resources_callables,
        ):
            continue
        module = _resources_package_name(node, constants=constants)
        if module is not None:
            modules.append(module)
    return tuple(modules)


_IMPORTLIB_RESOURCES_FUNCTIONS = frozenset(
    {
        "contents",
        "files",
        "is_resource",
        "open_binary",
        "open_text",
        "path",
        "read_binary",
        "read_text",
    }
)


def _importlib_resources_callable_assignments(
    tree: ast.AST,
    *,
    importlib_aliases: set[str],
    resources_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> set[str]:
    aliases = set(known_callables)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if not _is_importlib_resources_callable(
                    node.value,
                    importlib_aliases=importlib_aliases,
                    resources_aliases=resources_aliases,
                    constants=constants,
                    known_callables=aliases,
                ):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in aliases:
                        aliases.add(target.id)
                        changed = True
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.value is None:
                    continue
                if _is_importlib_resources_callable(
                    node.value,
                    importlib_aliases=importlib_aliases,
                    resources_aliases=resources_aliases,
                    constants=constants,
                    known_callables=aliases,
                ) and node.target.id not in aliases:
                    aliases.add(node.target.id)
                    changed = True
    return aliases - known_callables


def _is_importlib_resources_callable(
    node: ast.AST,
    *,
    importlib_aliases: set[str],
    resources_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in known_callables
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name):
            return (
                node.attr in _IMPORTLIB_RESOURCES_FUNCTIONS
                and node.value.id in resources_aliases
            )
        return (
            node.attr in _IMPORTLIB_RESOURCES_FUNCTIONS
            and isinstance(node.value, ast.Attribute)
            and node.value.attr == "resources"
            and isinstance(node.value.value, ast.Name)
            and node.value.value.id in importlib_aliases
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
    ):
        attribute = _literal_string_value(node.args[1], constants=constants)
        if attribute is None or attribute not in _IMPORTLIB_RESOURCES_FUNCTIONS:
            return False
        return _importlib_resources_owner(
            node.args[0],
            importlib_aliases=importlib_aliases,
            resources_aliases=resources_aliases,
        )
    lookup = _importlib_resources_dictionary_lookup(
        node,
        importlib_aliases=importlib_aliases,
        resources_aliases=resources_aliases,
        constants=constants,
    )
    if lookup is not None:
        _, attribute = lookup
        return attribute in _IMPORTLIB_RESOURCES_FUNCTIONS
    return False


def _importlib_resources_owner(
    node: ast.AST,
    *,
    importlib_aliases: set[str],
    resources_aliases: set[str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in resources_aliases
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "resources"
        and isinstance(node.value, ast.Name)
        and node.value.id in importlib_aliases
    )


def _importlib_resources_dictionary_lookup(
    node: ast.AST,
    *,
    importlib_aliases: set[str],
    resources_aliases: set[str],
    constants: dict[str, str],
) -> tuple[str, str] | None:
    if not isinstance(node, ast.Subscript):
        return None
    key = _literal_string_value(node.slice, constants=constants)
    if key is None:
        return None
    owner_node: ast.AST | None = None
    if isinstance(node.value, ast.Attribute) and node.value.attr == "__dict__":
        owner_node = node.value.value
    elif (
        isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "vars"
        and node.value.args
    ):
        owner_node = node.value.args[0]
    if owner_node is None:
        return None
    if not _importlib_resources_owner(
        owner_node,
        importlib_aliases=importlib_aliases,
        resources_aliases=resources_aliases,
    ):
        return None
    return "resources", key


def _resources_package_name(
    node: ast.Call,
    *,
    constants: dict[str, str],
) -> str | None:
    if node.args:
        return _literal_module_name(node.args[0], constants=constants)
    for keyword in node.keywords:
        if keyword.arg in {"anchor", "package"}:
            return _literal_module_name(keyword.value, constants=constants)
    return None


def _stdlib_module_resolution_modules(tree: ast.AST) -> tuple[str, ...]:
    constants = _constant_string_assignments(tree)
    pkgutil_aliases = {"pkgutil"}
    runpy_aliases = {"runpy"}
    module_resolution_callables: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "pkgutil":
                    pkgutil_aliases.add(alias.asname or alias.name)
                elif alias.name == "runpy":
                    runpy_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "pkgutil":
                for alias in node.names:
                    if alias.name in {"find_loader", "get_loader", "resolve_name"}:
                        module_resolution_callables.add(alias.asname or alias.name)
            elif node.module == "runpy":
                for alias in node.names:
                    if alias.name == "run_module":
                        module_resolution_callables.add(alias.asname or alias.name)
    module_resolution_callables.update(
        _stdlib_module_resolution_callable_assignments(
            tree,
            pkgutil_aliases=pkgutil_aliases,
            runpy_aliases=runpy_aliases,
            constants=constants,
            known_callables=module_resolution_callables,
        )
    )

    modules: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_stdlib_module_resolution_callable(
            node.func,
            pkgutil_aliases=pkgutil_aliases,
            runpy_aliases=runpy_aliases,
            constants=constants,
            known_callables=module_resolution_callables,
        ):
            continue
        module = _module_resolution_name(node, constants=constants)
        if module is not None:
            modules.append(module)
    return tuple(modules)


def _stdlib_module_resolution_callable_assignments(
    tree: ast.AST,
    *,
    pkgutil_aliases: set[str],
    runpy_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> set[str]:
    aliases = set(known_callables)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if not _is_stdlib_module_resolution_callable(
                    node.value,
                    pkgutil_aliases=pkgutil_aliases,
                    runpy_aliases=runpy_aliases,
                    constants=constants,
                    known_callables=aliases,
                ):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in aliases:
                        aliases.add(target.id)
                        changed = True
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.value is None:
                    continue
                if _is_stdlib_module_resolution_callable(
                    node.value,
                    pkgutil_aliases=pkgutil_aliases,
                    runpy_aliases=runpy_aliases,
                    constants=constants,
                    known_callables=aliases,
                ) and node.target.id not in aliases:
                    aliases.add(node.target.id)
                    changed = True
    return aliases - known_callables


def _is_stdlib_module_resolution_callable(
    node: ast.AST,
    *,
    pkgutil_aliases: set[str],
    runpy_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> bool:
    pkgutil_functions = {"find_loader", "get_loader", "resolve_name"}
    runpy_functions = {"run_module"}
    if isinstance(node, ast.Name):
        return node.id in known_callables
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return (
            node.attr in pkgutil_functions
            and node.value.id in pkgutil_aliases
        ) or (
            node.attr in runpy_functions
            and node.value.id in runpy_aliases
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Name)
    ):
        attribute = _literal_string_value(node.args[1], constants=constants)
        owner = node.args[0].id
        return (
            attribute in pkgutil_functions
            and owner in pkgutil_aliases
        ) or (
            attribute in runpy_functions
            and owner in runpy_aliases
        )
    lookup = _stdlib_module_resolution_dictionary_lookup(
        node,
        pkgutil_aliases=pkgutil_aliases,
        runpy_aliases=runpy_aliases,
        constants=constants,
    )
    if lookup is not None:
        owner, attribute = lookup
        return (
            attribute in pkgutil_functions
            and owner in pkgutil_aliases
        ) or (
            attribute in runpy_functions
            and owner in runpy_aliases
        )
    return False


def _stdlib_module_resolution_dictionary_lookup(
    node: ast.AST,
    *,
    pkgutil_aliases: set[str],
    runpy_aliases: set[str],
    constants: dict[str, str],
) -> tuple[str, str] | None:
    lookup = _module_dictionary_lookup(
        node,
        module_aliases=pkgutil_aliases | runpy_aliases,
        constants=constants,
    )
    if lookup is None:
        return None
    owner, attribute = lookup
    return owner, attribute


def _module_resolution_name(
    node: ast.Call,
    *,
    constants: dict[str, str],
) -> str | None:
    if node.args:
        return _literal_module_name(node.args[0], constants=constants)
    for keyword in node.keywords:
        if keyword.arg in {"fullname", "mod_name", "module_or_name", "name"}:
            return _literal_module_name(keyword.value, constants=constants)
    return None


def _literal_runtime_code_imported_modules(
    tree: ast.AST,
    *,
    relative_path: str,
) -> tuple[str, ...]:
    builtins_aliases = {"builtins", "__builtins__"}
    runtime_code_callables = {"compile", "eval", "exec"}
    constants = _constant_string_assignments(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "builtins":
                    builtins_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "builtins":
            for alias in node.names:
                if alias.name in runtime_code_callables:
                    runtime_code_callables.add(alias.asname or alias.name)
    runtime_code_callables.update(
        _runtime_code_callable_assignments(
            tree,
            builtins_aliases=builtins_aliases,
            constants=constants,
            known_callables=runtime_code_callables,
        )
    )
    modules: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_runtime_code_callable(
            node.func,
            builtins_aliases=builtins_aliases,
            constants=constants,
            known_callables=runtime_code_callables,
        ):
            continue
        source = _runtime_code_source(node, constants=constants)
        if source is None:
            continue
        modules.extend(
            _imported_modules(
                _parse_runtime_code_source(
                    source,
                    relative_path=relative_path,
                    function_name=_runtime_code_function_name(node.func),
                ),
                relative_path=relative_path,
            )
        )
    return tuple(modules)


def _runtime_code_callable_assignments(
    tree: ast.AST,
    *,
    builtins_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> set[str]:
    aliases = set(known_callables)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if not _is_runtime_code_callable(
                    node.value,
                    builtins_aliases=builtins_aliases,
                    constants=constants,
                    known_callables=aliases,
                ):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in aliases:
                        aliases.add(target.id)
                        changed = True
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.value is None:
                    continue
                if _is_runtime_code_callable(
                    node.value,
                    builtins_aliases=builtins_aliases,
                    constants=constants,
                    known_callables=aliases,
                ) and node.target.id not in aliases:
                    aliases.add(node.target.id)
                    changed = True
    return aliases - known_callables


def _is_runtime_code_callable(
    node: ast.AST,
    *,
    builtins_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> bool:
    runtime_functions = {"compile", "eval", "exec"}
    if isinstance(node, ast.Name):
        return node.id in known_callables
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.attr in runtime_functions and node.value.id in builtins_aliases
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id in builtins_aliases
    ):
        attribute = _literal_string_value(node.args[1], constants=constants)
        return attribute in runtime_functions
    lookup = _module_dictionary_lookup(
        node,
        module_aliases=builtins_aliases,
        constants=constants,
    )
    if lookup is not None:
        _, attribute = lookup
        return attribute in runtime_functions
    return False


def _runtime_code_function_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return "runtime"


def _runtime_code_source(
    node: ast.Call,
    *,
    constants: dict[str, str],
) -> str | None:
    if node.args:
        return _literal_string_value(node.args[0], constants=constants)
    for keyword in node.keywords:
        if keyword.arg in {"source", "object"}:
            return _literal_string_value(keyword.value, constants=constants)
    return None


def _parse_runtime_code_source(
    source: str,
    *,
    relative_path: str,
    function_name: str,
) -> ast.AST:
    try:
        return ast.parse(
            source,
            filename=f"{relative_path}:{function_name}",
            mode="exec",
        )
    except SyntaxError as exc:
        raise FirstPartySourceAuditError(
            "first-party source audit cannot parse literal runtime code "
            f"in {relative_path}"
        ) from exc


def _dynamic_import_callable_assignments(
    tree: ast.AST,
    *,
    builtins_aliases: set[str],
    importlib_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> set[str]:
    aliases = set(known_callables)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                if not _is_dynamic_import_callable(
                    node.value,
                    builtins_aliases=builtins_aliases,
                    importlib_aliases=importlib_aliases,
                    constants=constants,
                    known_callables=aliases,
                ):
                    continue
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id not in aliases:
                        aliases.add(target.id)
                        changed = True
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                if node.value is None:
                    continue
                if _is_dynamic_import_callable(
                    node.value,
                    builtins_aliases=builtins_aliases,
                    importlib_aliases=importlib_aliases,
                    constants=constants,
                    known_callables=aliases,
                ) and node.target.id not in aliases:
                    aliases.add(node.target.id)
                    changed = True
    return aliases - known_callables


def _is_dynamic_import_callable(
    node: ast.AST,
    *,
    builtins_aliases: set[str],
    importlib_aliases: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in known_callables
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return (
            node.attr == "import_module"
            and node.value.id in importlib_aliases
        ) or (
            node.attr == "__import__"
            and node.value.id in builtins_aliases
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
        and isinstance(node.args[0], ast.Name)
    ):
        attribute = _literal_string_value(node.args[1], constants=constants)
        owner = node.args[0].id
        return (
            attribute == "import_module"
            and owner in importlib_aliases
        ) or (
            attribute == "__import__"
            and owner in builtins_aliases
        )
    lookup = _module_dictionary_lookup(
        node,
        module_aliases=importlib_aliases | builtins_aliases,
        constants=constants,
    )
    if lookup is not None:
        owner, attribute = lookup
        return (
            attribute == "import_module"
            and owner in importlib_aliases
        ) or (
            attribute == "__import__"
            and owner in builtins_aliases
        )
    return False


def _module_dictionary_lookup(
    node: ast.AST,
    *,
    module_aliases: set[str],
    constants: dict[str, str],
) -> tuple[str, str] | None:
    if not isinstance(node, ast.Subscript):
        return None
    key = _literal_string_value(node.slice, constants=constants)
    if key is None:
        return None
    owner = _module_dictionary_owner(node.value)
    if owner is None or owner not in module_aliases:
        return None
    return owner, key


def _module_dictionary_owner(node: ast.AST) -> str | None:
    if isinstance(node, ast.Attribute) and node.attr == "__dict__":
        if isinstance(node.value, ast.Name):
            return node.value.id
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "vars"
        and node.args
        and isinstance(node.args[0], ast.Name)
    ):
        return node.args[0].id
    if isinstance(node, ast.Name) and node.id == "__builtins__":
        return node.id
    return None


def _constant_string_assignments(tree: ast.AST) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = _literal_string_value(node.value, constants=constants)
            if value is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is None:
                continue
            value = _literal_string_value(node.value, constants=constants)
            if value is not None:
                constants[node.target.id] = value
    return constants


def _constant_bytes_assignments(tree: ast.AST) -> dict[str, bytes]:
    constants: dict[str, bytes] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            value = _literal_bytes_value(node.value, constants=constants)
            if value is None:
                continue
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is None:
                continue
            value = _literal_bytes_value(node.value, constants=constants)
            if value is not None:
                constants[node.target.id] = value
    return constants


def _literal_module_name(
    node: ast.AST,
    *,
    constants: dict[str, str] | None = None,
) -> str | None:
    if isinstance(node, ast.Name) and constants is not None:
        value = constants.get(node.id)
    else:
        value = _literal_string_value(node, constants=constants)
    if value is not None:
        module = value.strip()
        if module and not module.startswith("."):
            return module
    return None


def _forbidden_string_markers(tree: ast.AST) -> tuple[str, ...]:
    markers: list[str] = []
    string_constants = _constant_string_assignments(tree)
    bytes_constants = _constant_bytes_assignments(tree)
    for node in ast.walk(tree):
        text = _literal_string_value(node, constants=string_constants)
        if text is not None:
            lowered = text.lower()
            markers.extend(
                marker
                for marker in FORBIDDEN_STRING_MARKERS
                if marker.lower() in lowered
            )
        byte_text = _literal_bytes_value(node, constants=bytes_constants)
        if byte_text is not None:
            lowered_bytes = byte_text.lower()
            markers.extend(
                marker
                for marker in FORBIDDEN_STRING_MARKERS
                if marker.lower().encode("ascii") in lowered_bytes
            )
    markers.extend(_forbidden_downloader_command_markers(tree))
    markers.extend(_forbidden_package_install_markers(tree))
    markers.extend(_forbidden_native_library_markers(tree))
    return tuple(markers)


def _forbidden_downloader_command_markers(tree: ast.AST) -> tuple[str, ...]:
    constants = _constant_string_assignments(tree)
    subprocess_aliases = {"subprocess"}
    os_aliases = {"os"}
    sys_aliases = {"sys"}
    sys_executable_names: set[str] = set()
    process_callables: set[str] = set()
    os_process_callables: set[str] = set()
    shell_callables: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                if alias.name == "subprocess":
                    subprocess_aliases.add(bound)
                elif alias.name == "os":
                    os_aliases.add(bound)
                elif alias.name == "sys":
                    sys_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "subprocess":
                for alias in node.names:
                    if alias.name == "*":
                        process_callables.update(_PYTHON_PROCESS_LAUNCH_FUNCTIONS)
                    elif alias.name in _PYTHON_PROCESS_LAUNCH_FUNCTIONS:
                        process_callables.add(alias.asname or alias.name)
            elif node.module == "os":
                for alias in node.names:
                    if alias.name == "*":
                        shell_callables.update(_PYTHON_SHELL_LAUNCH_FUNCTIONS)
                        os_process_callables.update(_PYTHON_OS_PROCESS_LAUNCH_FUNCTIONS)
                    elif alias.name in _PYTHON_SHELL_LAUNCH_FUNCTIONS:
                        shell_callables.add(alias.asname or alias.name)
                    elif alias.name in _PYTHON_OS_PROCESS_LAUNCH_FUNCTIONS:
                        os_process_callables.add(alias.asname or alias.name)
            elif node.module == "sys":
                for alias in node.names:
                    if alias.name == "executable":
                        sys_executable_names.add(alias.asname or alias.name)

    (
        new_process_callables,
        new_os_process_callables,
        new_shell_callables,
    ) = _python_process_callable_assignments(
        tree,
        subprocess_aliases=subprocess_aliases,
        os_aliases=os_aliases,
        constants=constants,
        known_process_callables=process_callables,
        known_os_process_callables=os_process_callables,
        known_shell_callables=shell_callables,
    )
    process_callables.update(new_process_callables)
    os_process_callables.update(new_os_process_callables)
    shell_callables.update(new_shell_callables)

    markers: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_python_process_launch_callable(
            node.func,
            subprocess_aliases=subprocess_aliases,
            constants=constants,
            known_callables=process_callables,
        ):
            command_node = _first_call_argument(node, keyword_names={"args"})
            if command_node is None:
                continue
            markers.extend(
                _forbidden_downloader_command_markers_from_tokens(
                    _literal_command_tokens(
                        command_node,
                        constants=constants,
                        sys_aliases=sys_aliases,
                        sys_executable_names=sys_executable_names,
                    )
                )
            )
        elif _is_python_os_process_launch_callable(
            node.func,
            os_aliases=os_aliases,
            constants=constants,
            known_callables=os_process_callables,
        ):
            for tokens in _os_process_command_token_sets(
                node,
                constants=constants,
                sys_aliases=sys_aliases,
                sys_executable_names=sys_executable_names,
            ):
                markers.extend(_forbidden_downloader_command_markers_from_tokens(tokens))
        elif _is_python_shell_launch_callable(
            node.func,
            os_aliases=os_aliases,
            constants=constants,
            known_callables=shell_callables,
        ):
            command_node = _first_call_argument(node, keyword_names={"cmd", "command"})
            if command_node is None:
                continue
            command = _literal_string_value(command_node, constants=constants)
            if command is None:
                continue
            markers.extend(
                _forbidden_downloader_command_markers_from_tokens(
                    _shell_command_tokens(command)
                )
            )
    return tuple(markers)


def _forbidden_downloader_command_markers_from_tokens(
    tokens: tuple[str, ...],
) -> tuple[str, ...]:
    references = _downloader_command_references(tokens)
    markers: list[str] = []
    for reference in references:
        markers.extend(_forbidden_package_reference_markers(reference))
    return tuple(markers)


def _downloader_command_references(tokens: tuple[str, ...]) -> tuple[str, ...]:
    if not tokens:
        return ()
    normalized = tuple(Path(token).name.lower() for token in tokens)
    for index, command in enumerate(normalized):
        if command in _DOWNLOADER_COMMANDS:
            return _downloader_reference_tokens(tokens[index + 1 :])
        if command in _VCS_COMMANDS:
            return _vcs_reference_tokens(tokens[index:])
    return ()


def _downloader_reference_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    references: list[str] = []
    skip_next = False
    options_with_values = {
        "-o",
        "-output",
        "-p",
        "-user-agent",
        "--directory-prefix",
        "--header",
        "--load-cookies",
        "--output",
        "--output-document",
        "--user-agent",
    }
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in {"&&", ";", "|"}:
            break
        if token.startswith("-"):
            if token in options_with_values:
                skip_next = True
            continue
        references.append(token)
    return tuple(references)


def _vcs_reference_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    if not tokens:
        return ()
    command = Path(tokens[0]).name.lower()
    if command == "git":
        return _git_reference_tokens(tokens[1:])
    if command == "gh":
        return _gh_reference_tokens(tokens[1:])
    if command in {"hg", "svn"}:
        return _simple_vcs_reference_tokens(tokens[1:])
    return ()


def _git_reference_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    if not tokens:
        return ()
    if tokens[0] == "clone":
        return _downloader_reference_tokens(tokens[1:])
    if len(tokens) >= 2 and tokens[0] == "submodule" and tokens[1] == "add":
        return _downloader_reference_tokens(tokens[2:])
    return ()


def _gh_reference_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    if len(tokens) >= 2 and tokens[0] == "repo" and tokens[1] == "clone":
        return _downloader_reference_tokens(tokens[2:])
    return ()


def _simple_vcs_reference_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    if tokens and tokens[0] in {"checkout", "clone"}:
        return _downloader_reference_tokens(tokens[1:])
    return ()


def _forbidden_package_install_markers(tree: ast.AST) -> tuple[str, ...]:
    constants = _constant_string_assignments(tree)
    subprocess_aliases = {"subprocess"}
    os_aliases = {"os"}
    sys_aliases = {"sys"}
    sys_executable_names: set[str] = set()
    process_callables: set[str] = set()
    os_process_callables: set[str] = set()
    shell_callables: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                if alias.name == "subprocess":
                    subprocess_aliases.add(bound)
                elif alias.name == "os":
                    os_aliases.add(bound)
                elif alias.name == "sys":
                    sys_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "subprocess":
                for alias in node.names:
                    if alias.name == "*":
                        process_callables.update(_PYTHON_PROCESS_LAUNCH_FUNCTIONS)
                    elif alias.name in _PYTHON_PROCESS_LAUNCH_FUNCTIONS:
                        process_callables.add(alias.asname or alias.name)
            elif node.module == "os":
                for alias in node.names:
                    if alias.name == "*":
                        shell_callables.update(_PYTHON_SHELL_LAUNCH_FUNCTIONS)
                        os_process_callables.update(_PYTHON_OS_PROCESS_LAUNCH_FUNCTIONS)
                    elif alias.name in _PYTHON_SHELL_LAUNCH_FUNCTIONS:
                        shell_callables.add(alias.asname or alias.name)
                    elif alias.name in _PYTHON_OS_PROCESS_LAUNCH_FUNCTIONS:
                        os_process_callables.add(alias.asname or alias.name)
            elif node.module == "sys":
                for alias in node.names:
                    if alias.name == "executable":
                        sys_executable_names.add(alias.asname or alias.name)

    (
        new_process_callables,
        new_os_process_callables,
        new_shell_callables,
    ) = _python_process_callable_assignments(
        tree,
        subprocess_aliases=subprocess_aliases,
        os_aliases=os_aliases,
        constants=constants,
        known_process_callables=process_callables,
        known_os_process_callables=os_process_callables,
        known_shell_callables=shell_callables,
    )
    process_callables.update(new_process_callables)
    os_process_callables.update(new_os_process_callables)
    shell_callables.update(new_shell_callables)

    markers: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_python_process_launch_callable(
            node.func,
            subprocess_aliases=subprocess_aliases,
            constants=constants,
            known_callables=process_callables,
        ):
            command_node = _first_call_argument(node, keyword_names={"args"})
            if command_node is None:
                continue
            markers.extend(
                _forbidden_package_install_command_markers(
                    _literal_command_tokens(
                        command_node,
                        constants=constants,
                        sys_aliases=sys_aliases,
                        sys_executable_names=sys_executable_names,
                    )
                )
            )
        elif _is_python_os_process_launch_callable(
            node.func,
            os_aliases=os_aliases,
            constants=constants,
            known_callables=os_process_callables,
        ):
            for tokens in _os_process_command_token_sets(
                node,
                constants=constants,
                sys_aliases=sys_aliases,
                sys_executable_names=sys_executable_names,
            ):
                markers.extend(_forbidden_package_install_command_markers(tokens))
        elif _is_python_shell_launch_callable(
            node.func,
            os_aliases=os_aliases,
            constants=constants,
            known_callables=shell_callables,
        ):
            command_node = _first_call_argument(node, keyword_names={"cmd", "command"})
            if command_node is None:
                continue
            command = _literal_string_value(command_node, constants=constants)
            if command is None:
                continue
            markers.extend(
                _forbidden_package_install_command_markers(
                    _shell_command_tokens(command)
                )
            )
    return tuple(markers)


def _os_process_command_token_sets(
    node: ast.Call,
    *,
    constants: dict[str, str],
    sys_aliases: set[str],
    sys_executable_names: set[str],
) -> tuple[tuple[str, ...], ...]:
    commands: list[tuple[str, ...]] = []
    if len(node.args) >= 2:
        commands.append(
            _literal_command_tokens(
                node.args[1],
                constants=constants,
                sys_aliases=sys_aliases,
                sys_executable_names=sys_executable_names,
            )
        )
        commands.append(
            _literal_command_tokens_from_elements(
                node.args[1:],
                constants=constants,
                sys_aliases=sys_aliases,
                sys_executable_names=sys_executable_names,
            )
        )
    if len(node.args) >= 3:
        commands.append(
            _literal_command_tokens(
                node.args[2],
                constants=constants,
                sys_aliases=sys_aliases,
                sys_executable_names=sys_executable_names,
            )
        )
        commands.append(
            _literal_command_tokens_from_elements(
                node.args[2:],
                constants=constants,
                sys_aliases=sys_aliases,
                sys_executable_names=sys_executable_names,
            )
        )
    return tuple(command for command in commands if command)


def _forbidden_package_install_command_markers(
    tokens: tuple[str, ...],
) -> tuple[str, ...]:
    package_tokens = _package_install_command_package_tokens(tokens)
    markers: list[str] = []
    for token in package_tokens:
        markers.extend(_forbidden_package_reference_markers(token))
    return tuple(markers)


def _package_install_command_package_tokens(tokens: tuple[str, ...]) -> tuple[str, ...]:
    if not tokens:
        return ()
    normalized = tuple(Path(token).name.lower() for token in tokens)
    for index, command in enumerate(normalized):
        if command not in _PACKAGE_MANAGER_COMMANDS:
            continue
        install_index = _package_install_command_index(normalized, start=index)
        if install_index is None:
            continue
        return _package_tokens_after_install(tokens[install_index + 1 :])
    return ()


def _package_install_command_index(
    normalized_tokens: tuple[str, ...],
    *,
    start: int,
) -> int | None:
    for index in range(start + 1, len(normalized_tokens)):
        token = normalized_tokens[index]
        if token in _PACKAGE_INSTALL_COMMANDS:
            return index
        if token in {"-m", "-q"}:
            continue
        if normalized_tokens[start] == "python" or normalized_tokens[start].startswith("python"):
            continue
    return None


def _package_tokens_after_install(tokens: tuple[str, ...]) -> tuple[str, ...]:
    package_tokens: list[str] = []
    skip_next = False
    options_with_values = {
        "-c",
        "-f",
        "-i",
        "-r",
        "--constraint",
        "--find-links",
        "--index-url",
        "--requirement",
    }
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token in {"&&", ";", "|"}:
            break
        if token.startswith("-"):
            if token in options_with_values:
                skip_next = True
            continue
        package_tokens.append(token)
    return tuple(package_tokens)


def _forbidden_package_reference_markers(reference: str) -> tuple[str, ...]:
    lowered = reference.lower()
    markers = {
        marker
        for marker in FORBIDDEN_STRING_MARKERS
        if marker.lower() in lowered
    }
    markers.update(
        prefix
        for prefix in FORBIDDEN_IMPORT_PREFIXES
        if prefix.lower() in lowered
    )
    markers.update(
        marker
        for marker in FORBIDDEN_NATIVE_LIBRARY_MARKERS
        if marker.lower() in lowered
    )
    return tuple(sorted(markers, key=lambda value: (-len(value), value)))


_CTYPES_LIBRARY_LOADERS = frozenset({"CDLL", "OleDLL", "PyDLL", "WinDLL"})
_CTYPES_LIBRARY_NAMESPACES = frozenset({"cdll", "oledll", "pydll", "windll"})


def _forbidden_native_library_markers(tree: ast.AST) -> tuple[str, ...]:
    constants = _constant_string_assignments(tree)
    ctypes_aliases = {"ctypes"}
    ctypes_util_aliases: set[str] = set()
    cffi_aliases: set[str] = set()
    native_load_callables: set[str] = set()
    native_library_namespaces: set[str] = set()
    cffi_ffi_callables: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".", 1)[0]
                if alias.name == "ctypes":
                    ctypes_aliases.add(bound)
                elif alias.name == "ctypes.util":
                    if alias.asname:
                        ctypes_util_aliases.add(alias.asname)
                    else:
                        ctypes_aliases.add(bound)
                elif alias.name == "cffi":
                    cffi_aliases.add(bound)
        elif isinstance(node, ast.ImportFrom):
            if node.module == "ctypes":
                for alias in node.names:
                    if alias.name == "*":
                        native_load_callables.update(_CTYPES_LIBRARY_LOADERS)
                        native_library_namespaces.update(_CTYPES_LIBRARY_NAMESPACES)
                    elif alias.name in _CTYPES_LIBRARY_LOADERS:
                        native_load_callables.add(alias.asname or alias.name)
                    elif alias.name in _CTYPES_LIBRARY_NAMESPACES:
                        native_library_namespaces.add(alias.asname or alias.name)
                    elif alias.name == "util":
                        ctypes_util_aliases.add(alias.asname or alias.name)
            elif node.module == "ctypes.util":
                for alias in node.names:
                    if alias.name == "find_library":
                        native_load_callables.add(alias.asname or alias.name)
            elif node.module == "cffi":
                for alias in node.names:
                    if alias.name == "FFI":
                        cffi_ffi_callables.add(alias.asname or alias.name)

    cffi_ffi_variables = _cffi_ffi_variables(
        tree,
        cffi_aliases=cffi_aliases,
        known_ffi_callables=cffi_ffi_callables,
    )
    native_load_callables.update(
        _native_library_callable_assignments(
            tree,
            ctypes_aliases=ctypes_aliases,
            ctypes_util_aliases=ctypes_util_aliases,
            native_library_namespaces=native_library_namespaces,
            cffi_ffi_variables=cffi_ffi_variables,
            constants=constants,
            known_callables=native_load_callables,
        )
    )

    markers: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not _is_native_library_load_callable(
            node.func,
            ctypes_aliases=ctypes_aliases,
            ctypes_util_aliases=ctypes_util_aliases,
            native_library_namespaces=native_library_namespaces,
            cffi_ffi_variables=cffi_ffi_variables,
            constants=constants,
            known_callables=native_load_callables,
        ):
            continue
        library = _native_library_name(node, constants=constants)
        if library is None:
            continue
        marker = _forbidden_native_library_marker(library)
        if marker is not None:
            markers.append(marker)
    return tuple(markers)


def _native_library_callable_assignments(
    tree: ast.AST,
    *,
    ctypes_aliases: set[str],
    ctypes_util_aliases: set[str],
    native_library_namespaces: set[str],
    cffi_ffi_variables: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> set[str]:
    aliases = set(known_callables)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            value: ast.AST | None = None
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
                value = node.value
            elif isinstance(node, ast.AnnAssign) and node.value is not None:
                targets = [node.target]
                value = node.value
            if value is None:
                continue
            if not _is_native_library_load_callable(
                value,
                ctypes_aliases=ctypes_aliases,
                ctypes_util_aliases=ctypes_util_aliases,
                native_library_namespaces=native_library_namespaces,
                cffi_ffi_variables=cffi_ffi_variables,
                constants=constants,
                known_callables=aliases,
            ):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in aliases:
                    aliases.add(target.id)
                    changed = True
    return aliases - known_callables


def _is_native_library_load_callable(
    node: ast.AST,
    *,
    ctypes_aliases: set[str],
    ctypes_util_aliases: set[str],
    native_library_namespaces: set[str],
    cffi_ffi_variables: set[str],
    constants: dict[str, str],
    known_callables: set[str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in known_callables
    if isinstance(node, ast.Attribute):
        if isinstance(node.value, ast.Name):
            return (
                node.attr in _CTYPES_LIBRARY_LOADERS
                and node.value.id in ctypes_aliases
            ) or (
                node.attr == "find_library"
                and node.value.id in ctypes_util_aliases
            ) or (
                node.attr == "LoadLibrary"
                and node.value.id in native_library_namespaces
            ) or (
                node.attr == "dlopen"
                and node.value.id in cffi_ffi_variables
            )
        return (
            node.attr == "find_library"
            and _ctypes_util_owner(
                node.value,
                ctypes_aliases=ctypes_aliases,
                ctypes_util_aliases=ctypes_util_aliases,
            )
        ) or (
            node.attr == "LoadLibrary"
            and _ctypes_library_namespace_owner(
                node.value,
                ctypes_aliases=ctypes_aliases,
                native_library_namespaces=native_library_namespaces,
            )
        )
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "getattr"
        and len(node.args) >= 2
    ):
        attribute = _literal_string_value(node.args[1], constants=constants)
        if attribute is None:
            return False
        return (
            attribute in _CTYPES_LIBRARY_LOADERS
            and _ctypes_owner(node.args[0], ctypes_aliases=ctypes_aliases)
        ) or (
            attribute == "find_library"
            and _ctypes_util_owner(
                node.args[0],
                ctypes_aliases=ctypes_aliases,
                ctypes_util_aliases=ctypes_util_aliases,
            )
        ) or (
            attribute == "LoadLibrary"
            and _ctypes_library_namespace_owner(
                node.args[0],
                ctypes_aliases=ctypes_aliases,
                native_library_namespaces=native_library_namespaces,
            )
        ) or (
            attribute == "dlopen"
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in cffi_ffi_variables
        )
    lookup = _native_library_dictionary_lookup(
        node,
        ctypes_aliases=ctypes_aliases,
        ctypes_util_aliases=ctypes_util_aliases,
        native_library_namespaces=native_library_namespaces,
        cffi_ffi_variables=cffi_ffi_variables,
        constants=constants,
    )
    return lookup


def _native_library_dictionary_lookup(
    node: ast.AST,
    *,
    ctypes_aliases: set[str],
    ctypes_util_aliases: set[str],
    native_library_namespaces: set[str],
    cffi_ffi_variables: set[str],
    constants: dict[str, str],
) -> bool:
    if not isinstance(node, ast.Subscript):
        return False
    key = _literal_string_value(node.slice, constants=constants)
    if key is None:
        return False
    owner_node: ast.AST | None = None
    if isinstance(node.value, ast.Attribute) and node.value.attr == "__dict__":
        owner_node = node.value.value
    elif (
        isinstance(node.value, ast.Call)
        and isinstance(node.value.func, ast.Name)
        and node.value.func.id == "vars"
        and node.value.args
    ):
        owner_node = node.value.args[0]
    if owner_node is None:
        return False
    return (
        key in _CTYPES_LIBRARY_LOADERS
        and _ctypes_owner(owner_node, ctypes_aliases=ctypes_aliases)
    ) or (
        key == "find_library"
        and _ctypes_util_owner(
            owner_node,
            ctypes_aliases=ctypes_aliases,
            ctypes_util_aliases=ctypes_util_aliases,
        )
    ) or (
        key == "LoadLibrary"
        and _ctypes_library_namespace_owner(
            owner_node,
            ctypes_aliases=ctypes_aliases,
            native_library_namespaces=native_library_namespaces,
        )
    ) or (
        key == "dlopen"
        and isinstance(owner_node, ast.Name)
        and owner_node.id in cffi_ffi_variables
    )


def _ctypes_owner(node: ast.AST, *, ctypes_aliases: set[str]) -> bool:
    return isinstance(node, ast.Name) and node.id in ctypes_aliases


def _ctypes_util_owner(
    node: ast.AST,
    *,
    ctypes_aliases: set[str],
    ctypes_util_aliases: set[str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in ctypes_util_aliases
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "util"
        and isinstance(node.value, ast.Name)
        and node.value.id in ctypes_aliases
    )


def _ctypes_library_namespace_owner(
    node: ast.AST,
    *,
    ctypes_aliases: set[str],
    native_library_namespaces: set[str],
) -> bool:
    if isinstance(node, ast.Name):
        return node.id in native_library_namespaces
    return (
        isinstance(node, ast.Attribute)
        and node.attr in _CTYPES_LIBRARY_NAMESPACES
        and isinstance(node.value, ast.Name)
        and node.value.id in ctypes_aliases
    )


def _cffi_ffi_variables(
    tree: ast.AST,
    *,
    cffi_aliases: set[str],
    known_ffi_callables: set[str],
) -> set[str]:
    variables: set[str] = set()
    for node in ast.walk(tree):
        targets: list[ast.expr] = []
        value: ast.AST | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
            value = node.value
        if value is None or not _is_cffi_ffi_constructor(
            value,
            cffi_aliases=cffi_aliases,
            known_ffi_callables=known_ffi_callables,
        ):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                variables.add(target.id)
    return variables


def _is_cffi_ffi_constructor(
    node: ast.AST,
    *,
    cffi_aliases: set[str],
    known_ffi_callables: set[str],
) -> bool:
    if not isinstance(node, ast.Call):
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id in known_ffi_callables
    return (
        isinstance(node.func, ast.Attribute)
        and node.func.attr == "FFI"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in cffi_aliases
    )


def _native_library_name(
    node: ast.Call,
    *,
    constants: dict[str, str],
) -> str | None:
    if node.args:
        return _literal_string_value(node.args[0], constants=constants)
    for keyword in node.keywords:
        if keyword.arg in {"name", "libname"}:
            return _literal_string_value(keyword.value, constants=constants)
    return None


def _forbidden_native_library_marker(library: str) -> str | None:
    lowered = library.strip().replace("\\", "/").lower()
    if not lowered:
        return None
    basename = Path(lowered).name
    candidates = {basename}
    for suffix in (".so", ".dll", ".dylib"):
        if suffix in basename:
            candidates.add(basename.split(suffix, 1)[0])
    candidates.update(
        candidate[3:]
        for candidate in tuple(candidates)
        if candidate.startswith("lib") and len(candidate) > 3
    )
    for marker in sorted(
        FORBIDDEN_NATIVE_LIBRARY_MARKERS,
        key=lambda value: (-len(value), value),
    ):
        normalized = marker.lower()
        if normalized in candidates:
            return marker
    return None


def _forbidden_dependency_markers(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    markers = {
        marker
        for marker in FORBIDDEN_STRING_MARKERS
        if marker.lower() in lowered
    }
    markers.update(
        prefix
        for prefix in FORBIDDEN_IMPORT_PREFIXES
        if prefix.lower() in lowered
    )
    return tuple(sorted(markers))


def _forbidden_artifact_name_markers(relative_path: str) -> tuple[str, ...]:
    lowered = relative_path.lower().replace("\\", "/")
    markers = {
        marker
        for marker in FORBIDDEN_STRING_MARKERS
        if marker.lower() in lowered
    }
    markers.update(
        prefix
        for prefix in FORBIDDEN_IMPORT_PREFIXES
        if prefix.lower() in lowered
    )
    markers.update(
        marker
        for marker in FORBIDDEN_NATIVE_LIBRARY_MARKERS
        if marker.lower() in lowered
    )
    return tuple(sorted(markers, key=lambda value: (-len(value), value)))


def _literal_string_value(
    node: ast.AST,
    *,
    constants: dict[str, str] | None = None,
) -> str | None:
    if isinstance(node, ast.Name) and constants is not None:
        return constants.get(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_string_value(node.left, constants=constants)
        right = _literal_string_value(node.right, constants=constants)
        if left is not None and right is not None:
            return left + right
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
                continue
            if (
                isinstance(value, ast.FormattedValue)
                and value.conversion == -1
                and value.format_spec is None
            ):
                formatted = _literal_string_value(value.value, constants=constants)
                if formatted is not None:
                    parts.append(formatted)
                    continue
                return None
            return None
        return "".join(parts)
    return None


def _literal_bytes_value(
    node: ast.AST,
    *,
    constants: dict[str, bytes] | None = None,
) -> bytes | None:
    if isinstance(node, ast.Name) and constants is not None:
        return constants.get(node.id)
    if isinstance(node, ast.Constant) and isinstance(node.value, bytes):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _literal_bytes_value(node.left, constants=constants)
        right = _literal_bytes_value(node.right, constants=constants)
        if left is not None and right is not None:
            return left + right
    return None


def _matches_prefix(module: str, prefixes: Iterable[str]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def _hash_many(values: tuple[str, ...], *, namespace: str) -> list[str]:
    return [hash_identifier(value, namespace=namespace) for value in values]


def _file_hash(relative_path: str, source: str) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "path": relative_path,
                "source_hash": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            }
        )
    ).hexdigest()


def _file_bytes_hash(relative_path: str, content: bytes) -> str:
    return hashlib.sha256(
        _canonical_json(
            {
                "content_hash": hashlib.sha256(content).hexdigest(),
                "path": relative_path,
            }
        )
    ).hexdigest()


def _assert_sha256_hex(value: str, field_name: str) -> None:
    if len(value) != 64:
        raise FirstPartySourceAuditError(f"{field_name} must be a sha256 hex digest")
    try:
        bytes.fromhex(value)
    except ValueError as exc:
        raise FirstPartySourceAuditError(
            f"{field_name} must be a sha256 hex digest"
        ) from exc


def _utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
