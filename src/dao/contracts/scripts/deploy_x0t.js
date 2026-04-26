/**
 * X0T Token Deployment Script
 * 
 * Usage:
 *   npx hardhat run scripts/deploy_x0t.js --network polygon_mumbai
 *   npx hardhat run scripts/deploy_x0t.js --network base_sepolia
 *   npx hardhat run scripts/deploy_x0t.js --network localhost
 * 
 * Environment variables required:
 *   PRIVATE_KEY - Deployer wallet private key
 *   POLYGONSCAN_API_KEY - For contract verification (optional)
 */

import hre from "hardhat";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

async function main() {
    console.log("🚀 Deploying X0T Token...\n");
    const { ethers, networkName } = await hre.network.getOrCreate();

    // Get deployer
    const [deployer] = await ethers.getSigners();
    console.log("Deployer address:", deployer.address);

    const balance = await ethers.provider.getBalance(deployer.address);
    console.log("Deployer balance:", ethers.formatEther(balance), "ETH/MATIC\n");

    // Deploy X0TToken
    console.log("Deploying X0TToken contract...");
    const X0TToken = await ethers.getContractFactory("X0TToken");
    const token = await X0TToken.deploy();
    await token.waitForDeployment();

    const tokenAddress = await token.getAddress();
    console.log("✅ X0TToken deployed to:", tokenAddress);

    // Get deployment info
    const totalSupply = await token.totalSupply();
    const symbol = await token.symbol();
    const name = await token.name();

    console.log("\n📊 Token Info:");
    console.log("  Name:", name);
    console.log("  Symbol:", symbol);
    console.log("  Total Supply:", ethers.formatEther(totalSupply), symbol);
    console.log("  Decimals: 18");

    // Constants
    console.log("\n💰 Economics:");
    console.log("  Min Stake:", ethers.formatEther(await token.MIN_STAKE()), symbol);
    console.log("  Stake Lock Period:", (await token.STAKE_LOCK_PERIOD()).toString(), "seconds");
    console.log("  Reward Pool/Epoch:", ethers.formatEther(await token.REWARD_POOL_PER_EPOCH()), symbol);
    console.log("  Epoch Duration:", (await token.EPOCH_DURATION()).toString(), "seconds");
    console.log("  Price per Relay:", ethers.formatEther(await token.PRICE_PER_RELAY()), symbol);
    console.log("  Fee Percent:", (await token.FEE_PERCENT()).toString(), "%");

    // Save deployment info
    const deploymentInfo = {
        network: networkName,
        chainId: (await ethers.provider.getNetwork()).chainId.toString(),
        deployer: deployer.address,
        contract: {
            name: "X0TToken",
            address: tokenAddress,
            symbol: symbol,
            totalSupply: ethers.formatEther(totalSupply)
        },
        timestamp: new Date().toISOString(),
        blockNumber: await ethers.provider.getBlockNumber()
    };

    // Use imported fs/path
    // const fs = require("fs");
    // const path = require("path");

    const deploymentsDir = path.join(__dirname, "..", "deployments");
    if (!fs.existsSync(deploymentsDir)) {
        fs.mkdirSync(deploymentsDir, { recursive: true });
    }

    const filename = `x0t_${networkName}_${Date.now()}.json`;
    fs.writeFileSync(
        path.join(deploymentsDir, filename),
        JSON.stringify(deploymentInfo, null, 2)
    );
    console.log("\n📁 Deployment info saved to:", `deployments/${filename}`);

    console.log("\nℹ️ Explorer verification is not bundled in the public Hardhat 3 package.");

    console.log("\n" + "=".repeat(50));
    console.log("🎉 DEPLOYMENT COMPLETE");
    console.log("=".repeat(50));
    console.log("\nContract Address:", tokenAddress);
    console.log("Network:", networkName);
    console.log("\nNext steps:");
    console.log("1. Add token to MetaMask:", tokenAddress);
    console.log("2. Authorize relay nodes: token.setRelayerAuthorized(address, true)");
    console.log("3. Stake tokens: token.stake(amount)");
    console.log("4. Set up epoch rewards scheduler");
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error("❌ Deployment failed:", error);
        process.exit(1);
    });
