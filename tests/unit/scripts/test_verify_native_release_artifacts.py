import hashlib
import json
from pathlib import Path

from scripts.ops.verify_native_release_artifacts import build_report, main


def _write_file(path: Path, data: bytes = b"x0t") -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _write_manifest(
    root: Path,
    platform: str,
    artifacts: list[dict],
    *,
    signing: dict | None = None,
    commit: str = "abc123",
) -> None:
    manifest_dir = root / f"x0tta6bl4-{platform}-manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "x0tta6bl4.native_build_manifest.v1",
        "platform": platform,
        "app_id": "net.x0tta6bl4.mesh",
        "run_id": "123",
        "commit": commit,
        "generated_at_utc": "2026-06-01T00:00:00Z",
        "artifacts": artifacts,
    }
    if signing is not None:
        payload["signing"] = signing
    (manifest_dir / "native-build-manifest.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _complete_artifact_root(root: Path) -> Path:
    debug_sha = _write_file(root / "x0tta6bl4-android-apks/debug/app-debug.apk")
    release_sha = _write_file(root / "x0tta6bl4-android-apks/release/app-release.apk")
    aab_sha = _write_file(root / "x0tta6bl4-android-release-aab/app-release.aab")
    _write_manifest(
        root,
        "android",
        [
            {
                "path": "android/app/build/outputs/apk/debug/app-debug.apk",
                "kind": "debug_apk",
                "sha256": debug_sha,
                "size_bytes": 3,
            },
            {
                "path": "android/app/build/outputs/apk/release/app-release.apk",
                "kind": "release_apk",
                "sha256": release_sha,
                "size_bytes": 3,
            },
            {
                "path": "android/app/build/outputs/bundle/release/app-release.aab",
                "kind": "release_aab",
                "sha256": aab_sha,
                "size_bytes": 3,
            },
        ],
        signing={"release_signing_requested": True, "signed_release_present": True},
    )

    sim_sha = _write_file(root / "x0tta6bl4-ios-simulator-app/App")
    device_sha = _write_file(root / "x0tta6bl4-ios-device-unsigned-app/App")
    ipa_sha = _write_file(root / "x0tta6bl4-ios-signed-ipa/App.ipa")
    _write_manifest(
        root,
        "ios",
        [
            {
                "path": "x0tta6bl4-app/ios/App/build/Build/Products/Debug-iphonesimulator/App.app/App",
                "kind": "simulator_app_file",
                "sha256": sim_sha,
                "size_bytes": 3,
            },
            {
                "path": "x0tta6bl4-app/ios/App/build-device/Build/Products/Release-iphoneos/App.app/App",
                "kind": "unsigned_device_app_file",
                "sha256": device_sha,
                "size_bytes": 3,
            },
            {
                "path": "x0tta6bl4-app/ios/App/build/ipa/App.ipa",
                "kind": "signed_ipa",
                "sha256": ipa_sha,
                "size_bytes": 3,
            },
        ],
        signing={
            "device_signing_requested": True,
            "unsigned_device_build_present": True,
            "signed_ipa_present": True,
        },
    )

    msi_sha = _write_file(root / "x0tta6bl4-windows-msi/x0tta6bl4.msi")
    _write_manifest(
        root,
        "windows",
        [
            {
                "path": "./src-tauri/target/release/bundle/msi/x0tta6bl4.msi",
                "kind": "msi",
                "sha256": msi_sha,
                "size_bytes": 3,
            }
        ],
    )

    deb_sha = _write_file(root / "x0tta6bl4-ubuntu-desktop/deb/x0tta6bl4.deb")
    appimage_sha = _write_file(
        root / "x0tta6bl4-ubuntu-desktop/appimage/x0tta6bl4.AppImage"
    )
    _write_manifest(
        root,
        "ubuntu",
        [
            {
                "path": "src-tauri/target/release/bundle/deb/x0tta6bl4.deb",
                "kind": "deb",
                "sha256": deb_sha,
                "size_bytes": 3,
            },
            {
                "path": "src-tauri/target/release/bundle/appimage/x0tta6bl4.AppImage",
                "kind": "appimage",
                "sha256": appimage_sha,
                "size_bytes": 3,
            },
        ],
    )
    return root


def test_complete_native_release_artifacts_pass(tmp_path: Path) -> None:
    root = _complete_artifact_root(tmp_path)

    report = build_report(artifact_root=root)

    assert report["complete"] is True
    assert report["summary"]["failures_total"] == 0
    assert report["platforms"]["ios"]["signing"]["signed_ipa_present"] is True


def test_missing_ios_signed_ipa_blocks_complete_release(tmp_path: Path) -> None:
    root = _complete_artifact_root(tmp_path)
    ipa = root / "x0tta6bl4-ios-signed-ipa/App.ipa"
    ipa.unlink()
    ios_manifest = root / "x0tta6bl4-ios-manifest/native-build-manifest.json"
    payload = json.loads(ios_manifest.read_text(encoding="utf-8"))
    payload["artifacts"] = [
        item for item in payload["artifacts"] if item["kind"] != "signed_ipa"
    ]
    payload["signing"]["signed_ipa_present"] = False
    ios_manifest.write_text(json.dumps(payload), encoding="utf-8")

    report = build_report(artifact_root=root)

    assert report["complete"] is False
    assert "ios:artifact_kind_missing:signed_ipa" in report["summary"]["failure_ids"]
    assert "ios:signed_ipa_missing" in report["summary"]["failure_ids"]


def test_hash_mismatch_blocks_platform_completion(tmp_path: Path) -> None:
    root = _complete_artifact_root(tmp_path)
    (root / "x0tta6bl4-windows-msi/x0tta6bl4.msi").write_bytes(b"changed")

    report = build_report(artifact_root=root)

    assert report["complete"] is False
    assert any(
        item.startswith("windows:sha256_mismatch:")
        for item in report["summary"]["failure_ids"]
    )


def test_main_require_complete_returns_two_for_incomplete_release(
    tmp_path: Path,
) -> None:
    root = _complete_artifact_root(tmp_path / "artifacts")
    (root / "x0tta6bl4-ios-signed-ipa/App.ipa").unlink()
    ios_manifest = root / "x0tta6bl4-ios-manifest/native-build-manifest.json"
    payload = json.loads(ios_manifest.read_text(encoding="utf-8"))
    payload["artifacts"] = [
        item for item in payload["artifacts"] if item["kind"] != "signed_ipa"
    ]
    payload["signing"]["signed_ipa_present"] = False
    ios_manifest.write_text(json.dumps(payload), encoding="utf-8")

    output = tmp_path / "report.json"
    code = main(
        [
            "--artifact-root",
            str(root),
            "--output",
            str(output),
            "--require-complete",
        ]
    )

    assert code == 2
    assert json.loads(output.read_text(encoding="utf-8"))["complete"] is False
