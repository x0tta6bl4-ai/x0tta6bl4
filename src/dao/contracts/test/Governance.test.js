import { expect } from "chai";
import hre from "hardhat";

const { ethers } = hre;

describe("Governance stack", function () {
    let token;
    let voting;
    let governance;
    let treasury;
    let target;
    let owner;
    let alice;
    let bob;
    let carol;
    let dave;
    let eve;

    beforeEach(async function () {
        [owner, alice, bob, carol, dave, eve] = await ethers.getSigners();

        const Token = await ethers.getContractFactory("X0TToken");
        token = await Token.deploy();
        await token.waitForDeployment();

        for (const signer of [alice, bob, carol, dave, eve]) {
            await token.transfer(signer.address, ethers.parseEther("10000"));
            await token.connect(signer).stake(ethers.parseEther("1000"));
        }

        const Voting = await ethers.getContractFactory("Voting");
        voting = await Voting.deploy(await token.getAddress(), owner.address);
        await voting.waitForDeployment();

        const Governance = await ethers.getContractFactory("Governance");
        governance = await Governance.deploy(await voting.getAddress());
        await governance.waitForDeployment();

        await voting.setExecutor(await governance.getAddress());

        const MockTarget = await ethers.getContractFactory("MockTarget");
        target = await MockTarget.deploy();
        await target.waitForDeployment();

        const Treasury = await ethers.getContractFactory("Treasury");
        treasury = await Treasury.deploy([
            owner.address,
            alice.address,
            bob.address,
            carol.address,
            dave.address,
        ]);
        await treasury.waitForDeployment();
    });

    it("runs the discussion -> vote -> execute workflow with quadratic voting", async function () {
        const calldata = target.interface.encodeFunctionData("setValue", [42n]);

        await governance.connect(alice).submitProposal(
            "Rotate PQC keys",
            "Approve hybrid Noise rollout for the next 30 days",
            [await target.getAddress()],
            [0],
            [calldata]
        );

        const proposalId = await voting.proposalCount();
        expect(await governance.executionHash(proposalId)).to.not.equal(ethers.ZeroHash);
        expect(await voting.state(proposalId)).to.equal(1n); // Discussion

        await ethers.provider.send("evm_increaseTime", [7 * 24 * 60 * 60 + 1]);
        await ethers.provider.send("evm_mine");

        await voting.connect(alice).castVote(proposalId, 1);
        await voting.connect(bob).castVote(proposalId, 1);
        await voting.connect(carol).castVote(proposalId, 0);

        await ethers.provider.send("evm_increaseTime", [3 * 24 * 60 * 60 + 1]);
        await ethers.provider.send("evm_mine");

        expect(await voting.state(proposalId)).to.equal(3n); // Succeeded

        await governance.executeProposal(proposalId);

        expect(await target.value()).to.equal(42n);
        expect(await voting.state(proposalId)).to.equal(5n); // Executed
    });

    it("executes a 3-of-5 multisig treasury transfer", async function () {
        const amount = ethers.parseEther("1");
        await owner.sendTransaction({
            to: await treasury.getAddress(),
            value: ethers.parseEther("5"),
        });

        await treasury.connect(owner).submitTransaction(eve.address, amount, "0x");
        await treasury.connect(alice).confirmTransaction(0);
        await treasury.connect(bob).confirmTransaction(0);

        await expect(
            treasury.connect(carol).executeTransaction(0)
        ).to.changeEtherBalances(
            [treasury, eve],
            [-amount, amount]
        );

        const txn = await treasury.getTransaction(0);
        expect(txn.executed).to.equal(true);
        expect(txn.confirmations).to.equal(3n);
    });
});
