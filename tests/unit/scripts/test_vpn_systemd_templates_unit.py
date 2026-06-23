import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[3]
BOOT_VALIDATE_SERVICE = ROOT / "infra/systemd/x0tta-vpn-boot-validate.service"
NODE_SAFE_OBSERVE_DROPIN = ROOT / "infra/systemd/x0tta-node-safe-observe.conf"
FIRSTPARTY_WRAPPER = (
    ROOT / "services/nl-server/firstparty-vpn-test/x0vpn_test_node.py"
)


def _load_firstparty_wrapper():
    spec = importlib.util.spec_from_file_location(
        "test_x0vpn_firstparty_wrapper",
        FIRSTPARTY_WRAPPER,
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class _PassingEvidence:
    passed = True
    failed_reasons = ()

    def to_json_dict(self):
        return {"passed": True, "checks": []}

    def evidence_hash(self):
        return "0" * 64


def test_boot_validation_does_not_require_x0tta_node():
    text = BOOT_VALIDATE_SERVICE.read_text(encoding="utf-8")

    requires_lines = [
        line for line in text.splitlines() if line.startswith("Requires=")
    ]
    assert requires_lines
    assert all("x0tta-node.service" not in line for line in requires_lines)
    assert "x0tta-vpn-watchdog.service" in "\n".join(requires_lines)
    assert "Wants=network-online.target x0tta-node.service" in text


def test_x0tta_node_dropin_is_observe_only():
    text = NODE_SAFE_OBSERVE_DROPIN.read_text(encoding="utf-8")

    assert "Environment=PYTHONPATH=/mnt/projects" in text
    assert "Environment=VPN_SELF_HEAL_ENABLE=false" in text
    assert "Environment=VPN_ENABLE_REALITY_ROTATION=false" in text
    assert "Environment=VPN_ENABLE_PULSE_SHIFT=false" in text


def test_firstparty_client_health_reports_ok_without_mutating_os(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22080,
                "tunnel": {
                    "client_tun_name": "x0vpn9",
                    "client_address": "10.90.0.9/32",
                    "route_all_traffic": True,
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        wrapper,
        "_systemd_service_active",
        lambda _service_name: (True, "active"),
    )
    monkeypatch.setattr(
        wrapper,
        "_linux_interface_addresses",
        lambda _tun_name: (("10.90.0.9",), None),
    )
    monkeypatch.setattr(wrapper, "_default_route_device", lambda: "x0vpn9")
    monkeypatch.setattr(
        wrapper,
        "_route_to_host_gateway_and_interface",
        lambda _host: ("192.0.2.1", "eth0"),
    )
    monkeypatch.setattr(
        wrapper,
        "_tcp_connect_open",
        lambda _host, _port, *, timeout: (True, None),
    )

    exit_code = wrapper.client_health(
        SimpleNamespace(
            config=str(config_path),
            service_name="x0tta-firstparty-vpn-client.service",
            timeout=0.1,
            skip_service=False,
            skip_tcp_connect=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "client-health"
    assert payload["os_mutation_performed"] is False
    assert payload["tun"] == "x0vpn9"
    assert {check["name"] for check in payload["checks"]} == {
        "systemd_service_active",
        "tun_interface_address",
        "default_route_uses_tun",
        "server_endpoint_uses_underlay",
        "server_tcp_port_open",
    }


def test_firstparty_client_doctor_combines_preflight_readiness_probe_and_health(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "host": "203.0.113.10",
                "port": 22080,
                "deployment_epoch": "test-epoch",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        wrapper,
        "_linux_preflight_evidence",
        lambda *_args, **_kwargs: (
            _PassingEvidence(),
            {"tun": "x0vpn0", "deployment_epoch": "test-epoch"},
        ),
    )

    async def fake_readiness(_args):
        return {
            "ok": True,
            "mode": "client-readiness",
            "checks": [],
            "os_mutation_performed": False,
        }

    async def fake_probe(*_args, **_kwargs):
        return {
            "ok": True,
            "mode": "probe",
            "tun_packet": True,
            "ping_pong_ok": True,
        }

    monkeypatch.setattr(wrapper, "_client_readiness_payload", fake_readiness)
    monkeypatch.setattr(wrapper, "_probe_payload", fake_probe)
    monkeypatch.setattr(
        wrapper,
        "_client_health_payload",
        lambda *_args, **_kwargs: {
            "ok": False,
            "mode": "client-health",
            "checks": [
                {
                    "name": "systemd_service_active",
                    "ok": False,
                    "required": True,
                    "details": {},
                }
            ],
            "os_mutation_performed": False,
        },
    )

    exit_code = wrapper.asyncio.run(
        wrapper.client_doctor(
            SimpleNamespace(
                config=str(config_path),
                service_name="x0tta-firstparty-vpn-client.service",
                install_dir="/opt/x0tta-firstparty-vpn-client",
                config_dir="/etc/x0tta-firstparty-vpn-client",
                service_python="/usr/bin/python3",
                health_timeout=5.0,
                readiness_timeout=5.0,
                probe_timeout=5.0,
                min_identity_valid_seconds=900,
                message="health",
                skip_preflight=False,
                skip_readiness=False,
                skip_probe=False,
                skip_health=False,
                skip_tcp_connect=False,
                skip_admission=False,
                skip_config_sync=False,
                skip_managed_install_plan=False,
                require_installed_health=False,
            )
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "client-doctor"
    assert payload["status"] == "ready_to_install"
    assert payload["require_installed_health"] is False
    assert payload["failed_required_checks"] == []
    assert [check["name"] for check in payload["checks"]] == [
        "linux_preflight",
        "client_readiness",
        "dataplane_probe",
        "installed_client_health",
    ]
    assert payload["checks"][3]["required"] is False


def test_firstparty_client_doctor_can_require_installed_health(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "host": "203.0.113.10",
                "port": 22080,
                "deployment_epoch": "test-epoch",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        wrapper,
        "_linux_preflight_evidence",
        lambda *_args, **_kwargs: (_PassingEvidence(), {}),
    )

    async def fake_readiness(_args):
        return {"ok": True, "mode": "client-readiness"}

    async def fake_probe(*_args, **_kwargs):
        return {"ok": True, "mode": "probe"}

    monkeypatch.setattr(wrapper, "_client_readiness_payload", fake_readiness)
    monkeypatch.setattr(wrapper, "_probe_payload", fake_probe)
    monkeypatch.setattr(
        wrapper,
        "_client_health_payload",
        lambda *_args, **_kwargs: {"ok": False, "mode": "client-health"},
    )

    exit_code = wrapper.asyncio.run(
        wrapper.client_doctor(
            SimpleNamespace(
                config=str(config_path),
                service_name="x0tta-firstparty-vpn-client.service",
                install_dir="/opt/x0tta-firstparty-vpn-client",
                config_dir="/etc/x0tta-firstparty-vpn-client",
                service_python="/usr/bin/python3",
                health_timeout=5.0,
                readiness_timeout=5.0,
                probe_timeout=5.0,
                min_identity_valid_seconds=900,
                message="health",
                skip_preflight=False,
                skip_readiness=False,
                skip_probe=False,
                skip_health=False,
                skip_tcp_connect=False,
                skip_admission=False,
                skip_config_sync=False,
                skip_managed_install_plan=False,
                require_installed_health=True,
            )
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["status"] == "needs_attention"
    assert payload["failed_required_checks"] == ["installed_client_health"]


def test_firstparty_source_audit_cli_passes_current_package(
    capsys,
):
    wrapper = _load_firstparty_wrapper()

    exit_code = wrapper.source_audit(
        SimpleNamespace(
            root=None,
            captured_at=123,
        )
    )

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["allowed"] is True
    assert payload["mode"] == "source-audit"
    assert payload["captured_at"] == 123
    assert payload["scanned_files"] > 1
    assert len(payload["source_tree_hash"]) == 64
    assert "/mnt/projects" not in output_text
    assert payload["os_mutation_performed"] is False


def test_firstparty_source_audit_cli_rejects_foreign_backend_without_raw_leak(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    root = tmp_path / "bad-firstparty"
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="utf-8")
    (root / "bad_backend.py").write_text(
        "import importlib\n"
        "backend = importlib.import_module('wireguard.crypto')\n"
        "marker = 'open' + 'vpn'\n",
        encoding="utf-8",
    )

    exit_code = wrapper.source_audit(
        SimpleNamespace(
            root=str(root),
            captured_at=123,
        )
    )

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["allowed"] is False
    assert payload["mode"] == "source-audit"
    assert "firstparty_forbidden_import_detected" in payload["reasons"]
    assert "firstparty_foreign_protocol_marker_detected" in payload["reasons"]
    assert str(root) not in output_text
    assert "wireguard" not in output_text.lower()
    assert "openvpn" not in output_text.lower()
    assert payload["forbidden_import_hashes"]
    assert payload["forbidden_marker_hashes"]
    assert payload["os_mutation_performed"] is False


def test_firstparty_server_health_reports_ok_without_mutating_os(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "server.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "bind_host": "0.0.0.0",
                "port": 22080,
                "tunnel": {
                    "server_tun_name": "x0vpns9",
                    "server_address": "10.90.0.1/24",
                    "client_cidr": "10.90.0.0/24",
                    "shared_return_by_client_address": True,
                    "client_leases": [
                        {
                            "identity_hash": "a" * 64,
                            "client_address": "10.90.0.2",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        wrapper,
        "_systemd_service_active",
        lambda _service_name: (True, "active"),
    )
    monkeypatch.setattr(
        wrapper,
        "_tcp_listening_on_port",
        lambda _port: (True, None),
    )
    monkeypatch.setattr(
        wrapper,
        "_linux_interface_addresses",
        lambda _tun_name: (("10.90.0.1",), None),
    )
    monkeypatch.setattr(
        wrapper,
        "_route_device_for_prefix",
        lambda _prefix: ("x0vpns9", None),
    )
    monkeypatch.setattr(wrapper, "_ipv4_forward_enabled", lambda: (True, None))
    monkeypatch.setattr(wrapper, "_default_route_interface", lambda: "eth0")

    exit_code = wrapper.server_health(
        SimpleNamespace(
            config=str(config_path),
            service_name="x0tta-firstparty-vpn-test.service",
            uplink_interface=None,
            skip_service=False,
            skip_listen=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "server-health"
    assert payload["os_mutation_performed"] is False
    assert payload["service_name"] == "x0tta-firstparty-vpn-test.service"
    assert payload["tun"] == "x0vpns9"
    assert {check["name"] for check in payload["checks"]} == {
        "systemd_service_active",
        "server_tcp_listener",
        "server_tun_interface_address",
        "client_cidr_route_uses_tun",
        "ipv4_forward_enabled",
        "uplink_interface_detected",
        "shared_return_client_leases",
    }


def test_firstparty_local_tun_probe_echo_reply_round_trips_icmp_request():
    wrapper = _load_firstparty_wrapper()
    request = wrapper._probe_icmp_echo_request(
        {
            "deployment_epoch": "local-firstparty-canary-test",
            "tunnel": {
                "client_address": "10.90.0.2/32",
                "client_peer": "10.90.0.1",
            },
        }
    )

    reply = wrapper._local_tun_probe_echo_reply(request["packet"])

    assert reply is not None
    assert wrapper._is_probe_icmp_echo_reply(reply, request)
    assert wrapper._local_tun_probe_echo_reply(b"x0vpn-test-echo") is None


def test_firstparty_local_canary_dataplane_reassembles_fragmented_tun_probe():
    wrapper = _load_firstparty_wrapper()
    request = wrapper._probe_icmp_echo_request(
        {
            "deployment_epoch": "local-firstparty-fragment-canary-test",
            "tunnel": {
                "client_address": "10.90.0.2/32",
                "client_peer": "10.90.0.1",
            },
        }
    )
    fragments = wrapper.PacketFragmenter(max_payload_size=32).split(request["packet"])
    session = SimpleNamespace(session_id=7)
    reassemblers = {}

    responses = [
        wrapper._local_canary_dataplane_response(
            fragment,
            session=session,
            reassemblers=reassemblers,
            fragmentation_enabled=True,
        )
        for fragment in fragments
    ]

    assert len(fragments) > 1
    assert responses[:-1] == [None] * (len(fragments) - 1)
    assert responses[-1] is not None
    assert wrapper._is_probe_icmp_echo_reply(responses[-1], request)
    assert reassemblers[7].pending_packets == 0
    assert (
        wrapper._local_canary_dataplane_response(
            b"plain",
            session=session,
            reassemblers=reassemblers,
            fragmentation_enabled=True,
        )
        == b"x0vpn-test-echo:plain"
    )


def test_firstparty_server_health_uses_config_service_name_when_default_requested(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    observed_service_names: list[str] = []
    config_path = tmp_path / "server.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "bind_host": "0.0.0.0",
                "port": 22081,
                "service_name": "x0tta-firstparty-vpn-managed-canary.service",
                "tunnel": {
                    "server_tun_name": "x0vpns1",
                    "server_address": "10.91.0.1/24",
                    "client_cidr": "10.91.0.0/24",
                    "shared_return_by_client_address": True,
                    "client_leases": [
                        {
                            "identity_hash": "a" * 64,
                            "client_address": "10.91.0.2",
                        }
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    def fake_systemd_service_active(service_name: str):
        observed_service_names.append(service_name)
        return True, "active"

    monkeypatch.setattr(wrapper, "_systemd_service_active", fake_systemd_service_active)
    monkeypatch.setattr(wrapper, "_tcp_listening_on_port", lambda _port: (True, None))
    monkeypatch.setattr(
        wrapper,
        "_linux_interface_addresses",
        lambda _tun_name: (("10.91.0.1",), None),
    )
    monkeypatch.setattr(
        wrapper,
        "_route_device_for_prefix",
        lambda _prefix: ("x0vpns1", None),
    )
    monkeypatch.setattr(wrapper, "_ipv4_forward_enabled", lambda: (True, None))
    monkeypatch.setattr(wrapper, "_default_route_interface", lambda: "eth0")

    exit_code = wrapper.server_health(
        SimpleNamespace(
            config=str(config_path),
            service_name=wrapper.DEFAULT_SERVER_SERVICE_NAME,
            uplink_interface=None,
            skip_service=False,
            skip_listen=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["service_name"] == "x0tta-firstparty-vpn-managed-canary.service"
    assert observed_service_names == ["x0tta-firstparty-vpn-managed-canary.service"]
    service_check = next(
        check for check in payload["checks"] if check["name"] == "systemd_service_active"
    )
    assert service_check["details"]["service_name"] == (
        "x0tta-firstparty-vpn-managed-canary.service"
    )


def test_firstparty_server_service_plan_does_not_mutate_os(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "server.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "bind_host": "0.0.0.0",
                "port": 22081,
                "tunnel": {
                    "server_tun_name": "x0vpns1",
                    "server_address": "10.91.0.1/24",
                    "client_cidr": "10.91.0.0/24",
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.server_service_plan(
        SimpleNamespace(
            config=str(config_path),
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            install_dir="/opt/x0tta-firstparty-vpn-managed-canary",
            config_dir="/etc/x0tta-firstparty-vpn-managed-canary",
            service_python="/usr/bin/python3",
            uplink_interface="eth0",
            enable_now=True,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    unit = payload["unit_content"]
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "server-service-plan"
    assert payload["os_mutation_performed"] is False
    assert payload["service_name"] == "x0tta-firstparty-vpn-managed-canary.service"
    assert payload["config_path"] == "/etc/x0tta-firstparty-vpn-managed-canary/server.json"
    assert payload["script_path"] == "/opt/x0tta-firstparty-vpn-managed-canary/x0vpn_node.py"
    assert "write private server config mode 0600" in payload["install_actions"]
    assert payload["post_install_commands"] == [
        "systemctl daemon-reload",
        "systemctl enable --now x0tta-firstparty-vpn-managed-canary.service",
    ]
    assert "server-tun" in unit
    assert "--allow-os-mutation" in unit
    assert "--uplink-interface eth0" in unit
    assert "issuer.json" not in json.dumps(payload, sort_keys=True)


def test_firstparty_service_plans_use_production_entrypoint_when_invoked_as_x0vpn_node(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    monkeypatch.setattr(wrapper, "__file__", str(tmp_path / "x0vpn_node.py"))
    server_config_path = tmp_path / "server.json"
    server_config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "bind_host": "0.0.0.0",
                "port": 22081,
                "tunnel": {
                    "server_tun_name": "x0vpns1",
                    "server_address": "10.91.0.1/24",
                    "client_cidr": "10.91.0.0/24",
                },
            }
        ),
        encoding="utf-8",
    )
    client_config_path = tmp_path / "client.json"
    client_config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22082,
                "transport": "camouflage",
            }
        ),
        encoding="utf-8",
    )

    assert wrapper.server_service_plan(
        SimpleNamespace(
            config=str(server_config_path),
            service_name="x0tta-firstparty-vpn.service",
            install_dir="/opt/x0tta-firstparty-vpn",
            config_dir="/etc/x0tta-firstparty-vpn",
            service_python="/usr/bin/python3",
            uplink_interface="eth0",
            enable_now=True,
        )
    ) == 0
    server_payload = json.loads(capsys.readouterr().out)
    assert server_payload["script_path"] == "/opt/x0tta-firstparty-vpn/x0vpn_node.py"
    assert "x0vpn_node.py server-tun" in server_payload["unit_content"]
    assert "x0vpn_test_node.py" not in server_payload["unit_content"]

    assert wrapper.client_service_plan(
        SimpleNamespace(
            config=str(client_config_path),
            service_name="x0tta-firstparty-vpn-client.service",
            install_dir="/opt/x0tta-firstparty-vpn-client",
            config_dir="/etc/x0tta-firstparty-vpn-client",
            service_python="/usr/bin/python3",
            disable_kill_switch=False,
            install_config_sync=False,
            enable=False,
            start=False,
            enable_now=False,
            require_readiness=False,
        )
    ) == 0
    client_payload = json.loads(capsys.readouterr().out)
    assert (
        client_payload["script_path"]
        == "/opt/x0tta-firstparty-vpn-client/x0vpn_node.py"
    )
    assert "x0vpn_node.py client-tun" in client_payload["unit_content"]
    assert "x0vpn_test_node.py" not in client_payload["unit_content"]


def test_firstparty_linux_preflight_reports_server_host_readiness(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    original_evaluate = wrapper.evaluate_linux_deployment_preflight
    monkeypatch.setattr(
        wrapper,
        "collect_linux_host_facts",
        lambda: wrapper.LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0",
            effective_uid=0,
            has_net_admin=True,
        ),
    )
    monkeypatch.setattr(wrapper, "_default_route_interface", lambda: "eth0")
    monkeypatch.setattr(
        wrapper,
        "evaluate_linux_deployment_preflight",
        lambda *, facts, config, apply_commands, rollback_commands: original_evaluate(
            facts=facts,
            config=config,
            apply_commands=apply_commands,
            rollback_commands=rollback_commands,
            path_exists=lambda _path: True,
            binary_exists=lambda _binary: True,
        ),
    )
    config_path = tmp_path / "server.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "bind_host": "0.0.0.0",
                "port": 22081,
                "tunnel": {
                    "server_tun_name": "x0vpns1",
                    "server_address": "10.91.0.1/24",
                    "client_cidr": "10.91.0.0/24",
                    "enable_iptables_compat": True,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.linux_preflight(
        SimpleNamespace(
            config=str(config_path),
            role="server",
            uplink_interface=None,
            underlay_gateway=None,
            underlay_interface=None,
            enable_kill_switch=False,
            no_require_root=False,
            no_require_net_admin=False,
            no_require_tun_device=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "linux-preflight"
    assert payload["role"] == "server"
    assert payload["tun"] == "x0vpns1"
    assert payload["uplink_interface"] == "eth0"
    assert payload["failed_reasons"] == []
    assert payload["apply_plan"]["command_count"] > 1
    assert payload["rollback_plan"]["command_count"] > 0
    assert payload["os_mutation_performed"] is False


def test_firstparty_linux_preflight_reports_client_host_readiness(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    original_evaluate = wrapper.evaluate_linux_deployment_preflight
    monkeypatch.setattr(
        wrapper,
        "collect_linux_host_facts",
        lambda: wrapper.LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0",
            effective_uid=0,
            has_net_admin=True,
        ),
    )
    monkeypatch.setattr(
        wrapper,
        "evaluate_linux_deployment_preflight",
        lambda *, facts, config, apply_commands, rollback_commands: original_evaluate(
            facts=facts,
            config=config,
            apply_commands=apply_commands,
            rollback_commands=rollback_commands,
            path_exists=lambda _path: True,
            binary_exists=lambda _binary: True,
        ),
    )
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22081,
                "tunnel": {
                    "client_tun_name": "x0vpn1",
                    "client_address": "10.91.0.2/32",
                    "client_peer": "10.91.0.1",
                    "dns_servers": ["1.1.1.1"],
                    "route_all_traffic": True,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.linux_preflight(
        SimpleNamespace(
            config=str(config_path),
            role="client",
            uplink_interface=None,
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
            enable_kill_switch=True,
            no_require_root=False,
            no_require_net_admin=False,
            no_require_tun_device=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "linux-preflight"
    assert payload["role"] == "client"
    assert payload["tun"] == "x0vpn1"
    assert payload["underlay_interface"] == "eth0"
    assert payload["failed_reasons"] == []
    assert payload["apply_plan"]["command_count"] > 1
    assert payload["rollback_plan"]["command_count"] > 0
    assert payload["os_mutation_performed"] is False


def test_firstparty_leak_protection_plan_reports_client_controls(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22081,
                "tunnel": {
                    "client_tun_name": "x0vpn1",
                    "client_address": "10.91.0.2/32",
                    "client_peer": "10.91.0.1",
                    "dns_servers": ["1.1.1.1"],
                    "route_all_traffic": True,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.leak_protection_plan(
        SimpleNamespace(
            config=str(config_path),
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
            enable_kill_switch=True,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "leak-protection-plan"
    assert payload["passed"] is True
    assert payload["reasons"] == []
    assert payload["kill_switch_enabled"] is True
    assert "full_tunnel_default_route" in payload["controls"]
    assert "tun_dns_servers" in payload["controls"]
    assert "kill_switch_output_drop_policy" in payload["controls"]
    assert "underlay_endpoint_route" in payload["controls"]
    assert "underlay_endpoint_kill_switch_allow" in payload["controls"]
    assert payload["command_plan"]["command_count"] > 1
    assert payload["os_mutation_performed"] is False


def test_firstparty_leak_protection_plan_uses_config_kill_switch_by_default(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22081,
                "tunnel": {
                    "client_tun_name": "x0vpn1",
                    "client_address": "10.91.0.2/32",
                    "client_peer": "10.91.0.1",
                    "dns_servers": ["1.1.1.1"],
                    "route_all_traffic": True,
                    "enable_kill_switch": True,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.leak_protection_plan(
        SimpleNamespace(
            config=str(config_path),
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
            enable_kill_switch=None,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["passed"] is True
    assert payload["kill_switch_enabled"] is True
    assert "kill_switch_disabled" not in payload["reasons"]


def test_firstparty_zero_trust_policy_reports_private_policy_evidence(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "policy": {
                    "allowed_tenants": ["team-a"],
                    "max_token_lifetime_seconds": 3600,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.zero_trust_policy(
        SimpleNamespace(
            config=str(config_path),
            target="nl",
            max_identity_lifetime_seconds=3600,
        )
    )

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["allowed"] is True
    assert payload["mode"] == "zero-trust-policy"
    assert payload["allowed_tenant_count"] == 1
    assert payload["allowed_workloads"] == ["vpn-client", "vpn-server"]
    assert payload["required_kem_algorithms"] == ["ML-KEM-1024", "ML-KEM-768"]
    assert payload["required_signature_algorithms"] == ["ML-DSA-65", "ML-DSA-87"]
    assert len(payload["policy_hash"]) == 64
    assert len(payload["evidence_hash"]) == 64
    assert payload["reasons"] == []
    assert "team-a" not in output_text
    assert payload["os_mutation_performed"] is False


def test_firstparty_probe_ipv4_packet_uses_client_and_peer_addresses():
    wrapper = _load_firstparty_wrapper()

    packet = wrapper._probe_ipv4_packet(
        {
            "tunnel": {
                "client_address": "10.91.0.2/32",
                "client_peer": "10.91.0.1",
            }
        },
        b"probe",
    )

    assert packet[0] >> 4 == 4
    assert int.from_bytes(packet[2:4], "big") == len(packet)
    assert packet[12:16] == b"\x0a\x5b\x00\x02"
    assert packet[16:20] == b"\x0a\x5b\x00\x01"
    assert packet[20:] == b"probe"


def test_firstparty_pqc_readiness_reports_candidate_and_runtime_mismatch(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    source_root = tmp_path / "firstparty"
    source_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    keypair = wrapper.mlkem_keygen_from_seeds(
        wrapper.KEM_ALGORITHM,
        b"pqc-readiness-d-seed".ljust(wrapper.ML_KEM_SEED_BYTES, b"d"),
        b"pqc-readiness-z-seed".ljust(wrapper.ML_KEM_SEED_BYTES, b"z"),
    )
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "pqc": {
                    "provider_id": "x0tta6bl4-firstparty-mlkem-live-test",
                    "kem_algorithm": wrapper.KEM_ALGORITHM,
                    "signature_algorithm": wrapper.SIGNATURE_ALGORITHM,
                    "mode": "test",
                    "reviewed": False,
                    "issued_at": 100,
                    "expires_at": 4600,
                    "implementation_hash": "a" * 64,
                    "encapsulation_key": keypair.encapsulation_key.hex(),
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.pqc_readiness(
        SimpleNamespace(
            config=str(config_path),
            source_root=str(source_root),
            captured_at=123,
            max_evidence_age_seconds=3600,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["mode"] == "pqc-readiness"
    assert payload["runtime_metadata_matches_manifest"] is False
    assert payload["pqc_provider_gate"]["allowed"] is False
    assert "pqc_runtime_attestation_manifest_mismatch" in payload[
        "pqc_provider_gate"
    ]["reasons"]
    assert payload["pqc_manifest"]["mode"] == "production"
    assert payload["pqc_manifest"]["reviewed"] is True
    assert payload["pqc_kat"]["passed"] is True
    assert payload["pqc_kat"]["vector_count"] == 1
    assert payload["candidate_pqc_metadata"]["mode"] == "production"
    assert payload["candidate_pqc_metadata"]["reviewed"] is True
    assert "encapsulation_key" not in payload["candidate_pqc_metadata"]
    assert payload["os_mutation_performed"] is False

    promoted_path = tmp_path / "client.promoted.json"
    promote_exit = wrapper.pqc_promote_config(
        SimpleNamespace(
            config=str(config_path),
            out_config=str(promoted_path),
            update_config=False,
            source_root=str(source_root),
            captured_at=123,
            max_evidence_age_seconds=3600,
        )
    )
    promote_payload = json.loads(capsys.readouterr().out)
    promoted_config = json.loads(promoted_path.read_text(encoding="utf-8"))

    assert promote_exit == 0
    assert promote_payload["ok"] is True
    assert promote_payload["file_mutation_performed"] is True
    assert promote_payload["os_mutation_performed"] is False
    assert promoted_config["pqc"]["mode"] == "production"
    assert promoted_config["pqc"]["reviewed"] is True
    assert promoted_config["pqc"]["encapsulation_key"] == (
        keypair.encapsulation_key.hex()
    )

    promoted_exit = wrapper.pqc_readiness(
        SimpleNamespace(
            config=str(promoted_path),
            source_root=str(source_root),
            captured_at=123,
            max_evidence_age_seconds=3600,
        )
    )
    promoted_payload = json.loads(capsys.readouterr().out)

    assert promoted_exit == 0
    assert promoted_payload["ok"] is True
    assert promoted_payload["runtime_metadata_matches_manifest"] is True
    assert promoted_payload["pqc_provider_gate"]["allowed"] is True
    assert promoted_payload["pqc_provider_gate"]["reasons"] == []


def test_firstparty_identity_signer_readiness_reports_private_safe_evidence(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    source_root = tmp_path / "firstparty"
    source_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    keypair = wrapper.mldsa_derive_reference_keypair(
        b"identity-signer-readiness-seed".ljust(
            wrapper.ML_DSA_KEYGEN_SEED_BYTES,
            b"k",
        ),
        wrapper.SIGNATURE_ALGORITHM,
    )
    signing_key = wrapper.IdentitySigningKey(
        key_id="test-identity-signer-key",
        signature_algorithm=wrapper.SIGNATURE_ALGORITHM,
        secret=keypair.signing_key,
        not_before=100,
        not_after=4600,
    )
    issuer_path = tmp_path / "issuer.json"
    issuer_path.write_text(
        json.dumps(
            {
                "issuer": "x0tta6bl4-firstparty-test-issuer",
                "policy_epoch": "test-policy",
                "active_key_id": signing_key.key_id,
                "signing_key": wrapper._key_to_json(signing_key),
                "default_lifetime_seconds": 3600,
                "max_lifetime_seconds": 3600,
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.identity_signer_readiness(
        SimpleNamespace(
            issuer_config=str(issuer_path),
            source_root=str(source_root),
            captured_at=123,
            max_evidence_age_seconds=3600,
        )
    )

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["allowed"] is True
    assert payload["mode"] == "identity-signer-readiness"
    assert payload["identity_signer_gate"]["allowed"] is True
    assert payload["identity_signer_gate"]["reasons"] == []
    assert payload["identity_signer_manifest"]["mode"] == "production"
    assert payload["identity_signer_manifest"]["reviewed"] is True
    assert payload["identity_signer_kat"]["passed"] is True
    assert payload["identity_signer_kat"]["vector_count"] == 1
    assert payload["identity_signer_conformance"]["passed"] is True
    assert payload["identity_signer_conformance"]["profile"] == "fips204-production"
    assert signing_key.secret.hex() not in output_text
    assert payload["os_mutation_performed"] is False


def test_firstparty_production_readiness_fails_closed_after_collecting_current_evidence(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    original_evaluate = wrapper.evaluate_linux_deployment_preflight
    source_root = tmp_path / "firstparty"
    source_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        wrapper,
        "collect_linux_host_facts",
        lambda: wrapper.LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0",
            effective_uid=0,
            has_net_admin=True,
        ),
    )
    monkeypatch.setattr(wrapper, "_default_route_interface", lambda: "eth0")
    monkeypatch.setattr(
        wrapper,
        "evaluate_linux_deployment_preflight",
        lambda *, facts, config, apply_commands, rollback_commands: original_evaluate(
            facts=facts,
            config=config,
            apply_commands=apply_commands,
            rollback_commands=rollback_commands,
            path_exists=lambda _path: True,
            binary_exists=lambda _binary: True,
        ),
    )
    config_path = tmp_path / "server.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "bind_host": "0.0.0.0",
                "port": 22081,
                "policy": {
                    "allowed_tenants": ["team-a"],
                    "max_token_lifetime_seconds": 3600,
                },
                "tunnel": {
                    "server_tun_name": "x0vpns1",
                    "server_address": "10.91.0.1/24",
                    "client_cidr": "10.91.0.0/24",
                    "enable_iptables_compat": True,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.production_readiness(
        SimpleNamespace(
            target="nl",
            source_root=str(source_root),
            config=str(config_path),
            issuer_config=None,
            role="server",
            uplink_interface=None,
            underlay_gateway=None,
            underlay_interface=None,
            enable_kill_switch=False,
            evaluated_at=123,
            max_evidence_age_seconds=3600,
            max_identity_lifetime_seconds=3600,
            no_require_root=False,
            no_require_net_admin=False,
            no_require_tun_device=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    reasons = set(payload["reasons"])

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["allowed"] is False
    assert payload["mode"] == "production-readiness"
    assert payload["collected"] == {
        "dataplane": False,
        "external_policy_source": False,
        "identity_signer": False,
        "leak_protection": False,
        "linux_preflight": True,
        "pqc": False,
        "rekey_policy": False,
        "rollout_gate": False,
        "source_audit": True,
        "zero_trust_policy": True,
    }
    assert payload["linux_preflight"]["passed"] is True
    assert payload["source_audit"]["allowed"] is True
    assert payload["zero_trust_policy"]["allowed_tenant_count"] == 1
    assert "linux_preflight_missing" not in reasons
    assert "linux_host_fingerprint_requirement_missing" not in reasons
    assert "apply_plan_hash_requirement_missing" not in reasons
    assert "rollback_plan_hash_requirement_missing" not in reasons
    assert "firstparty_source_audit_missing" not in reasons
    assert "firstparty_source_audit_root_requirement_missing" not in reasons
    assert "firstparty_source_audit_tree_requirement_missing" not in reasons
    assert "leak_protection_missing" not in reasons
    assert "dataplane_validation_missing" in reasons
    assert "tun_dataplane_validation_missing" in reasons
    assert "zero_trust_policy_missing" not in reasons
    assert "zero_trust_policy_hash_requirement_missing" not in reasons
    assert "rollout_gate_missing" in reasons
    assert payload["os_mutation_performed"] is False


def test_firstparty_production_readiness_collects_client_leak_protection(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    original_evaluate = wrapper.evaluate_linux_deployment_preflight
    source_root = tmp_path / "firstparty"
    source_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        wrapper,
        "collect_linux_host_facts",
        lambda: wrapper.LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0",
            effective_uid=0,
            has_net_admin=True,
        ),
    )
    monkeypatch.setattr(
        wrapper,
        "evaluate_linux_deployment_preflight",
        lambda *, facts, config, apply_commands, rollback_commands: original_evaluate(
            facts=facts,
            config=config,
            apply_commands=apply_commands,
            rollback_commands=rollback_commands,
            path_exists=lambda _path: True,
            binary_exists=lambda _binary: True,
        ),
    )
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22081,
                "policy": {
                    "allowed_tenants": ["team-a"],
                    "max_token_lifetime_seconds": 3600,
                },
                "tunnel": {
                    "client_tun_name": "x0vpn1",
                    "client_address": "10.91.0.2/32",
                    "client_peer": "10.91.0.1",
                    "dns_servers": ["1.1.1.1"],
                    "route_all_traffic": True,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.production_readiness(
        SimpleNamespace(
            target="nl",
            source_root=str(source_root),
            config=str(config_path),
            issuer_config=None,
            role="client",
            uplink_interface=None,
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
            enable_kill_switch=True,
            evaluated_at=123,
            max_evidence_age_seconds=3600,
            max_identity_lifetime_seconds=3600,
            no_require_root=False,
            no_require_net_admin=False,
            no_require_tun_device=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    reasons = set(payload["reasons"])

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["allowed"] is False
    assert payload["mode"] == "production-readiness"
    assert payload["collected"] == {
        "dataplane": False,
        "external_policy_source": False,
        "identity_signer": False,
        "leak_protection": True,
        "linux_preflight": True,
        "pqc": False,
        "rekey_policy": False,
        "rollout_gate": False,
        "source_audit": True,
        "zero_trust_policy": True,
    }
    assert payload["leak_protection"]["passed"] is True
    assert payload["leak_protection"]["kill_switch_enabled"] is True
    assert payload["zero_trust_policy"]["allowed_workloads"] == [
        "vpn-client",
        "vpn-server",
    ]
    assert "leak_protection_missing" not in reasons
    assert "leak_protection_plan_hash_requirement_missing" not in reasons
    assert "linux_preflight_missing" not in reasons
    assert "firstparty_source_audit_missing" not in reasons
    assert "zero_trust_policy_missing" not in reasons
    assert "zero_trust_policy_hash_requirement_missing" not in reasons
    assert "dataplane_validation_missing" in reasons
    assert payload["os_mutation_performed"] is False


def test_firstparty_production_readiness_collects_dataplane_evidence(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    original_evaluate = wrapper.evaluate_linux_deployment_preflight
    source_root = tmp_path / "firstparty"
    source_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        wrapper,
        "collect_linux_host_facts",
        lambda: wrapper.LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0",
            effective_uid=0,
            has_net_admin=True,
        ),
    )
    monkeypatch.setattr(
        wrapper,
        "evaluate_linux_deployment_preflight",
        lambda *, facts, config, apply_commands, rollback_commands: original_evaluate(
            facts=facts,
            config=config,
            apply_commands=apply_commands,
            rollback_commands=rollback_commands,
            path_exists=lambda _path: True,
            binary_exists=lambda _binary: True,
        ),
    )

    def fake_dataplane_bundle(
        config,
        *,
        captured_at,
        path_label,
        timeout_seconds,
        payload_size,
        mtu_candidates,
    ):
        probe = wrapper.DataplaneProbeSpec(
            probe_id="vps-tcp-22081",
            path_label=path_label,
            transport="tcp",
            remote_ref="test-remote",
            payload_size=payload_size,
            timeout_seconds=timeout_seconds,
        )
        plan = wrapper.DataplaneValidationPlan(
            probes=(probe,),
            required_path_labels=frozenset({path_label}),
            min_successful_probes=1,
        )

        async def dataplane_runner(current_probe):
            return wrapper.DataplaneProbeResult.success_result(
                current_probe,
                latency_millis=7,
                rx_frames=2,
                tx_frames=2,
                rx_bytes=64,
                tx_bytes=64,
            )

        dataplane = wrapper.asyncio.run(
            wrapper.evaluate_dataplane_validation(
                plan=plan,
                runner=dataplane_runner,
                captured_at=captured_at,
            )
        )
        tun_dataplane = wrapper.TunDataplaneValidationEvidence.from_results(
            plan=plan,
            results=(
                wrapper.TunDataplaneProbeResult.success_result(
                    probe,
                    packets_from_tun=1,
                    packets_to_tun=1,
                    bytes_from_tun=64,
                    bytes_to_tun=64,
                ),
            ),
            captured_at=captured_at,
        )
        mtu = wrapper.MtuValidationEvidence.from_results(
            plan=plan,
            results=(
                wrapper.MtuPathProbeResult.success_result(
                    probe,
                    wrapper.MtuProbeResult(
                        selected_payload_size=1280,
                        selected_fragment_payload_size=1216,
                        attempts=(wrapper.MtuProbeAttempt(1280, True),),
                    ),
                ),
            ),
            captured_at=captured_at,
        )
        return {
            "plan": plan,
            "dataplane": dataplane,
            "tun_dataplane": tun_dataplane,
            "mtu": mtu,
        }

    monkeypatch.setattr(wrapper, "_dataplane_evidence_bundle", fake_dataplane_bundle)
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22081,
                "policy": {
                    "allowed_tenants": ["team-a"],
                    "max_token_lifetime_seconds": 3600,
                },
                "tunnel": {
                    "client_tun_name": "x0vpn1",
                    "client_address": "10.91.0.2/32",
                    "client_peer": "10.91.0.1",
                    "dns_servers": ["1.1.1.1"],
                    "mtu": 1280,
                    "route_all_traffic": True,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.production_readiness(
        SimpleNamespace(
            target="nl",
            source_root=str(source_root),
            config=str(config_path),
            issuer_config=None,
            role="client",
            uplink_interface=None,
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
            enable_kill_switch=True,
            collect_dataplane=True,
            dataplane_path_label="vps",
            dataplane_timeout=3.0,
            dataplane_payload_size=64,
            dataplane_mtu_candidates=None,
            evaluated_at=123,
            max_evidence_age_seconds=3600,
            max_identity_lifetime_seconds=3600,
            no_require_root=False,
            no_require_net_admin=False,
            no_require_tun_device=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    reasons = set(payload["reasons"])

    assert exit_code == 1
    assert payload["collected"]["dataplane"] is True
    assert payload["dataplane"]["dataplane_validation"]["passed"] is True
    assert payload["dataplane"]["tun_dataplane_validation"]["passed"] is True
    assert payload["dataplane"]["mtu_validation"]["passed"] is True
    assert "dataplane_validation_missing" not in reasons
    assert "tun_dataplane_validation_missing" not in reasons
    assert "mtu_validation_missing" not in reasons
    assert "dataplane_probe_matrix_requirement_missing" not in reasons
    assert "dataplane_probe_matrix_mismatch" not in reasons
    assert payload["os_mutation_performed"] is False


def test_firstparty_production_readiness_collects_external_policy_source(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    original_evaluate = wrapper.evaluate_linux_deployment_preflight
    source_root = tmp_path / "firstparty"
    source_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        wrapper,
        "collect_linux_host_facts",
        lambda: wrapper.LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0",
            effective_uid=0,
            has_net_admin=True,
        ),
    )
    monkeypatch.setattr(
        wrapper,
        "evaluate_linux_deployment_preflight",
        lambda *, facts, config, apply_commands, rollback_commands: original_evaluate(
            facts=facts,
            config=config,
            apply_commands=apply_commands,
            rollback_commands=rollback_commands,
            path_exists=lambda _path: True,
            binary_exists=lambda _binary: True,
        ),
    )
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22081,
                "identity": {"policy_epoch": "test-policy"},
                "policy": {
                    "allowed_tenants": ["team-a"],
                    "max_token_lifetime_seconds": 3600,
                },
                "tunnel": {
                    "client_tun_name": "x0vpn1",
                    "client_address": "10.91.0.2/32",
                    "client_peer": "10.91.0.1",
                    "dns_servers": ["1.1.1.1"],
                    "route_all_traffic": True,
                },
            }
        ),
        encoding="utf-8",
    )
    snapshot = wrapper.PolicySnapshot(policy_epoch="test-policy", issued_at=100)
    policy_source_path = tmp_path / "external-policy.json"
    policy_source_path.write_text(
        json.dumps(snapshot.to_json_dict()),
        encoding="utf-8",
    )

    exit_code = wrapper.production_readiness(
        SimpleNamespace(
            target="nl",
            source_root=str(source_root),
            config=str(config_path),
            issuer_config=None,
            policy_source_path=str(policy_source_path),
            policy_source_id="test-policy-source",
            policy_source_epoch="test-policy",
            policy_source_minimum_issued_at=0,
            role="client",
            uplink_interface=None,
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
            enable_kill_switch=True,
            evaluated_at=123,
            max_evidence_age_seconds=3600,
            max_identity_lifetime_seconds=3600,
            no_require_root=False,
            no_require_net_admin=False,
            no_require_tun_device=False,
        )
    )

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)
    reasons = set(payload["reasons"])

    assert exit_code == 1
    assert payload["collected"]["external_policy_source"] is True
    assert payload["external_policy_source"]["policy_snapshot_hash"] == snapshot.snapshot_hash()
    assert "external_policy_source_missing" not in reasons
    assert "external_policy_source_hash_requirement_missing" not in reasons
    assert "policy_snapshot_hash_missing" not in reasons
    assert "policy_snapshot_hash_requirement_missing" not in reasons
    assert "test-policy-source" not in output_text
    assert str(policy_source_path) not in output_text
    assert payload["os_mutation_performed"] is False


def test_firstparty_production_readiness_collects_rekey_policy(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    original_evaluate = wrapper.evaluate_linux_deployment_preflight
    source_root = tmp_path / "firstparty"
    source_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        wrapper,
        "collect_linux_host_facts",
        lambda: wrapper.LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0",
            effective_uid=0,
            has_net_admin=True,
        ),
    )
    monkeypatch.setattr(
        wrapper,
        "evaluate_linux_deployment_preflight",
        lambda *, facts, config, apply_commands, rollback_commands: original_evaluate(
            facts=facts,
            config=config,
            apply_commands=apply_commands,
            rollback_commands=rollback_commands,
            path_exists=lambda _path: True,
            binary_exists=lambda _binary: True,
        ),
    )
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22081,
                "policy": {
                    "allowed_tenants": ["team-a"],
                    "max_token_lifetime_seconds": 3600,
                },
                "tunnel": {
                    "client_tun_name": "x0vpn1",
                    "client_address": "10.91.0.2/32",
                    "client_peer": "10.91.0.1",
                    "dns_servers": ["1.1.1.1"],
                    "route_all_traffic": True,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.production_readiness(
        SimpleNamespace(
            target="nl",
            source_root=str(source_root),
            config=str(config_path),
            issuer_config=None,
            role="client",
            uplink_interface=None,
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
            enable_kill_switch=True,
            collect_rekey_policy=True,
            rekey_max_session_age_seconds=1,
            rekey_requested_reason="scheduled-rotation",
            rekey_rollback_plan_id="test-rekey-rollback-plan",
            evaluated_at=123,
            max_evidence_age_seconds=3600,
            max_identity_lifetime_seconds=3600,
            no_require_root=False,
            no_require_net_admin=False,
            no_require_tun_device=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    reasons = set(payload["reasons"])

    assert exit_code == 1
    assert payload["collected"]["rekey_policy"] is True
    assert payload["rekey_policy"]["decision"]["allowed"] is True
    assert payload["rekey_policy"]["decision"]["rollback_plan_hash"]
    assert "rekey_policy_missing" not in reasons
    assert "rekey_policy_failed" not in reasons
    assert "rekey_rollback_evidence_missing" not in reasons
    assert "rekey_rollback_plan_requirement_missing" not in reasons
    assert payload["os_mutation_performed"] is False


def test_firstparty_production_readiness_collects_rollout_gate(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    original_evaluate = wrapper.evaluate_linux_deployment_preflight
    source_root = tmp_path / "firstparty"
    source_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        wrapper,
        "collect_linux_host_facts",
        lambda: wrapper.LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0",
            effective_uid=0,
            has_net_admin=True,
        ),
    )
    monkeypatch.setattr(
        wrapper,
        "evaluate_linux_deployment_preflight",
        lambda *, facts, config, apply_commands, rollback_commands: original_evaluate(
            facts=facts,
            config=config,
            apply_commands=apply_commands,
            rollback_commands=rollback_commands,
            path_exists=lambda _path: True,
            binary_exists=lambda _binary: True,
        ),
    )

    def fake_dataplane_bundle(
        config,
        *,
        captured_at,
        path_label,
        timeout_seconds,
        payload_size,
        mtu_candidates,
    ):
        probe = wrapper.DataplaneProbeSpec(
            probe_id="vps-tcp-22081",
            path_label=path_label,
            transport="tcp",
            remote_ref="test-remote",
            payload_size=payload_size,
            timeout_seconds=timeout_seconds,
        )
        plan = wrapper.DataplaneValidationPlan(
            probes=(probe,),
            required_path_labels=frozenset({path_label}),
            min_successful_probes=1,
        )

        async def dataplane_runner(current_probe):
            return wrapper.DataplaneProbeResult.success_result(
                current_probe,
                latency_millis=7,
                rx_frames=2,
                tx_frames=2,
                rx_bytes=64,
                tx_bytes=64,
            )

        dataplane = wrapper.asyncio.run(
            wrapper.evaluate_dataplane_validation(
                plan=plan,
                runner=dataplane_runner,
                captured_at=captured_at,
            )
        )
        tun_dataplane = wrapper.TunDataplaneValidationEvidence.from_results(
            plan=plan,
            results=(
                wrapper.TunDataplaneProbeResult.success_result(
                    probe,
                    packets_from_tun=1,
                    packets_to_tun=1,
                    bytes_from_tun=64,
                    bytes_to_tun=64,
                ),
            ),
            captured_at=captured_at,
        )
        mtu = wrapper.MtuValidationEvidence.from_results(
            plan=plan,
            results=(
                wrapper.MtuPathProbeResult.success_result(
                    probe,
                    wrapper.MtuProbeResult(
                        selected_payload_size=1280,
                        selected_fragment_payload_size=1216,
                        attempts=(wrapper.MtuProbeAttempt(1280, True),),
                    ),
                ),
            ),
            captured_at=captured_at,
        )
        return {
            "plan": plan,
            "dataplane": dataplane,
            "tun_dataplane": tun_dataplane,
            "mtu": mtu,
        }

    monkeypatch.setattr(wrapper, "_dataplane_evidence_bundle", fake_dataplane_bundle)
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22081,
                "identity": {"policy_epoch": "test-policy"},
                "policy": {
                    "allowed_tenants": ["team-a"],
                    "max_token_lifetime_seconds": 3600,
                },
                "tunnel": {
                    "client_tun_name": "x0vpn1",
                    "client_address": "10.91.0.2/32",
                    "client_peer": "10.91.0.1",
                    "dns_servers": ["1.1.1.1"],
                    "route_all_traffic": True,
                },
            }
        ),
        encoding="utf-8",
    )
    snapshot = wrapper.PolicySnapshot(policy_epoch="test-policy", issued_at=100)
    policy_source_path = tmp_path / "external-policy.json"
    policy_source_path.write_text(
        json.dumps(snapshot.to_json_dict()),
        encoding="utf-8",
    )

    exit_code = wrapper.production_readiness(
        SimpleNamespace(
            target="nl",
            source_root=str(source_root),
            config=str(config_path),
            issuer_config=None,
            policy_source_path=str(policy_source_path),
            policy_source_id="test-policy-source",
            policy_source_epoch="test-policy",
            policy_source_minimum_issued_at=0,
            role="client",
            uplink_interface=None,
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
            enable_kill_switch=True,
            collect_dataplane=True,
            dataplane_path_label="vps",
            dataplane_timeout=3.0,
            dataplane_payload_size=64,
            dataplane_mtu_candidates=None,
            collect_rollout_gate=True,
            rollout_expected_test_count=5,
            rollout_approval_id="test-rollout-approval",
            rollout_approved_by="test-operator",
            evaluated_at=123,
            max_evidence_age_seconds=3600,
            max_identity_lifetime_seconds=3600,
            no_require_root=False,
            no_require_net_admin=False,
            no_require_tun_device=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    reasons = set(payload["reasons"])

    assert exit_code == 1
    assert payload["collected"]["rollout_gate"] is True
    assert payload["rollout_gate"]["decision"]["allowed"] is True
    assert payload["rollout_gate"]["decision"]["decision_hash"]
    assert "rollout_gate_missing" not in reasons
    assert "rollout_gate_failed" not in reasons
    assert "rollout_gate_hash_requirement_missing" not in reasons
    assert payload["os_mutation_performed"] is False


def test_firstparty_production_readiness_collects_identity_signer(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    original_evaluate = wrapper.evaluate_linux_deployment_preflight
    source_root = tmp_path / "firstparty"
    source_root.mkdir()
    (source_root / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(
        wrapper,
        "collect_linux_host_facts",
        lambda: wrapper.LinuxHostFacts(
            os_name="Linux",
            kernel_release="6.8.0",
            effective_uid=0,
            has_net_admin=True,
        ),
    )
    monkeypatch.setattr(
        wrapper,
        "evaluate_linux_deployment_preflight",
        lambda *, facts, config, apply_commands, rollback_commands: original_evaluate(
            facts=facts,
            config=config,
            apply_commands=apply_commands,
            rollback_commands=rollback_commands,
            path_exists=lambda _path: True,
            binary_exists=lambda _binary: True,
        ),
    )
    keypair = wrapper.mldsa_derive_reference_keypair(
        b"identity-signer-readiness-seed".ljust(
            wrapper.ML_DSA_KEYGEN_SEED_BYTES,
            b"k",
        ),
        wrapper.SIGNATURE_ALGORITHM,
    )
    signing_key = wrapper.IdentitySigningKey(
        key_id="test-identity-signer-key",
        signature_algorithm=wrapper.SIGNATURE_ALGORITHM,
        secret=keypair.signing_key,
        not_before=100,
        not_after=4600,
    )
    issuer_path = tmp_path / "issuer.json"
    issuer_path.write_text(
        json.dumps(
            {
                "issuer": "x0tta6bl4-firstparty-test-issuer",
                "policy_epoch": "test-policy",
                "active_key_id": signing_key.key_id,
                "signing_key": wrapper._key_to_json(signing_key),
                "default_lifetime_seconds": 3600,
                "max_lifetime_seconds": 3600,
            }
        ),
        encoding="utf-8",
    )
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22081,
                "policy": {
                    "allowed_tenants": ["team-a"],
                    "max_token_lifetime_seconds": 3600,
                },
                "tunnel": {
                    "client_tun_name": "x0vpn1",
                    "client_address": "10.91.0.2/32",
                    "client_peer": "10.91.0.1",
                    "dns_servers": ["1.1.1.1"],
                    "route_all_traffic": True,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.production_readiness(
        SimpleNamespace(
            target="nl",
            source_root=str(source_root),
            config=str(config_path),
            issuer_config=str(issuer_path),
            role="client",
            uplink_interface=None,
            underlay_gateway="192.0.2.1",
            underlay_interface="eth0",
            enable_kill_switch=True,
            evaluated_at=123,
            max_evidence_age_seconds=3600,
            max_identity_lifetime_seconds=3600,
            no_require_root=False,
            no_require_net_admin=False,
            no_require_tun_device=False,
        )
    )

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)
    reasons = set(payload["reasons"])

    assert exit_code == 1
    assert payload["collected"]["identity_signer"] is True
    assert payload["identity_signer"]["gate"]["allowed"] is True
    assert payload["identity_signer"]["kat"]["passed"] is True
    assert payload["identity_signer"]["conformance"]["passed"] is True
    assert "identity_signer_gate_missing" not in reasons
    assert "identity_signer_manifest_missing" not in reasons
    assert "identity_signer_kat_missing" not in reasons
    assert "identity_signer_conformance_missing" not in reasons
    assert "identity_signer_manifest_hash_requirement_missing" not in reasons
    assert signing_key.secret.hex() not in output_text
    assert payload["os_mutation_performed"] is False


def test_firstparty_install_server_service_requires_os_mutation_flag(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "server.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "bind_host": "0.0.0.0",
                "port": 22081,
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.install_server_service(
        SimpleNamespace(
            config=str(config_path),
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            install_dir="/opt/x0tta-firstparty-vpn-managed-canary",
            config_dir="/etc/x0tta-firstparty-vpn-managed-canary",
            service_python="/usr/bin/python3",
            uplink_interface="eth0",
            allow_os_mutation=False,
            enable=False,
            start=False,
            enable_now=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["ok"] is False
    assert payload["mode"] == "install-server-service"
    assert payload["error"] == "OS mutation is blocked; pass --allow-os-mutation"


def test_firstparty_install_server_service_persists_systemd_service_name(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    service_name = "x0tta-firstparty-vpn-managed-canary.service"
    config_path = tmp_path / "server.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "bind_host": "0.0.0.0",
                "port": 22081,
            }
        ),
        encoding="utf-8",
    )
    original_plan = wrapper._server_service_plan_payload

    def fake_plan(args, *, config_path):
        plan = original_plan(args, config_path=config_path)
        install_dir = tmp_path / "opt" / "vpn"
        config_dir = tmp_path / "etc" / "vpn"
        unit_path = tmp_path / "systemd" / plan["service_name"]
        plan["install_dir"] = str(install_dir)
        plan["config_dir"] = str(config_dir)
        plan["script_path"] = str(install_dir / "x0vpn_test_node.py")
        plan["package_path"] = str(install_dir / "src/network/firstparty_vpn")
        plan["config_path"] = str(config_dir / "server.json")
        plan["unit_path"] = str(unit_path)
        return plan

    commands: list[tuple[str, ...]] = []
    monkeypatch.setattr(wrapper, "_server_service_plan_payload", fake_plan)
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))

    exit_code = wrapper.install_server_service(
        SimpleNamespace(
            config=str(config_path),
            service_name=service_name,
            install_dir="/unused",
            config_dir="/unused",
            service_python="/usr/bin/python3",
            uplink_interface="eth0",
            allow_os_mutation=True,
            enable=False,
            start=False,
            enable_now=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    installed_config = json.loads(
        (tmp_path / "etc/vpn/server.json").read_text(encoding="utf-8")
    )
    source_config = json.loads(config_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["service_name"] == service_name
    assert installed_config["systemd"]["service_name"] == service_name
    assert "systemd" not in source_config
    assert commands == [("systemctl", "daemon-reload")]


def test_firstparty_public_client_config_strips_server_install_metadata():
    wrapper = _load_firstparty_wrapper()
    public_config = wrapper._public_client_config(
        {
            "deployment_epoch": "test-epoch",
            "host": "203.0.113.10",
            "port": 22081,
            "service_name": "x0tta-firstparty-vpn-server.service",
            "systemd": {
                "service_name": "x0tta-firstparty-vpn-server.service",
            },
            "pqc": {
                "mode": "test",
                "encapsulation_key": "public",
                "decapsulation_key": "private",
            },
            "tokens": {
                "client": {"token": "client"},
                "server": {"token": "server"},
            },
            "tunnel": {
                "client_address": "10.90.0.2/32",
                "client_leases": [
                    {
                        "device_id": "client-1",
                        "client_address": "10.90.0.2",
                    }
                ],
            },
        }
    )

    assert "service_name" not in public_config
    assert "systemd" not in public_config
    assert "decapsulation_key" not in public_config["pqc"]
    assert "client_leases" not in public_config["tunnel"]


def test_firstparty_tun_icmp_probe_reassembles_anti_dpi_reply(monkeypatch):
    wrapper = _load_firstparty_wrapper()
    config = {
        "deployment_epoch": "test-epoch",
        "host": "203.0.113.10",
        "port": 22081,
        "tunnel": {
            "anti_dpi": wrapper._default_anti_dpi_profile("camouflage"),
            "client_address": "10.90.0.2/32",
            "client_peer": "10.90.0.1",
            "transport": "camouflage",
        },
    }
    request = wrapper._probe_icmp_echo_request(config)
    reply = wrapper._ipv4_packet(
        source=wrapper.ipaddress.ip_address(request["destination"]),
        destination=wrapper.ipaddress.ip_address(request["source"]),
        protocol=1,
        payload=wrapper._icmp_packet(
            icmp_type=0,
            identifier=request["identifier"],
            sequence=request["sequence"],
            payload=request["payload"],
        ),
        identification=42,
    )
    reply_fragments = wrapper.PacketFragmenter(max_payload_size=64).split(reply)

    class FakeClient:
        def __init__(self):
            self.sent_payloads: list[bytes] = []
            self._reply_fragments = list(reply_fragments)

        def send_data(self, payload: bytes) -> None:
            self.sent_payloads.append(payload)

        def send_data_fragments(self, payloads) -> None:
            self.sent_payloads.extend(payloads)

        async def drain(self) -> None:
            return None

        async def recv(self, *, timeout):
            _ = timeout
            return SimpleNamespace(
                frame_type=wrapper.FrameType.DATA,
                payload=self._reply_fragments.pop(0),
            )

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    fake_client = FakeClient()

    async def fake_open_admitted_probe_client(_config, *, timeout):
        _ = timeout
        return SimpleNamespace(client=fake_client)

    monkeypatch.setattr(
        wrapper,
        "_open_admitted_probe_client",
        fake_open_admitted_probe_client,
    )

    result = wrapper.asyncio.run(
        wrapper._run_tun_icmp_probe(
            config,
            wrapper.DataplaneProbeSpec(
                probe_id="tun-fragmented-reply",
                path_label="nl-anti-dpi-camouflage",
                transport="camouflage",
                remote_ref="private-ref",
                payload_size=96,
                timeout_seconds=1.0,
            ),
        )
    )

    assert result.success is True
    assert result.packets_from_tun == 1
    assert result.packets_to_tun == 1
    assert result.rx_fragments == len(reply_fragments)
    assert result.tx_fragments == len(fake_client.sent_payloads)


def test_firstparty_dataplane_readiness_label_defaults_to_first_endpoint():
    wrapper = _load_firstparty_wrapper()
    config = {
        "host": "203.0.113.10",
        "port": 22082,
        "tunnel": {
            "transport": "camouflage",
            "endpoints": [
                {
                    "endpoint_id": "primary",
                    "host": "203.0.113.10",
                    "path_label": "nl-anti-dpi-camouflage",
                    "port": 22082,
                    "priority": 0,
                    "transport": "camouflage",
                },
                {
                    "endpoint_id": "fallback",
                    "host": "203.0.113.10",
                    "path_label": "nl-anti-dpi-tcp",
                    "port": 22083,
                    "priority": 10,
                    "transport": "tcp",
                },
            ],
        },
    }

    assert (
        wrapper._dataplane_readiness_path_label(
            config,
            SimpleNamespace(dataplane_path_label=None),
        )
        == "nl-anti-dpi-camouflage"
    )
    assert (
        wrapper._dataplane_readiness_path_label(
            config,
            SimpleNamespace(dataplane_path_label="manual-path"),
        )
        == "manual-path"
    )


def test_firstparty_generate_configs_writes_camouflage_anti_dpi_profile(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    out_dir = tmp_path / "generated"

    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(out_dir),
            host="203.0.113.10",
            port=22081,
            transport="camouflage",
            fallback_endpoint=["tcp:203.0.113.10:22080:10:nl-managed-tcp"],
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0

    payload = json.loads(capsys.readouterr().out)
    server_config = json.loads((out_dir / "server.json").read_text(encoding="utf-8"))
    client_config = json.loads((out_dir / "client.json").read_text(encoding="utf-8"))
    public_info = json.loads(
        (out_dir / "public-info.json").read_text(encoding="utf-8")
    )
    anti_dpi = server_config["tunnel"]["anti_dpi"]
    endpoints = server_config["tunnel"]["endpoints"]
    listeners = server_config["tunnel"]["listeners"]

    assert payload["transport"] == "camouflage"
    assert public_info["transport"] == "camouflage"
    assert server_config["tunnel"]["transport"] == "camouflage"
    assert client_config["tunnel"]["transport"] == "camouflage"
    assert [endpoint["transport"] for endpoint in endpoints] == ["camouflage", "tcp"]
    assert endpoints[1]["port"] == 22080
    assert endpoints[1]["path_label"] == "nl-managed-tcp"
    assert listeners == [
        {"port": 22081, "transport": "camouflage"},
        {"port": 22080, "transport": "tcp"},
    ]
    assert server_config["deployment_epoch"].startswith("nl-production-")
    assert server_config["identity"]["issuer"] == "x0tta6bl4-firstparty-issuer"
    assert server_config["identity"]["policy_epoch"] == "nl-production-2026-06-06"
    assert server_config["pqc"]["provider_id"] == "x0tta6bl4-firstparty-mlkem"
    assert server_config["pqc"]["mode"] == "production"
    assert server_config["pqc"]["reviewed"] is True
    assert endpoints[0]["path_label"] == "nl-production-camouflage"
    assert anti_dpi["camouflage"]["enabled"] is True
    assert anti_dpi["geneva"]["selected_fragment_payload_size"] == 512
    assert anti_dpi["tesla"]["enabled"] is True
    assert server_config["tunnel"]["nat_table_name"] == "x0vpns0_nat"
    assert server_config["tunnel"]["filter_table_name"] == "x0vpns0_filter"
    assert server_config["tunnel"]["enable_kill_switch"] is True
    assert client_config["tunnel"]["enable_kill_switch"] is True
    assert len(server_config["tunnel"]["client_leases"]) == 2


def test_firstparty_wrapper_camouflage_transport_helpers_select_camouflage() -> None:
    wrapper = _load_firstparty_wrapper()
    config = {
        "deployment_epoch": "test-epoch",
        "host": "203.0.113.10",
        "bind_host": "0.0.0.0",
        "port": 22081,
        "tunnel": {
            "transport": "camouflage",
            "anti_dpi": wrapper._default_anti_dpi_profile("camouflage"),
            "listeners": [
                {"transport": "camouflage", "port": 22081},
                {"transport": "tcp", "port": 22083},
            ],
            "endpoints": [
                wrapper._endpoint_config(
                    host="203.0.113.10",
                    port=22081,
                    transport="camouflage",
                    priority=0,
                    path_label="nl-anti-dpi-camouflage",
                    endpoint_id="primary",
                ),
                wrapper._endpoint_config(
                    host="203.0.113.10",
                    port=22080,
                    transport="tcp",
                    priority=10,
                    path_label="nl-managed-tcp",
                    endpoint_id="fallback-1",
                ),
            ],
            "server_tun_name": "x0vpns0",
            "client_tun_name": "x0vpn0",
            "client_cidr": "10.90.0.0/24",
            "nat_table_name": "x0vpns0_nat",
            "filter_table_name": "x0vpns0_filter",
            "dns_servers": ["1.1.1.1"],
            "route_all_traffic": True,
        },
    }

    bind = wrapper._dataplane_bind(config)
    candidates = wrapper._dataplane_candidates(config)
    candidate = wrapper._dataplane_candidate(config)
    nat = wrapper._server_nat_config(
        config,
        uplink_interface="eth0",
        allow_os_mutation=False,
    )
    policy = wrapper._client_policy_config(
        config,
        underlay_gateway="192.0.2.1",
        underlay_interface="eth0",
        enable_kill_switch=True,
        allow_os_mutation=False,
    )
    fragmenter = wrapper._anti_dpi_fragmenter(config)

    assert bind.enable_camouflage is True
    assert bind.camouflage_port == 22081
    assert bind.enable_tcp is True
    assert bind.tcp_port == 22083
    assert candidate.transport == "camouflage"
    assert candidate.path_label == "nl-anti-dpi-camouflage"
    assert [item.transport for item in candidates] == ["camouflage", "tcp"]
    assert [item.remote_addr[1] for item in candidates] == [22081, 22080]
    assert [listener.transport for listener in nat.vpn_listeners] == [
        "camouflage",
        "tcp",
    ]
    assert [listener.port for listener in nat.vpn_listeners] == [22081, 22083]
    assert nat.nat_table_name == "x0vpns0_nat"
    assert nat.filter_table_name == "x0vpns0_filter"
    assert [endpoint.transport for endpoint in policy.remote_endpoints] == [
        "camouflage",
        "tcp",
    ]
    assert fragmenter is not None
    assert fragmenter.max_payload_size == 512
    assert wrapper._anti_dpi_reassembler(config) is not None


def test_firstparty_apply_server_config_restarts_and_health_checks(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    installed_dir = tmp_path / "installed"
    backup_dir = tmp_path / "backups"
    installed_dir.mkdir()
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    original_server = json.loads((generated_dir / "server.json").read_text(encoding="utf-8"))
    candidate_server = {**original_server, "deployment_epoch": "candidate-epoch"}
    installed_config = installed_dir / "server.json"
    candidate_config = tmp_path / "candidate-server.json"
    installed_config.write_text(json.dumps(original_server), encoding="utf-8")
    candidate_config.write_text(json.dumps(candidate_server), encoding="utf-8")
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_server_health_payload",
        lambda *_args, **_kwargs: {"ok": True, "mode": "server-health"},
    )

    exit_code = wrapper.apply_server_config(
        SimpleNamespace(
            candidate_config=str(candidate_config),
            installed_config=str(installed_config),
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            backup_dir=str(backup_dir),
            uplink_interface="eth0",
            allow_os_mutation=True,
            dry_run=False,
            skip_health=False,
            no_rollback_on_failure=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    applied_server = json.loads(installed_config.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "apply-server-config"
    assert payload["file_mutation_performed"] is True
    assert payload["service_restart_performed"] is True
    assert payload["rollback_performed"] is False
    assert payload["os_mutation_performed"] is True
    assert payload["health"]["ok"] is True
    assert applied_server["deployment_epoch"] == "candidate-epoch"
    assert commands == [("systemctl", "restart", "x0tta-firstparty-vpn-managed-canary.service")]
    assert Path(payload["backup_path"]).exists()


def test_firstparty_apply_server_config_rolls_back_when_health_fails(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    installed_dir = tmp_path / "installed"
    backup_dir = tmp_path / "backups"
    installed_dir.mkdir()
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    original_server = json.loads((generated_dir / "server.json").read_text(encoding="utf-8"))
    candidate_server = {**original_server, "deployment_epoch": "bad-candidate-epoch"}
    installed_config = installed_dir / "server.json"
    candidate_config = tmp_path / "candidate-server.json"
    installed_config.write_text(json.dumps(original_server), encoding="utf-8")
    candidate_config.write_text(json.dumps(candidate_server), encoding="utf-8")
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_server_health_payload",
        lambda *_args, **_kwargs: {"ok": False, "mode": "server-health"},
    )

    exit_code = wrapper.apply_server_config(
        SimpleNamespace(
            candidate_config=str(candidate_config),
            installed_config=str(installed_config),
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            backup_dir=str(backup_dir),
            uplink_interface="eth0",
            allow_os_mutation=True,
            dry_run=False,
            skip_health=False,
            no_rollback_on_failure=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    restored_server = json.loads(installed_config.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["rollback_performed"] is True
    assert payload["error"] == "server health check failed after config apply"
    assert restored_server["deployment_epoch"] == original_server["deployment_epoch"]
    assert commands == [
        ("systemctl", "restart", "x0tta-firstparty-vpn-managed-canary.service"),
        ("systemctl", "restart", "x0tta-firstparty-vpn-managed-canary.service"),
    ]


def test_firstparty_apply_client_config_restarts_and_health_checks(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    installed_dir = tmp_path / "installed"
    backup_dir = tmp_path / "backups"
    installed_dir.mkdir()
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    installed_config = installed_dir / "client.json"
    candidate_config = generated_dir / "client-2.json"
    installed_config.write_text(
        (generated_dir / "client.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_client_health_payload",
        lambda *_args, **_kwargs: {"ok": True, "mode": "client-health"},
    )

    exit_code = wrapper.apply_client_config(
        SimpleNamespace(
            candidate_config=str(candidate_config),
            installed_config=str(installed_config),
            service_name="x0tta-firstparty-vpn-client.service",
            backup_dir=str(backup_dir),
            timeout=2.0,
            allow_os_mutation=True,
            dry_run=False,
            skip_health=False,
            skip_tcp_connect=False,
            no_rollback_on_failure=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    applied_client = json.loads(installed_config.read_text(encoding="utf-8"))
    candidate_client = json.loads(candidate_config.read_text(encoding="utf-8"))
    public_candidate_client = wrapper._public_client_config(candidate_client)
    applied_client_text = json.dumps(applied_client, sort_keys=True)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "apply-client-config"
    assert payload["file_mutation_performed"] is True
    assert payload["service_restart_performed"] is True
    assert payload["rollback_performed"] is False
    assert payload["os_mutation_performed"] is True
    assert payload["health"]["ok"] is True
    assert Path(payload["backup_path"]).exists()
    assert applied_client == public_candidate_client
    assert "client_leases" not in applied_client_text
    assert "decapsulation_key" not in applied_client_text
    assert commands == [("systemctl", "restart", "x0tta-firstparty-vpn-client.service")]


def test_firstparty_apply_client_config_rolls_back_when_health_fails(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    installed_dir = tmp_path / "installed"
    backup_dir = tmp_path / "backups"
    installed_dir.mkdir()
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    installed_config = installed_dir / "client.json"
    candidate_config = generated_dir / "client-2.json"
    installed_config.write_text(
        (generated_dir / "client.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    original_client = json.loads(installed_config.read_text(encoding="utf-8"))
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_client_health_payload",
        lambda *_args, **_kwargs: {"ok": False, "mode": "client-health"},
    )

    exit_code = wrapper.apply_client_config(
        SimpleNamespace(
            candidate_config=str(candidate_config),
            installed_config=str(installed_config),
            service_name="x0tta-firstparty-vpn-client.service",
            backup_dir=str(backup_dir),
            timeout=2.0,
            allow_os_mutation=True,
            dry_run=False,
            skip_health=False,
            skip_tcp_connect=False,
            no_rollback_on_failure=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    restored_client = json.loads(installed_config.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["mode"] == "apply-client-config"
    assert payload["service_restart_performed"] is True
    assert payload["rollback_performed"] is True
    assert payload["os_mutation_performed"] is True
    assert payload["error"] == "client health check failed after config apply"
    assert restored_client == original_client
    assert commands == [
        ("systemctl", "restart", "x0tta-firstparty-vpn-client.service"),
        ("systemctl", "restart", "x0tta-firstparty-vpn-client.service"),
    ]


def test_firstparty_install_client_service_writes_public_client_config(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    install_dir = tmp_path / "install"
    config_dir = tmp_path / "config"
    unit_path = tmp_path / "x0tta-firstparty-vpn-client.service"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    installed_config = config_dir / "client.json"
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_client_service_plan_payload",
        lambda _args, config_path: {
            "service_name": "x0tta-firstparty-vpn-client.service",
            "unit_path": str(unit_path),
            "install_dir": str(install_dir),
            "config_dir": str(config_dir),
            "script_path": str(install_dir / "x0vpn_test_node.py"),
            "package_path": str(install_dir / "src/network/firstparty_vpn"),
            "config_path": str(installed_config),
            "source_config_path": str(config_path),
            "python": "/usr/bin/python3",
            "unit_content": "[Unit]\nDescription=test\n",
        },
    )

    exit_code = wrapper.install_client_service(
        SimpleNamespace(
            config=str(generated_dir / "client-2.json"),
            service_name="x0tta-firstparty-vpn-client.service",
            install_dir=str(install_dir),
            config_dir=str(config_dir),
            service_python="/usr/bin/python3",
            disable_kill_switch=False,
            allow_os_mutation=True,
            enable=False,
            start=False,
            enable_now=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    installed_client = json.loads(installed_config.read_text(encoding="utf-8"))
    installed_client_text = json.dumps(installed_client, sort_keys=True)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "install-client-service"
    assert payload["config_path"] == str(installed_config)
    assert "client_leases" not in installed_client_text
    assert "decapsulation_key" not in installed_client_text
    assert set(installed_client["tokens"]) == {"client", "server"}
    assert commands == [("systemctl", "daemon-reload")]


def test_firstparty_client_service_plan_can_include_config_sync(tmp_path, capsys):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "client.json"
    config_path.write_text(
        json.dumps(
            {
                "deployment_epoch": "test-epoch",
                "host": "203.0.113.10",
                "port": 22080,
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.client_service_plan(
        SimpleNamespace(
            config=str(config_path),
            service_name="x0tta-firstparty-vpn-client.service",
            install_dir="/opt/x0tta-firstparty-vpn-client",
            config_dir="/etc/x0tta-firstparty-vpn-client",
            service_python="/usr/bin/python3",
            disable_kill_switch=False,
            install_config_sync=True,
            config_sync_service_name=None,
            config_sync_timer_name=None,
            config_sync_timeout=4.0,
            config_sync_interval_seconds=120,
            enable_now=True,
        )
    )

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)
    sync_plan = payload["config_sync_plan"]

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "client-service-plan"
    assert payload["config_sync_installed"] is True
    assert payload["config_path"] == "/etc/x0tta-firstparty-vpn-client/client.json"
    assert sync_plan["timer_name"] == "x0tta-firstparty-vpn-client-config-sync.timer"
    assert sync_plan["sync_service_name"] == "x0tta-firstparty-vpn-client-config-sync.service"
    assert sync_plan["config_path"] == "/etc/x0tta-firstparty-vpn-client/client.json"
    assert sync_plan["interval_seconds"] == 120
    assert sync_plan["timeout_seconds"] == 4.0
    assert payload["post_install_commands"] == [
        "systemctl daemon-reload",
        "systemctl enable --now x0tta-firstparty-vpn-client.service",
        "systemctl enable --now x0tta-firstparty-vpn-client-config-sync.timer",
    ]
    assert "client-config-sync" in sync_plan["sync_service_content"]
    assert "--update-config" in sync_plan["sync_service_content"]
    assert "--restart-service" in sync_plan["sync_service_content"]
    assert "client_leases" not in output_text
    assert "decapsulation_key" not in output_text
    assert "signing_key" not in output_text


def test_firstparty_install_client_service_can_install_config_sync(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    install_dir = tmp_path / "install"
    config_dir = tmp_path / "config"
    unit_path = tmp_path / "x0tta-firstparty-vpn-client.service"
    sync_service_path = tmp_path / "x0tta-firstparty-vpn-client-config-sync.service"
    timer_path = tmp_path / "x0tta-firstparty-vpn-client-config-sync.timer"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    installed_config = config_dir / "client.json"
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_client_service_plan_payload",
        lambda _args, config_path: {
            "service_name": "x0tta-firstparty-vpn-client.service",
            "unit_path": str(unit_path),
            "install_dir": str(install_dir),
            "config_dir": str(config_dir),
            "script_path": str(install_dir / "x0vpn_test_node.py"),
            "package_path": str(install_dir / "src/network/firstparty_vpn"),
            "config_path": str(installed_config),
            "source_config_path": str(config_path),
            "python": "/usr/bin/python3",
            "unit_content": "[Unit]\nDescription=test\n",
            "config_sync_plan": {
                "timer_name": "x0tta-firstparty-vpn-client-config-sync.timer",
                "sync_service_name": "x0tta-firstparty-vpn-client-config-sync.service",
                "timer_path": str(timer_path),
                "sync_service_path": str(sync_service_path),
                "sync_service_content": "[Service]\nExecStart=client-config-sync\n",
                "timer_content": (
                    "[Timer]\n"
                    "Unit=x0tta-firstparty-vpn-client-config-sync.service\n"
                ),
            },
        },
    )

    exit_code = wrapper.install_client_service(
        SimpleNamespace(
            config=str(generated_dir / "client.json"),
            service_name="x0tta-firstparty-vpn-client.service",
            install_dir=str(install_dir),
            config_dir=str(config_dir),
            service_python="/usr/bin/python3",
            disable_kill_switch=False,
            install_config_sync=True,
            config_sync_service_name=None,
            config_sync_timer_name=None,
            config_sync_timeout=3.0,
            config_sync_interval_seconds=300,
            allow_os_mutation=True,
            enable=False,
            start=False,
            enable_now=True,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "install-client-service"
    assert payload["config_sync_installed"] is True
    assert payload["config_sync_enabled"] is True
    assert payload["config_sync_started"] is True
    assert unit_path.read_text(encoding="utf-8") == "[Unit]\nDescription=test\n"
    assert sync_service_path.read_text(encoding="utf-8") == (
        "[Service]\nExecStart=client-config-sync\n"
    )
    assert timer_path.read_text(encoding="utf-8") == (
        "[Timer]\nUnit=x0tta-firstparty-vpn-client-config-sync.service\n"
    )
    assert commands == [
        ("systemctl", "daemon-reload"),
        ("systemctl", "enable", "--now", "x0tta-firstparty-vpn-client.service"),
        (
            "systemctl",
            "enable",
            "--now",
            "x0tta-firstparty-vpn-client-config-sync.timer",
        ),
    ]


def test_firstparty_install_client_service_can_require_readiness(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    install_dir = tmp_path / "install"
    config_dir = tmp_path / "config"
    unit_path = tmp_path / "x0tta-firstparty-vpn-client.service"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    installed_config = config_dir / "client.json"
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_client_service_plan_payload",
        lambda _args, config_path: {
            "service_name": "x0tta-firstparty-vpn-client.service",
            "unit_path": str(unit_path),
            "install_dir": str(install_dir),
            "config_dir": str(config_dir),
            "script_path": str(install_dir / "x0vpn_test_node.py"),
            "package_path": str(install_dir / "src/network/firstparty_vpn"),
            "config_path": str(installed_config),
            "source_config_path": str(config_path),
            "python": "/usr/bin/python3",
            "unit_content": "[Unit]\nDescription=test\n",
            "config_sync_plan": None,
        },
    )

    async def fake_readiness(_args):
        return {
            "ok": True,
            "mode": "client-readiness",
            "checks": [{"name": "public_client_config", "ok": True, "required": True}],
            "os_mutation_performed": False,
        }

    monkeypatch.setattr(wrapper, "_client_readiness_payload", fake_readiness)

    exit_code = wrapper.install_client_service(
        SimpleNamespace(
            config=str(generated_dir / "client.json"),
            service_name="x0tta-firstparty-vpn-client.service",
            install_dir=str(install_dir),
            config_dir=str(config_dir),
            service_python="/usr/bin/python3",
            disable_kill_switch=False,
            install_config_sync=False,
            config_sync_service_name=None,
            config_sync_timer_name=None,
            config_sync_timeout=3.0,
            config_sync_interval_seconds=300,
            require_readiness=True,
            readiness_timeout=3.0,
            min_identity_valid_seconds=60,
            readiness_skip_tcp_connect=True,
            readiness_skip_admission=True,
            readiness_skip_config_sync=True,
            allow_os_mutation=True,
            enable=False,
            start=False,
            enable_now=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["readiness_required"] is True
    assert payload["readiness_ok"] is True
    assert payload["readiness"]["mode"] == "client-readiness"
    assert installed_config.exists()
    assert commands == [("systemctl", "daemon-reload")]


def test_firstparty_install_client_service_can_require_post_install_health(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    install_dir = tmp_path / "install"
    config_dir = tmp_path / "config"
    unit_path = tmp_path / "x0tta-firstparty-vpn-client.service"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    installed_config = config_dir / "client.json"
    commands = []
    health_calls = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_client_service_plan_payload",
        lambda _args, config_path: {
            "service_name": "x0tta-firstparty-vpn-client.service",
            "unit_path": str(unit_path),
            "install_dir": str(install_dir),
            "config_dir": str(config_dir),
            "script_path": str(install_dir / "x0vpn_test_node.py"),
            "package_path": str(install_dir / "src/network/firstparty_vpn"),
            "config_path": str(installed_config),
            "source_config_path": str(config_path),
            "python": "/usr/bin/python3",
            "unit_content": "[Unit]\nDescription=test\n",
            "config_sync_plan": None,
        },
    )

    def fake_wait_client_health(*_args, **kwargs):
        health_calls.append(kwargs)
        return {
            "ok": True,
            "mode": "client-health",
            "attempt": 2,
            "max_attempts": kwargs["attempts"],
        }

    monkeypatch.setattr(wrapper, "_wait_client_health_payload", fake_wait_client_health)

    exit_code = wrapper.install_client_service(
        SimpleNamespace(
            config=str(generated_dir / "client.json"),
            service_name="x0tta-firstparty-vpn-client.service",
            install_dir=str(install_dir),
            config_dir=str(config_dir),
            service_python="/usr/bin/python3",
            disable_kill_switch=False,
            install_config_sync=False,
            config_sync_service_name=None,
            config_sync_timer_name=None,
            config_sync_timeout=3.0,
            config_sync_interval_seconds=300,
            allow_os_mutation=True,
            enable=False,
            start=True,
            enable_now=False,
            require_post_install_health=True,
            post_install_health_timeout=4.0,
            post_install_health_retries=7,
            post_install_health_interval_seconds=0.0,
            post_install_health_skip_tcp_connect=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["post_install_health_required"] is True
    assert payload["post_install_health_ok"] is True
    assert payload["post_install_health"]["mode"] == "client-health"
    assert health_calls == [
        {
            "service_name": "x0tta-firstparty-vpn-client.service",
            "timeout": 4.0,
            "skip_service": False,
            "skip_tcp_connect": False,
            "attempts": 7,
            "interval_seconds": 0.0,
        }
    ]
    assert commands == [
        ("systemctl", "daemon-reload"),
        ("systemctl", "start", "x0tta-firstparty-vpn-client.service"),
    ]


def test_firstparty_install_client_service_fails_when_post_install_health_fails(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    install_dir = tmp_path / "install"
    config_dir = tmp_path / "config"
    unit_path = tmp_path / "x0tta-firstparty-vpn-client.service"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    installed_config = config_dir / "client.json"
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_client_service_plan_payload",
        lambda _args, config_path: {
            "service_name": "x0tta-firstparty-vpn-client.service",
            "unit_path": str(unit_path),
            "install_dir": str(install_dir),
            "config_dir": str(config_dir),
            "script_path": str(install_dir / "x0vpn_test_node.py"),
            "package_path": str(install_dir / "src/network/firstparty_vpn"),
            "config_path": str(installed_config),
            "source_config_path": str(config_path),
            "python": "/usr/bin/python3",
            "unit_content": "[Unit]\nDescription=test\n",
            "config_sync_plan": None,
        },
    )
    monkeypatch.setattr(
        wrapper,
        "_wait_client_health_payload",
        lambda *_args, **_kwargs: {
            "ok": False,
            "mode": "client-health",
            "attempt": 3,
            "max_attempts": 3,
        },
    )

    exit_code = wrapper.install_client_service(
        SimpleNamespace(
            config=str(generated_dir / "client.json"),
            service_name="x0tta-firstparty-vpn-client.service",
            install_dir=str(install_dir),
            config_dir=str(config_dir),
            service_python="/usr/bin/python3",
            disable_kill_switch=False,
            install_config_sync=False,
            config_sync_service_name=None,
            config_sync_timer_name=None,
            config_sync_timeout=3.0,
            config_sync_interval_seconds=300,
            allow_os_mutation=True,
            enable=False,
            start=True,
            enable_now=False,
            require_post_install_health=True,
            post_install_health_timeout=4.0,
            post_install_health_retries=3,
            post_install_health_interval_seconds=0.0,
            post_install_health_skip_tcp_connect=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["mode"] == "install-client-service"
    assert payload["error"] == "client post-install health failed"
    assert payload["post_install_health_required"] is True
    assert payload["post_install_health"]["ok"] is False
    assert payload["started"] is True
    assert payload["os_mutation_performed"] is True
    assert commands == [
        ("systemctl", "daemon-reload"),
        ("systemctl", "start", "x0tta-firstparty-vpn-client.service"),
    ]


def test_firstparty_install_client_service_stops_before_mutation_when_readiness_fails(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    config_path = tmp_path / "client.json"
    install_dir = tmp_path / "install"
    config_dir = tmp_path / "config"
    config_path.write_text("{}", encoding="utf-8")
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))

    async def fake_readiness(_args):
        return {
            "ok": False,
            "mode": "client-readiness",
            "checks": [
                {
                    "name": "identity_validity_window",
                    "ok": False,
                    "required": True,
                    "details": {"server_seconds_until_expiry": 0},
                }
            ],
            "os_mutation_performed": False,
        }

    monkeypatch.setattr(wrapper, "_client_readiness_payload", fake_readiness)

    exit_code = wrapper.install_client_service(
        SimpleNamespace(
            config=str(config_path),
            service_name="x0tta-firstparty-vpn-client.service",
            install_dir=str(install_dir),
            config_dir=str(config_dir),
            service_python="/usr/bin/python3",
            disable_kill_switch=False,
            install_config_sync=False,
            config_sync_service_name=None,
            config_sync_timer_name=None,
            config_sync_timeout=3.0,
            config_sync_interval_seconds=300,
            require_readiness=True,
            readiness_timeout=3.0,
            min_identity_valid_seconds=900,
            readiness_skip_tcp_connect=False,
            readiness_skip_admission=False,
            readiness_skip_config_sync=False,
            allow_os_mutation=True,
            enable=False,
            start=False,
            enable_now=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["mode"] == "install-client-service"
    assert payload["error"] == "client readiness failed"
    assert payload["readiness"]["ok"] is False
    assert payload["os_mutation_performed"] is False
    assert not install_dir.exists()
    assert not config_dir.exists()
    assert commands == []


def test_firstparty_uninstall_client_service_removes_config_sync_units(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    systemd_dir = tmp_path / "systemd"
    systemd_dir.mkdir()
    client_unit = systemd_dir / "x0tta-firstparty-vpn-client.service"
    sync_service_unit = systemd_dir / "x0tta-firstparty-vpn-client-config-sync.service"
    sync_timer_unit = systemd_dir / "x0tta-firstparty-vpn-client-config-sync.timer"
    client_unit.write_text("[Service]\nExecStart=client\n", encoding="utf-8")
    sync_service_unit.write_text("[Service]\nExecStart=sync\n", encoding="utf-8")
    sync_timer_unit.write_text("[Timer]\nUnit=sync\n", encoding="utf-8")
    real_path = wrapper.Path

    def fake_path(value):
        if value == "/etc/systemd/system":
            return systemd_dir
        return real_path(value)

    commands = []
    monkeypatch.setattr(wrapper, "Path", fake_path)
    monkeypatch.setattr(
        wrapper,
        "_run_unchecked",
        lambda command: commands.append(("unchecked", command)),
    )
    monkeypatch.setattr(
        wrapper,
        "_run_checked",
        lambda command: commands.append(("checked", command)),
    )

    exit_code = wrapper.uninstall_client_service(
        SimpleNamespace(
            service_name="x0tta-firstparty-vpn-client.service",
            install_dir=str(tmp_path / "install"),
            config_dir=str(tmp_path / "config"),
            allow_os_mutation=True,
            keep_config_sync=False,
            config_sync_service_name=None,
            config_sync_timer_name=None,
            remove_install_dir=False,
            remove_config_dir=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "uninstall-client-service"
    assert payload["config_sync_kept"] is False
    assert payload["config_sync_removed"] is True
    assert payload["config_sync_timer_unit_removed"] is True
    assert payload["config_sync_service_unit_removed"] is True
    assert payload["config_sync_timer_name"] == "x0tta-firstparty-vpn-client-config-sync.timer"
    assert payload["config_sync_service_name"] == (
        "x0tta-firstparty-vpn-client-config-sync.service"
    )
    assert not client_unit.exists()
    assert not sync_service_unit.exists()
    assert not sync_timer_unit.exists()
    assert commands == [
        (
            "unchecked",
            (
                "systemctl",
                "disable",
                "--now",
                "x0tta-firstparty-vpn-client-config-sync.timer",
            ),
        ),
        (
            "unchecked",
            ("systemctl", "stop", "x0tta-firstparty-vpn-client-config-sync.service"),
        ),
        (
            "unchecked",
            ("systemctl", "disable", "--now", "x0tta-firstparty-vpn-client.service"),
        ),
        ("checked", ("systemctl", "daemon-reload")),
    ]


def test_firstparty_provision_client_dry_run_does_not_write_files(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    out_dir = tmp_path / "provisioned"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    exit_code = wrapper.provision_client(
        SimpleNamespace(
            server_config=str(generated_dir / "server.json"),
            issuer_config=str(generated_dir / "issuer.json"),
            out_dir=str(out_dir),
            device_id="test-client-2",
            client_address=None,
            tenant=None,
            lifetime_seconds=None,
            kit_name=None,
            archive=None,
            apply_server_config=True,
            installed_server_config=None,
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            backup_dir=None,
            uplink_interface="eth0",
            allow_os_mutation=False,
            dry_run=True,
            skip_health=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "provision-client"
    assert payload["dry_run"] is True
    assert payload["apply_server_config"] is True
    assert payload["file_mutation_performed"] is False
    assert payload["issuer_mutation_performed"] is False
    assert payload["os_mutation_performed"] is False
    assert payload["client_address"] == "10.90.0.3/32"
    assert not out_dir.exists()


def test_firstparty_provision_client_exports_kit_and_applies_server_config(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    installed_dir = tmp_path / "installed"
    out_dir = tmp_path / "provisioned"
    backup_dir = tmp_path / "backups"
    installed_dir.mkdir()
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    installed_config = installed_dir / "server.json"
    installed_config.write_text(
        (generated_dir / "server.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    issuer_config = generated_dir / "issuer.json"
    original_issuer = json.loads(issuer_config.read_text(encoding="utf-8"))
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_server_health_payload",
        lambda *_args, **_kwargs: {"ok": True, "mode": "server-health"},
    )

    exit_code = wrapper.provision_client(
        SimpleNamespace(
            server_config=str(installed_config),
            issuer_config=str(issuer_config),
            out_dir=str(out_dir),
            device_id="test-client-2",
            client_address=None,
            tenant=None,
            lifetime_seconds=None,
            kit_name="test-client-2",
            archive=None,
            apply_server_config=True,
            installed_server_config=str(installed_config),
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            backup_dir=str(backup_dir),
            uplink_interface="eth0",
            allow_os_mutation=True,
            dry_run=False,
            skip_health=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    updated_issuer = json.loads(issuer_config.read_text(encoding="utf-8"))
    applied_server = json.loads(installed_config.read_text(encoding="utf-8"))
    client_config = json.loads((out_dir / "client.json").read_text(encoding="utf-8"))
    with tarfile.open(out_dir / "test-client-2.tar.gz", "r:gz") as archive:
        names = {Path(member.name).name for member in archive.getmembers()}
        archive_text = "\n".join(member.name for member in archive.getmembers())

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "provision-client"
    assert payload["file_mutation_performed"] is True
    assert payload["issuer_mutation_performed"] is True
    assert payload["os_mutation_performed"] is True
    assert payload["apply_server_config_result"]["ok"] is True
    assert payload["export_client_kit"]["server_secrets_included"] is False
    assert updated_issuer["serial_counter"] > original_issuer["serial_counter"]
    assert len(applied_server["tunnel"]["client_leases"]) == 2
    assert client_config["tokens"]["client"]["claims"]["device_id"] == "test-client-2"
    assert "server.json" not in names
    assert "issuer.json" not in names
    assert "__pycache__" not in archive_text
    assert ".pyc" not in archive_text
    assert commands == [("systemctl", "restart", "x0tta-firstparty-vpn-managed-canary.service")]


def test_firstparty_deprovision_client_dry_run_does_not_write_files(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    out_dir = tmp_path / "deprovisioned"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    server_config = generated_dir / "server.json"
    original_server = json.loads(server_config.read_text(encoding="utf-8"))
    removed_serial = original_server["tokens"]["clients"][1]["token"]["serial"]
    exit_code = wrapper.deprovision_client(
        SimpleNamespace(
            server_config=str(server_config),
            out_dir=str(out_dir),
            device_id="test-client-2",
            identity_hash=None,
            apply_server_config=True,
            installed_server_config=None,
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            backup_dir=None,
            uplink_interface="eth0",
            allow_os_mutation=False,
            dry_run=True,
            skip_health=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    still_original_server = json.loads(server_config.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "deprovision-client"
    assert payload["dry_run"] is True
    assert payload["removed"] is True
    assert payload["revoked_identity_serials"] == [removed_serial]
    assert payload["client_lease_count"] == 1
    assert payload["server_restart_required"] is True
    assert payload["apply_server_config"] is True
    assert payload["file_mutation_performed"] is False
    assert payload["os_mutation_performed"] is False
    assert still_original_server == original_server
    assert not out_dir.exists()


def test_firstparty_deprovision_client_writes_candidate_and_applies_server_config(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    installed_dir = tmp_path / "installed"
    out_dir = tmp_path / "deprovisioned"
    backup_dir = tmp_path / "backups"
    installed_dir.mkdir()
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    installed_config = installed_dir / "server.json"
    installed_config.write_text(
        (generated_dir / "server.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    original_server = json.loads(installed_config.read_text(encoding="utf-8"))
    removed_serial = original_server["tokens"]["clients"][1]["token"]["serial"]
    commands = []
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_server_health_payload",
        lambda *_args, **_kwargs: {"ok": True, "mode": "server-health"},
    )

    exit_code = wrapper.deprovision_client(
        SimpleNamespace(
            server_config=str(installed_config),
            out_dir=str(out_dir),
            device_id="test-client-2",
            identity_hash=None,
            apply_server_config=True,
            installed_server_config=str(installed_config),
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            backup_dir=str(backup_dir),
            uplink_interface="eth0",
            allow_os_mutation=True,
            dry_run=False,
            skip_health=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    candidate_server = json.loads((out_dir / "server.candidate.json").read_text(encoding="utf-8"))
    applied_server = json.loads(installed_config.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "deprovision-client"
    assert payload["removed"] is True
    assert payload["revoked_identity_serials"] == [removed_serial]
    assert payload["client_lease_count"] == 1
    assert payload["file_mutation_performed"] is True
    assert payload["os_mutation_performed"] is True
    assert payload["apply_server_config_result"]["ok"] is True
    assert len(candidate_server["tunnel"]["client_leases"]) == 1
    assert len(candidate_server["tokens"]["clients"]) == 1
    assert candidate_server["revocations"]["identity_serials"] == [removed_serial]
    assert applied_server == candidate_server
    assert commands == [("systemctl", "restart", "x0tta-firstparty-vpn-managed-canary.service")]


def test_firstparty_add_client_updates_server_and_does_not_leak_server_pqc_key(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    out_dir = tmp_path / "vpn"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(out_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    server_config = out_dir / "server.json"
    issuer_config = out_dir / "issuer.json"
    second_server_config = out_dir / "server-with-client-2.json"
    second_client_config = out_dir / "client-2.json"
    assert issuer_config.exists()
    assert wrapper.add_client(
        SimpleNamespace(
            server_config=str(server_config),
            issuer_config=str(issuer_config),
            out_client=str(second_client_config),
            server_config_out=str(second_server_config),
            update_server_config=False,
            device_id="test-client-2",
            client_address=None,
            tenant=None,
            lifetime_seconds=None,
            dry_run=False,
        )
    ) == 0

    output = json.loads(capsys.readouterr().out)
    updated_server = json.loads(second_server_config.read_text(encoding="utf-8"))
    issued_client = json.loads(second_client_config.read_text(encoding="utf-8"))
    updated_issuer = json.loads(issuer_config.read_text(encoding="utf-8"))

    assert output["ok"] is True
    assert output["mode"] == "add-client"
    assert output["file_mutation_performed"] is True
    assert output["os_mutation_performed"] is False
    assert output["client_address"] == "10.90.0.3/32"
    assert "decapsulation_key" in updated_server["pqc"]
    assert "decapsulation_key" not in issued_client["pqc"]
    assert issued_client["tokens"]["client"]["claims"]["device_id"] == "test-client-2"
    assert issued_client["tunnel"]["client_address"] == "10.90.0.3/32"
    assert len(updated_server["tunnel"]["client_leases"]) == 2
    assert updated_server["tunnel"]["client_leases"][1]["device_id"] == "test-client-2"
    assert updated_issuer["serial_counter"] >= 3


def test_firstparty_identity_auto_renew_skips_fresh_tokens(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    out_dir = tmp_path / "vpn"
    renew_dir = tmp_path / "renewed"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(out_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    exit_code = wrapper.identity_auto_renew(
        SimpleNamespace(
            server_config=str(out_dir / "server.json"),
            issuer_config=str(out_dir / "issuer.json"),
            out_dir=str(renew_dir),
            lifetime_seconds=3600,
            renew_before_seconds=60,
            server_config_out=None,
            update_server_config=False,
            update_issuer_config=True,
            apply_server_config=False,
            installed_server_config=None,
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            backup_dir=None,
            uplink_interface=None,
            allow_os_mutation=False,
            dry_run=False,
            skip_health=False,
            health_retries=10,
            health_retry_interval_seconds=0.5,
            no_rollback_on_failure=False,
            force=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "identity-auto-renew"
    assert payload["renewal_needed"] is False
    assert payload["renewal_reason"] == "identity_valid"
    assert payload["renewal_performed"] is False
    assert payload["file_mutation_performed"] is False
    assert payload["issuer_mutation_performed"] is False
    assert payload["server_restart_required"] is False
    assert payload["client_count"] == 2
    assert not renew_dir.exists()


def test_firstparty_identity_auto_renew_rotates_clients_and_applies_server_config(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    out_dir = tmp_path / "vpn"
    renew_dir = tmp_path / "renewed"
    backup_dir = tmp_path / "backups"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(out_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    server_config = out_dir / "server.json"
    issuer_config = out_dir / "issuer.json"
    original_server = json.loads(server_config.read_text(encoding="utf-8"))
    issuer_payload = json.loads(issuer_config.read_text(encoding="utf-8"))
    stale_verification_key = dict(original_server["identity"]["verification_key"])
    stale_verification_key["secret"] = "00" * (
        len(stale_verification_key["secret"]) // 2
    )
    original_server["identity"]["verification_key"] = stale_verification_key
    server_config.write_text(
        json.dumps(original_server, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    original_client = json.loads((out_dir / "client.json").read_text(encoding="utf-8"))
    original_server_serial = original_server["tokens"]["server"]["serial"]
    original_client_identity_hash = wrapper.identity_binding_hash(
        wrapper._token_from_json(original_client["tokens"]["client"]).claims
    ).hex()
    fake_now = original_server["tokens"]["server"]["claims"]["issued_at"] + 1800
    issuer_payload["signing_key"]["not_after"] = fake_now - 1
    issuer_payload["verification_key"]["not_after"] = fake_now - 1
    issuer_config.write_text(
        json.dumps(issuer_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    commands = []
    monkeypatch.setattr(wrapper, "_now", lambda: fake_now)
    monkeypatch.setattr(wrapper, "_run_checked", lambda command: commands.append(command))
    monkeypatch.setattr(
        wrapper,
        "_server_health_payload",
        lambda *_args, **_kwargs: {"ok": True, "mode": "server-health"},
    )

    exit_code = wrapper.identity_auto_renew(
        SimpleNamespace(
            server_config=str(server_config),
            issuer_config=str(issuer_config),
            out_dir=str(renew_dir),
            lifetime_seconds=3600,
            renew_before_seconds=2000,
            server_config_out=None,
            update_server_config=False,
            update_issuer_config=True,
            apply_server_config=True,
            installed_server_config=str(server_config),
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            backup_dir=str(backup_dir),
            uplink_interface="eth0",
            allow_os_mutation=True,
            dry_run=False,
            skip_health=False,
            health_retries=10,
            health_retry_interval_seconds=0.0,
            no_rollback_on_failure=False,
            force=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    applied_server = json.loads(server_config.read_text(encoding="utf-8"))
    updated_issuer = json.loads(issuer_config.read_text(encoding="utf-8"))
    renewed_client = json.loads((renew_dir / "client.json").read_text(encoding="utf-8"))
    second_client = json.loads((renew_dir / "client-2.json").read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["renewal_needed"] is True
    assert payload["renewal_reason"] == "identity_near_expiry"
    assert payload["renewal_performed"] is True
    assert payload["file_mutation_performed"] is True
    assert payload["issuer_mutation_performed"] is True
    assert payload["os_mutation_performed"] is True
    assert payload["apply_server_config_result"]["ok"] is True
    assert applied_server["identity"]["verification_key"] == updated_issuer["verification_key"]
    assert renewed_client["identity"]["verification_key"] == updated_issuer["verification_key"]
    assert second_client["identity"]["verification_key"] == updated_issuer["verification_key"]
    assert updated_issuer["signing_key"]["not_after"] >= fake_now + 3600
    assert updated_issuer["verification_key"]["not_after"] >= fake_now + 3600
    assert applied_server["tokens"]["server"]["serial"] != original_server_serial
    assert applied_server["tokens"]["server_previous"][0]["token"]["serial"] == original_server_serial
    assert applied_server["tokens"]["server"]["claims"]["expires_at"] == fake_now + 3600
    assert updated_issuer["serial_counter"] == payload["issuer_serial_counter"]
    assert renewed_client["tokens"]["server"]["serial"] == applied_server["tokens"]["server"]["serial"]
    assert second_client["tokens"]["server"]["serial"] == applied_server["tokens"]["server"]["serial"]
    assert renewed_client["tokens"]["client"]["claims"]["device_id"] == "test-client-1"
    assert second_client["tokens"]["client"]["claims"]["device_id"] == "test-client-2"
    assert "decapsulation_key" not in renewed_client["pqc"]
    assert "client_leases" not in json.dumps(renewed_client, sort_keys=True)
    verifier = wrapper._verifier(renewed_client)
    policy = wrapper._policy(renewed_client)
    client_decision = verifier.verify(
        wrapper._token_from_json(renewed_client["tokens"]["client"]),
        policy=policy,
        now=fake_now,
    )
    server_decision = verifier.verify(
        wrapper._token_from_json(renewed_client["tokens"]["server"]),
        policy=policy,
        now=fake_now,
    )
    assert client_decision.allowed
    assert server_decision.allowed
    assert len(applied_server["tunnel"]["client_leases"]) == 2
    assert applied_server["tunnel"]["client_leases"][0]["previous_identity_hashes"][0][
        "identity_hash"
    ] == original_client_identity_hash
    registry = wrapper._admission_registry(applied_server)
    old_hello, _old_material = wrapper._client_hello_and_material(original_client)
    old_result = registry.admit(old_hello)
    assert old_result.accept.server_identity.serial == original_server_serial
    assert commands == [("systemctl", "restart", "x0tta-firstparty-vpn-managed-canary.service")]


def test_firstparty_identity_rotation_keeps_multi_generation_grace(
    monkeypatch,
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    out_dir = tmp_path / "vpn"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(out_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=7200,
        )
    ) == 0
    capsys.readouterr()
    server_config = json.loads((out_dir / "server.json").read_text(encoding="utf-8"))
    issuer_config = json.loads((out_dir / "issuer.json").read_text(encoding="utf-8"))
    original_client = json.loads((out_dir / "client.json").read_text(encoding="utf-8"))
    original_server_serial = server_config["tokens"]["server"]["serial"]
    first_now = server_config["tokens"]["server"]["claims"]["issued_at"] + 1000
    second_now = first_now + 1000

    monkeypatch.setattr(wrapper, "_now", lambda: first_now)
    first_artifacts = wrapper._rotate_identity_artifacts(
        server_config=server_config,
        issuer_config=issuer_config,
        lifetime_seconds=7200,
    )
    first_server = first_artifacts["updated_server_config"]
    first_issuer = first_artifacts["updated_issuer_config"]
    first_client = first_artifacts["client_configs"][0]
    first_server_serial = first_server["tokens"]["server"]["serial"]

    monkeypatch.setattr(wrapper, "_now", lambda: second_now)
    second_artifacts = wrapper._rotate_identity_artifacts(
        server_config=first_server,
        issuer_config=first_issuer,
        lifetime_seconds=7200,
    )
    second_server = second_artifacts["updated_server_config"]
    second_server_serial = second_server["tokens"]["server"]["serial"]

    previous_serials = [
        item["token"]["serial"] for item in second_server["tokens"]["server_previous"]
    ]
    assert second_server_serial != first_server_serial
    assert previous_serials[:2] == [first_server_serial, original_server_serial]

    registry = wrapper._admission_registry(second_server)
    original_hello, _original_material = wrapper._client_hello_and_material(
        original_client
    )
    original_result = registry.admit(original_hello)
    first_hello, _first_material = wrapper._client_hello_and_material(first_client)
    first_result = registry.admit(first_hello)

    assert original_result.accept.server_identity.serial == original_server_serial
    assert first_result.accept.server_identity.serial == first_server_serial


def test_firstparty_server_renewal_plan_uses_auto_renew_without_secret_material(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()

    exit_code = wrapper.server_renewal_plan(
        SimpleNamespace(
            server_config="/etc/x0tta-firstparty-vpn-managed-canary/server.json",
            issuer_config="/etc/x0tta-firstparty-vpn-managed-canary/issuer.json",
            out_dir="/etc/x0tta-firstparty-vpn-managed-canary/renewed-clients",
            service_name="x0tta-firstparty-vpn-managed-canary.service",
            renewal_service_name=None,
            timer_name=None,
            install_dir="/opt/x0tta-firstparty-vpn-managed-canary",
            service_python="/usr/bin/python3",
            lifetime_seconds=3600,
            renew_before_seconds=900,
            interval_seconds=300,
            backup_dir="/etc/x0tta-firstparty-vpn-managed-canary/backups",
            uplink_interface="eth0",
            skip_health=False,
            enable_now=True,
        )
    )

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)
    service_unit = payload["renewal_service_content"]
    timer_unit = payload["timer_content"]

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "server-renewal-plan"
    assert payload["os_mutation_performed"] is False
    assert payload["timer_name"] == "x0tta-firstparty-vpn-managed-canary-identity-renewal.timer"
    assert payload["renewal_service_name"] == "x0tta-firstparty-vpn-managed-canary-identity-renewal.service"
    assert payload["post_install_commands"] == [
        "systemctl daemon-reload",
        "systemctl enable --now x0tta-firstparty-vpn-managed-canary-identity-renewal.timer",
    ]
    assert "identity-auto-renew" in service_unit
    assert "--apply-server-config" in service_unit
    assert "--update-issuer-config" in service_unit
    assert "--allow-os-mutation" in service_unit
    assert "--uplink-interface eth0" in service_unit
    assert "OnUnitActiveSec=300s" in timer_unit
    assert "Unit=x0tta-firstparty-vpn-managed-canary-identity-renewal.service" in timer_unit
    assert "signing_key" not in output_text
    assert "decapsulation_key" not in output_text


def test_firstparty_client_config_sync_fetches_rotated_config_over_protected_ping(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    out_dir = tmp_path / "vpn"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(out_dir),
            host="127.0.0.1",
            port=22080,
            bind_host="127.0.0.1",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    old_client = json.loads((out_dir / "client.json").read_text(encoding="utf-8"))
    server_config = json.loads((out_dir / "server.json").read_text(encoding="utf-8"))
    issuer_config = json.loads((out_dir / "issuer.json").read_text(encoding="utf-8"))
    artifacts = wrapper._rotate_identity_artifacts(
        server_config=server_config,
        issuer_config=issuer_config,
        lifetime_seconds=3600,
    )
    updated_server = artifacts["updated_server_config"]
    old_server_serial = old_client["tokens"]["server"]["serial"]
    new_server_serial = updated_server["tokens"]["server"]["serial"]

    async def scenario():
        server, _protocol, addr = await wrapper.open_tcp_admission_server(
            registry=wrapper._admission_registry(updated_server),
            host="127.0.0.1",
            port=0,
            on_session_ping=wrapper._client_config_update_ping_handler(updated_server),
        )
        old_client["host"] = addr[0]
        old_client["port"] = addr[1]
        for endpoint in old_client.get("tunnel", {}).get("endpoints", []):
            endpoint["host"] = addr[0]
            endpoint["port"] = addr[1]
        old_client_path = tmp_path / "old-client.json"
        synced_client_path = tmp_path / "synced-client.json"
        old_client_path.write_text(json.dumps(old_client), encoding="utf-8")
        try:
            exit_code = await wrapper.client_config_sync(
                SimpleNamespace(
                    config=str(old_client_path),
                    out_config=str(synced_client_path),
                    update_config=False,
                    timeout=10.0,
                    dry_run=False,
                    restart_service=False,
                    service_name="x0tta-firstparty-vpn-client.service",
                    allow_os_mutation=False,
                )
            )
        finally:
            server.close()
            await server.wait_closed()
        return exit_code, synced_client_path

    exit_code, synced_client_path = wrapper.asyncio.run(scenario())
    payload = json.loads(capsys.readouterr().out)
    synced_client = json.loads(synced_client_path.read_text(encoding="utf-8"))
    encoded_synced = json.dumps(synced_client, sort_keys=True)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "client-config-sync"
    assert payload["changed"] is True
    assert payload["file_mutation_performed"] is True
    assert synced_client["tokens"]["server"]["serial"] == new_server_serial
    assert synced_client["tokens"]["server"]["serial"] != old_server_serial
    assert synced_client["tokens"]["client"]["claims"]["device_id"] == "test-client-1"
    assert "decapsulation_key" not in encoded_synced
    assert "client_leases" not in encoded_synced
    assert "signing_key" not in encoded_synced


def test_firstparty_client_sync_plan_restarts_client_only_after_config_change(
    capsys,
):
    wrapper = _load_firstparty_wrapper()

    exit_code = wrapper.client_sync_plan(
        SimpleNamespace(
            config="/etc/x0tta-firstparty-vpn-client/client.json",
            service_name="x0tta-firstparty-vpn-client.service",
            sync_service_name=None,
            timer_name=None,
            install_dir="/opt/x0tta-firstparty-vpn-client",
            service_python="/usr/bin/python3",
            timeout=3.0,
            interval_seconds=300,
            enable_now=True,
        )
    )

    output_text = capsys.readouterr().out
    payload = json.loads(output_text)
    service_unit = payload["sync_service_content"]
    timer_unit = payload["timer_content"]

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "client-sync-plan"
    assert payload["os_mutation_performed"] is False
    assert payload["timer_name"] == "x0tta-firstparty-vpn-client-config-sync.timer"
    assert payload["sync_service_name"] == "x0tta-firstparty-vpn-client-config-sync.service"
    assert payload["post_install_commands"] == [
        "systemctl daemon-reload",
        "systemctl enable --now x0tta-firstparty-vpn-client-config-sync.timer",
    ]
    assert "client-config-sync" in service_unit
    assert "--update-config" in service_unit
    assert "--restart-service" in service_unit
    assert "--allow-os-mutation" in service_unit
    assert "--service-name x0tta-firstparty-vpn-client.service" in service_unit
    assert "OnUnitActiveSec=300s" in timer_unit
    assert "Unit=x0tta-firstparty-vpn-client-config-sync.service" in timer_unit
    assert "signing_key" not in output_text
    assert "decapsulation_key" not in output_text


def test_firstparty_client_readiness_validates_public_kit_without_mutating_os(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    out_dir = tmp_path / "vpn"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(out_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    exit_code = wrapper.asyncio.run(
        wrapper.client_readiness(
            SimpleNamespace(
                config=str(out_dir / "client.json"),
                service_name="x0tta-firstparty-vpn-client.service",
                install_dir="/opt/x0tta-firstparty-vpn-client",
                config_dir="/etc/x0tta-firstparty-vpn-client",
                service_python="/usr/bin/python3",
                timeout=3.0,
                min_identity_valid_seconds=60,
                skip_tcp_connect=True,
                skip_admission=True,
                skip_config_sync=True,
                skip_managed_install_plan=False,
            )
        )
    )

    payload = json.loads(capsys.readouterr().out)
    checks = {check["name"]: check for check in payload["checks"]}

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "client-readiness"
    assert payload["os_mutation_performed"] is False
    assert checks["public_client_config"]["ok"] is True
    assert checks["identity_policy_valid"]["ok"] is True
    assert checks["identity_validity_window"]["ok"] is True
    assert checks["server_tcp_port_open"]["required"] is False
    assert checks["admission_handshake"]["required"] is False
    assert checks["protected_config_sync"]["required"] is False
    assert checks["managed_install_plan"]["ok"] is True
    assert checks["managed_install_plan"]["details"]["config_sync_timer_name"] == (
        "x0tta-firstparty-vpn-client-config-sync.timer"
    )
    assert "decapsulation_key" not in json.dumps(payload, sort_keys=True)
    assert "signing_key" not in json.dumps(payload, sort_keys=True)


def test_firstparty_client_readiness_fails_closed_for_server_secret_marker(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    out_dir = tmp_path / "vpn"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(out_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    client_path = out_dir / "client.json"
    client = json.loads(client_path.read_text(encoding="utf-8"))
    client["pqc"]["decapsulation_key"] = "00"
    client_path.write_text(json.dumps(client), encoding="utf-8")

    exit_code = wrapper.asyncio.run(
        wrapper.client_readiness(
            SimpleNamespace(
                config=str(client_path),
                service_name="x0tta-firstparty-vpn-client.service",
                install_dir="/opt/x0tta-firstparty-vpn-client",
                config_dir="/etc/x0tta-firstparty-vpn-client",
                service_python="/usr/bin/python3",
                timeout=3.0,
                min_identity_valid_seconds=60,
                skip_tcp_connect=True,
                skip_admission=True,
                skip_config_sync=True,
                skip_managed_install_plan=True,
            )
        )
    )

    payload = json.loads(capsys.readouterr().out)
    checks = {check["name"]: check for check in payload["checks"]}

    assert exit_code == 1
    assert payload["ok"] is False
    assert checks["public_client_config"]["ok"] is False
    assert checks["public_client_config"]["details"]["forbidden_markers"] == [
        "decapsulation_key"
    ]


def test_firstparty_remove_client_updates_server_without_mutating_os(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    out_dir = tmp_path / "vpn"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(out_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    server_config = out_dir / "server.json"
    updated_server_config = out_dir / "server-without-client-2.json"
    assert wrapper.remove_client(
        SimpleNamespace(
            server_config=str(server_config),
            server_config_out=str(updated_server_config),
            update_server_config=False,
            device_id="test-client-2",
            identity_hash=None,
            dry_run=False,
        )
    ) == 0

    output = json.loads(capsys.readouterr().out)
    original_server = json.loads(server_config.read_text(encoding="utf-8"))
    updated_server = json.loads(updated_server_config.read_text(encoding="utf-8"))
    removed_serial = original_server["tokens"]["clients"][1]["token"]["serial"]

    assert output["ok"] is True
    assert output["mode"] == "remove-client"
    assert output["removed"] is True
    assert output["revoked_identity_serials"] == [removed_serial]
    assert output["server_restart_required"] is True
    assert output["file_mutation_performed"] is True
    assert output["os_mutation_performed"] is False
    assert len(original_server["tunnel"]["client_leases"]) == 2
    assert len(updated_server["tunnel"]["client_leases"]) == 1
    assert len(updated_server["tokens"]["clients"]) == 1
    assert updated_server["revocations"]["identity_serials"] == [removed_serial]
    assert updated_server["tunnel"]["client_leases"][0]["device_id"] == "test-client-1"
    assert updated_server["tokens"]["clients"][0]["device_id"] == "test-client-1"
    assert "last_client_removed_at" in updated_server


def test_firstparty_server_revocations_block_admission(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    out_dir = tmp_path / "vpn"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(out_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=1,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    server_config = json.loads((out_dir / "server.json").read_text(encoding="utf-8"))
    client_serial = server_config["tokens"]["client"]["serial"]
    server_config["revocations"] = {
        "identity_serials": [client_serial],
        "key_ids": [],
        "policy_epochs": [],
    }
    registry = wrapper._admission_registry(server_config)
    hello, _material = wrapper._client_hello_and_material(server_config)

    try:
        registry.admit(hello)
    except Exception as exc:
        assert "identity_revoked" in str(exc)
    else:
        raise AssertionError("revoked client identity was admitted")


def test_firstparty_export_client_kit_excludes_server_and_issuer_secrets(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    export_dir = tmp_path / "export"
    archive_path = tmp_path / "client-only.tar.gz"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    assert wrapper.export_client_kit(
        SimpleNamespace(
            client_config=str(generated_dir / "client.json"),
            issuer_config=str(generated_dir / "issuer.json"),
            out_dir=str(export_dir),
            archive=str(archive_path),
            kit_name="client-one",
        )
    ) == 0

    output = json.loads(capsys.readouterr().out)
    exported_client = json.loads(
        (export_dir / "client-one/client.json").read_text(encoding="utf-8")
    )
    public_info = json.loads(
        (export_dir / "client-one/public-info.json").read_text(encoding="utf-8")
    )
    release_info_path = export_dir / "client-one/CLIENT-RELEASE.json"
    release_info = json.loads(release_info_path.read_text(encoding="utf-8"))
    readme = (export_dir / "client-one/README.md").read_text(encoding="utf-8")
    install_script_path = export_dir / "client-one/install-linux.sh"
    install_script = install_script_path.read_text(encoding="utf-8")
    status_script_path = export_dir / "client-one/status-linux.sh"
    status_script = status_script_path.read_text(encoding="utf-8")
    uninstall_script_path = export_dir / "client-one/uninstall-linux.sh"
    uninstall_script = uninstall_script_path.read_text(encoding="utf-8")
    verify_script_path = export_dir / "client-one/verify-linux.sh"
    verify_script = verify_script_path.read_text(encoding="utf-8")
    manifest_path = export_dir / "client-one/KIT-MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    signature_path = export_dir / "client-one/KIT-MANIFEST-SIGNATURE.json"
    signature_payload = json.loads(signature_path.read_text(encoding="utf-8"))
    encoded_client = json.dumps(exported_client, sort_keys=True)
    with tarfile.open(archive_path, "r:gz") as archive:
        names = {Path(member.name).name for member in archive.getmembers()}
        archive_text = "\n".join(member.name for member in archive.getmembers())

    assert output["ok"] is True
    assert output["server_secrets_included"] is False
    assert output["readme"] == str(export_dir / "client-one/README.md")
    assert output["install_script"] == str(install_script_path)
    check_script_path = export_dir / "client-one/check-linux.sh"
    check_script = check_script_path.read_text(encoding="utf-8")
    doctor_script_path = export_dir / "client-one/doctor-linux.sh"
    doctor_script = doctor_script_path.read_text(encoding="utf-8")
    assert output["check_script"] == str(check_script_path)
    assert output["doctor_script"] == str(doctor_script_path)
    assert output["verify_script"] == str(verify_script_path)
    assert output["release_info"] == str(release_info_path)
    assert output["manifest"] == str(manifest_path)
    assert output["manifest_signature"] == str(signature_path)
    assert output["manifest_signed"] is True
    assert public_info["readme"] == "README.md"
    assert public_info["install_script"] == "install-linux.sh"
    assert public_info["check_script"] == "check-linux.sh"
    assert public_info["doctor_script"] == "doctor-linux.sh"
    assert public_info["status_script"] == "status-linux.sh"
    assert public_info["uninstall_script"] == "uninstall-linux.sh"
    assert public_info["verify_script"] == "verify-linux.sh"
    assert public_info["release_info"] == "CLIENT-RELEASE.json"
    assert public_info["entrypoint"] == "x0vpn_node.py"
    assert public_info["manifest"] == "KIT-MANIFEST.json"
    assert public_info["manifest_signature"] == "KIT-MANIFEST-SIGNATURE.json"
    assert release_info["mode"] == "x0vpn-client-release"
    assert release_info["release_status"] == "production_candidate"
    assert release_info["client_config_hash"] == wrapper._json_payload_hash(exported_client)
    assert release_info["manifest_signed"] is True
    assert release_info["entrypoint"] == "x0vpn_node.py"
    assert release_info["production_controls"]["kill_switch_enabled"] is True
    assert release_info["production_controls"]["client_identity_lifetime_seconds"] == 3600
    assert release_info["production_controls"]["server_identity_lifetime_seconds"] == 3600
    assert "README.md" in names
    assert "CLIENT-RELEASE.json" in names
    assert "install-linux.sh" in names
    assert "check-linux.sh" in names
    assert "doctor-linux.sh" in names
    assert "status-linux.sh" in names
    assert "uninstall-linux.sh" in names
    assert "verify-linux.sh" in names
    assert "KIT-MANIFEST.json" in names
    assert "KIT-MANIFEST-SIGNATURE.json" in names
    assert "x0vpn_node.py" in names
    assert "x0vpn_test_node.py" not in names
    assert "x0tta6bl4 first-party VPN client kit" in readme
    assert "./verify-linux.sh" in readme
    assert "./check-linux.sh" in readme
    assert "./doctor-linux.sh" in readme
    assert "Linux safe preinstall check" in readme
    assert "Manual dataplane probe" in readme
    assert "CLIENT-RELEASE.json" in readme
    assert "x0vpn_node.py" in readme
    assert "x0vpn_test_node.py" not in readme
    assert "probe --config client.json --timeout 5 --tun-packet" in readme
    assert "Manual Linux host preflight" in readme
    assert "PYTHONDONTWRITEBYTECODE=1" in readme
    assert "sudo ./uninstall-linux.sh" in readme
    assert "./verify-linux.sh" in check_script
    assert "x0vpn_node.py" in check_script
    assert "x0vpn_test_node.py" not in check_script
    assert "export PYTHONDONTWRITEBYTECODE=1" in check_script
    assert "linux-preflight --config client.json --role client" in check_script
    assert "--no-require-root --no-require-net-admin" in check_script
    assert "client-readiness" in check_script
    assert "probe --config client.json --timeout \"$PROBE_TIMEOUT\" --tun-packet" in check_script
    assert "PROBE_TIMEOUT=\"${PROBE_TIMEOUT:-5}\"" in check_script
    assert "client-service-plan" in check_script
    assert "--install-config-sync" in check_script
    assert "--require-readiness" in check_script
    assert check_script.index("./verify-linux.sh") < check_script.index("linux-preflight")
    assert check_script.index("linux-preflight") < check_script.index("client-readiness")
    assert check_script.index("client-readiness") < check_script.index("probe --config")
    assert check_script.index("probe --config") < check_script.index("client-service-plan")
    assert "client-doctor" in doctor_script
    assert "./verify-linux.sh" in doctor_script
    assert "REQUIRE_INSTALLED_HEALTH=\"${REQUIRE_INSTALLED_HEALTH:-0}\"" in doctor_script
    assert "--require-installed-health" in doctor_script
    assert "--probe-timeout \"$PROBE_TIMEOUT\"" in doctor_script
    assert "--readiness-timeout \"$READINESS_TIMEOUT\"" in doctor_script
    assert "x0vpn_node.py" in doctor_script
    assert "x0vpn_test_node.py" not in doctor_script
    assert "./verify-linux.sh" in install_script
    assert "x0vpn_node.py" in install_script
    assert "x0vpn_test_node.py" not in install_script
    assert "export PYTHONDONTWRITEBYTECODE=1" in install_script
    assert "linux-preflight --config client.json --role client" in install_script
    assert "client-readiness" in install_script
    assert "probe --config client.json --timeout \"$PROBE_TIMEOUT\" --tun-packet" in install_script
    assert "PROBE_TIMEOUT=\"${PROBE_TIMEOUT:-5}\"" in install_script
    assert "HEALTH_TIMEOUT=\"${HEALTH_TIMEOUT:-5}\"" in install_script
    assert "POST_INSTALL_HEALTH_RETRIES=\"${POST_INSTALL_HEALTH_RETRIES:-20}\"" in install_script
    assert "POST_INSTALL_HEALTH_INTERVAL_SECONDS=\"${POST_INSTALL_HEALTH_INTERVAL_SECONDS:-1}\"" in install_script
    assert "--require-post-install-health" in install_script
    assert "--post-install-health-timeout \"$HEALTH_TIMEOUT\"" in install_script
    assert "--post-install-health-retries \"$POST_INSTALL_HEALTH_RETRIES\"" in install_script
    assert "--post-install-health-interval-seconds \"$POST_INSTALL_HEALTH_INTERVAL_SECONDS\"" in install_script
    assert "install-client-service" in install_script
    assert "./status-linux.sh" in install_script
    assert "--require-readiness" in install_script
    assert install_script.index("./verify-linux.sh") < install_script.index("linux-preflight")
    assert install_script.index("linux-preflight") < install_script.index("client-readiness")
    assert install_script.index("client-readiness") < install_script.index("probe --config")
    assert install_script.index("probe --config") < install_script.index("install-client-service")
    assert install_script.index("install-client-service") < install_script.index("./status-linux.sh")
    assert "linux-preflight --config client.json --role client" in status_script
    assert "--no-require-root --no-require-net-admin" in status_script
    assert "client-health" in status_script
    assert "client-readiness" in status_script
    assert "probe --config client.json --timeout \"$PROBE_TIMEOUT\" --tun-packet" in status_script
    assert "PROBE_TIMEOUT=\"${PROBE_TIMEOUT:-5}\"" in status_script
    assert "PROBE_RC" in status_script
    assert "export PYTHONDONTWRITEBYTECODE=1" in status_script
    assert status_script.index("linux-preflight") < status_script.index("client-health")
    assert status_script.index("client-readiness") < status_script.index("probe --config")
    assert "x0vpn_node.py" in status_script
    assert "x0vpn_test_node.py" not in status_script
    assert "uninstall-client-service" in uninstall_script
    assert "x0vpn_node.py" in uninstall_script
    assert "x0vpn_test_node.py" not in uninstall_script
    assert "--remove-install-dir" in uninstall_script
    assert "--remove-config-dir" in uninstall_script
    assert "export PYTHONDONTWRITEBYTECODE=1" in uninstall_script
    assert "kit-verify" in verify_script
    assert "unexpected:" in verify_script
    assert "signature:verify" in verify_script
    assert install_script_path.stat().st_mode & 0o111
    assert check_script_path.stat().st_mode & 0o111
    assert doctor_script_path.stat().st_mode & 0o111
    assert status_script_path.stat().st_mode & 0o111
    assert uninstall_script_path.stat().st_mode & 0o111
    assert verify_script_path.stat().st_mode & 0o111
    assert manifest["mode"] == "x0vpn-client-kit-manifest"
    assert signature_payload["mode"] == "x0vpn-client-kit-manifest-signature"
    assert signature_payload["manifest_sha256"] == wrapper._json_payload_hash(manifest)
    assert signature_payload["signature"]
    manifest_files = {item["path"]: item for item in manifest["files"]}
    assert "KIT-MANIFEST.json" not in manifest_files
    assert "CLIENT-RELEASE.json" in manifest_files
    for relpath in (
        "CLIENT-RELEASE.json",
        "client.json",
        "x0vpn_node.py",
        "check-linux.sh",
        "doctor-linux.sh",
        "install-linux.sh",
        "status-linux.sh",
        "uninstall-linux.sh",
        "verify-linux.sh",
    ):
        item = manifest_files[relpath]
        data = (export_dir / "client-one" / relpath).read_bytes()
        assert item["sha256"] == hashlib.sha256(data).hexdigest()
        assert item["size_bytes"] == len(data)
    verify_result = subprocess.run(
        (str(verify_script_path),),
        cwd=verify_script_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert verify_result.returncode == 0
    assert '"ok": true' in verify_result.stdout
    assert '"signature_present": true' in verify_result.stdout
    signature_path.write_text(
        signature_path.read_text(encoding="utf-8").replace(
            signature_payload["signature"][:8],
            "0" * 8,
            1,
        ),
        encoding="utf-8",
    )
    bad_signature_result = subprocess.run(
        (str(verify_script_path),),
        cwd=verify_script_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert bad_signature_result.returncode == 1
    assert "signature:verify" in bad_signature_result.stdout
    signature_path.write_text(json.dumps(signature_payload, sort_keys=True), encoding="utf-8")
    (export_dir / "client-one/README.md").write_text(
        readme + "\nmodified\n",
        encoding="utf-8",
    )
    tampered_verify_result = subprocess.run(
        (str(verify_script_path),),
        cwd=verify_script_path.parent,
        capture_output=True,
        text=True,
        check=False,
    )
    assert tampered_verify_result.returncode == 1
    assert "sha256:README.md" in tampered_verify_result.stdout
    assert "server.json" not in names
    assert "issuer.json" not in names
    assert "__pycache__" not in archive_text
    assert ".pyc" not in archive_text
    assert "decapsulation_key" not in encoded_client
    assert "client_leases" not in encoded_client
    assert "revocations" not in encoded_client
    assert set(exported_client["tokens"]) == {"client", "server"}


def test_firstparty_export_client_kits_exports_all_clients_without_server_secrets(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    export_dir = tmp_path / "export"
    archive_dir = tmp_path / "archives"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    exit_code = wrapper.export_client_kits(
        SimpleNamespace(
            server_config=str(generated_dir / "server.json"),
            issuer_config=str(generated_dir / "issuer.json"),
            out_dir=str(export_dir),
            kit_prefix="managed",
            archive=True,
            archive_dir=str(archive_dir),
        )
    )

    payload = json.loads(capsys.readouterr().out)
    exports = payload["exports"]

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "export-client-kits"
    assert payload["client_count"] == 2
    assert payload["server_secrets_included"] is False
    assert [item["device_id"] for item in exports] == ["test-client-1", "test-client-2"]

    for item in exports:
        kit_dir = Path(item["kit_dir"])
        archive_path = Path(item["archive"])
        client = json.loads((kit_dir / "client.json").read_text(encoding="utf-8"))
        readme = (kit_dir / "README.md").read_text(encoding="utf-8")
        install_script_path = kit_dir / "install-linux.sh"
        install_script = install_script_path.read_text(encoding="utf-8")
        status_script_path = kit_dir / "status-linux.sh"
        status_script = status_script_path.read_text(encoding="utf-8")
        uninstall_script_path = kit_dir / "uninstall-linux.sh"
        uninstall_script = uninstall_script_path.read_text(encoding="utf-8")
        verify_script_path = kit_dir / "verify-linux.sh"
        verify_script = verify_script_path.read_text(encoding="utf-8")
        release_info_path = kit_dir / "CLIENT-RELEASE.json"
        release_info = json.loads(release_info_path.read_text(encoding="utf-8"))
        manifest_path = kit_dir / "KIT-MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        signature_path = kit_dir / "KIT-MANIFEST-SIGNATURE.json"
        signature_payload = json.loads(signature_path.read_text(encoding="utf-8"))
        encoded_client = json.dumps(client, sort_keys=True)
        with tarfile.open(archive_path, "r:gz") as archive:
            names = {Path(member.name).name for member in archive.getmembers()}
            archive_text = "\n".join(member.name for member in archive.getmembers())
        assert item["server_secrets_included"] is False
        assert client["tokens"]["client"]["claims"]["device_id"] == item["device_id"]
        assert item["readme"] == str(kit_dir / "README.md")
        assert item["install_script"] == str(install_script_path)
        check_script_path = kit_dir / "check-linux.sh"
        check_script = check_script_path.read_text(encoding="utf-8")
        doctor_script_path = kit_dir / "doctor-linux.sh"
        doctor_script = doctor_script_path.read_text(encoding="utf-8")
        assert item["check_script"] == str(check_script_path)
        assert item["doctor_script"] == str(doctor_script_path)
        assert item["status_script"] == str(status_script_path)
        assert item["uninstall_script"] == str(uninstall_script_path)
        assert item["verify_script"] == str(verify_script_path)
        assert item["release_info"] == str(release_info_path)
        assert item["manifest"] == str(manifest_path)
        assert item["manifest_signature"] == str(signature_path)
        assert item["manifest_signed"] is True
        assert "README.md" in names
        assert "CLIENT-RELEASE.json" in names
        assert "install-linux.sh" in names
        assert "check-linux.sh" in names
        assert "doctor-linux.sh" in names
        assert "status-linux.sh" in names
        assert "uninstall-linux.sh" in names
        assert "verify-linux.sh" in names
        assert "KIT-MANIFEST.json" in names
        assert "KIT-MANIFEST-SIGNATURE.json" in names
        assert "x0vpn_node.py" in names
        assert "x0vpn_test_node.py" not in names
        assert release_info["mode"] == "x0vpn-client-release"
        assert release_info["client_config_hash"] == wrapper._json_payload_hash(client)
        assert release_info["manifest_signed"] is True
        assert release_info["entrypoint"] == "x0vpn_node.py"
        assert release_info["production_controls"]["kill_switch_enabled"] is True
        assert release_info["production_controls"]["client_identity_lifetime_seconds"] == 3600
        assert f"Endpoint: {item['host']}:{item['port']}" in readme
        assert "CLIENT-RELEASE.json" in readme
        assert "x0vpn_node.py" in readme
        assert "x0vpn_test_node.py" not in readme
        assert "PYTHONDONTWRITEBYTECODE=1" in readme
        assert "./check-linux.sh" in readme
        assert "./doctor-linux.sh" in readme
        assert "Linux safe preinstall check" in readme
        assert "Manual dataplane probe" in readme
        assert "probe --config client.json --timeout 5 --tun-packet" in readme
        assert "./verify-linux.sh" in check_script
        assert "x0vpn_node.py" in check_script
        assert "x0vpn_test_node.py" not in check_script
        assert "export PYTHONDONTWRITEBYTECODE=1" in check_script
        assert "linux-preflight --config client.json --role client" in check_script
        assert "--no-require-root --no-require-net-admin" in check_script
        assert "client-readiness" in check_script
        assert "probe --config client.json --timeout \"$PROBE_TIMEOUT\" --tun-packet" in check_script
        assert "PROBE_TIMEOUT=\"${PROBE_TIMEOUT:-5}\"" in check_script
        assert "client-service-plan" in check_script
        assert "--install-config-sync" in check_script
        assert "--require-readiness" in check_script
        assert check_script.index("./verify-linux.sh") < check_script.index("linux-preflight")
        assert check_script.index("linux-preflight") < check_script.index("client-readiness")
        assert check_script.index("client-readiness") < check_script.index("probe --config")
        assert check_script.index("probe --config") < check_script.index("client-service-plan")
        assert "client-doctor" in doctor_script
        assert "./verify-linux.sh" in doctor_script
        assert "REQUIRE_INSTALLED_HEALTH=\"${REQUIRE_INSTALLED_HEALTH:-0}\"" in doctor_script
        assert "--require-installed-health" in doctor_script
        assert "--probe-timeout \"$PROBE_TIMEOUT\"" in doctor_script
        assert "--readiness-timeout \"$READINESS_TIMEOUT\"" in doctor_script
        assert "x0vpn_node.py" in doctor_script
        assert "x0vpn_test_node.py" not in doctor_script
        assert "./verify-linux.sh" in install_script
        assert "x0vpn_node.py" in install_script
        assert "x0vpn_test_node.py" not in install_script
        assert "export PYTHONDONTWRITEBYTECODE=1" in install_script
        assert "linux-preflight --config client.json --role client" in install_script
        assert "client-readiness" in install_script
        assert "probe --config client.json --timeout \"$PROBE_TIMEOUT\" --tun-packet" in install_script
        assert "PROBE_TIMEOUT=\"${PROBE_TIMEOUT:-5}\"" in install_script
        assert "HEALTH_TIMEOUT=\"${HEALTH_TIMEOUT:-5}\"" in install_script
        assert "POST_INSTALL_HEALTH_RETRIES=\"${POST_INSTALL_HEALTH_RETRIES:-20}\"" in install_script
        assert "POST_INSTALL_HEALTH_INTERVAL_SECONDS=\"${POST_INSTALL_HEALTH_INTERVAL_SECONDS:-1}\"" in install_script
        assert "--require-post-install-health" in install_script
        assert "--post-install-health-timeout \"$HEALTH_TIMEOUT\"" in install_script
        assert "--post-install-health-retries \"$POST_INSTALL_HEALTH_RETRIES\"" in install_script
        assert "--post-install-health-interval-seconds \"$POST_INSTALL_HEALTH_INTERVAL_SECONDS\"" in install_script
        assert "--require-readiness" in install_script
        assert "./status-linux.sh" in install_script
        assert install_script.index("./verify-linux.sh") < install_script.index("linux-preflight")
        assert install_script.index("linux-preflight") < install_script.index("client-readiness")
        assert install_script.index("client-readiness") < install_script.index("probe --config")
        assert install_script.index("probe --config") < install_script.index("install-client-service")
        assert install_script.index("install-client-service") < install_script.index("./status-linux.sh")
        assert "linux-preflight --config client.json --role client" in status_script
        assert "--no-require-root --no-require-net-admin" in status_script
        assert "client-health" in status_script
        assert "client-readiness" in status_script
        assert "probe --config client.json --timeout \"$PROBE_TIMEOUT\" --tun-packet" in status_script
        assert "PROBE_TIMEOUT=\"${PROBE_TIMEOUT:-5}\"" in status_script
        assert "PROBE_RC" in status_script
        assert "export PYTHONDONTWRITEBYTECODE=1" in status_script
        assert status_script.index("linux-preflight") < status_script.index("client-health")
        assert status_script.index("client-readiness") < status_script.index("probe --config")
        assert "x0vpn_node.py" in status_script
        assert "x0vpn_test_node.py" not in status_script
        assert "uninstall-client-service" in uninstall_script
        assert "x0vpn_node.py" in uninstall_script
        assert "x0vpn_test_node.py" not in uninstall_script
        assert "--remove-install-dir" in uninstall_script
        assert "--remove-config-dir" in uninstall_script
        assert "export PYTHONDONTWRITEBYTECODE=1" in uninstall_script
        assert "kit-verify" in verify_script
        assert "signature:verify" in verify_script
        assert install_script_path.stat().st_mode & 0o111
        assert check_script_path.stat().st_mode & 0o111
        assert doctor_script_path.stat().st_mode & 0o111
        assert status_script_path.stat().st_mode & 0o111
        assert uninstall_script_path.stat().st_mode & 0o111
        assert verify_script_path.stat().st_mode & 0o111
        manifest_files = {entry["path"]: entry for entry in manifest["files"]}
        assert "CLIENT-RELEASE.json" in manifest_files
        assert "client.json" in manifest_files
        assert "x0vpn_node.py" in manifest_files
        assert "x0vpn_test_node.py" not in manifest_files
        assert "check-linux.sh" in manifest_files
        assert "doctor-linux.sh" in manifest_files
        assert "verify-linux.sh" in manifest_files
        assert "KIT-MANIFEST.json" not in manifest_files
        assert signature_payload["manifest_sha256"] == wrapper._json_payload_hash(manifest)
        assert signature_payload["signature"]
        client_manifest = manifest_files["client.json"]
        client_bytes = (kit_dir / "client.json").read_bytes()
        assert client_manifest["sha256"] == hashlib.sha256(client_bytes).hexdigest()
        assert "server.json" not in names
        assert "issuer.json" not in names
        assert "__pycache__" not in archive_text
        assert ".pyc" not in archive_text
        assert "decapsulation_key" not in encoded_client
        assert "client_leases" not in encoded_client
        assert set(client["tokens"]) == {"client", "server"}


def test_firstparty_verify_client_kits_accepts_signed_archives(tmp_path, capsys):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    export_dir = tmp_path / "export"
    archive_dir = tmp_path / "archives"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    assert wrapper.export_client_kits(
        SimpleNamespace(
            server_config=str(generated_dir / "server.json"),
            issuer_config=str(generated_dir / "issuer.json"),
            out_dir=str(export_dir),
            kit_prefix="managed",
            archive=True,
            archive_dir=str(archive_dir),
        )
    ) == 0
    capsys.readouterr()

    exit_code = wrapper.verify_client_kits(
        SimpleNamespace(
            kits_dir=str(export_dir),
            archive_dir=str(archive_dir),
            require_signature=True,
            check_archives=True,
            require_readiness=True,
            readiness_timeout=0.1,
            min_identity_valid_seconds=60,
            readiness_skip_tcp_connect=True,
            readiness_skip_admission=True,
            readiness_skip_config_sync=True,
            readiness_skip_managed_install_plan=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "verify-client-kits"
    assert payload["kit_count"] == 2
    assert payload["failed_count"] == 0
    assert payload["failed_kits"] == []
    assert payload["readiness_required"] is True
    assert all(item["ok"] is True for item in payload["exports"])
    assert all(item["signature_present"] is True for item in payload["exports"])
    assert all(item["archive_present"] is True for item in payload["exports"])
    assert all(item["readiness"]["ok"] is True for item in payload["exports"])
    assert all(item["server_secrets_included"] is False for item in payload["exports"])


def test_firstparty_verify_client_kits_can_require_live_readiness(tmp_path, capsys):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    export_dir = tmp_path / "export"
    archive_dir = tmp_path / "archives"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    assert wrapper.export_client_kits(
        SimpleNamespace(
            server_config=str(generated_dir / "server.json"),
            issuer_config=str(generated_dir / "issuer.json"),
            out_dir=str(export_dir),
            kit_prefix="managed",
            archive=True,
            archive_dir=str(archive_dir),
        )
    ) == 0
    capsys.readouterr()

    exit_code = wrapper.verify_client_kits(
        SimpleNamespace(
            kits_dir=str(export_dir),
            archive_dir=str(archive_dir),
            require_signature=True,
            check_archives=True,
            require_readiness=True,
            readiness_timeout=0.1,
            min_identity_valid_seconds=7200,
            readiness_skip_tcp_connect=True,
            readiness_skip_admission=True,
            readiness_skip_config_sync=True,
            readiness_skip_managed_install_plan=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["mode"] == "verify-client-kits"
    assert payload["readiness_required"] is True
    assert payload["failed_count"] == 2
    assert all("readiness" in item["errors"] for item in payload["exports"])
    assert all(item["readiness"]["ok"] is False for item in payload["exports"])


def test_firstparty_verify_client_kits_rejects_tampered_kit(tmp_path, capsys):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    export_dir = tmp_path / "export"
    archive_dir = tmp_path / "archives"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()
    assert wrapper.export_client_kits(
        SimpleNamespace(
            server_config=str(generated_dir / "server.json"),
            issuer_config=str(generated_dir / "issuer.json"),
            out_dir=str(export_dir),
            kit_prefix="managed",
            archive=True,
            archive_dir=str(archive_dir),
        )
    ) == 0
    capsys.readouterr()
    readme_path = export_dir / "managed-test-client-1" / "README.md"
    readme_path.write_text(
        readme_path.read_text(encoding="utf-8") + "\ntampered\n",
        encoding="utf-8",
    )

    exit_code = wrapper.verify_client_kits(
        SimpleNamespace(
            kits_dir=str(export_dir),
            archive_dir=str(archive_dir),
            require_signature=True,
            check_archives=True,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["mode"] == "verify-client-kits"
    assert payload["kit_count"] == 2
    assert payload["failed_count"] == 1
    failed = [item for item in payload["exports"] if not item["ok"]]
    assert len(failed) == 1
    assert failed[0]["kit_dir"].endswith("managed-test-client-1")
    assert "sha256:README.md" in failed[0]["errors"]


def test_firstparty_export_client_kits_can_require_readiness_before_export(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    export_dir = tmp_path / "export"
    archive_dir = tmp_path / "archives"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    exit_code = wrapper.export_client_kits(
        SimpleNamespace(
            server_config=str(generated_dir / "server.json"),
            out_dir=str(export_dir),
            kit_prefix="managed",
            archive=True,
            archive_dir=str(archive_dir),
            require_readiness=True,
            readiness_timeout=0.1,
            min_identity_valid_seconds=60,
            readiness_skip_tcp_connect=True,
            readiness_skip_admission=True,
            readiness_skip_config_sync=True,
            readiness_skip_managed_install_plan=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["mode"] == "export-client-kits"
    assert payload["readiness_required"] is True
    assert len(payload["readiness"]) == 2
    assert all(item["ok"] is True for item in payload["readiness"])
    assert [item["device_id"] for item in payload["readiness"]] == [
        "test-client-1",
        "test-client-2",
    ]
    assert len(payload["exports"]) == 2
    assert all(Path(item["archive"]).exists() for item in payload["exports"])


def test_firstparty_export_client_kits_stops_before_export_when_readiness_fails(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    generated_dir = tmp_path / "generated"
    export_dir = tmp_path / "export"
    archive_dir = tmp_path / "archives"
    assert wrapper.generate_configs(
        SimpleNamespace(
            out_dir=str(generated_dir),
            host="203.0.113.10",
            port=22080,
            bind_host="0.0.0.0",
            tenant="team-a",
            server_tun_name="x0vpns0",
            client_tun_name="x0vpn0",
            tun_mtu=1280,
            client_cidr="10.90.0.0/24",
            server_tun_address="10.90.0.1/24",
            client_tun_address="10.90.0.2/32",
            client_tun_peer="10.90.0.1",
            client_count=2,
            client_device_prefix="test-client",
            client_address_offset=2,
            dns_server=[],
            lifetime_seconds=3600,
        )
    ) == 0
    capsys.readouterr()

    exit_code = wrapper.export_client_kits(
        SimpleNamespace(
            server_config=str(generated_dir / "server.json"),
            out_dir=str(export_dir),
            kit_prefix="managed",
            archive=True,
            archive_dir=str(archive_dir),
            require_readiness=True,
            readiness_timeout=0.1,
            min_identity_valid_seconds=7200,
            readiness_skip_tcp_connect=True,
            readiness_skip_admission=True,
            readiness_skip_config_sync=True,
            readiness_skip_managed_install_plan=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["mode"] == "export-client-kits"
    assert payload["error"] == "client kits readiness failed"
    assert payload["failed_devices"] == ["test-client-1", "test-client-2"]
    assert payload["readiness_required"] is True
    assert payload["file_mutation_performed"] is False
    assert payload["os_mutation_performed"] is False
    assert not export_dir.exists()
    assert not archive_dir.exists()


def test_firstparty_issuer_lifetime_policy_requires_file_mutation_flag(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    issuer_config_path = tmp_path / "issuer.json"
    issuer_config_path.write_text(
        json.dumps(
            {
                "default_lifetime_seconds": 3600,
                "max_lifetime_seconds": 3600,
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.issuer_lifetime_policy(
        SimpleNamespace(
            issuer_config=str(issuer_config_path),
            default_lifetime_seconds=86400,
            max_lifetime_seconds=86400,
            allow_file_mutation=False,
            dry_run=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    issuer_config = json.loads(issuer_config_path.read_text(encoding="utf-8"))

    assert exit_code == 2
    assert payload["ok"] is False
    assert payload["mode"] == "issuer-lifetime-policy"
    assert payload["error"] == "file mutation is blocked; pass --allow-file-mutation"
    assert issuer_config["default_lifetime_seconds"] == 3600
    assert issuer_config["max_lifetime_seconds"] == 3600


def test_firstparty_issuer_lifetime_policy_can_update_bounds(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    issuer_config_path = tmp_path / "issuer.json"
    issuer_config_path.write_text(
        json.dumps(
            {
                "default_lifetime_seconds": 3600,
                "max_lifetime_seconds": 3600,
                "active_key_id": "issuer-key",
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.issuer_lifetime_policy(
        SimpleNamespace(
            issuer_config=str(issuer_config_path),
            default_lifetime_seconds=86400,
            max_lifetime_seconds=86400,
            allow_file_mutation=True,
            dry_run=False,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    issuer_config = json.loads(issuer_config_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["old_default_lifetime_seconds"] == 3600
    assert payload["old_max_lifetime_seconds"] == 3600
    assert payload["default_lifetime_seconds"] == 86400
    assert payload["max_lifetime_seconds"] == 86400
    assert payload["file_mutation_performed"] is True
    assert issuer_config["default_lifetime_seconds"] == 86400
    assert issuer_config["max_lifetime_seconds"] == 86400
    assert issuer_config["active_key_id"] == "issuer-key"


def test_firstparty_issuer_lifetime_policy_dry_run_does_not_write(
    tmp_path,
    capsys,
):
    wrapper = _load_firstparty_wrapper()
    issuer_config_path = tmp_path / "issuer.json"
    issuer_config_path.write_text(
        json.dumps(
            {
                "default_lifetime_seconds": 3600,
                "max_lifetime_seconds": 3600,
            }
        ),
        encoding="utf-8",
    )

    exit_code = wrapper.issuer_lifetime_policy(
        SimpleNamespace(
            issuer_config=str(issuer_config_path),
            default_lifetime_seconds=86400,
            max_lifetime_seconds=86400,
            allow_file_mutation=False,
            dry_run=True,
        )
    )

    payload = json.loads(capsys.readouterr().out)
    issuer_config = json.loads(issuer_config_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert payload["ok"] is True
    assert payload["dry_run"] is True
    assert payload["changed"] is True
    assert payload["file_mutation_performed"] is False
    assert issuer_config["default_lifetime_seconds"] == 3600
    assert issuer_config["max_lifetime_seconds"] == 3600
