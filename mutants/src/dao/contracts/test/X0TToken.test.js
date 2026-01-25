/**
 * X0T Token Unit Tests
 * 
 * Run: npx hardhat test
 */

const { expect } = require("chai");
const { ethers } = require("hardhat");

describe("X0TToken", function () {
    let token;
    let owner;
    let user1;
    let user2;
    let relayer;

    const INITIAL_SUPPLY = ethers.parseEther("1000000000"); // 1 billion
    const MIN_STAKE = ethers.parseEther("100");
    const PRICE_PER_RELAY = ethers.parseEther("0.0001");

    beforeEach(async function () {
        [owner, user1, user2, relayer] = await ethers.getSigners();
        
        const X0TToken = await ethers.getContractFactory("X0TToken");
        token = await X0TToken.deploy();
        await token.waitForDeployment();

        // Transfer some tokens to users for testing
        await token.transfer(user1.address, ethers.parseEther("10000"));
        await token.transfer(user2.address, ethers.parseEther("10000"));
        await token.transfer(relayer.address, ethers.parseEther("1000"));
    });

    describe("Deployment", function () {
        it("Should set correct name and symbol", async function () {
            expect(await token.name()).to.equal("x0tta6bl4 Token");
            expect(await token.symbol()).to.equal("X0T");
        });

        it("Should mint initial supply to deployer", async function () {
            const ownerBalance = await token.balanceOf(owner.address);
            // Owner has initial supply minus what was transferred to users
            expect(ownerBalance).to.be.gt(0);
        });

        it("Should have correct constants", async function () {
            expect(await token.MIN_STAKE()).to.equal(MIN_STAKE);
            expect(await token.PRICE_PER_RELAY()).to.equal(PRICE_PER_RELAY);
            expect(await token.FEE_PERCENT()).to.equal(1);
        });
    });

    describe("Staking", function () {
        it("Should allow staking above minimum", async function () {
            const stakeAmount = ethers.parseEther("500");
            
            await token.connect(user1).stake(stakeAmount);
            
            const stakeInfo = await token.getStakeInfo(user1.address);
            expect(stakeInfo.amount).to.equal(stakeAmount);
        });

        it("Should reject staking below minimum", async function () {
            const stakeAmount = ethers.parseEther("50"); // Below MIN_STAKE
            
            await expect(
                token.connect(user1).stake(stakeAmount)
            ).to.be.revertedWith("Below minimum stake");
        });

        it("Should update total staked", async function () {
            await token.connect(user1).stake(ethers.parseEther("500"));
            await token.connect(user2).stake(ethers.parseEther("300"));
            
            expect(await token.totalStaked()).to.equal(ethers.parseEther("800"));
        });

        it("Should return voting power equal to staked amount", async function () {
            const stakeAmount = ethers.parseEther("1000");
            await token.connect(user1).stake(stakeAmount);
            
            expect(await token.votingPower(user1.address)).to.equal(stakeAmount);
        });

        it("Should prevent unstaking during lock period", async function () {
            await token.connect(user1).stake(ethers.parseEther("500"));
            
            await expect(
                token.connect(user1).unstake(ethers.parseEther("100"))
            ).to.be.revertedWith("Stake locked");
        });

        it("Should allow unstaking after lock period", async function () {
            await token.connect(user1).stake(ethers.parseEther("500"));
            
            // Fast forward time past lock period
            await ethers.provider.send("evm_increaseTime", [86401]); // 1 day + 1 second
            await ethers.provider.send("evm_mine");
            
            await token.connect(user1).unstake(ethers.parseEther("200"));
            
            const stakeInfo = await token.getStakeInfo(user1.address);
            expect(stakeInfo.amount).to.equal(ethers.parseEther("300"));
        });
    });

    describe("Relay Rewards", function () {
        beforeEach(async function () {
            // Authorize relayer
            await token.setRelayerAuthorized(relayer.address, true);
        });

        it("Should allow authorized relayer to claim payment", async function () {
            const relayCount = 100n;
            const expectedPayment = PRICE_PER_RELAY * relayCount;
            const expectedFee = expectedPayment / 100n; // 1%
            
            const relayerBalanceBefore = await token.balanceOf(relayer.address);
            const user1BalanceBefore = await token.balanceOf(user1.address);
            
            await token.connect(relayer).payForRelay(user1.address, relayCount);
            
            const relayerBalanceAfter = await token.balanceOf(relayer.address);
            const user1BalanceAfter = await token.balanceOf(user1.address);
            
            // Relayer received payment
            expect(relayerBalanceAfter - relayerBalanceBefore).to.equal(expectedPayment);
            
            // User paid price + fee
            expect(user1BalanceBefore - user1BalanceAfter).to.equal(expectedPayment + expectedFee);
        });

        it("Should reject unauthorized relayer", async function () {
            await expect(
                token.connect(user2).payForRelay(user1.address, 100)
            ).to.be.revertedWith("Not authorized relayer");
        });

        it("Should emit RelayPaid event", async function () {
            await expect(
                token.connect(relayer).payForRelay(user1.address, 100)
            ).to.emit(token, "RelayPaid");
        });
    });

    describe("Resource Payments", function () {
        it("Should transfer payment to provider and burn fee", async function () {
            const amount = ethers.parseEther("10");
            const fee = amount / 100n; // 1%
            
            const totalSupplyBefore = await token.totalSupply();
            const user2BalanceBefore = await token.balanceOf(user2.address);
            
            await token.connect(user1).payForResource(
                user2.address,
                amount,
                "bandwidth"
            );
            
            const totalSupplyAfter = await token.totalSupply();
            const user2BalanceAfter = await token.balanceOf(user2.address);
            
            // Provider received payment
            expect(user2BalanceAfter - user2BalanceBefore).to.equal(amount);
            
            // Fee was burned
            expect(totalSupplyBefore - totalSupplyAfter).to.equal(fee);
        });

        it("Should emit ResourcePaid event", async function () {
            await expect(
                token.connect(user1).payForResource(
                    user2.address,
                    ethers.parseEther("5"),
                    "storage"
                )
            ).to.emit(token, "ResourcePaid")
             .withArgs(user1.address, user2.address, ethers.parseEther("5"), "storage");
        });
    });

    describe("Epoch Rewards", function () {
        beforeEach(async function () {
            // Setup stakes
            await token.connect(user1).stake(ethers.parseEther("1000"));
            await token.connect(user2).stake(ethers.parseEther("500"));
        });

        it("Should reject distribution before epoch complete", async function () {
            await expect(
                token.distributeEpochRewards(
                    [user1.address, user2.address],
                    [100, 100]
                )
            ).to.be.revertedWith("Epoch not complete");
        });

        it("Should distribute rewards proportionally after epoch", async function () {
            // Fast forward 1 hour
            await ethers.provider.send("evm_increaseTime", [3601]);
            await ethers.provider.send("evm_mine");
            
            const user1BalanceBefore = await token.balanceOf(user1.address);
            const user2BalanceBefore = await token.balanceOf(user2.address);
            
            // user1: 1000 stake * 100% uptime = 1000 score
            // user2: 500 stake * 50% uptime = 250 score
            // Total: 1250
            // user1 gets: 1000/1250 * 10000 = 8000 X0T
            // user2 gets: 250/1250 * 10000 = 2000 X0T
            
            await token.distributeEpochRewards(
                [user1.address, user2.address],
                [100, 50] // uptimes in percent
            );
            
            const user1BalanceAfter = await token.balanceOf(user1.address);
            const user2BalanceAfter = await token.balanceOf(user2.address);
            
            const user1Reward = user1BalanceAfter - user1BalanceBefore;
            const user2Reward = user2BalanceAfter - user2BalanceBefore;
            
            // Check proportional distribution (allowing small rounding)
            expect(user1Reward).to.be.closeTo(
                ethers.parseEther("8000"),
                ethers.parseEther("1")
            );
            expect(user2Reward).to.be.closeTo(
                ethers.parseEther("2000"),
                ethers.parseEther("1")
            );
        });

        it("Should increment epoch counter", async function () {
            await ethers.provider.send("evm_increaseTime", [3601]);
            await ethers.provider.send("evm_mine");
            
            const epochBefore = await token.currentEpoch();
            
            await token.distributeEpochRewards([user1.address], [100]);
            
            const epochAfter = await token.currentEpoch();
            expect(epochAfter).to.equal(epochBefore + 1n);
        });
    });

    describe("View Functions", function () {
        it("Should return correct staker count", async function () {
            await token.connect(user1).stake(ethers.parseEther("500"));
            await token.connect(user2).stake(ethers.parseEther("300"));
            
            expect(await token.getStakerCount()).to.equal(2);
        });

        it("Should return correct staking ratio", async function () {
            // Total supply is ~1 billion, stake 1000
            await token.connect(user1).stake(ethers.parseEther("1000"));
            
            const ratio = await token.getStakingRatio();
            // Should be very small but > 0
            expect(ratio).to.be.gt(0);
        });

        it("Should correctly report canDistributeRewards", async function () {
            expect(await token.canDistributeRewards()).to.be.false;
            
            await ethers.provider.send("evm_increaseTime", [3601]);
            await ethers.provider.send("evm_mine");
            
            expect(await token.canDistributeRewards()).to.be.true;
        });
    });
});
