#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "nl-beta-2443.example.json"
TEMPLATE_META = ROOT / "templates" / "nl-beta-2443.example.json.meta.json"

SECRET_PATTERNS = (
    re.compile(r"\b(vless|vmess|trojan|ss)://"),
    re.compile(r"[0-9]{8,10}:[A-Za-z0-9_-]{35,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"),
)


class TemplateTests(unittest.TestCase):
    def test_nl_beta_template_is_valid_json_shape(self) -> None:
        payload = json.loads(TEMPLATE.read_text(encoding="utf-8"))

        self.assertFalse(payload["_source_shape"]["production_values_saved"])
        self.assertEqual(payload["inbounds"][0]["port"], 2443)
        self.assertEqual(payload["inbounds"][0]["protocol"], "vless")
        self.assertEqual(payload["inbounds"][0]["streamSettings"]["security"], "reality")
        self.assertEqual(payload["outbounds"][0]["tag"], "direct")

    def test_nl_beta_template_contains_placeholders_not_secret_values(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")
        payload = json.loads(text)
        client = payload["inbounds"][0]["settings"]["clients"][0]
        reality = payload["inbounds"][0]["streamSettings"]["realitySettings"]

        self.assertEqual(client["id"], "REPLACE_WITH_RUNTIME_UUID")
        self.assertEqual(reality["privateKey"], "REPLACE_WITH_RUNTIME_PRIVATE_KEY")
        self.assertEqual(reality["shortIds"], ["REPLACE_WITH_RUNTIME_SHORT_ID"])

        for pattern in SECRET_PATTERNS:
            self.assertIsNone(pattern.search(text), pattern.pattern)

    def test_nl_beta_template_has_redaction_metadata(self) -> None:
        meta = json.loads(TEMPLATE_META.read_text(encoding="utf-8"))

        self.assertEqual(meta["remote_path"], "/etc/ghost-access/nl-beta-2443.json")
        self.assertEqual(meta["target_path"], "templates/nl-beta-2443.example.json")
        self.assertFalse(meta["raw_saved_locally"])
        self.assertFalse(meta["deployable_to_nl"])
        self.assertRegex(meta["raw_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(meta["redacted_sha256"], r"^[0-9a-f]{64}$")


if __name__ == "__main__":
    unittest.main()
