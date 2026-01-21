/**
 * Hardhat tests for x0tta6bl4 DAO smart contracts
 * Tests: GovernanceToken, Governor, Timelock, Treasury
 * Version: 1.0.0
 */

const { expect } = require('chai');
const { ethers } = require('hardhat');
const { time } = require('@nomicfoundation/hardhat-network-helpers');

describe('x0tta6bl4 DAO Smart Contracts', function () {
  let governanceToken, governor, timelock, treasury;
  let owner, addr1, addr2, addrs;

  const GOVERNANCE_TOKEN_NAME = 'x0tta6bl4 Governance Token';
  const GOVERNANCE_TOKEN_SYMBOL = 'X0OTTA';
  const TOTAL_SUPPLY = ethers.parseEther('10000000'); // 10M tokens
  const VOTING_DELAY = 1n;
  const VOTING_PERIOD = 50400n; // ~1 week
  const PROPOSAL_THRESHOLD = ethers.parseEther('100');
  const QUORUM_PERCENTAGE = 10;
  const TIMELOCK_DELAY = 2n * 24n * 60n * 60n; // 2 days

  beforeEach(async function () {
    [owner, addr1, addr2, ...addrs] = await ethers.getSigners();

    // Deploy GovernanceToken
    const GovernanceToken = await ethers.getContractFactory('GovernanceToken');
    governanceToken = await GovernanceToken.deploy();
    await governanceToken.waitForDeployment();

    // Deploy Timelock
    const Timelock = await ethers.getContractFactory('Timelock');
    timelock = await Timelock.deploy(
      [owner.address],
      [owner.address],
      owner.address
    );
    await timelock.waitForDeployment();

    // Deploy Governor
    const Governor = await ethers.getContractFactory('Governor');
    governor = await Governor.deploy(
      await governanceToken.getAddress(),
      await timelock.getAddress(),
      VOTING_DELAY,
      VOTING_PERIOD,
      PROPOSAL_THRESHOLD,
      QUORUM_PERCENTAGE
    );
    await governor.waitForDeployment();

    // Deploy Treasury
    const Treasury = await ethers.getContractFactory('Treasury');
    treasury = await Treasury.deploy(await governor.getAddress());
    await treasury.waitForDeployment();

    // Grant MINTER_ROLE to owner
    const MINTER_ROLE = await governanceToken.MINTER_ROLE();
    await governanceToken.grantRole(MINTER_ROLE, owner.address);
  });

  describe('GovernanceToken', function () {
    it('Should have correct name and symbol', async function () {
      expect(await governanceToken.name()).to.equal(GOVERNANCE_TOKEN_NAME);
      expect(await governanceToken.symbol()).to.equal(GOVERNANCE_TOKEN_SYMBOL);
    });

    it('Should have 18 decimals', async function () {
      expect(await governanceToken.decimals()).to.equal(18);
    });

    it('Should mint tokens to owner', async function () {
      const mintAmount = ethers.parseEther('1000');
      await governanceToken.mint(owner.address, mintAmount);
      expect(await governanceToken.balanceOf(owner.address)).to.equal(mintAmount);
    });

    it('Should allow burning tokens', async function () {
      const mintAmount = ethers.parseEther('1000');
      await governanceToken.mint(owner.address, mintAmount);
      
      const burnAmount = ethers.parseEther('100');
      await governanceToken.burn(burnAmount);
      
      expect(await governanceToken.balanceOf(owner.address)).to.equal(mintAmount - burnAmount);
    });

    it('Should allow voting power delegation', async function () {
      const mintAmount = ethers.parseEther('1000');
      await governanceToken.mint(owner.address, mintAmount);
      
      await governanceToken.delegate(owner.address);
      
      const blockNumber = await ethers.provider.getBlockNumber();
      const votes = await governanceToken.getVotes(owner.address);
      expect(votes).to.equal(mintAmount);
    });
  });

  describe('Governor', function () {
    it('Should have correct voting parameters', async function () {
      expect(await governor.votingDelay()).to.equal(VOTING_DELAY);
      expect(await governor.votingPeriod()).to.equal(VOTING_PERIOD);
      expect(await governor.proposalThreshold()).to.equal(PROPOSAL_THRESHOLD);
      expect(await governor.quorumNumerator()).to.equal(QUORUM_PERCENTAGE);
    });

    it('Should create proposal with sufficient tokens', async function () {
      // Mint tokens to addr1
      await governanceToken.mint(addr1.address, PROPOSAL_THRESHOLD);
      
      // Delegate voting power
      await governanceToken.connect(addr1).delegate(addr1.address);
      await time.mine(1); // Wait for delegation to take effect
      
      // Create proposal
      const targets = [treasury.address];
      const values = [0];
      const calldatas = [
        treasury.interface.encodeFunctionData('depositToken', [
          await governanceToken.getAddress(),
          ethers.parseEther('100'),
        ]),
      ];
      const description = 'Test Proposal';
      const descriptionHash = ethers.id(description);
      
      const tx = await governor.connect(addr1).propose(
        targets,
        values,
        calldatas,
        description
      );
      
      const receipt = await tx.wait();
      expect(receipt.status).to.equal(1);
    });

    it('Should allow voting on proposals', async function () {
      // Setup: mint tokens and create proposal
      await governanceToken.mint(addr1.address, PROPOSAL_THRESHOLD);
      await governanceToken.connect(addr1).delegate(addr1.address);
      await time.mine(1);
      
      const targets = [treasury.address];
      const values = [0];
      const calldatas = [
        treasury.interface.encodeFunctionData('depositToken', [
          await governanceToken.getAddress(),
          ethers.parseEther('100'),
        ]),
      ];
      const description = 'Test Proposal';
      
      const tx = await governor.connect(addr1).propose(
        targets,
        values,
        calldatas,
        description
      );
      
      const receipt = await tx.wait();
      const proposalId = receipt.logs[0].topics[1]; // Extract proposal ID
      
      // Move to voting phase
      await time.mine(Number(VOTING_DELAY) + 1);
      
      // Cast vote (1 = FOR)
      await governor.connect(addr1).castVote(proposalId, 1);
      
      const proposalVotes = await governor.proposalVotes(proposalId);
      expect(proposalVotes.forVotes).to.be.gt(0);
    });
  });

  describe('Timelock', function () {
    it('Should have correct min delay', async function () {
      const minDelay = await timelock.getMinDelay();
      expect(minDelay).to.equal(TIMELOCK_DELAY);
    });

    it('Should queue and execute operations after delay', async function () {
      const data = treasury.interface.encodeFunctionData('depositToken', [
        await governanceToken.getAddress(),
        ethers.parseEther('100'),
      ]);
      
      const salt = ethers.id('test-operation');
      
      // Queue operation
      await timelock.schedule(
        treasury.address,
        0, // value
        data,
        '0x00', // predecessor
        salt,
        TIMELOCK_DELAY
      );
      
      // Fast forward time
      await time.increase(Number(TIMELOCK_DELAY) + 1);
      
      // Execute operation
      await timelock.execute(
        treasury.address,
        0,
        data,
        '0x00',
        salt
      );
    });
  });

  describe('Treasury', function () {
    it('Should accept ETH deposits', async function () {
      const depositAmount = ethers.parseEther('1');
      
      // Send ETH to treasury
      await owner.sendTransaction({
        to: await treasury.getAddress(),
        value: depositAmount,
      });
      
      const balance = await ethers.provider.getBalance(await treasury.getAddress());
      expect(balance).to.equal(depositAmount);
    });

    it('Should withdraw ETH if governance approves', async function () {
      const depositAmount = ethers.parseEther('1');
      const withdrawAmount = ethers.parseEther('0.5');
      
      // Deposit
      await owner.sendTransaction({
        to: await treasury.getAddress(),
        value: depositAmount,
      });
      
      // Grant GOVERNANCE_ROLE to owner
      const GOVERNANCE_ROLE = await treasury.GOVERNANCE_ROLE();
      await treasury.grantRole(GOVERNANCE_ROLE, owner.address);
      
      // Withdraw
      const initialBalance = await ethers.provider.getBalance(owner.address);
      const tx = await treasury.withdrawETH(owner.address, withdrawAmount);
      const receipt = await tx.wait();
      
      const treasuryBalance = await ethers.provider.getBalance(await treasury.getAddress());
      expect(treasuryBalance).to.equal(depositAmount - withdrawAmount);
    });

    it('Should deposit and withdraw ERC-20 tokens', async function () {
      const depositAmount = ethers.parseEther('1000');
      
      // Grant GOVERNANCE_ROLE to owner
      const GOVERNANCE_ROLE = await treasury.GOVERNANCE_ROLE();
      await treasury.grantRole(GOVERNANCE_ROLE, owner.address);
      
      // Mint tokens to treasury for withdrawal test
      await governanceToken.mint(await treasury.getAddress(), depositAmount);
      
      // Withdraw tokens
      const initialBalance = await governanceToken.balanceOf(owner.address);
      await treasury.withdrawToken(await governanceToken.getAddress(), owner.address, depositAmount);
      
      const finalBalance = await governanceToken.balanceOf(owner.address);
      expect(finalBalance).to.equal(initialBalance + depositAmount);
    });
  });

  describe('Integration Tests', function () {
    it('Should execute full governance flow', async function () {
      // 1. Mint tokens
      const tokenAmount = PROPOSAL_THRESHOLD * 2n;
      await governanceToken.mint(addr1.address, tokenAmount);
      
      // 2. Delegate voting power
      await governanceToken.connect(addr1).delegate(addr1.address);
      await time.mine(1);
      
      // 3. Create proposal
      const targets = [treasury.address];
      const values = [0];
      const calldatas = [
        treasury.interface.encodeFunctionData('depositToken', [
          await governanceToken.getAddress(),
          ethers.parseEther('100'),
        ]),
      ];
      const description = 'Full Flow Test';
      
      const proposeTx = await governor.connect(addr1).propose(
        targets,
        values,
        calldatas,
        description
      );
      
      const proposeReceipt = await proposeTx.wait();
      const proposalId = proposeReceipt.logs[0].topics[1];
      
      // 4. Wait for voting to start
      await time.mine(Number(VOTING_DELAY) + 1);
      
      // 5. Vote
      await governor.connect(addr1).castVote(proposalId, 1); // FOR
      
      // 6. Wait for voting to end
      await time.mine(Number(VOTING_PERIOD) + 1);
      
      // 7. Queue proposal
      const descriptionHash = ethers.id(description);
      await governor.queue(
        targets,
        values,
        calldatas,
        descriptionHash
      );
      
      // 8. Wait for timelock delay
      await time.increase(Number(TIMELOCK_DELAY) + 1);
      
      // 9. Execute proposal
      await governor.execute(
        targets,
        values,
        calldatas,
        descriptionHash
      );
      
      const state = await governor.state(proposalId);
      expect(state).to.equal(7); // Executed state
    });
  });
});
