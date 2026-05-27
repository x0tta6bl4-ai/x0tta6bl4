import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_script(name: str, rel_path: str):
    path = ROOT / rel_path
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _missing_runner(_root, args, _timeout):
    if args[:4] == ["ip", "-j", "link", "show"]:
        return {
            "args": args,
            "available": True,
            "exit_code": 0,
            "stdout": json.dumps([{"ifname": args[-1]}]),
            "stderr": "",
        }
    return {
        "args": args,
        "available": False,
        "exit_code": None,
        "stdout": "",
        "stderr": f"{args[0]} not found",
    }


def _verified_runner():
    map_dump_calls = 0

    def runner(_root, args, _timeout):
        nonlocal map_dump_calls
        stdout = ""
        if args == ["uname", "-r"]:
            stdout = "6.8.0-test\n"
        elif args == ["ip", "-d", "-j", "link", "show"]:
            stdout = json.dumps(
                [
                    {
                        "ifname": "eth-test",
                        "xdp": {"prog_id": 42, "mode": "driver"},
                    }
                ]
            )
        elif args[:4] == ["ip", "-j", "link", "show"]:
            stdout = json.dumps(
                [
                    {
                        "ifname": args[-1],
                        "xdp": {"prog_id": 42, "mode": "driver"},
                    }
                ]
            )
        elif args[:5] == ["ip", "-d", "-j", "link", "show"]:
            stdout = json.dumps(
                [
                    {
                        "ifname": args[-1],
                        "xdp": {"prog_id": 42, "mode": "driver"},
                    }
                ]
            )
        elif args == ["bpftool", "prog", "show"]:
            stdout = "42: xdp name x0tta6bl4_pulse tag abc123\n"
        elif args == ["bpftool", "net"]:
            stdout = "xdp:\neth-test prog/x0tta6bl4_pulse id 42\n"
        elif args == ["bpftool", "map", "show", "name", "pulse_stats"]:
            stdout = "123: hash name pulse_stats\n"
        elif args == ["bpftool", "map", "dump", "name", "pulse_stats"]:
            stdout = "packets: 4\n" if map_dump_calls == 0 else "packets: 9\n"
            map_dump_calls += 1
        else:
            raise AssertionError(f"unexpected command: {args!r}")
        return {
            "args": args,
            "available": True,
            "exit_code": 0,
            "stdout": stdout,
            "stderr": "",
        }

    return runner


def _sudo_verified_runner():
    map_dump_calls = 0

    def runner(_root, args, _timeout):
        nonlocal map_dump_calls
        stdout = ""
        if args == ["uname", "-r"]:
            stdout = "6.8.0-test\n"
        elif args == ["ip", "-d", "-j", "link", "show"]:
            stdout = json.dumps(
                [
                    {
                        "ifname": "eth-test",
                        "xdp": {"prog_id": 42, "mode": "driver"},
                    }
                ]
            )
        elif args[:4] == ["ip", "-j", "link", "show"]:
            stdout = json.dumps(
                [
                    {
                        "ifname": args[-1],
                        "xdp": {"prog_id": 42, "mode": "driver"},
                    }
                ]
            )
        elif args[:5] == ["ip", "-d", "-j", "link", "show"]:
            stdout = json.dumps(
                [
                    {
                        "ifname": args[-1],
                        "xdp": {"prog_id": 42, "mode": "driver"},
                    }
                ]
            )
        elif args == ["sudo", "-n", "bpftool", "prog", "show"]:
            stdout = "42: xdp name x0tta6bl4_pulse tag abc123\n"
        elif args == ["sudo", "-n", "bpftool", "net"]:
            stdout = "xdp:\neth-test prog/x0tta6bl4_pulse id 42\n"
        elif args == ["sudo", "-n", "bpftool", "map", "show", "name", "pulse_stats"]:
            stdout = "123: hash name pulse_stats\n"
        elif args == ["sudo", "-n", "bpftool", "map", "dump", "name", "pulse_stats"]:
            stdout = "packets: 4\n" if map_dump_calls == 0 else "packets: 9\n"
            map_dump_calls += 1
        else:
            raise AssertionError(f"unexpected command: {args!r}")
        return {
            "args": args,
            "available": True,
            "exit_code": 0,
            "stdout": stdout,
            "stderr": "",
        }

    return runner


def _sudo_password_required_runner(_root, args, _timeout):
    if args == ["uname", "-r"]:
        return {
            "args": args,
            "available": True,
            "exit_code": 0,
            "stdout": "6.8.0-test\n",
            "stderr": "",
        }
    if args == ["ip", "-d", "-j", "link", "show"]:
        return {
            "args": args,
            "available": True,
            "exit_code": 0,
            "stdout": json.dumps([{"ifname": "enp8s0"}]),
            "stderr": "",
        }
    if args[:4] == ["ip", "-j", "link", "show"] or args[:5] == ["ip", "-d", "-j", "link", "show"]:
        return {
            "args": args,
            "available": True,
            "exit_code": 0,
            "stdout": json.dumps([{"ifname": args[-1]}]),
            "stderr": "",
        }
    if args[:3] == ["sudo", "-n", "bpftool"]:
        return {
            "args": args,
            "available": True,
            "exit_code": 1,
            "stdout": "",
            "stderr": "sudo: a password is required\n",
        }
    raise AssertionError(f"unexpected command: {args!r}")


def _permission_denied_runner(_root, args, _timeout):
    if args == ["uname", "-r"]:
        return {
            "args": args,
            "available": True,
            "exit_code": 0,
            "stdout": "6.8.0-test\n",
            "stderr": "",
        }
    if args == ["ip", "-d", "-j", "link", "show"]:
        return {
            "args": args,
            "available": True,
            "exit_code": 0,
            "stdout": json.dumps([{"ifname": "enp8s0"}]),
            "stderr": "",
        }
    if args[:4] == ["ip", "-j", "link", "show"] or args[:5] == ["ip", "-d", "-j", "link", "show"]:
        return {
            "args": args,
            "available": True,
            "exit_code": 0,
            "stdout": json.dumps([{"ifname": args[-1]}]),
            "stderr": "",
        }
    if args and args[0] == "bpftool":
        return {
            "args": args,
            "available": True,
            "exit_code": 255,
            "stdout": "",
            "stderr": "Error: can't query prog: Operation not permitted\n",
        }
    raise AssertionError(f"unexpected command: {args!r}")


def _write_pulse_source_and_minimal_object(root: Path):
    source = root / "src/network/ebpf/x0tta6bl4_pulse.bpf.c"
    obj = root / "src/network/ebpf/x0tta6bl4_pulse.o"
    source.parent.mkdir(parents=True)
    source.write_text(
        """
#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u64);
} pulse_stats SEC(".maps");

SEC("xdp")
int xdp_x0tta6bl4_pulse(struct xdp_md *ctx) {
    return XDP_PASS;
}
""",
        encoding="utf-8",
    )
    header = bytearray(128)
    header[0:4] = b"\x7fELF"
    header[4] = 2
    header[5] = 1
    header[6] = 1
    header[16:18] = (1).to_bytes(2, "little")
    header[18:20] = (247).to_bytes(2, "little")
    obj.write_bytes(
        bytes(header) + b"\x00xdp\x00.maps\x00.BTF\x00pulse_stats\x00xdp_x0tta6bl4_pulse\x00"
    )


def test_kernel_attach_collector_fails_closed_without_kernel_observations(tmp_path):
    collector = _load_script(
        "collect_ghost_pulse_kernel_attach_evidence",
        "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
    )

    report = collector.build_report(
        root=tmp_path,
        iface="lo",
        command_runner=_missing_runner,
        counter_wait_seconds=0.0,
    )
    output_json = tmp_path / "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.md"
    paths = collector.write_report_outputs(tmp_path, report, output_json, output_md)
    written = json.loads(output_json.read_text(encoding="utf-8"))

    assert written["schema"] == collector.SCHEMA
    assert written["claim_id"] == collector.CLAIM_ID
    assert written["status"] == collector.STATUS_INCOMPLETE
    assert written["simulated"] is False
    assert written["dry_run"] is False
    assert written["template"] is False
    assert written["claim_boundary"]["kernel_attach_verified"] is False
    assert "ip link did not show an XDP attach on interface: lo" in written["failures"]
    assert written["collection_diagnostics"]["status"] == "ACTION_REQUIRED"
    assert "bpftool_unavailable" in written["collection_diagnostics"]["blockers"]
    assert written["collection_diagnostics"]["bpftool_permission_denied"] is False
    assert written["object_preflight"]["status"] == "ACTION_REQUIRED"
    assert "pulse_source_missing" in written["object_preflight"]["blockers"]
    assert "pulse_object_missing" in written["object_preflight"]["blockers"]
    assert written["collection_diagnostics"]["object_preflight_status"] == "ACTION_REQUIRED"
    assert written["candidate_import_readiness"]["status"] == "ACTION_REQUIRED"
    assert written["candidate_import_readiness"]["candidate_path"] == (
        "docs/verification/incoming/kernel_attach.json"
    )
    assert written["candidate_import_readiness"]["source_latest_evidence"] == (
        "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json"
    )
    assert written["candidate_import_readiness"]["can_stage_candidate"] is False
    assert written["candidate_import_readiness"]["do_not_stage_candidate"] is True
    assert written["candidate_import_readiness"]["stage_candidate_command"] is None
    assert "kernel_evidence_not_verified" in written["candidate_import_readiness"]["blocking_reasons"]
    assert "bpftool_unavailable" in written["candidate_import_readiness"]["blocking_reasons"]
    assert written["candidate_import_readiness"]["read_only_import_command"] == [
        "python3",
        "scripts/ops/import_ghost_pulse_external_evidence.py",
        "--claim",
        "kernel_attach",
        "--candidate",
        "docs/verification/incoming/kernel_attach.json",
        "--require-ready",
        "--json",
    ]
    assert paths["latest_md"].exists()
    assert paths["latest_json"].read_text(encoding="utf-8") == paths["bundle_json"].read_text(encoding="utf-8")
    assert paths["latest_md"].read_text(encoding="utf-8") == paths["bundle_md"].read_text(encoding="utf-8")
    assert list(paths["latest_json"].parent.glob(".*.tmp")) == []
    assert list(paths["bundle_json"].parent.glob(".*.tmp")) == []
    assert {artifact["role"] for artifact in written["artifacts"]} == {
        "kernel_commands",
        "kernel_measurements",
        "kernel_interface_scan",
        "kernel_candidate_audit",
        "kernel_object_preflight",
    }
    for artifact in written["artifacts"]:
        artifact_path = tmp_path / artifact["path"]
        assert artifact_path.exists()
        assert artifact["sha256"] == collector.sha256_file(artifact_path)


def test_kernel_attach_collector_accepts_complete_observed_contract(tmp_path):
    collector = _load_script(
        "collect_ghost_pulse_kernel_attach_evidence_verified",
        "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
    )
    proof = _load_script(
        "run_ghost_pulse_proof_gate_for_kernel_attach",
        "scripts/ops/run_ghost_pulse_proof_gate.py",
    )

    report = collector.build_report(
        root=tmp_path,
        iface="eth-test",
        command_runner=_verified_runner(),
        counter_wait_seconds=0.0,
    )
    output_json = tmp_path / "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.md"
    collector.write_report_outputs(tmp_path, report, output_json, output_md)

    written = json.loads(output_json.read_text(encoding="utf-8"))
    assert written["status"] == collector.STATUS_VERIFIED
    assert written["measurements"]["interface"] == "eth-test"
    assert written["measurements"]["interface_scan_count"] == 1
    assert written["measurements"]["interface_scan_xdp_interfaces"] == ["eth-test"]
    assert written["measurements"]["xdp_attached"] is True
    assert written["measurements"]["bpftool_prog_show_contains_pulse"] is True
    assert written["measurements"]["bpftool_net_contains_interface"] is True
    assert written["measurements"]["map_counter_delta_packets"] == 5
    assert written["collection_diagnostics"]["status"] == "READY_FOR_PROOF"
    assert written["collection_diagnostics"]["blockers"] == []
    assert written["collection_diagnostics"]["bpftool_permission_denied"] is False
    assert written["candidate_import_readiness"]["status"] == "READY_TO_STAGE_CANDIDATE"
    assert written["candidate_import_readiness"]["can_stage_candidate"] is True
    assert written["candidate_import_readiness"]["do_not_stage_candidate"] is False
    assert written["candidate_import_readiness"]["blocking_reasons"] == []
    assert written["candidate_import_readiness"]["stage_candidate_command"] == [
        "cp",
        "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json",
        "docs/verification/incoming/kernel_attach.json",
    ]
    assert all(command["exit_code"] == 0 for command in written["commands"])
    artifact_roles = {artifact["role"] for artifact in written["artifacts"]}
    assert set(proof.EXTERNAL_REQUIREMENTS[0]["required_artifact_roles"]).issubset(artifact_roles)
    assert "kernel_object_preflight" in artifact_roles

    row = proof.validate_external_evidence(tmp_path, proof.EXTERNAL_REQUIREMENTS[0])

    assert row["status"] == "VERIFIED"
    assert row["errors"] == []


def test_kernel_attach_collector_records_disk_object_preflight_without_promoting_claim(tmp_path):
    collector = _load_script(
        "collect_ghost_pulse_kernel_attach_evidence_object_preflight",
        "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
    )
    _write_pulse_source_and_minimal_object(tmp_path)

    report = collector.build_report(
        root=tmp_path,
        iface="lo",
        command_runner=_missing_runner,
        counter_wait_seconds=0.0,
    )

    assert report["status"] == collector.STATUS_INCOMPLETE
    assert report["claim_boundary"]["kernel_attach_verified"] is False
    assert report["object_preflight"]["status"] == "READY_FOR_CONTROLLED_ATTACH_TEST"
    assert report["object_preflight"]["blockers"] == []
    assert report["object_preflight"]["source"]["contains_xdp_section"] is True
    assert report["object_preflight"]["source"]["contains_pulse_stats"] is True
    assert report["object_preflight"]["source"]["contains_pulse_function"] is True
    assert report["object_preflight"]["object"]["is_ebpf"] is True
    assert report["object_preflight"]["object"]["has_xdp_section"] is True
    assert report["object_preflight"]["object"]["has_maps_section"] is True
    assert report["object_preflight"]["object"]["has_btf_section"] is True
    assert report["object_preflight"]["object"]["contains_pulse_stats"] is True
    assert report["object_preflight"]["object"]["contains_pulse_function"] is True
    assert report["collection_diagnostics"]["object_preflight_status"] == (
        "READY_FOR_CONTROLLED_ATTACH_TEST"
    )
    assert "xdp_attach_not_visible" in report["collection_diagnostics"]["blockers"]


def test_kernel_attach_collector_can_observe_bpftool_through_sudo_noninteractive(tmp_path):
    collector = _load_script(
        "collect_ghost_pulse_kernel_attach_evidence_sudo",
        "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
    )
    proof = _load_script(
        "run_ghost_pulse_proof_gate_for_kernel_attach_sudo",
        "scripts/ops/run_ghost_pulse_proof_gate.py",
    )

    report = collector.build_report(
        root=tmp_path,
        iface="eth-test",
        command_runner=_sudo_verified_runner(),
        counter_wait_seconds=0.0,
        bpftool_sudo=True,
    )
    output_json = tmp_path / "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.json"
    output_md = tmp_path / "docs/verification/GHOST_PULSE_KERNEL_ATTACH_LATEST.md"
    collector.write_report_outputs(tmp_path, report, output_json, output_md)

    written = json.loads(output_json.read_text(encoding="utf-8"))
    bpftool_commands = [command for command in written["commands"] if command["args"][0] == "bpftool"]

    assert written["status"] == collector.STATUS_VERIFIED
    assert written["collection_options"]["bpftool_sudo"] is True
    assert written["collection_diagnostics"]["bpftool_privilege_mode"] == "sudo_noninteractive"
    assert written["collection_diagnostics"]["sudo_noninteractive_unavailable"] is False
    assert bpftool_commands
    assert all(command["execution_args"][:3] == ["sudo", "-n", "bpftool"] for command in bpftool_commands)
    assert all(command["args"][0] == "bpftool" for command in bpftool_commands)
    assert written["candidate_import_readiness"]["status"] == "READY_TO_STAGE_CANDIDATE"

    row = proof.validate_external_evidence(tmp_path, proof.EXTERNAL_REQUIREMENTS[0])

    assert row["status"] == "VERIFIED"
    assert row["errors"] == []


def test_kernel_attach_collector_records_noninteractive_sudo_blocker(tmp_path):
    collector = _load_script(
        "collect_ghost_pulse_kernel_attach_evidence_sudo_blocked",
        "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
    )

    report = collector.build_report(
        root=tmp_path,
        iface="enp8s0",
        command_runner=_sudo_password_required_runner,
        counter_wait_seconds=0.0,
        bpftool_sudo=True,
    )

    diagnostics = report["collection_diagnostics"]
    bpftool_commands = [command for command in report["commands"] if command["args"][0] == "bpftool"]
    assert report["status"] == collector.STATUS_INCOMPLETE
    assert diagnostics["bpftool_privilege_mode"] == "sudo_noninteractive"
    assert diagnostics["sudo_noninteractive_enabled"] is True
    assert diagnostics["sudo_noninteractive_unavailable"] is True
    assert "sudo_noninteractive_unavailable" in diagnostics["blockers"]
    assert "bpftool_command_failed" in diagnostics["blockers"]
    assert all(command["execution_args"][:3] == ["sudo", "-n", "bpftool"] for command in bpftool_commands)
    readiness = report["candidate_import_readiness"]
    assert readiness["status"] == "ACTION_REQUIRED"
    assert "sudo_noninteractive_unavailable" in readiness["blocking_reasons"]


def test_kernel_attach_collector_classifies_bpftool_permission_denied(tmp_path):
    collector = _load_script(
        "collect_ghost_pulse_kernel_attach_evidence_permission",
        "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
    )

    report = collector.build_report(
        root=tmp_path,
        iface="enp8s0",
        command_runner=_permission_denied_runner,
        counter_wait_seconds=0.0,
    )

    diagnostics = report["collection_diagnostics"]
    assert report["status"] == collector.STATUS_INCOMPLETE
    assert diagnostics["status"] == "ACTION_REQUIRED"
    assert diagnostics["bpftool_permission_denied"] is True
    assert "bpftool_permission_denied" in diagnostics["blockers"]
    assert "xdp_attach_not_visible" in diagnostics["blockers"]
    assert diagnostics["bpftool_permission_denied_commands"][0]["name"] == "bpftool_prog_show"
    assert diagnostics["bpftool_permission_denied_commands"][0]["exit_code"] == 255
    readiness = report["candidate_import_readiness"]
    assert readiness["status"] == "ACTION_REQUIRED"
    assert readiness["can_stage_candidate"] is False
    assert "bpftool_permission_denied" in readiness["blocking_reasons"]


def test_kernel_attach_collector_counter_parser_handles_json_payload():
    collector = _load_script(
        "collect_ghost_pulse_kernel_attach_evidence_counter",
        "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
    )

    assert collector.parse_packet_counter('{"value": {"packets": 17}}') == 17
    assert collector.parse_packet_counter("packets: 23\n") == 23
    assert collector.parse_packet_counter('[{"key": 0, "value": 31}]') == 31


def test_kernel_attach_candidate_audit_rejects_non_pulse_xdp_artifact(tmp_path):
    collector = _load_script(
        "collect_ghost_pulse_kernel_attach_evidence_candidate_audit",
        "scripts/ops/collect_ghost_pulse_kernel_attach_evidence.py",
    )
    candidate = tmp_path / "docs/verification/xdp-live-attach/example.log"
    candidate.parent.mkdir(parents=True)
    candidate.write_text(
        "status: interface=enp8s0\nprog/xdp id 5920 name xdp_mesh_filter\n",
        encoding="utf-8",
    )

    audit = collector.audit_candidate_artifacts(
        tmp_path,
        "enp8s0",
        ("docs/verification/xdp-live-attach/example.log",),
    )

    assert audit["status"] == "NO_ACCEPTED_CANDIDATE"
    assert audit["accepted"] == []
    assert audit["candidates"][0]["contains_xdp_attach"] is True
    assert audit["candidates"][0]["contains_interface"] is True
    assert audit["candidates"][0]["contains_pulse_marker"] is False
    assert "candidate references xdp_mesh_filter, not x0tta6bl4_pulse" in (
        audit["candidates"][0]["rejection_reasons"]
    )
