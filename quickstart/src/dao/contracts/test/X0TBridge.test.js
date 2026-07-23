import { expect } from "chai";
import hre from "hardhat";

const { ethers } = await hre.network.getOrCreate();

describe("X0TBridge", function () {
    let token;
    let bridge;
    let owner;
    let user;
    let recipient;
    let operator;
    let other;

    const amount = ethers.parseEther("25");

    beforeEach(async function () {
        [owner, user, recipient, operator, other] = await ethers.getSigners();

        const X0TToken = await ethers.getContractFactory("X0TToken");
        token = await X0TToken.deploy();
        await token.waitForDeployment();

        await token.transfer(user.address, ethers.parseEther("1000"));

        const X0TBridge = await ethers.getContractFactory("X0TBridge");
        bridge = await X0TBridge.deploy(await token.getAddress(), operator.address);
        await bridge.waitForDeployment();
    });

    async function approveAndDeposit(depositAmount = amount) {
        await token.connect(user).approve(await bridge.getAddress(), depositAmount);
        await bridge.connect(user).depositFor(recipient.address, "mesh-node-1", depositAmount);
    }

    it("locks tokens and emits a mesh deposit event", async function () {
        await token.connect(user).approve(await bridge.getAddress(), amount);

        await expect(
            bridge.connect(user).depositFor(recipient.address, "mesh-node-1", amount)
        ).to.emit(bridge, "BridgeDeposit");

        expect(await token.balanceOf(await bridge.getAddress())).to.equal(amount);
        expect(await bridge.depositNonce()).to.equal(1n);
    });

    it("supports self-recipient deposits", async function () {
        await token.connect(user).approve(await bridge.getAddress(), amount);

        await expect(
            bridge.connect(user).depositForMesh("mesh-node-1", amount)
        ).to.emit(bridge, "BridgeDeposit");

        expect(await token.balanceOf(await bridge.getAddress())).to.equal(amount);
    });

    it("rejects invalid deposits", async function () {
        await expect(
            bridge.connect(user).depositFor(recipient.address, "mesh-node-1", 0)
        ).to.be.revertedWithCustomError(bridge, "ZeroAmount");

        await expect(
            bridge.connect(user).depositFor(recipient.address, "", amount)
        ).to.be.revertedWithCustomError(bridge, "EmptyMeshNodeId");

        await expect(
            bridge.connect(user).depositFor(
                recipient.address,
                "x".repeat(129),
                amount
            )
        ).to.be.revertedWithCustomError(bridge, "MeshNodeIdTooLong");
    });

    it("allows bridge operators to release escrowed tokens once", async function () {
        await approveAndDeposit();
        const releaseId = ethers.id("mesh-release-1");
        const balanceBefore = await token.balanceOf(recipient.address);

        await expect(
            bridge.connect(operator).releaseToChain(releaseId, recipient.address, amount)
        ).to.emit(bridge, "BridgeRelease")
            .withArgs(releaseId, recipient.address, amount);

        expect(await token.balanceOf(recipient.address)).to.equal(balanceBefore + amount);
        expect(await bridge.processedReleases(releaseId)).to.equal(true);

        await expect(
            bridge.connect(operator).releaseToChain(releaseId, recipient.address, amount)
        ).to.be.revertedWithCustomError(bridge, "ReleaseAlreadyProcessed");
    });

    it("rejects release calls from non-operators", async function () {
        await approveAndDeposit();

        await expect(
            bridge.connect(other).releaseToChain(ethers.id("mesh-release-1"), recipient.address, amount)
        ).to.be.revertedWithCustomError(bridge, "NotBridgeOperator");
    });

    it("allows owner to authorize and revoke bridge operators", async function () {
        expect(await bridge.bridgeOperators(other.address)).to.equal(false);

        await expect(
            bridge.connect(owner).setBridgeOperator(other.address, true)
        ).to.emit(bridge, "BridgeOperatorUpdated")
            .withArgs(other.address, true);

        expect(await bridge.bridgeOperators(other.address)).to.equal(true);

        await bridge.connect(owner).setBridgeOperator(other.address, false);
        expect(await bridge.bridgeOperators(other.address)).to.equal(false);
    });

    it("blocks deposits and releases while paused", async function () {
        await approveAndDeposit();
        await bridge.connect(owner).pause();
        await token.connect(user).approve(await bridge.getAddress(), amount);

        await expect(
            bridge.connect(user).depositForMesh("mesh-node-2", amount)
        ).to.be.revertedWithCustomError(bridge, "EnforcedPause");

        await expect(
            bridge.connect(operator).releaseToChain(ethers.id("mesh-release-1"), recipient.address, amount)
        ).to.be.revertedWithCustomError(bridge, "EnforcedPause");
    });
});
