import asyncio
from types import SimpleNamespace

import src.api.vision_endpoints as vision_mod
from src.core.reliability_policy import get_degraded_dependencies


class _FakeProcessor:
    api_key = None
    require_external_provider = False

    async def process_image(self, image_data, context=None):
        return {"status": "success"}

    async def extract_text(self, image_path):
        return ""


class _FakeTopologyAnalyzer:
    async def analyze_bytes(self, image_data):
        return {"status": "success"}

    async def analyze(self, image_path):
        return {"status": "success"}

    def clear_cache(self):
        return None


class _FakeCorrectionEngine:
    async def debug_bytes(self, image_data, context_metrics=None):
        return {"status": "analysis_complete", "findings": {}, "proposed_plan": []}

    async def debug_visually(self, image_path, context_metrics=None):
        return {"status": "analysis_complete", "findings": {}, "proposed_plan": []}


def _patch_ready_components(monkeypatch):
    monkeypatch.setattr(vision_mod, "VISION_AVAILABLE", True)
    monkeypatch.setattr(vision_mod, "_processor", _FakeProcessor(), raising=False)
    monkeypatch.setattr(
        vision_mod, "_topology_analyzer", _FakeTopologyAnalyzer(), raising=False
    )
    monkeypatch.setattr(
        vision_mod, "_correction_engine", _FakeCorrectionEngine(), raising=False
    )


def test_vision_readiness_ready_when_component_surfaces_are_available(monkeypatch):
    _patch_ready_components(monkeypatch)

    payload = vision_mod._vision_readiness_status()

    assert payload["status"] == "ready"
    assert payload["vision_runtime_ready"] is True
    assert payload["vision_components_ready"] is True
    assert payload["processor_surface_ready"] is True
    assert payload["topology_surface_ready"] is True
    assert payload["correction_surface_ready"] is True
    assert payload["upload_surface_ready"] is True
    assert payload["local_image_backend_ready"] is True
    assert payload["external_provider_required"] is False
    assert payload["cross_plane_claim_gate"]["allowed"] is False
    assert "production_readiness" in payload["cross_plane_claim_gate"]["requested_claim_ids"]
    assert payload["external_provider_configured"] is False
    assert payload["degraded_dependencies"] == []


def test_vision_readiness_degraded_when_components_are_missing(monkeypatch):
    monkeypatch.setattr(vision_mod, "VISION_AVAILABLE", False)
    monkeypatch.setattr(vision_mod, "_processor", None, raising=False)
    monkeypatch.setattr(vision_mod, "_topology_analyzer", None, raising=False)
    monkeypatch.setattr(vision_mod, "_correction_engine", None, raising=False)

    payload = vision_mod._vision_readiness_status()

    assert payload["status"] == "degraded"
    assert payload["vision_runtime_ready"] is False
    assert payload["vision_components_ready"] is False
    assert set(payload["degraded_dependencies"]) == {
        "vision_components",
        "processor_surface",
        "topology_surface",
        "correction_surface",
        "local_image_backend",
    }
    assert payload["upload_surface_ready"] is True
    assert payload["backing_state"] == {
        "processor": None,
        "topology_analyzer": None,
        "correction_engine": None,
    }


def test_vision_readiness_route_exposes_rate_limit_and_claim_boundary(monkeypatch):
    _patch_ready_components(monkeypatch)

    payload = vision_mod._vision_readiness_status()

    assert payload["route_registered"] is True
    assert payload["registration_mode"] == "full_mode_only"
    assert payload["route_present_in_light_mode"] is False
    assert payload["lifecycle_binding"] == "route_import_only"
    assert payload["startup_hook_completed"] is None
    assert payload["route_precedence"]["fixed_prefix"] == "/api/v1/vision"
    assert payload["route_precedence"]["legacy_maas_catch_all_shadowing"] == (
        "not_applicable"
    )
    assert "/api/v1/vision/analyze/topology" in payload["route_precedence"][
        "rate_limited_paths"
    ]
    assert "does not process an image" in payload["claim_boundary"]


def test_vision_readiness_endpoint_marks_degraded_dependencies(monkeypatch):
    monkeypatch.setattr(vision_mod, "VISION_AVAILABLE", False)
    monkeypatch.setattr(vision_mod, "_processor", None, raising=False)
    monkeypatch.setattr(vision_mod, "_topology_analyzer", None, raising=False)
    monkeypatch.setattr(vision_mod, "_correction_engine", None, raising=False)
    request = SimpleNamespace(state=SimpleNamespace())

    payload = asyncio.run(vision_mod.vision_readiness(request))

    assert payload["status"] == "degraded"
    assert get_degraded_dependencies(request) == sorted(payload["degraded_dependencies"])


def test_vision_router_has_readiness_route():
    route_paths = [route.path for route in vision_mod.router.routes]

    assert "/api/v1/vision/readiness" in route_paths
