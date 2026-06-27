#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).with_name("build_vpn_goal_status.py")
SPEC = importlib.util.spec_from_file_location("build_vpn_goal_status", MODULE_PATH)
assert SPEC and SPEC.loader
goal_status = importlib.util.module_from_spec(SPEC)
sys.modules["build_vpn_goal_status"] = goal_status
SPEC.loader.exec_module(goal_status)


def sample_decision() -> dict:
    return {
        "generated_at": goal_status.utc_now(),
        "decision": {
            "decision": "observe",
            "nl_mutation_allowed": False,
        },
        "classification": {
            "overall_status": "advisory",
            "transport_status": "advisory",
            "telegram_media_status": "degraded",
            "evidence": [
                "external exit IP is VPN server",
                "packet_loss_percent=0",
                "NL key services active",
                "NL core listeners 443/2083/39829 present",
            ],
        },
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "auto_profile_switch_allowed": False,
    }


def sample_matrix(*, complete: bool = False) -> dict:
    missing = [] if complete else [
        "android_happ_or_hiddify",
        "mobile_network",
        "restricted_or_work_wifi",
    ]
    return {
        "decision": "CLIENT_MATRIX_COMPLETE" if complete else "CLIENT_MATRIX_PARTIAL_REAL_DEVICES_REQUIRED",
        "privacy_rule": {"raw_secret_material_stored": False},
        "completion_rule": {
            "current_status": "complete" if complete else "not_complete",
            "missing_requirements": missing,
        },
        "real_client_checks": [
            {
                "status": "pass",
                "raw_secret_material_stored": False,
                "client": "v2rayN",
                "network_type": "desktop",
            },
            {
                "status": "pass",
                "raw_secret_material_stored": False,
                "client": "Happ",
                "network_type": "mobile",
            },
        ],
    }


def sample_anti_block_audit(*, complete: bool = False) -> dict:
    return {
        "decision": (
            "PRODUCTION_CANDIDATE_READY"
            if complete
            else "PRODUCTION_CANDIDATE_GOAL_NOT_MARKED_COMPLETE"
        ),
        "remaining_before_goal_complete": []
        if complete
        else [
            "record Android Happ/Hiddify client evidence after rollout",
            "record one mobile network evidence case",
        ],
        "privacy": {"output_privacy_ok": True, "raw_uuid_stored": False},
    }


def sample_remote_request(*, complete: bool = False) -> dict:
    if complete:
        return {
            "generated_at": goal_status.utc_now(),
            "decision": "REMOTE_CLIENT_EVIDENCE_REQUEST_NOT_NEEDED",
            "missing_requirements": [],
            "request_count": 0,
            "minimum_reports_required": 0,
            "privacy": {"output_privacy_ok": True, "raw_uuid_stored": False},
        }
    hash_guard = (
        "--expect-request-packet-sha256 "
        "\"$(sha256sum nl-diagnostics/nl-anti-block-remote-client-evidence-request-2026-06-02.json "
        "| awk '{print $1}')\""
    )
    record_pass = (
        "printf '%s\\n' \"pass connected\" | "
        "python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py "
        "--write --record-matrix --refresh-artifacts --request-id remote-client-evidence-1 "
        f"--reply-stdin {hash_guard} --json"
    )
    record_fail = record_pass.replace("pass connected", "fail timeout")
    validate_pass = (
        "printf '%s\\n' \"pass connected\" | "
        "python3 services/nl-server/ghost-access/record_remote_client_evidence_reply.py "
        f"--request-id remote-client-evidence-1 --reply-stdin {hash_guard} --json"
    )
    validate_fail = validate_pass.replace("pass connected", "fail timeout")
    return {
        "generated_at": goal_status.utc_now(),
        "decision": "REMOTE_CLIENT_EVIDENCE_REQUEST_READY",
        "request_freshness_policy": (
            "record_remote_client_evidence_reply.py rejects request packets older than 24 hours; "
            "refresh this packet before recording delayed replies"
        ),
        "request_packet_hash_binding_policy": (
            "record_remote_client_evidence_reply.py supports --expect-request-packet-sha256; "
            "before recording a reply, bind it to the exact request artifact hash from "
            "scripts/vpn_status.sh --json client_evidence.remote_request_packet.source_sha256 "
            "or from sha256sum of this request packet"
        ),
        "missing_requirements": [
            "android_happ_or_hiddify",
            "mobile_network",
            "restricted_or_work_wifi",
        ],
        "request_count": 2,
        "minimum_reports_required": 2,
        "requests": [
            {
                "operator_reply_record_pass_command": record_pass,
                "operator_reply_record_fail_command": record_fail,
                "operator_reply_validate_pass_command": validate_pass,
                "operator_reply_validate_fail_command": validate_fail,
                "safe_reply_options": [
                    "pass connected",
                    "fail timeout",
                    "fail import",
                    "fail no-internet",
                ],
            },
            {
                "operator_reply_record_pass_command": record_pass.replace(
                    "remote-client-evidence-1", "remote-client-evidence-2"
                ),
                "operator_reply_record_fail_command": record_fail.replace(
                    "remote-client-evidence-1", "remote-client-evidence-2"
                ),
                "operator_reply_validate_pass_command": validate_pass.replace(
                    "remote-client-evidence-1", "remote-client-evidence-2"
                ),
                "operator_reply_validate_fail_command": validate_fail.replace(
                    "remote-client-evidence-1", "remote-client-evidence-2"
                ),
                "safe_reply_options": [
                    "pass connected",
                    "fail timeout",
                    "fail import",
                    "fail no-internet",
                ],
            },
        ],
        "privacy": {"output_privacy_ok": True, "raw_uuid_stored": False},
    }


def sample_warp_plan(*, safe: bool = True) -> dict:
    return {
        "decision": "TELEGRAM_MEDIA_WARP_ROUTE_READY_TO_STAGE",
        "blockers": [],
        "current_evidence": {
            "telegram_media_status": "degraded",
            "warp_status": "healthy",
            "xray_outbound_tags": ["direct", "warp", "blocked"],
        },
        "target_rule": {"outboundTag": "warp"},
        "rollout": {
            "requires_explicit_operator_confirm": (
                "APPLY_TELEGRAM_MEDIA_WARP_ROUTE" if safe else "wrong"
            ),
            "requires_fresh_readonly_snapshot": True,
            "requires_config_backup": True,
            "requires_xray_config_test_before_restart": True,
            "restart_scope": ["x-ui"],
            "forbidden_restarts": [
                "ghost-access-nl-xhttp.service",
                "ghost-access-nl-https-ws.service",
                "telegram-bot-simple.service",
                "nginx",
            ],
            "mutation_scope": "routing.rules only",
        },
        "privacy": {"output_privacy_ok": True, "raw_uuid_stored": False},
    }


def sample_readiness() -> dict:
    return {
        "ok": True,
        "summary": {
            "nl_write_allowed": False,
            "automatic_failover_allowed": False,
            "spb_fallback_allowed": False,
        },
    }


def sample_manifest(*, nl_write_allowed: bool = False) -> dict:
    return {
        "status": "planning_only",
        "nl_write_allowed": nl_write_allowed,
    }


def sample_preflight(*, ok: bool = True) -> dict:
    return {
        "ok": ok,
        "deploy_status": "local_ready_but_deploy_blocked" if ok else "deploy_allowed",
        "nl_write_allowed": False if ok else True,
        "checks": [
            {"name": "remote_client_evidence_request_hash_binding_policy_present", "ok": ok},
            {"name": "remote_client_evidence_request_reply_commands_present", "ok": ok},
            {"name": "remote_client_evidence_reply_dry_run_uses_packet_hash", "ok": ok},
        ],
        "validator_exit_code": 0 if ok else 1,
    }


def sample_firstparty_core(*, passed: bool = True) -> dict:
    return {
        "source_audit_precomputed": True,
        "source_audit_passed": passed,
        "source_audit_scanned_files": 37 if passed else 0,
        "source_audit_reasons": [] if passed else ["firstparty_forbidden_import_detected"],
        "source_audit_root_hash": "a" * 64,
        "source_audit_tree_hash": "b" * 64,
    }


def sample_firstparty_canary(*, passed: bool = True) -> dict:
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-live-canary-test/summary.json",
        "transport": "tcp",
        "deployment_epoch": "local-firstparty-canary-test",
        "host": "127.0.0.1",
        "server_bind_addr": ["127.0.0.1", 38425],
        "os_mutation_performed": False,
        "nl_vpn_services_touched": False,
        "return_codes": {
            "probe": 0,
            "admission": 0,
            "dataplane_readiness": 0,
            "source_audit": 0,
        },
        "checks": {
            "generate_ok": passed,
            "server_ok": passed,
            "probe_ok": passed,
            "admission_ok": passed,
            "dataplane_readiness_ok": passed,
            "dataplane_validation_passed": passed,
            "tun_dataplane_validation_passed": passed,
            "mtu_validation_passed": passed,
            "source_audit_ok": passed,
            "source_audit_allowed": passed,
        },
        "dataplane_failed_reasons": [] if passed else ["probe_failed"],
        "tun_dataplane_failed_reasons": [] if passed else ["unexpected_tun_reply"],
        "mtu_failed_reasons": [],
        "source_tree_hash": "c" * 64,
        "scanned_files": 37,
    }


def sample_firstparty_production_readiness(*, passed: bool = True) -> dict:
    collected = {
        "dataplane": passed,
        "external_policy_source": passed,
        "identity_signer": passed,
        "leak_protection": passed,
        "linux_preflight": passed,
        "pqc": passed,
        "rekey_policy": passed,
        "rollout_gate": passed,
        "source_audit": passed,
        "zero_trust_policy": passed,
    }
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-production-readiness-test/summary.json",
        "decision_allowed": passed,
        "decision_reasons": [] if passed else ["pqc_provider_gate_failed"],
        "deployment_epoch": "local-firstparty-production-readiness-test",
        "transport": "tcp",
        "server_bind_addr": ["127.0.0.1", 53929],
        "collected": collected,
        "return_codes": {
            "pqc_promote_server": 0,
            "pqc_promote_client": 0,
            "policy_snapshot": 0,
            "production_readiness": 0 if passed else 1,
        },
        "checks": {
            "generate_ok": True,
            "server_ok": True,
            "pqc_promote_server_ok": True,
            "pqc_promote_client_ok": True,
            "policy_snapshot_ok": True,
            "production_readiness_ok": passed,
            "pqc_provider_gate_allowed": passed,
            "linux_preflight_collected": passed,
            "leak_protection_collected": passed,
            "dataplane_collected": passed,
            "pqc_collected": passed,
            "identity_signer_collected": passed,
            "zero_trust_policy_collected": passed,
            "external_policy_source_collected": passed,
            "rekey_policy_collected": passed,
            "rollout_gate_collected": passed,
            "source_audit_collected": passed,
            "os_mutation_performed_false": True,
        },
        "pqc_runtime_metadata_matches_manifest": passed,
        "pqc_provider_gate_reasons": [] if passed else ["pqc_provider_attestation_not_active"],
        "source_tree_hash": "d" * 64,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
    }


def sample_firstparty_staging_packet(*, passed: bool = True) -> dict:
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-staging-packet-test/summary.json",
        "deployment_epoch": "local-firstparty-staging-packet-test",
        "transport": "tcp",
        "server_bind_addr": ["127.0.0.1", 39979],
        "server_service_name": "x0tta-firstparty-vpn.service",
        "client_service_name": "x0tta-firstparty-vpn-client.service",
        "server_unit_path": "/etc/systemd/system/x0tta-firstparty-vpn.service",
        "client_unit_path": "/etc/systemd/system/x0tta-firstparty-vpn-client.service",
        "server_config_target": "/etc/x0tta-firstparty-vpn-server/server.json",
        "client_config_target": "/etc/x0tta-firstparty-vpn-client/client.json",
        "client_kit_count": 2 if passed else 0,
        "verified_kit_count": 2 if passed else 0,
        "readiness_required": passed,
        "archive_checked": passed,
        "signature_required": passed,
        "server_secrets_included": False,
        "raw_secret_material_stored_in_evidence": False,
        "kit_material_persisted_in_repo": False,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "checks": {
            "generate_ok": True,
            "server_ok": True,
            "server_service_plan_ok": True,
            "client_service_plan_ok": True,
            "apply_server_dry_run_ok": True,
            "apply_client_dry_run_ok": True,
            "export_client_kits_ok": passed,
            "verify_client_kits_ok": passed,
            "export_server_secrets_excluded": True,
            "verify_signature_required": passed,
            "verify_archives_checked": passed,
            "client_kit_count_matches": passed,
            "client_readiness_required": passed,
            "all_verified_kits_ok": passed,
            "all_verified_archives_present": passed,
            "all_verified_signatures_present": passed,
            "all_verified_readiness_ok": passed,
            "all_verified_server_secrets_excluded": passed,
            "no_os_mutation": True,
        },
    }


def sample_firstparty_rollout_packet(*, passed: bool = True) -> dict:
    checks = {
        "staging_ok": passed,
        "production_readiness_ok": passed,
        "canary_ok": passed,
        "server_service_plan_ok": passed,
        "client_service_plan_ok": passed,
        "server_unit_starts_firstparty_server_tun": passed,
        "client_unit_starts_firstparty_client_tun": passed,
        "client_unit_has_rollback_exec_stop": passed,
        "server_apply_dry_run_ok": passed,
        "client_apply_dry_run_ok": passed,
        "server_config_hash_matches_staging": passed,
        "client_config_hash_matches_staging": passed,
        "client_kits_verified": passed,
        "client_kits_exported_without_server_secrets": passed,
        "no_raw_secret_material_in_evidence": passed,
        "kit_material_not_persisted_in_repo": passed,
        "legacy_protocol_markers_absent": passed,
        "approval_required": True,
        "production_mutation_blocked": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-rollout-packet-test/summary.json",
        "deployment_epoch": "local-firstparty-staging-packet-test",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "server_service_name": "x0tta-firstparty-vpn.service",
        "client_service_name": "x0tta-firstparty-vpn-client.service",
        "server_config_target": "/etc/x0tta-firstparty-vpn-server/server.json",
        "client_config_target": "/etc/x0tta-firstparty-vpn-client/client.json",
        "client_kit_count": 2 if passed else 2,
        "verified_kit_count": 2 if passed else 1,
        "legacy_protocol_findings": [] if passed else ["unit:xray"],
        "checks": checks,
    }


def sample_firstparty_production_endpoint(*, passed: bool = True) -> dict:
    checks = {
        "generate_ok": passed,
        "server_service_plan_ok": passed,
        "client_service_plan_ok": passed,
        "endpoint_host_public": passed,
        "server_bind_not_loopback": passed,
        "generated_server_bind_matches": passed,
        "generated_client_host_matches": passed,
        "generated_port_matches": passed,
        "generated_transport_matches": passed,
        "candidate_port_in_range": True,
        "candidate_port_not_legacy_known": passed,
        "candidate_port_free_on_nl_snapshot": passed,
        "service_units_firstparty_only": passed,
        "temp_config_dir_removed": True,
        "raw_secret_material_not_stored_in_evidence": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-production-endpoint-test/summary.json",
        "host": "89.125.1.107" if passed else "127.0.0.1",
        "bind_host": "0.0.0.0" if passed else "127.0.0.1",
        "port": 40467,
        "transport": "tcp",
        "deployment_epoch": "production-firstparty-endpoint-test",
        "server_service_name": "x0tta-firstparty-vpn.service",
        "client_service_name": "x0tta-firstparty-vpn-client.service",
        "occupied_port_count": 42,
        "legacy_unit_findings": [] if passed else ["value0:xray"],
        "raw_secret_material_stored_in_evidence": False,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "checks": checks,
    }


def sample_firstparty_production_apply_packet(*, passed: bool = True) -> dict:
    checks = {
        "endpoint_summary_ok": passed,
        "endpoint_host_public": passed,
        "endpoint_bind_not_loopback": passed,
        "endpoint_port_free_on_nl_snapshot": passed,
        "endpoint_no_mutation": passed,
        "generate_ok": passed,
        "generated_server_bind_matches_endpoint": passed,
        "generated_client_host_matches_endpoint": passed,
        "generated_port_matches_endpoint": passed,
        "generated_transport_matches_endpoint": passed,
        "server_service_plan_ok": passed,
        "client_service_plan_ok": passed,
        "server_unit_starts_firstparty_server_tun": passed,
        "client_unit_starts_firstparty_client_tun": passed,
        "client_unit_has_rollback_exec_stop": passed,
        "service_units_firstparty_only": passed,
        "server_apply_dry_run_ok": passed,
        "client_apply_dry_run_ok": passed,
        "server_apply_hash_matches_generated": passed,
        "client_apply_hash_matches_generated": passed,
        "client_kits_exported": passed,
        "client_kits_verified": passed,
        "client_kits_signed": passed,
        "client_kits_without_server_secrets": passed,
        "approval_required": True,
        "approval_not_present": True,
        "production_mutation_blocked": True,
        "post_apply_validation_required": True,
        "secure_material_handoff_required": True,
        "temp_config_dir_removed": True,
        "raw_secret_material_not_stored_in_evidence": True,
        "kit_material_not_persisted_in_repo": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-production-apply-packet-test/summary.json",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "post_apply_validation_required": True,
        "secure_material_handoff_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "raw_secret_material_stored_in_evidence": False,
        "kit_material_persisted_in_repo": False,
        "host": "89.125.1.107" if passed else "127.0.0.1",
        "bind_host": "0.0.0.0" if passed else "127.0.0.1",
        "port": 40467,
        "transport": "tcp",
        "deployment_epoch": "production-firstparty-apply-test",
        "endpoint_deployment_epoch": "production-firstparty-endpoint-test",
        "server_service_name": "x0tta-firstparty-vpn.service",
        "client_service_name": "x0tta-firstparty-vpn-client.service",
        "client_kit_count": 2,
        "verified_kit_count": 2 if passed else 1,
        "legacy_protocol_findings": [] if passed else ["value0:xray"],
        "checks": checks,
    }


def sample_firstparty_secure_material_handoff(*, passed: bool = True) -> dict:
    checks = {
        "apply_packet_ok": passed,
        "apply_packet_approval_blocked": passed,
        "apply_packet_external_endpoint": passed,
        "apply_packet_requires_secure_handoff": passed,
        "handoff_dir_outside_repo": passed,
        "handoff_archive_outside_repo": passed,
        "handoff_dir_private": passed,
        "handoff_archive_private": passed,
        "private_files_mode_ok": passed,
        "source_tree_included": passed,
        "source_tree_hash_matches_current": passed,
        "generate_ok": passed,
        "server_service_plan_ok": passed,
        "client_service_plan_ok": passed,
        "server_apply_dry_run_ok": passed,
        "client_apply_dry_run_ok": passed,
        "generated_server_bind_matches_apply_packet": passed,
        "generated_client_host_matches_apply_packet": passed,
        "generated_port_matches_apply_packet": passed,
        "generated_transport_matches_apply_packet": passed,
        "client_kits_exported": passed,
        "client_kits_verified": passed,
        "client_kits_signed": passed,
        "client_kits_without_server_secrets": passed,
        "legacy_protocol_markers_absent": passed,
        "manifest_secret_free": passed,
        "raw_secret_material_not_stored_in_evidence": True,
        "repo_material_not_persisted": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-secure-material-handoff-test/summary.json",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "raw_secret_material_stored_in_evidence": False,
        "repo_material_persisted": False,
        "host": "89.125.1.107" if passed else "127.0.0.1",
        "bind_host": "0.0.0.0" if passed else "127.0.0.1",
        "port": 40467,
        "transport": "tcp",
        "deployment_epoch": "production-firstparty-handoff-test",
        "handoff_dir": "/home/user/.local/share/x0tta-firstparty-vpn/handoff",
        "handoff_archive": "/home/user/.local/share/x0tta-firstparty-vpn/handoff.tar.gz",
        "handoff_dir_mode": "0700" if passed else "0755",
        "handoff_archive_mode": "0600" if passed else "0644",
        "archive_sha256": "e" * 64,
        "manifest_sha256": "f" * 64,
        "source_tree_hash": "c" * 64,
        "client_kit_count": 2,
        "verified_kit_count": 2 if passed else 1,
        "legacy_protocol_findings": [] if passed else ["value0:xray"],
        "checks": checks,
    }


def sample_firstparty_production_authorization(*, passed: bool = True) -> dict:
    checks = {
        "endpoint_summary_ok": passed,
        "apply_packet_ok": passed,
        "secure_handoff_ok": passed,
        "rollout_packet_ok": passed,
        "preapply_readiness_ok": passed,
        "endpoint_fields_match_apply_and_handoff": passed,
        "approval_blocked_apply_packet": passed,
        "approval_blocked_handoff": passed,
        "approval_blocked_rollout": passed,
        "approval_blocked_preapply": passed,
        "mutation_blocked_all_packets": passed,
        "post_apply_validation_required": passed,
        "secure_material_handoff_required": passed,
        "handoff_dir_exists": passed,
        "handoff_archive_exists": passed,
        "handoff_manifest_exists": passed,
        "handoff_dir_outside_repo": passed,
        "handoff_archive_outside_repo": passed,
        "handoff_manifest_outside_repo": passed,
        "handoff_dir_private": passed,
        "handoff_archive_private": passed,
        "handoff_manifest_private": passed,
        "handoff_archive_hash_matches_summary": passed,
        "handoff_manifest_hash_matches_summary": passed,
        "handoff_summary_secret_free": passed,
        "all_evidence_fresh": passed,
        "manual_approval_still_required": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-production-authorization-test/summary.json",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "endpoint": {
            "host": "89.125.1.107" if passed else "127.0.0.1",
            "bind_host": "0.0.0.0" if passed else "127.0.0.1",
            "port": 40467,
            "transport": "tcp",
        },
        "evidence_paths": {
            "handoff_dir": "/home/user/.local/share/x0tta-firstparty-vpn/handoff",
            "handoff_archive": "/home/user/.local/share/x0tta-firstparty-vpn/handoff.tar.gz",
        },
        "evidence_hashes": {
            "endpoint_summary_sha256": "a" * 64,
            "apply_packet_summary_sha256": "b" * 64,
            "handoff_summary_sha256": "c" * 64,
            "rollout_summary_sha256": "d" * 64,
            "preapply_summary_sha256": "e" * 64,
            "handoff_archive_sha256": "f" * 64,
            "handoff_manifest_sha256": "1" * 64,
        },
        "handoff_dir_mode": "0700" if passed else "0755",
        "handoff_archive_mode": "0600" if passed else "0644",
        "handoff_manifest_mode": "0600" if passed else "0644",
        "checks": checks,
    }


def sample_firstparty_production_apply_runbook(*, passed: bool = True) -> dict:
    checks = {
        "authorization_ok": passed,
        "authorization_approval_guarded": passed,
        "authorization_no_mutation": True,
        "authorization_evidence_fresh": passed,
        "apply_packet_ok": passed,
        "apply_packet_hash_bound_to_authorization": passed,
        "handoff_summary_ok": passed,
        "handoff_summary_hash_bound_to_authorization": passed,
        "handoff_archive_exists": passed,
        "handoff_archive_private": passed,
        "handoff_archive_hash_bound_to_authorization": passed,
        "handoff_manifest_exists": passed,
        "handoff_manifest_private": passed,
        "handoff_manifest_hash_bound_to_authorization": passed,
        "handoff_manifest_secret_free": passed,
        "endpoint_external_shape": passed,
        "service_names_firstparty_only": passed,
        "precheck_commands_present": passed,
        "guarded_copy_command_present": passed,
        "guarded_apply_commands_present": passed,
        "post_apply_validation_commands_present": passed,
        "post_apply_evidence_paths_present": passed,
        "post_apply_validation_commands_capture_json": passed,
        "completion_audit_command_present": passed,
        "rollback_commands_present": passed,
        "mutating_commands_have_approval_guard": passed,
        "mutating_x0vpn_commands_have_allow_os_mutation": passed,
        "no_legacy_service_targets_in_commands": passed,
        "server_rollback_scope_firstparty_only": passed,
        "client_rollback_scope_firstparty_only": passed,
        "runbook_does_not_execute_commands": True,
        "approval_not_present": True,
        "production_mutation_blocked": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    approval_guard = (
        "APPROVAL=\"${APPROVAL:-}\"; test \"$APPROVAL\" = "
        "'APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT'"
    )
    command_ids = [
        ("verify_authorization_summary_hash", False, "sha256sum authz.json"),
        ("verify_apply_packet_hash", False, "sha256sum apply.json"),
        ("verify_handoff_summary_hash", False, "sha256sum handoff.json"),
        ("verify_handoff_archive_hash_and_mode", False, "sha256sum handoff.tar.gz"),
        ("verify_handoff_manifest_hash_and_mode", False, "sha256sum MANIFEST.secret-free.json"),
        ("verify_nl_port_still_free_readonly", False, "ssh nl ss -H -lnt '( sport = :40467 )'"),
        ("copy_handoff_to_nl_after_approval", True, f"{approval_guard} && rsync handoff nl:/root/x0tta-firstparty-vpn/"),
        (
            "install_server_service_after_approval",
            True,
            f"{approval_guard} && sudo python3 x0vpn_node.py install-server-service --allow-os-mutation",
        ),
        ("server_health_post_apply", False, "sudo python3 x0vpn_node.py server-health"),
        (
            "apply_client_config_after_approval",
            True,
            f"{approval_guard} && sudo python3 x0vpn_node.py install-client-service --allow-os-mutation",
        ),
        ("client_health_post_apply", False, "sudo python3 x0vpn_node.py client-health"),
        ("client_doctor_post_apply", False, "sudo python3 x0vpn_node.py client-doctor"),
        (
            "build_completion_audit_after_post_apply",
            False,
            "python3 nl-diagnostics/build_firstparty_production_completion_audit.py --write --json",
        ),
        (
            "rollback_client_policy_and_service_after_approval",
            True,
            f"{approval_guard} && sudo python3 x0vpn_node.py client-policy-rollback --allow-os-mutation",
        ),
        (
            "rollback_server_service_after_approval",
            True,
            f"{approval_guard} && sudo python3 x0vpn_node.py uninstall-server-service --allow-os-mutation",
        ),
    ]
    if not passed:
        checks["rollback_commands_present"] = False
        command_ids = command_ids[:-1]
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-production-apply-runbook-test/summary.json",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "service_names": {
            "server": "x0tta-firstparty-vpn.service",
            "client": "x0tta-firstparty-vpn-client.service",
        },
        "post_apply_evidence_paths": {
            "evidence_dir": "/mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence-test",
            "server_health_local_path": "/mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence-test/server-health.json",
            "client_health_local_path": "/mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence-test/client-health.json",
            "client_doctor_local_path": "/mnt/projects/nl-diagnostics/firstparty-production-postapply-evidence-test/client-doctor.json",
        },
        "evidence_hashes": {
            "authorization_summary_sha256": "2" * 64,
            "apply_packet_summary_sha256": "3" * 64,
            "handoff_summary_sha256": "4" * 64,
            "handoff_archive_sha256": "5" * 64,
            "handoff_manifest_sha256": "6" * 64,
        },
        "commands": [
            {
                "id": item_id,
                "mutation": mutation,
                "approval_required": mutation,
                "command": command,
            }
            for item_id, mutation, command in command_ids
        ],
        "legacy_command_findings": [] if passed else ["rollback_server_service_after_approval:xray"],
        "checks": checks,
    }


def sample_firstparty_production_operator_script(*, passed: bool = True) -> dict:
    checks = {
        "runbook_summary_ok": passed,
        "runbook_hash_present": passed,
        "runbook_approval_guarded": passed,
        "runbook_no_mutation": True,
        "required_apply_commands_present": passed,
        "required_rollback_commands_present": passed,
        "apply_script_excludes_rollback": passed,
        "rollback_script_contains_only_rollback": passed,
        "mutating_commands_guarded": passed,
        "commands_syntax_ok": passed,
        "apply_script_syntax_ok": passed,
        "rollback_script_syntax_ok": passed,
        "scripts_default_dry_run": passed,
        "scripts_require_approval_to_execute": passed,
        "scripts_hash_bound_to_runbook": passed,
        "scripts_log_self_hash_meta": passed,
        "no_legacy_commands": passed,
        "operator_builder_does_not_execute_commands": True,
        "no_nl_or_spb_writes_performed": True,
        "script_files_written_executable_not_group_world_writable": passed,
        "script_file_hashes_match_preview": passed,
    }
    failed_checks = sorted(name for name, ok in checks.items() if ok is not True)
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-production-operator-script-test/summary.json",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "runbook_summary_path": "nl-diagnostics/firstparty-production-apply-runbook-test/summary.json",
        "runbook_summary_sha256": "7" * 64 if passed else "missing",
        "script_paths": {
            "apply": "/mnt/projects/nl-diagnostics/firstparty-production-operator-script-test/apply-firstparty-production.sh",
            "rollback": "/mnt/projects/nl-diagnostics/firstparty-production-operator-script-test/rollback-firstparty-production.sh",
        },
        "script_file_modes": {
            "apply": "0755" if passed else "0777",
            "rollback": "0755" if passed else "0777",
        },
        "script_file_hashes": {
            "apply_script_sha256": "8" * 64 if passed else "missing",
            "rollback_script_sha256": "9" * 64 if passed else "missing",
        },
        "apply_command_count": 13 if passed else 12,
        "rollback_command_count": 2 if passed else 1,
        "mutating_command_count": 5,
        "legacy_command_findings": [] if passed else ["install_server_service_after_approval:xray"],
        "failed_checks": failed_checks,
        "checks": checks,
    }


def sample_firstparty_production_operator_dryrun_audit(*, passed: bool = True) -> dict:
    checks = {
        "operator_summary_ok": passed,
        "operator_summary_no_mutation": True,
        "operator_summary_approval_guarded": passed,
        "script_paths_present": passed,
        "script_hashes_match_summary": passed,
        "scripts_syntax_ok": passed,
        "dryrun_env_safe": True,
        "apply_dryrun_exit_zero": passed,
        "rollback_dryrun_exit_zero": passed,
        "apply_transcript_complete": passed,
        "rollback_transcript_complete": passed,
        "apply_transcript_excludes_rollback": passed,
        "rollback_transcript_contains_only_rollback": passed,
        "dryrun_transcripts_have_no_finish_events": passed,
        "apply_transcript_meta_present": passed,
        "rollback_transcript_meta_present": passed,
        "apply_transcript_meta_role_apply": passed,
        "rollback_transcript_meta_role_rollback": passed,
        "apply_transcript_meta_execute_disabled": passed,
        "rollback_transcript_meta_execute_disabled": passed,
        "apply_transcript_meta_dry_run_enabled": passed,
        "rollback_transcript_meta_dry_run_enabled": passed,
        "apply_transcript_meta_approval_not_ok": passed,
        "rollback_transcript_meta_approval_not_ok": passed,
        "apply_transcript_meta_runbook_hash_matches": passed,
        "rollback_transcript_meta_runbook_hash_matches": passed,
        "apply_transcript_meta_script_hash_matches": passed,
        "rollback_transcript_meta_script_hash_matches": passed,
        "guard_blocks_execute_without_dryrun_pair": passed,
        "guard_blocks_wrong_approval": passed,
        "guard_checks_do_not_start_steps": passed,
        "no_legacy_command_findings": passed,
        "audit_only_runs_dryrun_scripts": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, ok in checks.items() if ok is not True)
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-production-operator-dryrun-audit-test/summary.json",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "operator_summary_path": "nl-diagnostics/firstparty-production-operator-script-test/summary.json",
        "transcript_paths": {
            "apply": "/mnt/projects/nl-diagnostics/firstparty-production-operator-dryrun-audit-test/apply-dryrun.jsonl",
            "rollback": "/mnt/projects/nl-diagnostics/firstparty-production-operator-dryrun-audit-test/rollback-dryrun.jsonl",
            "guard_requires_pair": "/mnt/projects/nl-diagnostics/firstparty-production-operator-dryrun-audit-test/guard-requires-execute-and-dryrun.jsonl",
            "guard_requires_approval": "/mnt/projects/nl-diagnostics/firstparty-production-operator-dryrun-audit-test/guard-requires-approval.jsonl",
        },
        "dryrun_results": {
            "apply": {"exit_code": 0 if passed else 1, "event_count": 27 if passed else 0},
            "rollback": {"exit_code": 0 if passed else 1, "event_count": 5 if passed else 0},
        },
        "guard_results": {
            "execute_without_dryrun_pair": {"exit_code": 41 if passed else 0, "event_count": 0},
            "wrong_approval": {"exit_code": 42 if passed else 0, "event_count": 0},
        },
        "failed_checks": failed_checks,
        "checks": checks,
    }


def sample_firstparty_production_apply_transcript_audit(*, passed: bool = True) -> dict:
    checks = {
        "operator_summary_ok": passed,
        "operator_summary_approval_guarded": passed,
        "operator_summary_no_mutation": True,
        "apply_script_path_present": passed,
        "rollback_script_path_present": passed,
        "apply_script_hash_matches_summary": passed,
        "rollback_script_hash_matches_summary": passed,
        "apply_script_syntax_ok": passed,
        "rollback_script_syntax_ok": passed,
        "apply_transcript_present": passed,
        "apply_transcript_nonempty": passed,
        "apply_transcript_all_expected_starts_present": passed,
        "apply_transcript_all_expected_finishes_rc0": passed,
        "apply_transcript_no_dry_run_events": passed,
        "apply_transcript_excludes_rollback_steps": passed,
        "apply_transcript_no_failed_finishes": passed,
        "apply_transcript_has_only_expected_apply_steps": passed,
        "apply_transcript_meta_present": passed,
        "apply_transcript_meta_role_apply": passed,
        "apply_transcript_meta_execute_enabled": passed,
        "apply_transcript_meta_dry_run_disabled": passed,
        "apply_transcript_meta_approval_ok": passed,
        "apply_transcript_meta_runbook_hash_matches": passed,
        "apply_transcript_meta_script_hash_matches": passed,
        "audit_does_not_execute_commands": True,
        "os_mutation_not_performed_by_audit": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, ok in checks.items() if ok is not True)
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-production-apply-transcript-audit-test/summary.json",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "manual_approval_still_required": True,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "apply_execution_proven": passed,
        "operator_summary_path": "nl-diagnostics/firstparty-production-operator-script-test/summary.json",
        "apply_transcript_path": "/mnt/projects/nl-diagnostics/firstparty-production-operator-transcripts/test/apply-execution.jsonl",
        "failed_checks": failed_checks,
        "checks": checks,
    }


def sample_firstparty_production_completion_audit(*, passed: bool = True) -> dict:
    checks = {
        "runbook_summary_ok": True,
        "runbook_approval_guarded": True,
        "runbook_required_checks_ok": True,
        "runbook_required_commands_present": True,
        "runbook_no_legacy_commands": True,
        "completion_evidence_present": passed,
        "server_health_evidence_present": passed,
        "server_health_ok": passed,
        "client_health_evidence_present": passed,
        "client_health_ok": passed,
        "client_doctor_evidence_present": passed,
        "client_doctor_ok": passed,
        "client_doctor_requires_installed_health": passed,
        "endpoint_matches_runbook": passed,
        "service_names_match": passed,
        "post_apply_evidence_no_os_mutation": True,
        "audit_does_not_execute_commands": True,
        "no_nl_or_spb_writes_performed": True,
    }
    failed_checks = sorted(name for name, ok in checks.items() if ok is not True)
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-production-completion-audit-test/summary.json",
        "completion_decision": (
            "FIRSTPARTY_VPN_PRODUCTION_COMPLETE"
            if passed
            else "FIRSTPARTY_VPN_PRODUCTION_NOT_PROVEN"
        ),
        "goal_completion_claim_allowed": passed,
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "production_apply_still_required": not passed,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "required_operator_evidence_commands": {
            "server_health_post_apply": "sudo python3 x0vpn_node.py server-health --json",
            "client_health_post_apply": "sudo python3 x0vpn_node.py client-health --json",
            "client_doctor_post_apply": "sudo python3 x0vpn_node.py client-doctor --json",
        },
        "rollback_commands": {
            "client": (
                "APPROVAL=APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT "
                "sudo python3 x0vpn_node.py client-policy-rollback --allow-os-mutation"
            ),
            "server": (
                "APPROVAL=APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT "
                "sudo python3 x0vpn_node.py uninstall-server-service --allow-os-mutation"
            ),
        },
        "server_failed_required_checks": [] if passed else ["server_tun_route_nat_dns"],
        "client_failed_required_checks": [] if passed else ["client_tun_route_dns"],
        "client_doctor_failed_required_checks": [] if passed else ["installed_client_health"],
        "failed_checks": failed_checks,
        "checks": checks,
    }


def sample_firstparty_preapply_readiness(*, passed: bool = True) -> dict:
    checks = {
        "rollout_packet_ok": passed,
        "rollout_packet_mutation_blocked": passed,
        "rollout_packet_no_nl_spb_writes": passed,
        "approval_phrase_expected": passed,
        "approval_not_present": passed,
        "manifest_nl_write_allowed_false": passed,
        "manifest_not_deployable_to_nl": passed,
        "firstparty_service_names_unique": passed,
        "firstparty_service_names_scoped": passed,
        "firstparty_unit_paths_scoped": passed,
        "firstparty_config_targets_scoped": passed,
        "firstparty_server_client_targets_distinct": passed,
        "legacy_service_markers_absent": passed,
        "source_post_apply_validation_ready": passed,
        "preapply_packet_does_not_authorize_mutation": True,
        "os_mutation_not_performed": True,
        "no_nl_or_spb_writes_performed": True,
    }
    source_checks = {
        "build_linux_post_apply_validator": passed,
        "executor_requires_post_apply_validation": passed,
        "collect_linux_applied_state_snapshot": passed,
        "evaluate_linux_applied_state": passed,
        "applied_state_checks_tun_routes_dns_nat": passed,
    }
    return {
        "ok": passed,
        "summary_path": "nl-diagnostics/firstparty-preapply-readiness-test/summary.json",
        "deployment_epoch": "local-firstparty-staging-packet-test",
        "approval_phrase_required": "APPLY_FIRSTPARTY_VPN_PRODUCTION_ROLLOUT",
        "approval_present": False,
        "production_mutation_allowed": False,
        "os_mutation_performed": False,
        "no_nl_or_spb_writes_performed": True,
        "server_service_name": "x0tta-firstparty-vpn.service",
        "client_service_name": "x0tta-firstparty-vpn-client.service",
        "legacy_service_findings": [] if passed else ["value0:xray"],
        "checks": checks,
        "source_checks": source_checks,
    }


def sample_firstparty_no_foreign(*, passed: bool = True) -> dict:
    tree_hash = "b" * 64
    return {
        "precomputed": True,
        "source_audit_passed": passed,
        "source_audit_reasons": []
        if passed
        else ["firstparty_foreign_protocol_marker_detected"],
        "source_audit_scanned_files": 37 if passed else 37,
        "current_source_tree_hash": tree_hash,
        "canary_source_tree_hash": tree_hash,
        "production_readiness_source_tree_hash": tree_hash,
    }


def sample_monitor_restore_readiness(*, passed: bool = True) -> dict:
    return {
        "decision": (
            "MONITOR_RESTORE_READY_FOR_APPROVAL"
            if passed
            else "MONITOR_RESTORE_NOT_READY"
        ),
        "ready_for_approval": passed,
        "apply_allowed_now": False,
        "approval_required": True,
        "approval_phrase": "APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER",
        "no_nl_or_spb_writes_performed": True,
    }


def sample_inputs(*, complete: bool = False) -> dict:
    return {
        "firstparty_core": sample_firstparty_core(),
        "firstparty_canary": sample_firstparty_canary(),
        "firstparty_production_readiness": sample_firstparty_production_readiness(),
        "firstparty_staging_packet": sample_firstparty_staging_packet(),
        "firstparty_production_endpoint": sample_firstparty_production_endpoint(),
        "firstparty_production_apply_packet": sample_firstparty_production_apply_packet(),
        "firstparty_secure_material_handoff": sample_firstparty_secure_material_handoff(),
        "firstparty_production_authorization": sample_firstparty_production_authorization(),
        "firstparty_production_apply_runbook": sample_firstparty_production_apply_runbook(),
        "firstparty_production_operator_script": sample_firstparty_production_operator_script(),
        "firstparty_production_operator_dryrun_audit": sample_firstparty_production_operator_dryrun_audit(),
        "firstparty_production_apply_transcript_audit": sample_firstparty_production_apply_transcript_audit(),
        "firstparty_production_completion_audit": sample_firstparty_production_completion_audit(),
        "firstparty_rollout_packet": sample_firstparty_rollout_packet(),
        "firstparty_preapply_readiness": sample_firstparty_preapply_readiness(),
        "firstparty_no_foreign": sample_firstparty_no_foreign(),
        "decision": sample_decision(),
        "anti_block_audit": sample_anti_block_audit(complete=complete),
        "client_matrix": sample_matrix(complete=complete),
        "remote_request": sample_remote_request(complete=complete),
        "telegram_warp_plan": sample_warp_plan(),
        "monitor_restore_readiness": sample_monitor_restore_readiness(),
        "readiness_audit": sample_readiness(),
        "manifest": sample_manifest(),
        "preflight": sample_preflight(),
    }


class VpnGoalStatusTests(unittest.TestCase):
    def test_firstparty_core_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        core = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-CORE-01")
        self.assertEqual(core["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(core["ok"])
        self.assertIn("source_audit_passed=true", core["evidence"])
        self.assertIn("wire_magic_x0vpn001_present=true", core["evidence"])

    def test_firstparty_core_source_audit_failure_blocks_goal(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_core"] = sample_firstparty_core(passed=False)

        payload = goal_status.build_payload(inputs)

        core = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-CORE-01")
        self.assertFalse(payload["goal_complete"])
        self.assertEqual(core["status"], goal_status.MISSING)
        self.assertIn("source_audit_passed=false", core["evidence"])

    def test_firstparty_live_canary_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        canary = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-CANARY-01")
        self.assertEqual(canary["status"], goal_status.PASS)
        self.assertTrue(canary["ok"])
        self.assertIn("canary_ok=true", canary["evidence"])
        self.assertIn("tun_dataplane_failed_reasons=none", canary["evidence"])

    def test_firstparty_live_canary_failure_blocks_goal(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_canary"] = sample_firstparty_canary(passed=False)

        payload = goal_status.build_payload(inputs)

        canary = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-CANARY-01")
        self.assertFalse(payload["goal_complete"])
        self.assertEqual(canary["status"], goal_status.MISSING)
        self.assertIn("failed_checks=", "\n".join(canary["evidence"]))

    def test_firstparty_production_readiness_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        readiness = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-PROD-READY-01")
        self.assertEqual(readiness["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(readiness["ok"])
        self.assertIn("decision_allowed=true", readiness["evidence"])
        self.assertIn("pqc_provider_gate_reasons=none", readiness["evidence"])

    def test_firstparty_production_readiness_failure_blocks_goal(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_production_readiness"] = sample_firstparty_production_readiness(
            passed=False
        )

        payload = goal_status.build_payload(inputs)

        readiness = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-PROD-READY-01")
        self.assertFalse(payload["goal_complete"])
        self.assertEqual(readiness["status"], goal_status.MISSING)
        self.assertIn("decision_reasons=pqc_provider_gate_failed", readiness["evidence"])

    def test_firstparty_staging_packet_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        staging = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-STAGING-PACKET-01")
        self.assertEqual(staging["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(staging["ok"])
        self.assertIn("staging_ok=true", staging["evidence"])
        self.assertIn("client_kit_count=2", staging["evidence"])
        self.assertIn("raw_secret_material_stored_in_evidence=false", staging["evidence"])

    def test_firstparty_staging_packet_failure_blocks_goal(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_staging_packet"] = sample_firstparty_staging_packet(passed=False)

        payload = goal_status.build_payload(inputs)

        staging = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-STAGING-PACKET-01")
        self.assertFalse(payload["goal_complete"])
        self.assertEqual(staging["status"], goal_status.MISSING)
        self.assertIn("kit_counts_ok=false", staging["evidence"])

    def test_firstparty_rollout_packet_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        rollout = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-ROLLOUT-PACKET-01")
        self.assertEqual(rollout["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(rollout["ok"])
        self.assertIn("approval_guarded=true", rollout["evidence"])
        self.assertIn("checks_passed=true", rollout["evidence"])
        self.assertIn("kit_counts_ok=true", rollout["evidence"])

    def test_firstparty_rollout_packet_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_rollout_packet"] = sample_firstparty_rollout_packet(passed=False)

        payload = goal_status.build_payload(inputs)

        rollout = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-ROLLOUT-PACKET-01")
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(rollout["status"], goal_status.MISSING)
        self.assertIn(
            "rebuild first-party rollout packet; service plans, dry-run apply, rollback, signed kits, and no-legacy checks must pass",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_production_endpoint_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        endpoint = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-PRODUCTION-ENDPOINT-01")
        self.assertEqual(endpoint["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(endpoint["ok"])
        self.assertIn("host=89.125.1.107", endpoint["evidence"])
        self.assertIn("bind_host=0.0.0.0", endpoint["evidence"])
        self.assertIn("candidate_port_free_on_nl_snapshot=true", endpoint["evidence"])

    def test_firstparty_production_endpoint_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_production_endpoint"] = sample_firstparty_production_endpoint(
            passed=False
        )

        payload = goal_status.build_payload(inputs)

        endpoint = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-PRODUCTION-ENDPOINT-01")
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(endpoint["status"], goal_status.MISSING)
        self.assertIn(
            "rebuild production endpoint packet with non-loopback bind, public host, free NL port, and first-party-only units",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_production_apply_packet_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        apply_packet = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-APPLY-PACKET-01"
        )
        self.assertEqual(apply_packet["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(apply_packet["ok"])
        self.assertIn("host=89.125.1.107", apply_packet["evidence"])
        self.assertIn("server_apply_dry_run_ok=true", apply_packet["evidence"])
        self.assertIn("client_apply_dry_run_ok=true", apply_packet["evidence"])
        self.assertIn("secure_material_handoff_required=true", apply_packet["evidence"])

    def test_firstparty_production_apply_packet_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_production_apply_packet"] = (
            sample_firstparty_production_apply_packet(passed=False)
        )

        payload = goal_status.build_payload(inputs)

        apply_packet = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-APPLY-PACKET-01"
        )
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(apply_packet["status"], goal_status.MISSING)
        self.assertIn("external_shape_ok=false", apply_packet["evidence"])
        self.assertIn(
            "rebuild production apply packet from the external endpoint; dry-run apply, signed kits, approval block, and secret-free evidence must pass",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_secure_material_handoff_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        handoff = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-SECURE-MATERIAL-HANDOFF-01"
        )
        self.assertEqual(handoff["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(handoff["ok"])
        self.assertIn("handoff_dir_mode=0700", handoff["evidence"])
        self.assertIn("handoff_archive_mode=0600", handoff["evidence"])
        self.assertIn("private_handoff_ready=true", handoff["evidence"])
        self.assertIn("kit_counts_ok=true", handoff["evidence"])

    def test_firstparty_secure_material_handoff_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_secure_material_handoff"] = (
            sample_firstparty_secure_material_handoff(passed=False)
        )

        payload = goal_status.build_payload(inputs)

        handoff = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-SECURE-MATERIAL-HANDOFF-01"
        )
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(handoff["status"], goal_status.MISSING)
        self.assertIn("handoff_dir_mode=0755", handoff["evidence"])
        self.assertIn("private_handoff_ready=false", handoff["evidence"])
        self.assertIn(
            "rebuild secure handoff outside repo; private modes, signed kits, source tree, dry-run apply, and secret-free evidence must pass",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_production_authorization_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        authz = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-AUTHZ-01"
        )
        self.assertEqual(authz["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(authz["ok"])
        self.assertIn("checks_passed=true", authz["evidence"])
        self.assertIn("all_evidence_fresh=true", authz["evidence"])
        self.assertIn("handoff_archive_hash_matches_summary=true", authz["evidence"])
        self.assertIn("manual_approval_still_required=true", authz["evidence"])

    def test_firstparty_production_authorization_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_production_authorization"] = (
            sample_firstparty_production_authorization(passed=False)
        )

        payload = goal_status.build_payload(inputs)

        authz = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-AUTHZ-01"
        )
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(authz["status"], goal_status.MISSING)
        self.assertIn("all_evidence_fresh=false", authz["evidence"])
        self.assertIn("handoff_archive_mode=0644", authz["evidence"])
        self.assertIn(
            "rebuild first-party production authorization packet; endpoint/apply/handoff/rollout/preapply evidence, hashes, freshness, and approval block must pass",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_production_apply_runbook_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        runbook = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-RUNBOOK-01"
        )
        self.assertEqual(runbook["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(runbook["ok"])
        self.assertIn("approval_guarded=true", runbook["evidence"])
        self.assertIn("post_apply_validation_commands_present=true", runbook["evidence"])
        self.assertIn("post_apply_evidence_paths_present=true", runbook["evidence"])
        self.assertIn("post_apply_validation_commands_capture_json=true", runbook["evidence"])
        self.assertIn("completion_audit_command_present=true", runbook["evidence"])
        self.assertIn("rollback_commands_present=true", runbook["evidence"])
        self.assertIn("runbook_does_not_execute_commands=true", runbook["evidence"])
        self.assertIn("legacy_command_findings=none", runbook["evidence"])

    def test_firstparty_production_apply_runbook_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_production_apply_runbook"] = (
            sample_firstparty_production_apply_runbook(passed=False)
        )

        payload = goal_status.build_payload(inputs)

        runbook = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-RUNBOOK-01"
        )
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(runbook["status"], goal_status.MISSING)
        self.assertIn("rollback_commands_present=false", runbook["evidence"])
        self.assertIn("legacy_command_findings=rollback_server_service_after_approval:xray", runbook["evidence"])
        self.assertIn(
            "rebuild first-party production apply runbook; approval guard, rollback, post-apply validation, handoff hashes, and no-legacy command scope must pass",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_production_operator_script_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        operator_script = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-OPERATOR-SCRIPT-01"
        )
        self.assertEqual(operator_script["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(operator_script["ok"])
        self.assertIn("operator_script_ok=true", operator_script["evidence"])
        self.assertIn("scripts_default_dry_run=true", operator_script["evidence"])
        self.assertIn("scripts_require_approval_to_execute=true", operator_script["evidence"])
        self.assertIn("scripts_hash_bound_to_runbook=true", operator_script["evidence"])
        self.assertIn("scripts_log_self_hash_meta=true", operator_script["evidence"])
        self.assertIn("apply_script_excludes_rollback=true", operator_script["evidence"])
        self.assertIn("rollback_script_contains_only_rollback=true", operator_script["evidence"])
        self.assertIn("modes_not_group_world_writable=true", operator_script["evidence"])
        self.assertIn("legacy_command_findings=none", operator_script["evidence"])

    def test_firstparty_production_operator_script_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_production_operator_script"] = (
            sample_firstparty_production_operator_script(passed=False)
        )

        payload = goal_status.build_payload(inputs)

        operator_script = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-OPERATOR-SCRIPT-01"
        )
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(operator_script["status"], goal_status.MISSING)
        self.assertIn("scripts_default_dry_run=false", operator_script["evidence"])
        self.assertIn("modes_not_group_world_writable=false", operator_script["evidence"])
        self.assertIn("legacy_command_findings=install_server_service_after_approval:xray", operator_script["evidence"])
        self.assertIn(
            "rebuild first-party production operator scripts from the latest guarded runbook; scripts must be dry-run by default, approval-gated, hash-bound, rollback-separated, and legacy-free",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_production_operator_dryrun_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        dryrun = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-OPERATOR-DRYRUN-01"
        )
        self.assertEqual(dryrun["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(dryrun["ok"])
        self.assertIn("dryrun_ok=true", dryrun["evidence"])
        self.assertIn("apply_exit_code=0", dryrun["evidence"])
        self.assertIn("rollback_exit_code=0", dryrun["evidence"])
        self.assertIn("guard_pair_exit_code=41", dryrun["evidence"])
        self.assertIn("guard_approval_exit_code=42", dryrun["evidence"])
        self.assertIn("apply_transcript_complete=true", dryrun["evidence"])
        self.assertIn("rollback_transcript_complete=true", dryrun["evidence"])
        self.assertIn("dryrun_transcripts_have_no_finish_events=true", dryrun["evidence"])
        self.assertIn("apply_transcript_meta_present=true", dryrun["evidence"])
        self.assertIn("rollback_transcript_meta_present=true", dryrun["evidence"])
        self.assertIn("apply_transcript_meta_execute_disabled=true", dryrun["evidence"])
        self.assertIn("rollback_transcript_meta_dry_run_enabled=true", dryrun["evidence"])
        self.assertIn("apply_transcript_meta_script_hash_matches=true", dryrun["evidence"])
        self.assertIn("rollback_transcript_meta_script_hash_matches=true", dryrun["evidence"])
        self.assertIn("guard_checks_do_not_start_steps=true", dryrun["evidence"])

    def test_firstparty_production_operator_dryrun_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_production_operator_dryrun_audit"] = (
            sample_firstparty_production_operator_dryrun_audit(passed=False)
        )

        payload = goal_status.build_payload(inputs)

        dryrun = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-OPERATOR-DRYRUN-01"
        )
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(dryrun["status"], goal_status.MISSING)
        self.assertIn("apply_exit_code=1", dryrun["evidence"])
        self.assertIn("guard_pair_exit_code=0", dryrun["evidence"])
        self.assertIn("apply_transcript_complete=false", dryrun["evidence"])
        self.assertIn(
            "rerun first-party production operator scripts in dry-run mode and verify transcripts plus pre-step approval guard failures",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_production_apply_transcript_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        transcript = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-APPLY-TRANSCRIPT-01"
        )
        self.assertEqual(transcript["status"], goal_status.PASS)
        self.assertTrue(transcript["ok"])
        self.assertIn("transcript_ok=true", transcript["evidence"])
        self.assertIn("apply_execution_proven=true", transcript["evidence"])
        self.assertIn("apply_transcript_present=true", transcript["evidence"])
        self.assertIn("apply_transcript_all_expected_finishes_rc0=true", transcript["evidence"])
        self.assertIn("apply_transcript_no_dry_run_events=true", transcript["evidence"])
        self.assertIn("apply_transcript_excludes_rollback_steps=true", transcript["evidence"])
        self.assertIn("apply_transcript_meta_present=true", transcript["evidence"])
        self.assertIn("apply_transcript_meta_execute_enabled=true", transcript["evidence"])
        self.assertIn("apply_transcript_meta_dry_run_disabled=true", transcript["evidence"])
        self.assertIn("apply_transcript_meta_approval_ok=true", transcript["evidence"])
        self.assertIn("apply_transcript_meta_runbook_hash_matches=true", transcript["evidence"])
        self.assertIn("apply_transcript_meta_script_hash_matches=true", transcript["evidence"])
        self.assertIn("apply_script_hash_matches_summary=true", transcript["evidence"])

    def test_firstparty_production_apply_transcript_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_production_apply_transcript_audit"] = (
            sample_firstparty_production_apply_transcript_audit(passed=False)
        )

        payload = goal_status.build_payload(inputs)

        transcript = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-APPLY-TRANSCRIPT-01"
        )
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(transcript["status"], goal_status.MISSING)
        self.assertIn("apply_execution_proven=false", transcript["evidence"])
        self.assertIn("apply_transcript_present=false", transcript["evidence"])
        self.assertIn("apply_transcript_no_dry_run_events=false", transcript["evidence"])
        self.assertIn("apply_transcript_meta_present=false", transcript["evidence"])
        self.assertIn("apply_transcript_meta_approval_ok=false", transcript["evidence"])
        self.assertIn(
            "run the generated apply script only after explicit approval and audit its apply-execution transcript; meta must prove EXECUTE=1, DRY_RUN=0, approval_ok=true, matching runbook/script hashes, and all apply steps must finish rc=0 without dry-run or rollback events",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_production_completion_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        completion = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-COMPLETION-01"
        )
        self.assertEqual(completion["status"], goal_status.PASS)
        self.assertTrue(completion["ok"])
        self.assertIn("completion_ok=true", completion["evidence"])
        self.assertIn(
            "completion_decision=FIRSTPARTY_VPN_PRODUCTION_COMPLETE",
            completion["evidence"],
        )
        self.assertIn("completion_evidence_present=true", completion["evidence"])
        self.assertIn("server_health_ok=true", completion["evidence"])
        self.assertIn("client_health_ok=true", completion["evidence"])
        self.assertIn("client_doctor_ok=true", completion["evidence"])
        self.assertIn("endpoint_matches_runbook=true", completion["evidence"])
        self.assertIn("service_names_match=true", completion["evidence"])

    def test_firstparty_production_completion_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_production_completion_audit"] = (
            sample_firstparty_production_completion_audit(passed=False)
        )

        payload = goal_status.build_payload(inputs)

        completion = next(
            row
            for row in payload["requirements"]
            if row["id"] == "FIRSTPARTY-PRODUCTION-COMPLETION-01"
        )
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(payload["firstparty_decision"], "FIRSTPARTY_VPN_PRODUCTION_NOT_PROVEN")
        self.assertEqual(completion["status"], goal_status.MISSING)
        self.assertIn("completion_evidence_present=false", completion["evidence"])
        self.assertIn("server_health_ok=false", completion["evidence"])
        self.assertIn("client_health_ok=false", completion["evidence"])
        self.assertIn("client_doctor_ok=false", completion["evidence"])
        self.assertIn(
            "collect post-apply server-health, client-health, and client-doctor JSON from the guarded first-party production runbook, then rebuild completion audit",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_preapply_readiness_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        preapply = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-PREAPPLY-READY-01")
        self.assertEqual(preapply["status"], goal_status.READY_TO_STAGE)
        self.assertTrue(preapply["ok"])
        self.assertIn("approval_guarded=true", preapply["evidence"])
        self.assertIn("source_checks_passed=true", preapply["evidence"])
        self.assertIn("legacy_service_findings=none", preapply["evidence"])

    def test_firstparty_preapply_readiness_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_preapply_readiness"] = sample_firstparty_preapply_readiness(
            passed=False
        )

        payload = goal_status.build_payload(inputs)

        preapply = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-PREAPPLY-READY-01")
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(preapply["status"], goal_status.MISSING)
        self.assertIn(
            "rebuild first-party pre-apply readiness; approval, scoped services, manifest gate, and post-apply validator must all pass",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_firstparty_no_foreign_evidence_is_visible(self):
        payload = goal_status.build_payload(sample_inputs())

        no_foreign = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-NO-FOREIGN-01")
        self.assertEqual(no_foreign["status"], goal_status.PASS)
        self.assertTrue(no_foreign["ok"])
        self.assertIn("source_audit_passed=true", no_foreign["evidence"])
        self.assertIn(
            "legacy_requirements_non_blocking_for_firstparty_goal=true",
            no_foreign["evidence"],
        )

    def test_firstparty_no_foreign_failure_blocks_firstparty_build(self):
        inputs = sample_inputs(complete=True)
        inputs["firstparty_no_foreign"] = sample_firstparty_no_foreign(passed=False)

        payload = goal_status.build_payload(inputs)

        no_foreign = next(row for row in payload["requirements"] if row["id"] == "FIRSTPARTY-NO-FOREIGN-01")
        self.assertFalse(payload["goal_complete"])
        self.assertFalse(payload["firstparty_build_complete"])
        self.assertEqual(no_foreign["status"], goal_status.MISSING)
        self.assertIn(
            "rerun first-party source audit and refresh local canary/readiness evidence from the same source tree",
            payload["firstparty_remaining_before_build_complete"],
        )

    def test_legacy_gates_do_not_block_firstparty_build(self):
        payload = goal_status.build_payload(sample_inputs())

        self.assertFalse(payload["goal_complete"])
        self.assertTrue(payload["firstparty_build_complete"])
        self.assertEqual(
            payload["firstparty_requirements_passed"],
            payload["firstparty_requirements_total"],
        )
        self.assertEqual(payload["firstparty_remaining_before_build_complete"], [])
        self.assertTrue(payload["legacy_requirements_non_blocking_for_firstparty_goal"])
        self.assertIn("ANTIBLOCK-CLIENTS-01", payload["legacy_foreign_requirement_ids"])

    def test_partial_client_matrix_keeps_goal_incomplete(self):
        payload = goal_status.build_payload(sample_inputs())

        self.assertEqual(payload["decision"], "VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE")
        self.assertFalse(payload["goal_complete"])
        anti_block = next(row for row in payload["requirements"] if row["id"] == "ANTIBLOCK-CLIENTS-01")
        self.assertEqual(anti_block["status"], goal_status.BLOCKED_EXTERNAL_EVIDENCE)
        self.assertIn("remote_request_ready=true", anti_block["evidence"])
        self.assertIn("remote_request_validate_commands_no_write=true", anti_block["evidence"])
        self.assertIn("remote_request_hash_binding_policy_ok=true", anti_block["evidence"])
        self.assertIn("remote_request_reply_commands_hash_guard_ok=true", anti_block["evidence"])
        self.assertIn("remote_request_reply_dry_run_uses_packet_hash=true", anti_block["evidence"])
        self.assertEqual(
            anti_block["next_step"],
            "collect the privacy-safe remote request-packet reports and record short replies",
        )
        self.assertIn("record Android Happ/Hiddify client evidence after rollout", payload["remaining_before_goal_complete"])

    def test_missing_remote_request_is_visible_in_client_evidence_requirement(self):
        inputs = sample_inputs()
        inputs["remote_request"] = {}

        payload = goal_status.build_payload(inputs)

        anti_block = next(row for row in payload["requirements"] if row["id"] == "ANTIBLOCK-CLIENTS-01")
        self.assertIn("remote_request_ready=false", anti_block["evidence"])
        self.assertEqual(
            anti_block["next_step"],
            "record safe real-client evidence for Android Happ/Hiddify, mobile network, and restricted/work Wi-Fi",
        )

    def test_remote_request_without_nonwriting_validate_commands_is_not_ready(self):
        inputs = sample_inputs()
        request = inputs["remote_request"]
        request["requests"][0]["operator_reply_validate_pass_command"] = request["requests"][0][
            "operator_reply_record_pass_command"
        ]

        payload = goal_status.build_payload(inputs)

        anti_block = next(row for row in payload["requirements"] if row["id"] == "ANTIBLOCK-CLIENTS-01")
        self.assertIn("remote_request_contract_ready=true", anti_block["evidence"])
        self.assertIn("remote_request_ready=false", anti_block["evidence"])
        self.assertIn("remote_request_validate_commands_no_write=false", anti_block["evidence"])
        self.assertEqual(
            anti_block["next_step"],
            "regenerate remote request packet with stdin record commands, non-writing validate commands, and packet hash guard",
        )

    def test_remote_request_without_packet_hash_guard_is_not_ready(self):
        inputs = sample_inputs()
        request = inputs["remote_request"]
        request["request_packet_hash_binding_policy"] = "missing"
        request["requests"][0]["operator_reply_record_pass_command"] = request["requests"][0][
            "operator_reply_record_pass_command"
        ].replace("--expect-request-packet-sha256", "--missing-packet-hash")

        payload = goal_status.build_payload(inputs)

        anti_block = next(row for row in payload["requirements"] if row["id"] == "ANTIBLOCK-CLIENTS-01")
        self.assertIn("remote_request_ready=false", anti_block["evidence"])
        self.assertIn("remote_request_hash_binding_policy_ok=false", anti_block["evidence"])
        self.assertIn("remote_request_reply_commands_hash_guard_ok=false", anti_block["evidence"])
        self.assertEqual(
            anti_block["next_step"],
            "regenerate remote request packet with stdin record commands, non-writing validate commands, and packet hash guard",
        )

    def test_remote_request_without_packet_hash_dry_run_is_not_ready(self):
        inputs = sample_inputs()
        inputs["preflight"]["checks"] = [
            row
            for row in inputs["preflight"]["checks"]
            if row["name"] != "remote_client_evidence_reply_dry_run_uses_packet_hash"
        ]

        payload = goal_status.build_payload(inputs)

        anti_block = next(row for row in payload["requirements"] if row["id"] == "ANTIBLOCK-CLIENTS-01")
        self.assertIn("remote_request_ready=false", anti_block["evidence"])
        self.assertIn("remote_request_reply_dry_run_uses_packet_hash=false", anti_block["evidence"])
        self.assertEqual(
            anti_block["next_step"],
            "rerun preflight validator; reply dry-run must bind to the request packet hash",
        )

    def test_manual_profile_review_does_not_fail_core_reality_when_core_evidence_is_good(self):
        inputs = sample_inputs()
        inputs["decision"]["decision"]["decision"] = "manual_profile_review"

        payload = goal_status.build_payload(inputs)

        core = next(row for row in payload["requirements"] if row["id"] == "CORE-REALITY-01")
        self.assertEqual(core["status"], goal_status.PASS)
        self.assertTrue(core["ok"])

    def test_restore_transport_canary_monitor_has_specific_core_next_step(self):
        inputs = sample_inputs()
        inputs["decision"]["decision"]["decision"] = "restore_transport_canary_monitor"
        inputs["decision"]["classification"]["transport_status"] = "degraded"

        payload = goal_status.build_payload(inputs)

        core = next(row for row in payload["requirements"] if row["id"] == "CORE-REALITY-01")
        self.assertEqual(core["status"], goal_status.MISSING)
        self.assertIn("monitor_restore_decision=MONITOR_RESTORE_READY_FOR_APPROVAL", core["evidence"])
        self.assertIn("monitor_restore_ready_for_approval=true", core["evidence"])
        self.assertIn("monitor_restore_apply_allowed_now=false", core["evidence"])
        self.assertIn("restore_nl_vpn_monitor_canary_timer.sh", core["next_step"])
        self.assertIn("APPLY_RESTORE_NL_VPN_MONITOR_CANARY_TIMER", core["next_step"])

    def test_stale_decision_evidence_blocks_goal_status(self):
        inputs = sample_inputs(complete=True)
        inputs["decision"]["generated_at"] = "2026-01-01T00:00:00Z"

        payload = goal_status.build_payload(inputs)

        freshness = next(row for row in payload["requirements"] if row["id"] == "EVIDENCE-FRESHNESS-01")
        self.assertEqual(freshness["status"], goal_status.MISSING)
        self.assertFalse(payload["goal_complete"])
        self.assertIn(
            "refresh read-only snapshot, current decision, remote request packet, and goal status",
            payload["remaining_before_goal_complete"],
        )

    def test_complete_evidence_marks_goal_complete(self):
        payload = goal_status.build_payload(sample_inputs(complete=True))

        self.assertEqual(payload["decision"], "VPN_PRODUCTION_CANDIDATE_GOAL_COMPLETE")
        self.assertTrue(payload["goal_complete"])
        self.assertTrue(payload["firstparty_build_complete"])
        self.assertEqual(payload["requirements_passed"], payload["requirements_total"])

    def test_unsafe_warp_rollout_blocks_goal(self):
        inputs = sample_inputs(complete=True)
        inputs["telegram_warp_plan"] = sample_warp_plan(safe=False)

        payload = goal_status.build_payload(inputs)

        self.assertFalse(payload["goal_complete"])
        warp = next(row for row in payload["requirements"] if row["id"] == "TELEGRAM-WARP-01")
        self.assertEqual(warp["status"], goal_status.MISSING)

    def test_nl_write_allowed_blocks_goal(self):
        inputs = sample_inputs(complete=True)
        inputs["manifest"] = sample_manifest(nl_write_allowed=True)

        payload = goal_status.build_payload(inputs)

        self.assertFalse(payload["goal_complete"])
        gate = next(row for row in payload["requirements"] if row["id"] == "NL-GATE-01")
        self.assertEqual(gate["status"], goal_status.MISSING)

    def test_readiness_audit_missing_secondary_does_not_fail_nl_write_gate(self):
        inputs = sample_inputs(complete=True)
        inputs["readiness_audit"] = sample_readiness()
        inputs["readiness_audit"]["ok"] = False
        inputs["readiness_audit"]["summary"]["missing_items"] = ["FAILOVER-01"]

        payload = goal_status.build_payload(inputs)

        gate = next(row for row in payload["requirements"] if row["id"] == "NL-GATE-01")
        self.assertEqual(gate["status"], goal_status.PASS)
        self.assertTrue(gate["ok"])
        self.assertIn("readiness_ok=false", gate["evidence"])
        self.assertIn("safety_flags_block_writes=true", gate["evidence"])

    def test_readiness_safety_flags_allowing_failover_blocks_nl_write_gate(self):
        inputs = sample_inputs(complete=True)
        inputs["readiness_audit"]["summary"]["automatic_failover_allowed"] = True

        payload = goal_status.build_payload(inputs)

        self.assertFalse(payload["goal_complete"])
        gate = next(row for row in payload["requirements"] if row["id"] == "NL-GATE-01")
        self.assertEqual(gate["status"], goal_status.MISSING)
        self.assertIn("safety_flags_block_writes=false", gate["evidence"])

    def test_privacy_finding_blocks_claims(self):
        inputs = sample_inputs(complete=True)
        inputs["anti_block_audit"]["privacy"]["raw_uuid_stored"] = True

        payload = goal_status.build_payload(inputs)

        self.assertFalse(payload["goal_complete"])
        claims = next(row for row in payload["requirements"] if row["id"] == "CLAIMS-EVIDENCE-01")
        self.assertEqual(claims["status"], goal_status.MISSING)

    def test_markdown_renders_status_and_no_write_notice(self):
        payload = goal_status.build_payload(sample_inputs())
        markdown = goal_status.render_markdown(payload)

        self.assertIn("VPN Production-Candidate Goal Status", markdown)
        self.assertIn("VPN_PRODUCTION_CANDIDATE_GOAL_NOT_COMPLETE", markdown)
        self.assertIn("firstparty_build_complete: `true`", markdown)
        self.assertIn("No NL or SPB writes", markdown)


if __name__ == "__main__":
    unittest.main()
