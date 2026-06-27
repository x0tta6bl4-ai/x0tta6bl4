/**
 * Deployment script for x0tta6bl4 DAO smart contracts
 * Deploys to Polygon Mumbai testnet
 * Order: GovernanceToken → Timelock → Governor → Treasury
 * Version: 1.0.0
 */

const hre = require('hardhat');
const { ethers } = require('hardhat');
const fs = require('fs');
const path = require('path');

// Deployment configuration
const DEPLOYMENT_CONFIG = {
  governance_token: {
    name: 'x0tta6bl4 Governance Token',
    symbol: 'X0OTTA',
    max_supply: ethers.parseEther('10000000'), // 10M tokens
  },
  governor: {
    voting_delay: 1, // blocks
    voting_period: 50400, // blocks (~1 week)
    proposal_threshold: ethers.parseEther('100'), // 100 tokens
    quorum_percentage: 10, // 10%
  },
  timelock: {
    min_delay: 2 * 24 * 60 * 60, // 2 days in seconds (172800)
  },
  treasury: {
    initial_balance: 0,
  },
};

async function deployDAO() {
  try {
    console.log('\n╔════════════════════════════════════════════════════╗');
    console.log('║     x0tta6bl4 DAO Smart Contract Deployment        ║');
    console.log('╚════════════════════════════════════════════════════╝\n');

    // Get deployer account
    const [deployer] = await ethers.getSigners();
    console.log(`📍 Deployer Account: ${deployer.address}`);
    console.log(`💰 Balance: ${ethers.formatEther(await ethers.provider.getBalance(deployer.address))} MATIC\n`);

    const deploymentAddresses = {};

    // ============ 1. Deploy GovernanceToken ============
    console.log('📦 Step 1: Deploying GovernanceToken (ERC-20 + Voting)...');
    const GovernanceToken = await ethers.getContractFactory('GovernanceToken');
    const governanceToken = await GovernanceToken.deploy();
    await governanceToken.waitForDeployment();
    deploymentAddresses.governanceToken = await governanceToken.getAddress();
    console.log(`✅ GovernanceToken deployed at: ${deploymentAddresses.governanceToken}\n`);

    // ============ 2. Deploy Timelock ============
    console.log('📦 Step 2: Deploying Timelock (Execution Delay)...');
    const Timelock = await ethers.getContractFactory('Timelock');
    const timelock = await Timelock.deploy(
      [deployer.address], // proposers
      [deployer.address], // executors
      deployer.address  // admin
    );
    await timelock.waitForDeployment();
    deploymentAddresses.timelock = await timelock.getAddress();
    console.log(`✅ Timelock deployed at: ${deploymentAddresses.timelock}`);
    console.log(`   Min Delay: ${DEPLOYMENT_CONFIG.timelock.min_delay} seconds (2 days)\n`);

    // ============ 3. Deploy Governor ============
    console.log('📦 Step 3: Deploying Governor (Voting & Proposals)...');
    const Governor = await ethers.getContractFactory('Governor');
    const governor = await Governor.deploy(
      deploymentAddresses.governanceToken,
      deploymentAddresses.timelock,
      DEPLOYMENT_CONFIG.governor.voting_delay,
      DEPLOYMENT_CONFIG.governor.voting_period,
      DEPLOYMENT_CONFIG.governor.proposal_threshold,
      DEPLOYMENT_CONFIG.governor.quorum_percentage
    );
    await governor.waitForDeployment();
    deploymentAddresses.governor = await governor.getAddress();
    console.log(`✅ Governor deployed at: ${deploymentAddresses.governor}`);
    console.log(`   Voting Delay: ${DEPLOYMENT_CONFIG.governor.voting_delay} blocks`);
    console.log(`   Voting Period: ${DEPLOYMENT_CONFIG.governor.voting_period} blocks (~1 week)`);
    console.log(`   Proposal Threshold: ${ethers.formatEther(DEPLOYMENT_CONFIG.governor.proposal_threshold)} tokens`);
    console.log(`   Quorum: ${DEPLOYMENT_CONFIG.governor.quorum_percentage}%\n`);

    // ============ 4. Deploy Treasury ============
    console.log('📦 Step 4: Deploying Treasury (Fund Management)...');
    const Treasury = await ethers.getContractFactory('Treasury');
    const treasury = await Treasury.deploy(deploymentAddresses.governor);
    await treasury.waitForDeployment();
    deploymentAddresses.treasury = await treasury.getAddress();
    console.log(`✅ Treasury deployed at: ${deploymentAddresses.treasury}\n`);

    // ============ 5. Setup Roles & Permissions ============
    console.log('🔐 Step 5: Setting up Roles & Permissions...');

    // Grant MINTER_ROLE to deployer for initial token distribution
    const MINTER_ROLE = await governanceToken.MINTER_ROLE();
    await governanceToken.grantRole(MINTER_ROLE, deployer.address);
    console.log(`✅ Granted MINTER_ROLE to deployer\n`);

    // ============ 6. Verify Contract Initialization ============
    console.log('✔️  Step 6: Verifying Contract Initialization...');
    
    const tokenName = await governanceToken.name();
    const tokenSymbol = await governanceToken.symbol();
    const votingDelay = await governor.votingDelay();
    const votingPeriod = await governor.votingPeriod();
    const proposalThreshold = await governor.proposalThreshold();
    const quorum = await governor.quorumNumerator();

    console.log(`   Token Name: ${tokenName}`);
    console.log(`   Token Symbol: ${tokenSymbol}`);
    console.log(`   Governor Voting Delay: ${votingDelay}`);
    console.log(`   Governor Voting Period: ${votingPeriod}`);
    console.log(`   Governor Proposal Threshold: ${ethers.formatEther(proposalThreshold)} tokens`);
    console.log(`   Governor Quorum: ${quorum}%\n`);

    // ============ 7. Save Deployment Addresses ============
    console.log('💾 Step 7: Saving Deployment Addresses...');
    const deploymentInfo = {
      network: hre.network.name,
      timestamp: new Date().toISOString(),
      deployer: deployer.address,
      addresses: {
        governanceToken: deploymentAddresses.governanceToken,
        timelock: deploymentAddresses.timelock,
        governor: deploymentAddresses.governor,
        treasury: deploymentAddresses.treasury,
      },
      config: DEPLOYMENT_CONFIG,
    };

    const deploymentPath = path.join(__dirname, `../deployments/${hre.network.name}.json`);
    const deploymentsDir = path.dirname(deploymentPath);
    
    if (!fs.existsSync(deploymentsDir)) {
      fs.mkdirSync(deploymentsDir, { recursive: true });
    }
    
    fs.writeFileSync(deploymentPath, JSON.stringify(deploymentInfo, null, 2));
    console.log(`✅ Deployment addresses saved to ${deploymentPath}\n`);

    // ============ Summary ============
    console.log('╔════════════════════════════════════════════════════╗');
    console.log('║              DEPLOYMENT SUCCESSFUL ✅              ║');
    console.log('╚════════════════════════════════════════════════════╝\n');
    
    console.log('📋 CONTRACT ADDRESSES:');
    console.log(`   GovernanceToken: ${deploymentAddresses.governanceToken}`);
    console.log(`   Timelock:        ${deploymentAddresses.timelock}`);
    console.log(`   Governor:        ${deploymentAddresses.governor}`);
    console.log(`   Treasury:        ${deploymentAddresses.treasury}\n`);

    console.log('🔗 NEXT STEPS:');
    console.log('   1. Mint initial governance tokens');
    console.log('   2. Verify contracts on PolygonScan');
    console.log('   3. Create first governance proposal');
    console.log('   4. Test voting and execution flow');
    console.log('   5. Integrate with MAPE-K system\n');

    return deploymentAddresses;

  } catch (error) {
    console.error('❌ Deployment failed:', error);
    process.exit(1);
  }
}

// Run deployment
deployDAO().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

module.exports = { deployDAO, DEPLOYMENT_CONFIG };
