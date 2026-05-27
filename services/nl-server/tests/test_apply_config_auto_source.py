#!/usr/bin/env python3
from __future__ import annotations

import ast
import copy
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "mesh-runtime" / "apply_config_auto.py"


def load_function(name: str):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"))
    function = next(
        node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name
    )
    module = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(module)
    namespace = {
        "Dict": dict,
        "List": list,
        "Any": object,
        "logger": FakeLogger(),
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace[name]


class ApplyConfigAutoSourceTests(unittest.TestCase):
    def test_dns_config_is_added_only_when_missing(self) -> None:
        ensure_dns_config = load_function("ensure_dns_config")
        config = {}

        self.assertTrue(ensure_dns_config(config))
        self.assertEqual(config["dns"]["queryStrategy"], "UseIPv4")
        self.assertGreaterEqual(len(config["dns"]["servers"]), 3)

        unchanged = copy.deepcopy(config)
        self.assertFalse(ensure_dns_config(config))
        self.assertEqual(config, unchanged)

    def test_warp_outbound_is_inserted_after_direct(self) -> None:
        ensure_warp_outbound = load_function("ensure_warp_outbound")
        config = {"outbounds": [{"tag": "direct", "protocol": "freedom"}]}

        self.assertTrue(ensure_warp_outbound(config))
        self.assertEqual([item["tag"] for item in config["outbounds"]], ["direct", "warp"])
        self.assertEqual(config["outbounds"][1]["settings"]["servers"][0]["port"], 40000)

        self.assertFalse(ensure_warp_outbound(config))

    def test_routing_rules_are_rebuilt_with_expected_outbounds(self) -> None:
        ensure_routing_rules = load_function("ensure_routing_rules")
        config = {"routing": {"rules": [{"outboundTag": "old"}]}}

        self.assertTrue(ensure_routing_rules(config))
        rules = config["routing"]["rules"]
        outbound_tags = {rule.get("outboundTag") for rule in rules}

        self.assertIn("api", outbound_tags)
        self.assertIn("warp", outbound_tags)
        self.assertIn("direct", outbound_tags)
        self.assertIn("blocked", outbound_tags)
        self.assertEqual(config["routing"]["domainStrategy"], "IPIfNonMatch")
        self.assertEqual(config["routing"]["domainMatcher"], "hybrid")

    def test_inbound_and_log_config_updates_are_scoped(self) -> None:
        ensure_inbound_config = load_function("ensure_inbound_config")
        ensure_log_config = load_function("ensure_log_config")
        config = {
            "inbounds": [
                {"port": 443, "listen": "127.0.0.1"},
                {"port": 39829, "sniffing": {"enabled": False}},
            ],
            "log": {"loglevel": "debug"},
        }

        self.assertTrue(ensure_inbound_config(config))
        self.assertEqual(config["inbounds"][1]["listen"], "0.0.0.0")
        self.assertTrue(config["inbounds"][1]["sniffing"]["enabled"])
        self.assertFalse(config["inbounds"][1]["sniffing"]["routeOnly"])

        self.assertTrue(ensure_log_config(config))
        self.assertEqual(config["log"], {"loglevel": "warning", "access": "none", "dnsLog": False})
        self.assertFalse(ensure_log_config(config))

    def test_source_remains_class_c_mutating_tool(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")

        self.assertIn('/usr/local/x-ui/bin/config.json', text)
        self.assertIn('backup_config()', text)
        self.assertIn('save_config(config)', text)
        self.assertIn('validate_config(config)', text)


class FakeLogger:
    def info(self, message: str) -> None:
        pass

    def warning(self, message: str) -> None:
        pass

    def error(self, message: str, *args, **kwargs) -> None:
        pass


if __name__ == "__main__":
    unittest.main()
