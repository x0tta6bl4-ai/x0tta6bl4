/**
 * X0T Bridge deployment script.
 *
 * Base Sepolia usage:
 *   X0T_DEPLOY_BRIDGE_APPROVAL=deploy-bridge-base-sepolia \
 *   X0T_TOKEN_ADDRESS=0x... \
 *   X0T_BRIDGE_OPERATOR_ADDRESS=0x... \
 *   PRIVATE_KEY=0x... \
 *   npx hardhat run scripts/deploy_bridge.js --network base_sepolia
 */

import hre from "hardhat";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BASE_SEPOLIA_CHAIN_ID = 84532;
const APPROVAL_VALUE = "deploy-bridge-base-sepolia";
const ZERO_PRIVATE_KEY =
    "0x0000000000000000000000000000000000000000000000000000000000000001";

function requireAddress(ethers, name, value) {
    if (!value || !ethers.isAddress(value) || value === ethers.ZeroAddress) {
        throw new Error(`${name} must be a non-zero 0x-prefixed 20-byte address`);
    }
    return value;
}

function assertLiveDeployApproved(networkName, chainId) {
    const isBaseSepolia = networkName === "base_sepolia" || chainId === BASE_SEPOLIA_CHAIN_ID;
    if (!isBaseSepolia) {
        return;
    }

    if (process.env.X0T_DEPLOY_BRIDGE_APPROVAL !== APPROVAL_VALUE) {
        throw new Error(
            `Base Sepolia bridge deployment requires X0T_DEPLOY_BRIDGE_APPROVAL=${APPROVAL_VALUE}`
        );
    }
    if (!process.env.PRIVATE_KEY || process.env.PRIVATE_KEY === ZERO_PRIVATE_KEY) {
        throw new Error("Base Sepolia bridge deployment requires a real PRIVATE_KEY");
    }
    if (!process.env.X0T_BRIDGE_OPERATOR_ADDRESS) {
        throw new Error("Base Sepolia bridge deployment requires X0T_BRIDGE_OPERATOR_ADDRESS");
    }
}

async function main() {
    const { ethers, networkName } = await hre.network.getOrCreate();
    const network = await ethers.provider.getNetwork();
    const chainId = Number(network.chainId);

    assertLiveDeployApproved(networkName, chainId);

    const [deployer] = await ethers.getSigners();
    const tokenAddress = requireAddress(ethers, "X0T_TOKEN_ADDRESS", process.env.X0T_TOKEN_ADDRESS);
    const operatorAddress = requireAddress(
        ethers,
        "X0T_BRIDGE_OPERATOR_ADDRESS",
        process.env.X0T_BRIDGE_OPERATOR_ADDRESS || deployer.address
    );

    console.log("Deploying X0TBridge");
    console.log("Network:", networkName);
    console.log("Chain ID:", chainId);
    console.log("Deployer:", deployer.address);
    console.log("X0T token:", tokenAddress);
    console.log("Bridge operator:", operatorAddress);

    const X0TBridge = await ethers.getContractFactory("X0TBridge");
    const bridge = await X0TBridge.deploy(tokenAddress, operatorAddress);
    await bridge.waitForDeployment();

    const bridgeAddress = await bridge.getAddress();
    const deploymentInfo = {
        network: networkName,
        chainId,
        deployer: deployer.address,
        contracts: {
            X0TToken: tokenAddress,
            X0TBridge: bridgeAddress,
        },
        bridgeOperator: operatorAddress,
        timestamp: new Date().toISOString(),
        blockNumber: await ethers.provider.getBlockNumber(),
        approval: process.env.X0T_DEPLOY_BRIDGE_APPROVAL || "",
    };

    const deploymentsDir = path.join(__dirname, "..", "deployments");
    fs.mkdirSync(deploymentsDir, { recursive: true });

    const filename = `bridge_${networkName}_${Date.now()}.json`;
    fs.writeFileSync(
        path.join(deploymentsDir, filename),
        JSON.stringify(deploymentInfo, null, 2)
    );

    console.log("X0TBridge deployed to:", bridgeAddress);
    console.log("Deployment info saved to:", `deployments/${filename}`);
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("Deployment failed:", error);
        process.exit(1);
    });
