// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./Voting.sol";

contract Governance is Ownable, ReentrancyGuard {
    struct ExecutionPlan {
        bytes32 actionHash;
        address[] targets;
        uint256[] values;
        bytes[] calldatas;
        bool exists;
    }

    Voting public immutable voting;
    mapping(uint256 => ExecutionPlan) private _plans;

    event GovernanceProposalRegistered(
        uint256 indexed proposalId,
        address indexed proposer,
        bytes32 indexed actionHash
    );
    event GovernanceProposalExecuted(uint256 indexed proposalId, address indexed executor);

    constructor(address votingAddress) Ownable(msg.sender) {
        require(votingAddress != address(0), "Governance: voting required");
        voting = Voting(votingAddress);
    }

    function submitProposal(
        string calldata title,
        string calldata description,
        address[] calldata targets,
        uint256[] calldata values,
        bytes[] calldata calldatas
    ) external returns (uint256 proposalId) {
        require(targets.length > 0, "Governance: empty execution plan");
        require(targets.length == values.length, "Governance: length mismatch");
        require(targets.length == calldatas.length, "Governance: length mismatch");

        bytes32 actionHash = keccak256(abi.encode(targets, values, calldatas));
        proposalId = voting.createProposal(title, description, actionHash, msg.sender);

        ExecutionPlan storage plan = _plans[proposalId];
        plan.exists = true;
        plan.actionHash = actionHash;
        for (uint256 i = 0; i < targets.length; i++) {
            plan.targets.push(targets[i]);
            plan.values.push(values[i]);
            plan.calldatas.push(calldatas[i]);
        }

        emit GovernanceProposalRegistered(proposalId, msg.sender, actionHash);
    }

    function executeProposal(uint256 proposalId) external nonReentrant {
        require(voting.state(proposalId) == Voting.ProposalState.Succeeded, "Governance: proposal not passed");

        ExecutionPlan storage plan = _plans[proposalId];
        require(plan.exists, "Governance: unknown plan");

        bytes32 actionHash = keccak256(abi.encode(plan.targets, plan.values, plan.calldatas));
        require(actionHash == plan.actionHash, "Governance: action hash mismatch");

        for (uint256 i = 0; i < plan.targets.length; i++) {
            (bool success, ) = plan.targets[i].call{value: plan.values[i]}(plan.calldatas[i]);
            require(success, "Governance: action failed");
        }

        voting.markExecuted(proposalId);
        emit GovernanceProposalExecuted(proposalId, msg.sender);
    }

    function executionHash(uint256 proposalId) external view returns (bytes32) {
        return _plans[proposalId].actionHash;
    }

    receive() external payable {}
}
