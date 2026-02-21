"""
Unit tests for MaaS auxiliary modules:
  - maas_supply_chain  (SBOM, attestations)
  - maas_playbooks     (signed playbooks)
  - maas_marketplace   (P2P node rental)
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_user(role: str = "user", plan: str = "pro", user_id: str = "user-1", email: str = "test@x0t.net"):
    u = MagicMock()
    u.id = user_id
    u.email = email
    u.role = role
    u.plan = plan
    return u


def _admin_user():
    return _mock_user(role="admin", user_id="admin-1", email="admin@x0t.net")


# Фиктивный результат sign_token — используется там, где реальный PQC недоступен в тестах.
_FAKE_SIGN_RESULT = {
    "token": "test-token",
    "algorithm": "HMAC-SHA256",
    "signature": "a" * 64,
    "pqc_secured": False,
}


# ---------------------------------------------------------------------------
# Supply Chain — SBOM
# Endpoint-функции возвращают dict при прямом вызове (FastAPI конвертирует
# в Pydantic-модель только при HTTP-ответе).
# ---------------------------------------------------------------------------

class TestSupplyChainSBOM:
    @pytest.mark.asyncio
    async def test_get_sbom_known_version(self):
        from src.api.maas_supply_chain import get_sbom
        result = await get_sbom("v3.4.0-alpha")
        # get_sbom возвращает dict из реестра (FastAPI конвертирует в SBOMResponse при HTTP)
        assert result["version"] == "3.4.0-alpha"
        assert result["format"] == "CycloneDX-JSON"
        assert len(result["components"]) > 0

    @pytest.mark.asyncio
    async def test_get_sbom_unknown_raises_404(self):
        from src.api.maas_supply_chain import get_sbom
        with pytest.raises(HTTPException) as exc:
            await get_sbom("v99.99.99")
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_sbom_components_contain_agent(self):
        from src.api.maas_supply_chain import get_sbom
        result = await get_sbom("v3.4.0-alpha")
        names = [c["name"] for c in result["components"]]
        assert "x0tta6bl4-agent" in names

    @pytest.mark.asyncio
    async def test_sbom_has_attestation(self):
        from src.api.maas_supply_chain import get_sbom
        result = await get_sbom("v3.4.0-alpha")
        attestation = result.get("attestation")
        assert attestation is not None
        assert attestation.get("type") == "Sigstore-Bundle"

    @pytest.mark.asyncio
    async def test_verify_binary_known_version(self):
        from src.api.maas_supply_chain import verify_binary
        result = await verify_binary("v3.4.0-alpha", "sha256:abc123")
        assert result["status"] == "verified"
        assert result["pqc_compliant"] is True

    @pytest.mark.asyncio
    async def test_verify_binary_unknown_raises_400(self):
        from src.api.maas_supply_chain import verify_binary
        with pytest.raises(HTTPException) as exc:
            await verify_binary("v0.0.0", "sha256:bad")
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_register_artifact_adds_to_registry(self):
        from src.api.maas_supply_chain import register_artifact, SBOMResponse, _sbom_registry
        req = SBOMResponse(
            version="v9.9.9-test",
            format="CycloneDX-JSON",
            components=[{"name": "test-comp", "version": "1.0", "type": "library"}],
        )
        result = await register_artifact(req, current_user=_admin_user())
        assert result["status"] == "registered"
        assert result["version"] == "v9.9.9-test"
        assert "v9.9.9-test" in _sbom_registry


# ---------------------------------------------------------------------------
# Playbooks
# token_signer работает через oqs, который замокан в тестах.
# Патчим sign_token на уровне модуля, чтобы получить предсказуемый результат.
# ---------------------------------------------------------------------------

class TestPlaybooks:
    @pytest.mark.asyncio
    async def test_create_playbook_returns_signed_response(self):
        from src.api.maas_playbooks import create_playbook, PlaybookCreateRequest, PlaybookAction
        req = PlaybookCreateRequest(
            name="restart-sensors",
            target_nodes=["node-a", "node-b"],
            actions=[PlaybookAction(action="restart", params={})],
            expires_in_sec=3600,
        )
        with patch("src.api.maas_playbooks.token_signer") as mock_signer:
            mock_signer.sign_token.return_value = _FAKE_SIGN_RESULT
            result = await create_playbook("mesh-001", req, current_user=_admin_user())
        assert result.playbook_id.startswith("pbk-")
        assert result.name == "restart-sensors"
        assert result.signature == _FAKE_SIGN_RESULT["signature"]
        assert result.algorithm == "HMAC-SHA256"

    @pytest.mark.asyncio
    async def test_create_playbook_enqueues_for_each_node(self):
        from src.api.maas_playbooks import (
            create_playbook, poll_playbooks,
            PlaybookCreateRequest, PlaybookAction, _node_queues
        )
        node_id = "enqueue-test-node"
        req = PlaybookCreateRequest(
            name="upgrade-firmware",
            target_nodes=[node_id],
            actions=[PlaybookAction(action="upgrade", params={"version": "3.5.0"})],
        )
        with patch("src.api.maas_playbooks.token_signer") as mock_signer:
            mock_signer.sign_token.return_value = _FAKE_SIGN_RESULT
            result = await create_playbook("mesh-002", req, current_user=_admin_user())
        assert result.playbook_id.startswith("pbk-")
        assert node_id in _node_queues

    @pytest.mark.asyncio
    async def test_poll_returns_pending_playbooks(self):
        from src.api.maas_playbooks import (
            create_playbook, poll_playbooks,
            PlaybookCreateRequest, PlaybookAction
        )
        node_id = "poll-test-node"
        req = PlaybookCreateRequest(
            name="poll-test",
            target_nodes=[node_id],
            actions=[PlaybookAction(action="restart", params={})],
        )
        with patch("src.api.maas_playbooks.token_signer") as mock_signer:
            mock_signer.sign_token.return_value = _FAKE_SIGN_RESULT
            await create_playbook("mesh-003", req, current_user=_admin_user())
        result = await poll_playbooks("mesh-003", node_id)
        assert len(result["playbooks"]) >= 1
        pb = result["playbooks"][0]
        assert "playbook_id" in pb
        assert "signature" in pb
        assert "payload" in pb

    @pytest.mark.asyncio
    async def test_poll_pops_from_queue_on_delivery(self):
        from src.api.maas_playbooks import (
            create_playbook, poll_playbooks,
            PlaybookCreateRequest, PlaybookAction
        )
        node_id = "pop-test-node"
        req = PlaybookCreateRequest(
            name="pop-test",
            target_nodes=[node_id],
            actions=[PlaybookAction(action="restart", params={})],
        )
        with patch("src.api.maas_playbooks.token_signer") as mock_signer:
            mock_signer.sign_token.return_value = _FAKE_SIGN_RESULT
            await create_playbook("mesh-004", req, current_user=_admin_user())
        first = await poll_playbooks("mesh-004", node_id)
        second = await poll_playbooks("mesh-004", node_id)
        assert len(first["playbooks"]) == 1
        assert len(second["playbooks"]) == 0  # очередь пуста после первой доставки

    @pytest.mark.asyncio
    async def test_poll_empty_node_returns_empty_list(self):
        from src.api.maas_playbooks import poll_playbooks
        result = await poll_playbooks("mesh-000", "node-with-no-playbooks")
        assert result["playbooks"] == []

    @pytest.mark.asyncio
    async def test_acknowledge_playbook(self):
        from src.api.maas_playbooks import acknowledge_playbook
        result = await acknowledge_playbook("pbk-test123", "node-a", status="completed")
        assert result["status"] == "received"

    @pytest.mark.asyncio
    async def test_playbook_payload_is_valid_json(self):
        import json
        from src.api.maas_playbooks import create_playbook, PlaybookCreateRequest, PlaybookAction
        req = PlaybookCreateRequest(
            name="json-test",
            target_nodes=["node-x"],
            actions=[PlaybookAction(action="exec", params={"cmd": "echo hello"})],
        )
        with patch("src.api.maas_playbooks.token_signer") as mock_signer:
            mock_signer.sign_token.return_value = _FAKE_SIGN_RESULT
            result = await create_playbook("mesh-005", req, current_user=_admin_user())
        payload = json.loads(result.payload)
        assert "playbook_id" in payload
        assert "mesh_id" in payload
        assert "actions" in payload
        assert payload["actions"][0]["action"] == "exec"

    @pytest.mark.asyncio
    async def test_expired_playbooks_not_delivered(self):
        """Истёкшие плейбуки не должны попасть в poll."""
        from datetime import datetime, timedelta
        from src.api.maas_playbooks import (
            create_playbook, poll_playbooks, _playbook_store, _node_queues,
            PlaybookCreateRequest, PlaybookAction
        )
        node_id = "expire-test-node"
        req = PlaybookCreateRequest(
            name="expire-test",
            target_nodes=[node_id],
            actions=[PlaybookAction(action="restart", params={})],
            expires_in_sec=3600,
        )
        with patch("src.api.maas_playbooks.token_signer") as mock_signer:
            mock_signer.sign_token.return_value = _FAKE_SIGN_RESULT
            result = await create_playbook("mesh-006", req, current_user=_admin_user())
        # Форсируем истечение
        _playbook_store[result.playbook_id]["expires_at"] = (
            datetime.utcnow() - timedelta(seconds=1)
        ).isoformat()
        polled = await poll_playbooks("mesh-006", node_id)
        assert len(polled["playbooks"]) == 0


# ---------------------------------------------------------------------------
# Marketplace
# Функции возвращают dict (не Pydantic) при прямом вызове.
# ---------------------------------------------------------------------------

class TestMarketplace:
    @pytest.mark.asyncio
    async def test_create_listing(self):
        from src.api.maas_marketplace import create_listing, ListingCreate
        req = ListingCreate(
            node_id="robot-edge-01",
            region="eu-central",
            price_per_hour=0.05,
            bandwidth_mbps=100,
        )
        user = _mock_user(user_id="seller-1", email="seller@x0t.net")
        result = await create_listing(req, current_user=user)
        assert result["listing_id"].startswith("lst-")
        assert result["owner_id"] == "seller-1"
        assert result["status"] == "available"
        assert result["region"] == "eu-central"

    @pytest.mark.asyncio
    async def test_search_listings_returns_list(self):
        from src.api.maas_marketplace import create_listing, search_listings, ListingCreate
        req = ListingCreate(
            node_id="search-test-node",
            region="us-west",
            price_per_hour=0.02,
            bandwidth_mbps=200,
        )
        await create_listing(req, current_user=_mock_user(user_id="s2"))
        results = await search_listings()
        assert isinstance(results, list)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_search_filter_by_region(self):
        from src.api.maas_marketplace import create_listing, search_listings, ListingCreate
        req = ListingCreate(
            node_id="asia-node",
            region="asia-south",
            price_per_hour=0.01,
            bandwidth_mbps=50,
        )
        await create_listing(req, current_user=_mock_user(user_id="s3"))
        results = await search_listings(region="asia-south")
        assert all(r["region"] == "asia-south" for r in results)

    @pytest.mark.asyncio
    async def test_search_filter_by_max_price(self):
        from src.api.maas_marketplace import create_listing, search_listings, ListingCreate
        req = ListingCreate(
            node_id="expensive-node",
            region="us-east",
            price_per_hour=9.99,
            bandwidth_mbps=1000,
        )
        await create_listing(req, current_user=_mock_user(user_id="s4"))
        cheap = await search_listings(max_price=0.1)
        assert all(r["price_per_hour"] <= 0.1 for r in cheap)

    @pytest.mark.asyncio
    async def test_search_filter_by_min_bandwidth(self):
        from src.api.maas_marketplace import create_listing, search_listings, ListingCreate
        await create_listing(
            ListingCreate(node_id="fast-node", region="global", price_per_hour=0.05, bandwidth_mbps=1000),
            current_user=_mock_user(user_id="s5"),
        )
        await create_listing(
            ListingCreate(node_id="slow-node", region="global", price_per_hour=0.01, bandwidth_mbps=10),
            current_user=_mock_user(user_id="s6"),
        )
        results = await search_listings(min_bandwidth=500)
        assert all(r["bandwidth_mbps"] >= 500 for r in results)

    @pytest.mark.asyncio
    async def test_rent_node_changes_status(self):
        from src.api.maas_marketplace import create_listing, rent_node, ListingCreate, _listings
        seller = _mock_user(user_id="seller-rent", email="seller@x0t.net")
        listing = await create_listing(
            ListingCreate(node_id="rentable-node", region="global", price_per_hour=0.10, bandwidth_mbps=100),
            current_user=seller,
        )
        lid = listing["listing_id"]
        buyer = _mock_user(user_id="buyer-1", email="buyer@x0t.net")
        result = await rent_node(lid, "mesh-rent-01", current_user=buyer)
        assert result["status"] == "success"
        assert _listings[lid]["status"] == "rented"

    @pytest.mark.asyncio
    async def test_rent_own_node_raises_400(self):
        from src.api.maas_marketplace import create_listing, rent_node, ListingCreate
        owner = _mock_user(user_id="owner-self", email="owner@x0t.net")
        listing = await create_listing(
            ListingCreate(node_id="own-node", region="us-east", price_per_hour=0.05, bandwidth_mbps=50),
            current_user=owner,
        )
        with pytest.raises(HTTPException) as exc:
            await rent_node(listing["listing_id"], "mesh-x", current_user=owner)
        assert exc.value.status_code == 400

    @pytest.mark.asyncio
    async def test_rent_nonexistent_raises_404(self):
        from src.api.maas_marketplace import rent_node
        with pytest.raises(HTTPException) as exc:
            await rent_node("lst-doesnotexist", "mesh-y", current_user=_mock_user(user_id="b2"))
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_cancel_listing_removes_it(self):
        from src.api.maas_marketplace import create_listing, cancel_listing, ListingCreate, _listings
        owner = _mock_user(user_id="owner-cancel", email="cancel@x0t.net")
        listing = await create_listing(
            ListingCreate(node_id="cancel-node", region="us-west", price_per_hour=0.03, bandwidth_mbps=100),
            current_user=owner,
        )
        lid = listing["listing_id"]
        result = await cancel_listing(lid, current_user=owner)
        assert result["status"] == "cancelled"
        assert lid not in _listings

    @pytest.mark.asyncio
    async def test_cancel_wrong_owner_raises_403(self):
        from src.api.maas_marketplace import create_listing, cancel_listing, ListingCreate
        owner = _mock_user(user_id="real-owner")
        listing = await create_listing(
            ListingCreate(node_id="perm-node", region="eu-central", price_per_hour=0.05, bandwidth_mbps=100),
            current_user=owner,
        )
        thief = _mock_user(user_id="not-the-owner")
        with pytest.raises(HTTPException) as exc:
            await cancel_listing(listing["listing_id"], current_user=thief)
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_double_rent_raises_400(self):
        from src.api.maas_marketplace import create_listing, rent_node, ListingCreate
        seller = _mock_user(user_id="seller-dr")
        listing = await create_listing(
            ListingCreate(node_id="double-rent-node", region="global", price_per_hour=0.05, bandwidth_mbps=100),
            current_user=seller,
        )
        lid = listing["listing_id"]
        await rent_node(lid, "mesh-1", current_user=_mock_user(user_id="buyer-dr-1"))
        with pytest.raises(HTTPException) as exc:
            await rent_node(lid, "mesh-2", current_user=_mock_user(user_id="buyer-dr-2"))
        assert exc.value.status_code == 400
