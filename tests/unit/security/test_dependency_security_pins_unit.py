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


def _requirements(path: Path) -> dict[str, Requirement]:
    parsed: dict[str, Requirement] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        req = Requirement(line)
        parsed[canonicalize_name(req.name)] = req
    return parsed


def test_requirements_txt_keeps_sbom_security_fix_pins() -> None:
    requirements = _requirements(ROOT / "requirements.txt")

    for package, version in SECURITY_PIN_FIXES.items():
        req = requirements[package]
        assert str(req.specifier) == f"=={version}"


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
