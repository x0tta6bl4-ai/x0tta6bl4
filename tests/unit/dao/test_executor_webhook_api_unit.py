import asyncio
import os
import sys
import unittest
import warnings
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from pydantic.warnings import UnsupportedFieldAttributeWarning

# Make repository root importable as "src".
ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# FastAPI + pydantic in this environment emits this warning for route model aliases.
warnings.filterwarnings("ignore", category=UnsupportedFieldAttributeWarning)

# Prevent heavy web3 import path side effects in this unit file.
with patch.dict("sys.modules", {"web3": MagicMock()}):
    from src.dao.executor_webhook import (
        ProposalExecutedWebhook,
        create_app,
        _verify_webhook_token,
    )


class _DummyRequest:
    def __init__(self, headers=None):
        self.headers = headers or {}


class TestExecutorWebhookAPI(unittest.TestCase):
    def setUp(self):
        self.executor = MagicMock()
        self.executor.process_proposal = AsyncMock(
            return_value={"executed": True, "reason": "upgrade_success", "proposal_id": 77}
        )

    def tearDown(self):
        os.environ.pop("DAO_EXECUTOR_WEBHOOK_TOKEN", None)

    def test_create_app_registers_routes(self):
        app = create_app(self.executor)
        routes = {route.path for route in app.routes}
        self.assertIn("/healthz", routes)
        self.assertIn("/status", routes)
        self.assertIn("/webhook/proposal-executed", routes)

    def test_verify_webhook_token_no_secret_configured(self):
        os.environ.pop("DAO_EXECUTOR_WEBHOOK_TOKEN", None)
        _verify_webhook_token(None)
        _verify_webhook_token("anything")

    def test_verify_webhook_token_requires_match(self):
        os.environ["DAO_EXECUTOR_WEBHOOK_TOKEN"] = "super-secret"
        with self.assertRaises(Exception):
            _verify_webhook_token(None)
        with self.assertRaises(Exception):
            _verify_webhook_token("wrong")
        _verify_webhook_token("super-secret")

    def test_webhook_endpoint_calls_executor(self):
        os.environ["DAO_EXECUTOR_WEBHOOK_TOKEN"] = "super-secret"
        app = create_app(self.executor)

        endpoint = None
        for route in app.routes:
            if getattr(route, "path", "") == "/webhook/proposal-executed":
                endpoint = route.endpoint
                break
        self.assertIsNotNone(endpoint)

        payload = ProposalExecutedWebhook(
            proposal_id=77,
            title="HELM_UPGRADE: v3.4.1",
            source="unit-test",
        )
        response = asyncio.run(
            endpoint(
                event_data=payload,
                request=_DummyRequest(headers={"X-Executor-Token": "super-secret"}),
            )
        )

        self.assertEqual(response["accepted"], True)
        self.assertEqual(response["proposal_id"], 77)
        self.executor.process_proposal.assert_awaited_once_with(
            proposal_id=77,
            proposal_title="HELM_UPGRADE: v3.4.1",
            source="unit-test",
        )

    def test_status_route_returns_executor_state(self):
        app = create_app(self.executor)
        self.executor._processed_ids = {1, 2, 3}
        self.executor.last_block = 1234
        self.executor.last_result = {"proposal_id": 3, "reason": "upgrade_success"}

        endpoint = None
        for route in app.routes:
            if getattr(route, "path", "") == "/status":
                endpoint = route.endpoint
                break
        self.assertIsNotNone(endpoint)

        response = asyncio.run(endpoint())
        self.assertEqual(response["processed_count"], 3)
        self.assertEqual(response["last_block"], 1234)
        self.assertEqual(response["last_result"]["proposal_id"], 3)


if __name__ == "__main__":
    unittest.main()
