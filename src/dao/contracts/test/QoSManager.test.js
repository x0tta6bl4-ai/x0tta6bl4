import { expect } from "chai";
import hre from "hardhat";

const { ethers } = await hre.network.getOrCreate();

describe("QoSManager", function () {
    let token;
    let qosManager;
    let owner;
    let fundedUser;
    let emptyUser;

    beforeEach(async function () {
        [owner, fundedUser, emptyUser] = await ethers.getSigners();

        const Token = await ethers.getContractFactory("X0TToken");
        token = await Token.deploy();
        await token.waitForDeployment();

        const QoSManager = await ethers.getContractFactory("QoSManager");
        qosManager = await QoSManager.deploy(await token.getAddress());
        await qosManager.waitForDeployment();

        await token.transfer(fundedUser.address, ethers.parseEther("100"));
    });

    it("returns the base multiplier for zero stake proxy", async function () {
        expect(await qosManager.getBandwidthMultiplier(emptyUser.address)).to.equal(100n);
    });

    it("returns a higher multiplier for non-zero stake proxy", async function () {
        expect(await qosManager.getBandwidthMultiplier(fundedUser.address)).to.be.gt(100n);
    });

    it("keeps quadratic pricing monotonic", async function () {
        const costOne = await qosManager.quotePremiumSliceCost(1);
        const costTwo = await qosManager.quotePremiumSliceCost(2);
        const costThree = await qosManager.quotePremiumSliceCost(3);

        expect(costTwo).to.be.gt(costOne);
        expect(costThree).to.be.gt(costTwo);
        expect(costThree - costTwo).to.be.gt(costTwo - costOne);
    });

    it("rejects zero bandwidth quotes", async function () {
        await expect(
            qosManager.quotePremiumSliceCost(0)
        ).to.be.revertedWith("Bandwidth must be > 0");
    });

    it("rejects a premium slice allocation when allowance is insufficient", async function () {
        await token.connect(fundedUser).approve(await qosManager.getAddress(), 0);

        await expect(
            qosManager.connect(fundedUser).allocatePremiumSlice(1)
        ).to.be.revertedWith("Insufficient X0T allowance");
    });

    it("rejects a premium slice allocation when balance is insufficient", async function () {
        await token.transfer(emptyUser.address, ethers.parseEther("1"));
        await token.connect(emptyUser).approve(await qosManager.getAddress(), ethers.parseEther("2"));

        await expect(
            qosManager.connect(emptyUser).allocatePremiumSlice(40)
        ).to.be.revertedWith("Insufficient X0T balance");
    });
});
