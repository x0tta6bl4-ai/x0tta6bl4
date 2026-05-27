import json
from pathlib import Path

from src.integration import x0t_bridge_config as mod


VALID_GOV = "0x1111111111111111111111111111111111111111"
VALID_TOKEN = "0x2222222222222222222222222222222222222222"
VALID_BRIDGE = "0x3333333333333333333333333333333333333333"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload))


def _base(root: Path, *, configured_bridge: str = "0x0000000000000000000000000000000000000000") -> None:
    _write_json(
        root / mod.DEFAULT_DEPLOYMENT_MANIFEST,
        {"MeshGovernance": VALID_GOV, "X0TToken": VALID_TOKEN, "chainId": mod.EXPECTED_CHAIN_ID},
    )
    _write(
        root / mod.DEFAULT_CONFIG_PATH,
        "\n".join(
            [
                "apiVersion: x0tta6bl4.io/v1alpha1",
                "kind: MeshCluster",
                "spec:",
                "  dao:",
                "    bridge:",
                "      enabled: true",
                "      chainId: 84532",
                f"      contractAddress: \"{configured_bridge}\"  # bridge contract address",
                "      confirmations: 5",
            ]
        )
        + "\n",
    )


def test_missing_address_blocks_without_mutation(tmp_path):
    _base(tmp_path)

    report = mod.build_report(tmp_path)

    assert report["decision"] == "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
    assert report["bridge_config_ready"] is False
    assert report["mutates_chain"] is False
    assert report["submits_transaction"] is False
    assert report["mutates_config"] is False
    assert report["summary"]["bridge_address_input_ready"] is False
    assert report["missing_inputs"][0]["id"] == "bridge_contract_address"
    assert report["missing_inputs"][0]["status"] == "OPERATOR_INPUT_REQUIRED"
    assert report["summary"]["missing_inputs_operator_input_required"] == 1
    assert report["summary"]["missing_inputs_generic_operator_required"] == 0


def test_rejects_governance_or_token_address(tmp_path):
    _base(tmp_path)

    gov_report = mod.build_report(tmp_path, bridge_address=VALID_GOV)
    token_report = mod.build_report(tmp_path, bridge_address=VALID_TOKEN)

    assert any("must not equal MeshGovernance" in error for error in gov_report["input"]["errors"])
    assert any("must not equal X0TToken" in error for error in token_report["input"]["errors"])
    assert gov_report["bridge_config_ready"] is False
    assert token_report["bridge_config_ready"] is False


def test_valid_address_is_ready_to_apply_but_does_not_write_without_approval(tmp_path):
    _base(tmp_path)

    report = mod.build_report(tmp_path, bridge_address=VALID_BRIDGE)

    assert report["decision"] == "X0T_BRIDGE_CONFIG_READY_TO_APPLY"
    assert report["bridge_config_ready"] is False
    assert report["summary"]["bridge_address_input_ready"] is True
    assert report["summary"]["write_performed"] is False
    assert report["missing_inputs"][0]["id"] == "bridge_config_apply"
    assert report["missing_inputs"][0]["status"] == "OPERATOR_APPROVAL_REQUIRED"
    assert report["summary"]["missing_inputs_operator_approval_required"] == 1
    assert VALID_BRIDGE not in (tmp_path / mod.DEFAULT_CONFIG_PATH).read_text(encoding="utf-8")


def test_write_config_requires_approval(tmp_path):
    _base(tmp_path)

    report = mod.build_report(tmp_path, bridge_address=VALID_BRIDGE, write_config=True)

    assert report["decision"] == "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
    assert report["bridge_config_ready"] is False
    assert report["write"]["error"] == f"{mod.APPROVAL_ENV} must be {mod.APPROVAL_VALUE}"
    assert report["summary"]["write_performed"] is False


def test_write_config_with_approval_updates_bridge_address(tmp_path):
    _base(tmp_path)

    report = mod.build_report(
        tmp_path,
        bridge_address=VALID_BRIDGE,
        write_config=True,
        approval=mod.APPROVAL_VALUE,
    )

    assert report["decision"] == "X0T_BRIDGE_CONFIG_READY"
    assert report["bridge_config_ready"] is True
    assert report["summary"]["write_performed"] is True
    text = (tmp_path / mod.DEFAULT_CONFIG_PATH).read_text(encoding="utf-8")
    assert f'contractAddress: "{VALID_BRIDGE}"  # bridge contract address' in text


def test_cli_writes_artifact_and_require_input_ready_blocks(tmp_path, capsys):
    _base(tmp_path)
    output = tmp_path / "bridge.json"

    exit_code = mod.main([
        "--root",
        str(tmp_path),
        "--write-json",
        "--output-json",
        str(output),
        "--require-input-ready",
    ])

    assert exit_code == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == mod.SCHEMA_VERSION
    assert payload["summary"]["bridge_address_input_ready"] is False
    printed = json.loads(capsys.readouterr().out)
    assert printed["decision"] == "X0T_BRIDGE_CONFIG_BLOCKED_ON_OPERATOR"
