from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/CURRENT_LIFECYCLE_READINESS_MAP.json"
APP_PATH = ROOT / "src/core/app.py"
LIFESPAN_PATH = ROOT / "src/core/production_lifespan.py"

INCLUDE_RE = re.compile(r'_include_maas_router\("([^"]+)",\s*"([^"]+)"\)')


def _load_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _module_path(module: str) -> Path:
    return ROOT / (module.replace(".", "/") + ".py")


def _app_router_registrations() -> list[dict[str, str]]:
    registrations: list[dict[str, str]] = []
    mode = "always"

    for line_no, line in enumerate(APP_PATH.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped == "if not is_light_mode:":
            mode = "full_mode_only"
            continue
        if mode == "full_mode_only" and line and not line.startswith(" "):
            mode = "always"

        match = INCLUDE_RE.search(line)
        if match:
            module, label = match.groups()
            registrations.append(
                {
                    "module": module,
                    "label": label,
                    "registration_mode": mode,
                    "line": str(line_no),
                }
            )

    return registrations


def test_lifecycle_readiness_map_covers_current_app_router_registrations():
    lifecycle_map = _load_map()
    mapped = {
        (entry["module"], entry["label"], entry["registration_mode"])
        for entry in lifecycle_map["routers"]
    }
    actual = {
        (entry["module"], entry["label"], entry["registration_mode"])
        for entry in _app_router_registrations()
    }

    assert mapped == actual


def test_lifecycle_readiness_source_refs_resolve_to_existing_files_and_lines():
    lifecycle_map = _load_map()
    source_refs = [
        *lifecycle_map["app_lifespan_modes"]["light_mode"]["source_refs"],
        *lifecycle_map["app_lifespan_modes"]["non_light_mode"]["source_refs"],
        *lifecycle_map["production_lifespan_runtime"]["source_refs"],
    ]
    for router in lifecycle_map["routers"]:
        source_refs.extend(router["source_refs"])

    for source_ref in source_refs:
        path_text, line_text = source_ref.rsplit(":", 1)
        path = ROOT / path_text
        assert path.exists(), source_ref
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        assert 1 <= int(line_text) <= line_count, source_ref


def test_lifecycle_hooks_are_declared_in_router_modules_and_called_by_lifespan():
    lifecycle_map = _load_map()
    lifespan_source = LIFESPAN_PATH.read_text(encoding="utf-8")

    hook_bound = [
        router
        for router in lifecycle_map["routers"]
        if router["lifecycle_binding"] == "production_lifespan_hook"
    ]
    assert {router["id"] for router in hook_bound} == {"edge-computing", "event-sourcing"}

    for router in hook_bound:
        module_source = _module_path(router["module"]).read_text(encoding="utf-8")
        startup_hook = router["startup_hook"]
        shutdown_hook = router["shutdown_hook"]

        assert f"async def {startup_hook}(" in module_source, router["id"]
        assert f"async def {shutdown_hook}(" in module_source, router["id"]
        assert router["runtime_readiness_field"] in module_source, router["id"]
        assert startup_hook in lifespan_source, router["id"]
        assert shutdown_hook in lifespan_source, router["id"]
        assert f"await {startup_hook}()" in lifespan_source, router["id"]
        assert f"await {shutdown_hook}()" in lifespan_source, router["id"]


def test_lifecycle_map_captures_light_mode_route_runtime_gap():
    lifecycle_map = _load_map()
    app_source = APP_PATH.read_text(encoding="utf-8")

    assert "lifespan=production_lifespan" in app_source
    assert 'os.getenv("MAAS_LIGHT_MODE", "false")' in app_source

    hook_bound = [
        router
        for router in lifecycle_map["routers"]
        if router["lifecycle_binding"] == "production_lifespan_hook"
    ]
    for router in hook_bound:
        assert router["registration_mode"] == "always", router["id"]
        assert router["route_present_in_light_mode"] is True, router["id"]
        assert router["hook_available_only_when_lifespan_runs"] is True, router["id"]
        assert "light mode" in router["hidden_dependency"], router["id"]


def test_lifecycle_map_tracks_marketplace_route_only_write_readiness():
    lifecycle_map = _load_map()
    marketplace = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-marketplace"
    )
    source = _module_path(marketplace["module"]).read_text(encoding="utf-8")

    assert marketplace["lifecycle_binding"] == "route_import_only"
    assert marketplace["registration_mode"] == "always"
    assert marketplace["route_present_in_light_mode"] is True
    assert marketplace["readiness_signal"] == "/api/v1/maas/marketplace/status"
    assert marketplace["runtime_readiness_field"] == "write_db_ready"
    assert "database-backed write path" in marketplace["hidden_dependency"]
    assert '@router.get("/status")' in source
    assert "write_db_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_billing_route_only_stripe_readiness():
    lifecycle_map = _load_map()
    billing = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-billing"
    )
    source = _module_path(billing["module"]).read_text(encoding="utf-8")

    assert billing["lifecycle_binding"] == "route_import_only"
    assert billing["registration_mode"] == "always"
    assert billing["route_present_in_light_mode"] is True
    assert billing["readiness_signal"] == "/api/v1/maas/billing/readiness"
    assert billing["runtime_readiness_field"] == "stripe_config_ready"
    assert "Stripe configuration" in billing["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "stripe_config_ready" in source
    assert "stripe_plans_ready" in source
    assert "legacy_metering_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_billing_api_route_only_runtime_readiness():
    lifecycle_map = _load_map()
    billing = next(
        router for router in lifecycle_map["routers"] if router["id"] == "billing-api"
    )
    source = _module_path(billing["module"]).read_text(encoding="utf-8")

    assert billing["lifecycle_binding"] == "route_import_only"
    assert billing["registration_mode"] == "always"
    assert billing["route_present_in_light_mode"] is True
    assert billing["readiness_signal"] == "/api/v1/billing/readiness"
    assert billing["runtime_readiness_field"] == "billing_api_runtime_ready"
    assert "checkout, Stripe webhook processing" in billing["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "billing_api_runtime_ready" in source
    assert "stripe_checkout_config_ready" in source
    assert "stripe_webhook_config_ready" in source
    assert "stripe_transport_ready" in source
    assert "billing_models_ready" in source
    assert "vless_link_ready" in source
    assert "provisioning_imports_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_maas_auth_route_only_runtime_readiness():
    lifecycle_map = _load_map()
    auth = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-auth"
    )
    source = _module_path(auth["module"]).read_text(encoding="utf-8")

    assert auth["lifecycle_binding"] == "route_import_only"
    assert auth["registration_mode"] == "always"
    assert auth["route_present_in_light_mode"] is True
    assert auth["readiness_signal"] == "/api/v1/maas/auth/readiness"
    assert auth["runtime_readiness_field"] == "maas_auth_runtime_ready"
    assert "MaaSAuthService" in auth["hidden_dependency"]
    assert "optional BOOTSTRAP_TOKEN" in auth["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "maas_auth_runtime_ready" in source
    assert "auth_db_ready" in source
    assert "user_model_ready" in source
    assert "session_model_ready" in source
    assert "auth_service_ready" in source
    assert "api_key_manager_ready" in source
    assert "rbac_ready" in source
    assert "token_helpers_ready" in source
    assert "audit_log_ready" in source
    assert "oidc_redirect_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_governance_route_only_control_plane_readiness():
    lifecycle_map = _load_map()
    governance = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-governance"
    )
    source = _module_path(governance["module"]).read_text(encoding="utf-8")

    assert governance["lifecycle_binding"] == "route_import_only"
    assert governance["registration_mode"] == "always"
    assert governance["route_present_in_light_mode"] is True
    assert governance["readiness_signal"] == "/api/v1/maas/governance/readiness"
    assert governance["runtime_readiness_field"] == "control_plane_ready"
    assert "EventBus trace publication" in governance["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "control_plane_ready" in source
    assert "governance_db_ready" in source
    assert "policy_engine_ready" in source
    assert "safe_actuator_ready" in source
    assert "service_identity_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_supply_chain_route_only_evidence_readiness():
    lifecycle_map = _load_map()
    supply_chain = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-supply-chain"
    )
    source = _module_path(supply_chain["module"]).read_text(encoding="utf-8")

    assert supply_chain["lifecycle_binding"] == "route_import_only"
    assert supply_chain["registration_mode"] == "always"
    assert supply_chain["route_present_in_light_mode"] is True
    assert supply_chain["readiness_signal"] == "/api/v1/maas/supply-chain/readiness"
    assert supply_chain["runtime_readiness_field"] == "persistent_supply_chain_ready"
    assert "database-backed SBOMEntry and NodeBinaryAttestation state" in supply_chain["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "persistent_supply_chain_ready" in source
    assert "attestation_store_ready" in source
    assert "audit_log_ready" in source
    assert "ebpf_filter_adapter_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_analytics_route_only_runtime_readiness():
    lifecycle_map = _load_map()
    analytics = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-analytics"
    )
    source = _module_path(analytics["module"]).read_text(encoding="utf-8")

    assert analytics["lifecycle_binding"] == "route_import_only"
    assert analytics["registration_mode"] == "always"
    assert analytics["route_present_in_light_mode"] is True
    assert analytics["readiness_signal"] == "/api/v1/maas/analytics/readiness"
    assert analytics["runtime_readiness_field"] == "analytics_runtime_ready"
    assert "MaaSAnalyticsService" in analytics["hidden_dependency"]
    assert "Redis real-time telemetry" in analytics["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "analytics_runtime_ready" in source
    assert "analytics_db_ready" in source
    assert "analytics_service_ready" in source
    assert "realtime_telemetry_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_playbooks_route_only_control_plane_readiness():
    lifecycle_map = _load_map()
    playbooks = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-playbooks"
    )
    source = _module_path(playbooks["module"]).read_text(encoding="utf-8")

    assert playbooks["lifecycle_binding"] == "route_import_only"
    assert playbooks["registration_mode"] == "always"
    assert playbooks["route_present_in_light_mode"] is True
    assert playbooks["readiness_signal"] == "/api/v1/maas/playbooks/readiness"
    assert playbooks["runtime_readiness_field"] == "playbook_control_plane_ready"
    assert "token_signer signing/verification" in playbooks["hidden_dependency"]
    assert "SignedPlaybook and PlaybookAck database state" in playbooks["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "playbook_control_plane_ready" in source
    assert "playbook_dispatch_ready" in source
    assert "persistent_playbook_ready" in source
    assert "memory_queue_ready" in source
    assert "token_signer_ready" in source
    assert "playbook_db_ready" in source
    assert "audit_log_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_policies_route_precedence_readiness():
    lifecycle_map = _load_map()
    policies = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-policies"
    )
    source = _module_path(policies["module"]).read_text(encoding="utf-8")

    assert policies["lifecycle_binding"] == "route_import_only"
    assert policies["registration_mode"] == "full_mode_only"
    assert policies["route_present_in_light_mode"] is False
    assert policies["readiness_signal"] == "/api/v1/maas/policies/readiness"
    assert policies["runtime_readiness_field"] == "policy_runtime_ready"
    assert "shadow GET/POST /{mesh_id}/policies" in policies["hidden_dependency"]
    assert "DB-backed ACLPolicy DELETE path" in policies["hidden_dependency"]
    assert '@router.get("/policies/readiness")' in source
    assert "policy_runtime_ready" in source
    assert "policy_db_ready" in source
    assert "acl_policy_model_ready" in source
    assert "rbac_dependency_ready" in source
    assert "legacy_route_shadowing" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_nodes_route_precedence_readiness():
    lifecycle_map = _load_map()
    nodes = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-nodes"
    )
    source = _module_path(nodes["module"]).read_text(encoding="utf-8")

    assert nodes["lifecycle_binding"] == "route_import_only"
    assert nodes["registration_mode"] == "full_mode_only"
    assert nodes["route_present_in_light_mode"] is False
    assert nodes["readiness_signal"] == "/api/v1/maas/nodes/readiness"
    assert nodes["runtime_readiness_field"] == "node_runtime_ready"
    assert "shadow POST /{mesh_id}/nodes/register" in nodes["hidden_dependency"]
    assert "heartbeat, telemetry readback, ACL check, delete, and heal routes" in (
        nodes["hidden_dependency"]
    )
    assert '@router.get("/nodes/readiness")' in source
    assert "node_runtime_ready" in source
    assert "node_db_ready" in source
    assert "node_model_ready" in source
    assert "node_rbac_ready" in source
    assert "telemetry_bridge_ready" in source
    assert "healing_service_ready" in source
    assert "legacy_route_shadowing" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_telemetry_route_precedence_readiness():
    lifecycle_map = _load_map()
    telemetry = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-telemetry"
    )
    source = _module_path(telemetry["module"]).read_text(encoding="utf-8")

    assert telemetry["lifecycle_binding"] == "route_import_only"
    assert telemetry["registration_mode"] == "full_mode_only"
    assert telemetry["route_present_in_light_mode"] is False
    assert telemetry["readiness_signal"] == "/api/v1/maas/telemetry/readiness"
    assert telemetry["runtime_readiness_field"] == "telemetry_runtime_ready"
    assert "shadow POST /heartbeat and GET /{mesh_id}/topology" in telemetry["hidden_dependency"]
    assert "marketplace settlement uptime checks" in telemetry["hidden_dependency"]
    assert '@router.get("/telemetry/readiness")' in source
    assert "telemetry_runtime_ready" in source
    assert "telemetry_db_ready" in source
    assert "redis_persistence_ready" in source
    assert "fallback_cache_ready" in source
    assert "uptime_tracker_ready" in source
    assert "settlement_uptime_ready" in source
    assert "legacy_route_shadowing" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_vpn_route_only_runtime_readiness():
    lifecycle_map = _load_map()
    vpn = next(router for router in lifecycle_map["routers"] if router["id"] == "vpn")
    source = _module_path(vpn["module"]).read_text(encoding="utf-8")

    assert vpn["lifecycle_binding"] == "route_import_only"
    assert vpn["registration_mode"] == "full_mode_only"
    assert vpn["route_present_in_light_mode"] is False
    assert vpn["readiness_signal"] == "/vpn/readiness"
    assert vpn["runtime_readiness_field"] == "vpn_runtime_ready"
    assert "/vpn fixed prefix is not shadowed" in vpn["hidden_dependency"]
    assert "legacy ZKP subscription database helpers" in vpn["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "vpn_runtime_ready" in source
    assert "vpn_db_ready" in source
    assert "config_generators_ready" in source
    assert "xui_client_factory_ready" in source
    assert "legacy_admin_token_ready" in source
    assert "zkp_legacy_db_ready" in source
    assert "production_env_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_users_route_only_runtime_readiness():
    lifecycle_map = _load_map()
    users = next(router for router in lifecycle_map["routers"] if router["id"] == "users")
    source = _module_path(users["module"]).read_text(encoding="utf-8")

    assert users["lifecycle_binding"] == "route_import_only"
    assert users["registration_mode"] == "full_mode_only"
    assert users["route_present_in_light_mode"] is False
    assert users["readiness_signal"] == "/api/v1/users/readiness"
    assert users["runtime_readiness_field"] == "users_runtime_ready"
    assert "/api/v1/users fixed prefix is outside legacy MaaS catch-all" in (
        users["hidden_dependency"]
    )
    assert "users_db dictionary is test-only" in users["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "users_runtime_ready" in source
    assert "users_db_ready" in source
    assert "user_model_ready" in source
    assert "session_model_ready" in source
    assert "password_hashing_ready" in source
    assert "token_generation_ready" in source
    assert "rate_limiter_ready" in source
    assert "admin_token_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_swarm_api_route_only_runtime_readiness():
    lifecycle_map = _load_map()
    swarm = next(
        router for router in lifecycle_map["routers"] if router["id"] == "swarm-api"
    )
    source = _module_path(swarm["module"]).read_text(encoding="utf-8")

    assert swarm["lifecycle_binding"] == "route_import_only"
    assert swarm["registration_mode"] == "full_mode_only"
    assert swarm["route_present_in_light_mode"] is False
    assert swarm["readiness_signal"] == "/api/v3/swarm/health"
    assert swarm["runtime_readiness_field"] == "swarm_runtime_ready"
    assert "/api/v3/swarm fixed prefix is outside legacy MaaS catch-all" in (
        swarm["hidden_dependency"]
    )
    assert "in-memory _swarms registry" in swarm["hidden_dependency"]
    assert '@router.get("/health")' in source
    assert "swarm_runtime_ready" in source
    assert "registry_ready" in source
    assert "admin_token_ready" in source
    assert "rate_limiter_ready" in source
    assert "orchestrator_ready" in source
    assert "task_model_ready" in source
    assert "vision_engine_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_ledger_api_route_only_runtime_readiness():
    lifecycle_map = _load_map()
    ledger = next(
        router for router in lifecycle_map["routers"] if router["id"] == "ledger-api"
    )
    source = _module_path(ledger["module"]).read_text(encoding="utf-8")

    assert ledger["lifecycle_binding"] == "route_import_only"
    assert ledger["registration_mode"] == "full_mode_only"
    assert ledger["route_present_in_light_mode"] is False
    assert ledger["readiness_signal"] == "/api/v1/ledger/status"
    assert ledger["runtime_readiness_field"] == "ledger_runtime_ready"
    assert "/api/v1/ledger fixed prefix is outside legacy MaaS catch-all" in (
        ledger["hidden_dependency"]
    )
    assert "service_event_trace_history" in ledger["hidden_dependency"]
    assert '@router.get("/status")' in source
    assert "ledger_runtime_ready" in source
    assert "rag_surface_ready" in source
    assert "continuity_file_ready" in source
    assert "verification_evidence_ready" in source
    assert "event_trace_index_ready" in source
    assert "event_trace_dependencies_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_swarm_orchestration_route_only_runtime_readiness():
    lifecycle_map = _load_map()
    swarm_orchestration = next(
        router
        for router in lifecycle_map["routers"]
        if router["id"] == "swarm-orchestration"
    )
    source = _module_path(swarm_orchestration["module"]).read_text(encoding="utf-8")

    assert swarm_orchestration["lifecycle_binding"] == "route_import_only"
    assert swarm_orchestration["registration_mode"] == "full_mode_only"
    assert swarm_orchestration["route_present_in_light_mode"] is False
    assert swarm_orchestration["readiness_signal"] == "/api/v1/swarm/readiness"
    assert (
        swarm_orchestration["runtime_readiness_field"]
        == "swarm_orchestration_ready"
    )
    assert "/api/v1/swarm fixed prefix is outside legacy MaaS catch-all" in (
        swarm_orchestration["hidden_dependency"]
    )
    assert "accepting /task is not the same as having an initialized agent" in (
        swarm_orchestration["hidden_dependency"]
    )
    assert '@router.get("/readiness")' in source
    assert "swarm_orchestration_ready" in source
    assert "swarm_components_ready" in source
    assert "orchestrator_surface_ready" in source
    assert "orchestrator_state_ready" in source
    assert "task_scheduler_ready" in source
    assert "agents_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_vision_analytics_route_only_runtime_readiness():
    lifecycle_map = _load_map()
    vision = next(
        router for router in lifecycle_map["routers"] if router["id"] == "vision-analytics"
    )
    source = _module_path(vision["module"]).read_text(encoding="utf-8")

    assert vision["lifecycle_binding"] == "route_import_only"
    assert vision["registration_mode"] == "full_mode_only"
    assert vision["route_present_in_light_mode"] is False
    assert vision["readiness_signal"] == "/api/v1/vision/readiness"
    assert vision["runtime_readiness_field"] == "vision_runtime_ready"
    assert "/api/v1/vision fixed prefix is outside legacy MaaS catch-all" in (
        vision["hidden_dependency"]
    )
    assert "does not process an image" in vision["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "vision_runtime_ready" in source
    assert "vision_components_ready" in source
    assert "processor_surface_ready" in source
    assert "topology_surface_ready" in source
    assert "correction_surface_ready" in source
    assert "upload_surface_ready" in source
    assert "local_image_backend_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source


def test_lifecycle_map_tracks_maas_dashboard_route_only_runtime_readiness():
    lifecycle_map = _load_map()
    dashboard = next(
        router for router in lifecycle_map["routers"] if router["id"] == "maas-dashboard"
    )
    source = _module_path(dashboard["module"]).read_text(encoding="utf-8")

    assert dashboard["lifecycle_binding"] == "route_import_only"
    assert dashboard["registration_mode"] == "always"
    assert dashboard["route_present_in_light_mode"] is True
    assert dashboard["readiness_signal"] == "/api/v1/maas/dashboard/readiness"
    assert dashboard["runtime_readiness_field"] == "dashboard_runtime_ready"
    assert "MaaSAnalyticsService.get_mesh_timeseries" in dashboard["hidden_dependency"]
    assert "without querying dashboard data" in dashboard["hidden_dependency"]
    assert '@router.get("/readiness")' in source
    assert "dashboard_runtime_ready" in source
    assert "dashboard_db_ready" in source
    assert "dashboard_models_ready" in source
    assert "dashboard_auth_ready" in source
    assert "dashboard_analytics_ready" in source
    assert "dashboard_resilience_ready" in source
    assert "mark_degraded_dependency(request, dependency)" in source
