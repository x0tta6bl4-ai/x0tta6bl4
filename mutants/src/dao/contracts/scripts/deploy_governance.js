const hre = require("hardhat");

async function main() {
  console.log("🚀 Deploying MeshGovernance...\n");

  // Get deployer account
  const [deployer] = await hre.ethers.getSigners();
  console.log("📝 Deploying with account:", deployer.address);
  console.log("💰 Account balance:", hre.ethers.formatEther(await hre.ethers.provider.getBalance(deployer.address)), "ETH\n");

  // Get X0TToken address from latest deployment
  const fs = require("fs");
  const path = require("path");
  const deploymentsDir = path.join(__dirname, "../deployments");
  
  let tokenAddress;
  const deploymentFiles = fs.readdirSync(deploymentsDir)
    .filter(f => f.endsWith(".json") && f.includes("localhost"))
    .sort()
    .reverse();
  
  if (deploymentFiles.length > 0) {
    const latestDeployment = JSON.parse(
      fs.readFileSync(path.join(deploymentsDir, deploymentFiles[0]), "utf8")
    );
    tokenAddress = latestDeployment.contract.address;
    console.log("📄 Using X0TToken:", tokenAddress);
  } else {
    throw new Error("No X0TToken deployment found. Deploy token first.");
  }

  // Deploy MeshGovernance
  const MeshGovernance = await hre.ethers.getContractFactory("MeshGovernance");
  const governance = await MeshGovernance.deploy(tokenAddress);

  await governance.waitForDeployment();
  const governanceAddress = await governance.getAddress();

  console.log("\n✅ MeshGovernance deployed to:", governanceAddress);

  // Get contract info
  const proposalCount = await governance.proposalCount();
  const votingDelay = await governance.votingDelay();
  const votingPeriod = await governance.votingPeriod();

  console.log("\n📊 Governance Info:");
  console.log("  Proposal Count:", proposalCount.toString());
  console.log("  Voting Delay:", votingDelay.toString(), "seconds");
  console.log("  Voting Period:", votingPeriod.toString(), "seconds");
  console.log("  Quorum:", "50%");
  console.log("  Threshold:", "50% + 1");

  // Save deployment info
  const deploymentInfo = {
    network: hre.network.name,
    chainId: (await hre.ethers.provider.getNetwork()).chainId.toString(),
    deployer: deployer.address,
    contract: {
      name: "MeshGovernance",
      address: governanceAddress,
      tokenAddress: tokenAddress
    },
    timestamp: new Date().toISOString(),
    blockNumber: (await hre.ethers.provider.getBlockNumber()).toString()
  };

  const deploymentFile = path.join(
    deploymentsDir,
    `governance_${hre.network.name}_${Date.now()}.json`
  );
  fs.writeFileSync(deploymentFile, JSON.stringify(deploymentInfo, null, 2));
  console.log("\n📁 Deployment info saved to:", deploymentFile);

  console.log("\n" + "=".repeat(50));
  console.log("🎉 DEPLOYMENT COMPLETE");
  console.log("=".repeat(50));
  console.log("\nContract Address:", governanceAddress);
  console.log("Network:", hre.network.name);
  console.log("\nNext steps:");
  console.log("1. Link governance contract in Python code");
  console.log("2. Test creating proposals");
  console.log("3. Test voting");
  console.log("4. Test proposal execution");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });

