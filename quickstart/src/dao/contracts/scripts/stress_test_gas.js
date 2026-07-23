const { ethers } = require("hardhat");

async function main() {
  console.log("🚀 Starting X0T Reward Distribution Stress Test...");

  // 1. Setup
  const [owner] = await ethers.getSigners();
  const X0T = await ethers.getContractFactory("X0TToken");
  const x0t = await X0T.deploy();
  await x0t.waitForDeployment();
  const address = await x0t.getAddress();
  console.log(`✅ Token deployed at: ${address}`);

  const nodeCount = 100;
  const recipients = [];
  const uptimes = [];

  console.log(`Generating ${nodeCount} dummy addresses and stakes...`);
  
  // 2. Generate nodes and stake tokens
  for (let i = 0; i < nodeCount; i++) {
    const wallet = ethers.Wallet.createRandom();
    recipients.push(wallet.address);
    uptimes.push(Math.floor(Math.random() * 20) + 80); // 80-100% uptime

    // Stake some tokens for each to ensure distribution logic is exercised
    // (Owner sends tokens to wallet, then wallet stakes)
    const stakeAmount = ethers.parseEther("1000");
    await x0t.transfer(wallet.address, stakeAmount);
    
    // We need to connect as the wallet to stake
    const walletWithProvider = wallet.connect(ethers.provider);
    
    // Fund wallet with ETH for gas (local)
    await owner.sendTransaction({
      to: wallet.address,
      value: ethers.parseEther("1.0")
    });

    await x0t.connect(walletWithProvider).stake(stakeAmount);
    if (i % 20 === 0) console.log(`   Processed ${i} nodes...`);
  }

  // 3. Fast-forward time to end of epoch (1 hour)
  console.log("Fast-forwarding time by 1 hour...");
  await ethers.provider.send("evm_increaseTime", [3601]);
  await ethers.provider.send("evm_mine");

  // 4. Measure Gas for distribution
  console.log(`\n📊 Running distributeEpochRewards for ${nodeCount} nodes...`);
  
  const tx = await x0t.distributeEpochRewards(recipients, uptimes);
  const receipt = await tx.wait();

  const gasUsed = receipt.gasUsed;
  console.log("-----------------------------------------");
  console.log(`🔥 Gas Used: ${gasUsed.toString()}`);
  
  // Base Mainnet pricing estimates
  const gasPriceGwei = 0.1; // Typical Base gas price
  const ethPriceUSD = 3500;
  const costETH = Number(gasUsed) * gasPriceGwei * 1e-9;
  const costUSD = costETH * ethPriceUSD;

  console.log(`💰 Estimated Cost on Base: ${costETH.toFixed(6)} ETH (~$${costUSD.toFixed(4)})`);
  console.log("-----------------------------------------");

  if (gasUsed > 10000000n) {
    console.log("⚠️ WARNING: Gas usage is high (> 10M). This might hit block limits if node count grows.");
  } else {
    console.log("✅ Gas usage is well within limits for 100 nodes.");
  }
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
