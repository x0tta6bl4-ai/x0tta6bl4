from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name


ROOT = Path(__file__).resolve().parents[3]

SECURITY_PIN_FIXES = {
    "authlib": "1.6.12",
    "gitpython": "3.1.50",
    "idna": "3.15",
    "mako": "1.3.12",
    "python-multipart": "0.0.27",
    "urllib3": "2.7.0",
}

CORE_DEPENDENCY_MANIFESTS = (
    "requirements.txt",
    "requirements.lock",
    "requirements-staging.txt",
    "requirements-dev.txt",
    "docker/mesh-node/requirements.txt",
    "monitoring/geo-leak-detector/requirements.txt",
)

REMOVED_DEPENDABOT_MANIFESTS = (
    "другие проекты/базис-веб/requirements-neural.txt",
)

REMOVED_UNPATCHED_DEPENDENCIES = (
    "paramiko",
)


def _requirements(path: Path) -> dict[str, Requirement]:
    parsed: dict[str, Requirement] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        req = Requirement(line)
        parsed[canonicalize_name(req.name)] = req
    return parsed


def test_core_dependency_manifests_parse_as_requirements() -> None:
    for manifest in CORE_DEPENDENCY_MANIFESTS:
        _requirements(ROOT / manifest)


def test_requirements_txt_keeps_sbom_security_fix_pins() -> None:
    requirements = _requirements(ROOT / "requirements.txt")

    for package, version in SECURITY_PIN_FIXES.items():
        req = requirements[package]
        assert str(req.specifier) == f"=={version}"


def test_requirements_lock_matches_requirements_txt_pins() -> None:
    requirements = _requirements(ROOT / "requirements.txt")
    lock = _requirements(ROOT / "requirements.lock")

    for package, req in requirements.items():
        assert package in lock
        assert str(lock[package].specifier) == str(req.specifier)


def test_staging_and_pyproject_keep_security_floor_versions() -> None:
    staging = _requirements(ROOT / "requirements-staging.txt")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_requirements = {
        canonicalize_name(req.name): req
        for req in (
            Requirement(item)
            for item in pyproject["project"]["dependencies"]
        )
    }

    assert str(staging["python-multipart"].specifier) == ">=0.0.27"
    assert str(project_requirements["python-multipart"].specifier) == ">=0.0.27"
    assert str(project_requirements["urllib3"].specifier) == ">=2.7.0"
    assert str(project_requirements["idna"].specifier) == ">=3.15"


def test_removed_dependabot_manifests_stay_absent() -> None:
    for manifest in REMOVED_DEPENDABOT_MANIFESTS:
        assert not (ROOT / manifest).exists(), (
            f"{manifest} was removed from the current baseline. If it is restored, "
            "add it back to the dependency security pins before merging."
        )


def test_removed_unpatched_dependencies_stay_out_of_runtime_baseline() -> None:
    requirements = _requirements(ROOT / "requirements.txt")
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project_requirements = {
        canonicalize_name(req.name): req
        for req in (
            Requirement(item)
            for item in pyproject["project"]["dependencies"]
        )
    }
    skill_update_script = (
        ROOT / "x0tta6bl4-core-skill/x0tta6bl4-core/scripts/update_dependencies.sh"
    ).read_text(encoding="utf-8").lower()

    for package in REMOVED_UNPATCHED_DEPENDENCIES:
        assert package not in requirements
        assert package not in project_requirements
        assert package not in skill_update_script
