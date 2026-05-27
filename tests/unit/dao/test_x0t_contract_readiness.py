import json
from pathlib import Path

from src.integration import x0t_contract_readiness as mod


VALID_GOV = "0x1111111111111111111111111111111111111111"
VALID_TOKEN = "0x2222222222222222222222222222222222222222"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write(path, json.dumps(payload))


def _write_package(root: Path, *, engine: str = ">=22.10.0") -> None:
    _write_json(
        root / mod.CONTRACT_PACKAGE_JSON,
        {
            "type": "module",
            "engines": {"node": engine},
            "dependencies": {"@openzeppelin/contracts": "5.4.0"},
            "devDependencies": {
                "@nomicfoundation/hardhat-ethers": "^4.0.9",
                "@nomicfoundation/hardhat-ethers-chai-matchers": "^3.0.6",
                "@nomicfoundation/hardhat-mocha": "^3.0.17",
                "chai": "^5.3.3",
                "ethers": "^6.16.0",
                "hardhat": "^3.4.1",
                "mocha": "^11.7.5",
            },
        },
    )
    _write(
        root / mod.CONTRACT_HARDHAT_CONFIG,
        "\n".join(
            [
                'import hardhatEthers from "@nomicfoundation/hardhat-ethers";',
                'import hardhatEthersChaiMatchers from "@nomicfoundation/hardhat-ethers-chai-matchers";',
                'import hardhatMocha from "@nomicfoundation/hardhat-mocha";',
            ]
        ),
    )
    _write(
        root / mod.BRIDGE_CONTRACT_SOURCE,
        (
            "contract X0TBridge { SafeERC20 ReentrancyGuard Pausable "
            "BridgeDeposit BridgeRelease bridgeOperators processedReleases "
            "depositFor releaseToChain }\n"
        ),
    )
    _write(
        root / mod.BRIDGE_DEPLOY_SCRIPT,
        (
            "X0TBridge X0T_TOKEN_ADDRESS X0T_BRIDGE_OPERATOR_ADDRESS "
            "X0T_DEPLOY_BRIDGE_APPROVAL deploy-bridge-base-sepolia PRIVATE_KEY\n"
        ),
    )
    _write(
        root / mod.BRIDGE_CONTRACT_TEST,
        "X0TBridge BridgeDeposit BridgeRelease ReleaseAlreadyProcessed NotBridgeOperator\n",
    )


def _install_package(root: Path, name: str, version: str) -> None:
    package_json = root / mod.CONTRACT_PACKAGE_DIR / "node_modules" / Path(*name.split("/")) / "package.json"
    _write_json(package_json, {"name": name, "version": version})


def _install_ready_packages(root: Path) -> None:
    versions = {
        "@openzeppelin/contracts": "5.4.0",
        "@nomicfoundation/hardhat-ethers": "4.0.9",
        "@nomicfoundation/hardhat-ethers-chai-matchers": "3.0.6",
        "@nomicfoundation/hardhat-mocha": "3.0.17",
        "chai": "5.3.3",
        "ethers": "6.16.0",
        "hardhat": "3.4.1",
        "mocha": "11.7.5",
    }
    for name, version in versions.items():
        _install_package(root, name, version)


def _write_build_verification(root: Path, *, ready: bool = True) -> None:
    _write_json(
        root / mod.CONTRACT_BUILD_VERIFICATION,
        {
            "schema_version": "x0tta6bl4-x0t-contract-build-verification-v1",
            "status": "VERIFIED HERE",
            "ok": True,
            "decision": "X0T_CONTRACT_BUILD_VERIFIED" if ready else "X0T_CONTRACT_BUILD_BLOCKED",
            "contract_build_verified": ready,
            "mutates_chain": False,
            "runs_live_rpc": False,
            "submits_transaction": False,
            "summary": {
                "required_node_runtime_ready": ready,
                "hardhat_compile_ready": ready,
                "hardhat_test_ready": ready,
            },
        },
    )


def _write_valid_deployment_and_configs(root: Path) -> None:
    _write_json(
        root / mod.BASE_SEPOLIA_DEPLOYMENT,
        {"MeshGovernance": VALID_GOV, "X0TToken": VALID_TOKEN, "chainId": 84532},
    )
    for relative in mod.OPERATOR_CONFIGS:
        _write(root / relative, f"dao:\n  contractAddress: \"{VALID_GOV}\"\n")
    _write(root / "contracts/Voting.sol", "contract Voting is Ownable { constructor(address tokenAddress) Ownable(msg.sender) {} function vote(uint256 id) external {} }\n")


def test_report_blocks_current_failure_classes(tmp_path):
    _write_package(tmp_path)
    _install_package(tmp_path, "@openzeppelin/contracts", "5.4.0")
    _install_package(tmp_path, "hardhat", "2.28.6")
    _install_package(tmp_path, "mocha", "10.8.2")
    _write_json(
        tmp_path / mod.BASE_SEPOLIA_DEPLOYMENT,
        {"MeshGovernance": "0xGovNew", "X0TToken": "0xTokNew", "chainId": 84532},
    )
    for relative in mod.OPERATOR_CONFIGS:
        _write(root_path := tmp_path / relative, 'dao:\n  contractAddress: "0x0000000000000000000000000000000000000000"\n')
        assert root_path.exists()
    _write(tmp_path / "contracts/Voting.sol", "contract Voting is Ownable { constructor(address tokenAddress) { } func vote(uint256 id) external {} }\n")

    report = mod.build_report(tmp_path, node_version="v20.19.6")

    assert report["contract_readiness_clear"] is False
    assert report["decision"] == "BLOCKED_ON_BUILD_ENV_AND_DEPLOYMENT_CONFIG_AND_LEGACY_CONTRACT_SURFACE"
    assert report["summary"]["node_runtime_ready"] is False
    assert report["summary"]["effective_node_runtime_ready"] is False
    assert report["summary"]["contract_build_verification_ready"] is False
    assert report["summary"]["bridge_contract_source_ready"] is True
    assert report["summary"]["missing_contract_dependencies"] == 5
    assert report["summary"]["invalid_contract_dependencies"] == 2
    assert report["deployment_manifest"]["address_checks"][0]["status"] == "PLACEHOLDER_ADDRESS"
    assert report["operator_configs"]["ready"] is False
    assert report["legacy_contracts"]["ready"] is False
    assert "authoritative Base Sepolia deployment manifest with non-placeholder addresses" in report["not_verified_yet"]
    assert "operator configs wired to verified contract addresses" in report["not_verified_yet"]
    assert report["goal_can_be_marked_complete"] is False
    assert report["mutates_chain"] is False
    assert report["submits_transaction"] is False


def test_report_clears_when_package_and_addresses_are_ready(tmp_path):
    _write_package(tmp_path)
    _install_ready_packages(tmp_path)
    _write_build_verification(tmp_path)
    _write_valid_deployment_and_configs(tmp_path)

    report = mod.build_report(tmp_path, node_version="v22.10.0")

    assert report["decision"] == "CONTRACT_READINESS_CLEAR"
    assert report["contract_readiness_clear"] is True
    assert report["summary"]["build_env_ready"] is True
    assert report["summary"]["effective_node_runtime_ready"] is True
    assert report["summary"]["node_runtime_ready_source"] == "current_shell"
    assert report["summary"]["contract_build_verification_ready"] is True
    assert report["summary"]["deployment_config_ready"] is True
    assert report["summary"]["legacy_contract_surface_ready"] is True
    assert report["summary"]["bridge_contract_source_ready"] is True
    assert report["missing_inputs"] == []
    assert "authoritative Base Sepolia deployment manifest with non-placeholder addresses" not in report["not_verified_yet"]
    assert "operator configs wired to verified contract addresses" not in report["not_verified_yet"]
    assert report["not_verified_yet"] == ["live execute receipt and external settlement receipt gates"]
    assert report["goal_can_be_marked_complete"] is False


def test_cli_writes_artifact_and_require_ready_blocks(tmp_path, capsys):
    _write_package(tmp_path)
    _write_json(
        tmp_path / mod.BASE_SEPOLIA_DEPLOYMENT,
        {"MeshGovernance": "0xGovNew", "X0TToken": "0xTokNew", "chainId": 84532},
    )
    for relative in mod.OPERATOR_CONFIGS:
        _write(tmp_path / relative, 'dao:\n  contractAddress: "0x0000000000000000000000000000000000000000"\n')
    _write(tmp_path / "contracts/Voting.sol", "func vote(uint256 id) external {}\n")
    output = tmp_path / "out.json"

    exit_code = mod.main([
        "--root",
        str(tmp_path),
        "--write-json",
        "--output-json",
        str(output),
        "--require-ready",
    ])

    assert exit_code == 2
    assert output.exists()
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["schema_version"] == mod.SCHEMA_VERSION
    assert saved["contract_readiness_clear"] is False
    printed = json.loads(capsys.readouterr().out)
    assert printed["decision"].startswith("BLOCKED_ON_")


def test_bridge_placeholder_is_reported_as_bridge_specific(tmp_path):
    _write_package(tmp_path, engine=">=20.0.0")
    _install_ready_packages(tmp_path)
    _write_build_verification(tmp_path)
    _write_json(
        tmp_path / mod.BASE_SEPOLIA_DEPLOYMENT,
        {"MeshGovernance": VALID_GOV, "X0TToken": VALID_TOKEN, "chainId": 84532},
    )
    _write(
        tmp_path / mod.OPERATOR_CONFIGS[0],
        f"dao:\n  contractAddress: \"{VALID_GOV}\"\n",
    )
    _write(
        tmp_path / mod.OPERATOR_CONFIGS[1],
        "\n".join(
            [
                "spec:",
                "  dao:",
                "    bridge:",
                "      enabled: true",
                "      contractAddress: \"0x0000000000000000000000000000000000000000\"",
            ]
        ),
    )
    _write_valid_deployment_and_configs(tmp_path)
    _write(
        tmp_path / mod.OPERATOR_CONFIGS[1],
        "\n".join(
            [
                "spec:",
                "  dao:",
                "    bridge:",
                "      enabled: true",
                "      contractAddress: \"0x0000000000000000000000000000000000000000\"",
            ]
        ),
    )

    report = mod.build_report(tmp_path, node_version="v22.10.0")

    bridge_address = report["operator_configs"]["checks"][1]["addresses"][0]
    assert bridge_address["address_kind"] == "bridge_contract"
    assert bridge_address["status"] == "MISSING_BRIDGE_CONTRACT_ADDRESS"
    assert report["missing_inputs"][0]["status"] == "OPERATOR_INPUT_REQUIRED"
    assert report["summary"]["missing_inputs_operator_input_required"] == 1
    assert report["summary"]["missing_inputs_generic_operator_required"] == 0
    assert "do not substitute X0TToken or MeshGovernance" in report["missing_inputs"][0]["reason"]
    assert report["missing_inputs"][0]["commands"][1].startswith(
        "python3 scripts/ops/apply_x0t_bridge_contract_address.py"
    )
    assert "deployed bridge contract address for operator bridge config" in report["not_verified_yet"]
    assert "authoritative Base Sepolia deployment manifest with non-placeholder addresses" not in report["not_verified_yet"]


def test_missing_build_verification_is_local_verification_required(tmp_path):
    _write_package(tmp_path)
    _install_ready_packages(tmp_path)
    _write_valid_deployment_and_configs(tmp_path)

    report = mod.build_report(tmp_path, node_version="v22.10.0")

    missing_ids = {item["id"] for item in report["missing_inputs"]}
    assert report["contract_readiness_clear"] is False
    assert report["summary"]["contract_build_verification_ready"] is False
    assert "contract_build_verification" in missing_ids
    assert "node_runtime" not in missing_ids
    assert "successful Hardhat compile/test under the required Node runtime" in report["not_verified_yet"]


def test_build_verification_satisfies_effective_node_runtime(tmp_path):
    _write_package(tmp_path)
    _install_ready_packages(tmp_path)
    _write_build_verification(tmp_path)
    _write_valid_deployment_and_configs(tmp_path)

    report = mod.build_report(tmp_path, node_version="v20.19.6")

    assert report["contract_readiness_clear"] is True
    assert report["summary"]["node_runtime_ready"] is False
    assert report["summary"]["effective_node_runtime_ready"] is True
    assert report["summary"]["node_runtime_ready_source"] == "contract_build_verification"
    assert report["missing_inputs"] == []
    assert "Node runtime matching the contract package engine" not in report["not_verified_yet"]


def test_missing_bridge_source_surface_is_repo_required(tmp_path):
    _write_package(tmp_path)
    _install_ready_packages(tmp_path)
    _write_build_verification(tmp_path)
    _write_valid_deployment_and_configs(tmp_path)
    (tmp_path / mod.BRIDGE_DEPLOY_SCRIPT).unlink()

    report = mod.build_report(tmp_path, node_version="v22.10.0")

    missing_ids = {item["id"] for item in report["missing_inputs"]}
    assert report["contract_readiness_clear"] is False
    assert report["decision"] == "BLOCKED_ON_BRIDGE_SOURCE_SURFACE"
    assert report["summary"]["bridge_contract_source_ready"] is False
    assert "x0t_bridge_contract_source_surface" in missing_ids
    assert "deployable X0TBridge contract source/deploy/test surface" in report["not_verified_yet"]
