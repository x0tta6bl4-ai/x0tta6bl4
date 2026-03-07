// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/math/Math.sol";

interface IX0TGovernanceToken {
    function votingPower(address account) external view returns (uint256);
    function totalStaked() external view returns (uint256);
}

contract Voting is Ownable, ReentrancyGuard {
    uint256 public constant DISCUSSION_PERIOD = 7 days;
    uint256 public constant VOTING_PERIOD = 3 days;
    uint256 public constant MIN_PROPOSER_POWER = 10;
    uint256 public constant QUORUM_BPS = 1_000; // 10% of sqrt(total staked)

    enum ProposalState {
        Unknown,
        Discussion,
        Active,
        Succeeded,
        Defeated,
        Executed
    }

    struct Proposal {
        uint256 id;
        address proposer;
        string title;
        string description;
        bytes32 executionHash;
        uint64 discussionEndsAt;
        uint64 voteEndsAt;
        uint128 forVotes;
        uint128 againstVotes;
        uint128 abstainVotes;
        bool executed;
    }

    IX0TGovernanceToken public immutable token;
    address public executor;
    uint256 public proposalCount;

    mapping(uint256 => Proposal) private _proposals;
    mapping(uint256 => mapping(address => bool)) public hasVoted;

    event ProposalCreated(
        uint256 indexed proposalId,
        address indexed proposer,
        string title,
        uint256 discussionEndsAt,
        uint256 voteEndsAt,
        bytes32 executionHash
    );
    event VoteCast(
        uint256 indexed proposalId,
        address indexed voter,
        uint8 support,
        uint256 votingPower
    );
    event ProposalExecuted(uint256 indexed proposalId, address indexed executor);
    event ExecutorUpdated(address indexed executor);

    constructor(address tokenAddress, address initialExecutor) Ownable(msg.sender) {
        require(tokenAddress != address(0), "Voting: token required");
        require(initialExecutor != address(0), "Voting: executor required");
        token = IX0TGovernanceToken(tokenAddress);
        executor = initialExecutor;
    }

    function setExecutor(address newExecutor) external onlyOwner {
        require(newExecutor != address(0), "Voting: executor required");
        executor = newExecutor;
        emit ExecutorUpdated(newExecutor);
    }

    function createProposal(
        string calldata title,
        string calldata description,
        bytes32 executionHash,
        address proposer
    ) external returns (uint256 proposalId) {
        require(bytes(title).length > 0, "Voting: title required");
        require(bytes(description).length > 0, "Voting: description required");
        require(proposer != address(0), "Voting: proposer required");
        require(msg.sender == proposer || msg.sender == executor, "Voting: invalid proposer");
        require(token.votingPower(proposer) >= MIN_PROPOSER_POWER, "Voting: insufficient proposer power");

        proposalId = ++proposalCount;
        uint64 discussionEndsAt = uint64(block.timestamp + DISCUSSION_PERIOD);
        uint64 voteEndsAt = uint64(block.timestamp + DISCUSSION_PERIOD + VOTING_PERIOD);

        _proposals[proposalId] = Proposal({
            id: proposalId,
            proposer: proposer,
            title: title,
            description: description,
            executionHash: executionHash,
            discussionEndsAt: discussionEndsAt,
            voteEndsAt: voteEndsAt,
            forVotes: 0,
            againstVotes: 0,
            abstainVotes: 0,
            executed: false
        });

        emit ProposalCreated(
            proposalId,
            proposer,
            title,
            discussionEndsAt,
            voteEndsAt,
            executionHash
        );
    }

    function castVote(uint256 proposalId, uint8 support) external nonReentrant {
        require(support <= 2, "Voting: invalid support");
        Proposal storage proposal = _proposals[proposalId];
        require(proposal.id != 0, "Voting: unknown proposal");
        require(state(proposalId) == ProposalState.Active, "Voting: proposal not active");
        require(!hasVoted[proposalId][msg.sender], "Voting: already voted");

        uint256 weight = token.votingPower(msg.sender);
        require(weight > 0, "Voting: no voting power");

        hasVoted[proposalId][msg.sender] = true;
        if (support == 0) {
            proposal.againstVotes += uint128(weight);
        } else if (support == 1) {
            proposal.forVotes += uint128(weight);
        } else {
            proposal.abstainVotes += uint128(weight);
        }

        emit VoteCast(proposalId, msg.sender, support, weight);
    }

    function markExecuted(uint256 proposalId) external {
        require(msg.sender == executor, "Voting: only executor");
        Proposal storage proposal = _proposals[proposalId];
        require(proposal.id != 0, "Voting: unknown proposal");
        require(state(proposalId) == ProposalState.Succeeded, "Voting: proposal not passed");
        proposal.executed = true;
        emit ProposalExecuted(proposalId, msg.sender);
    }

    function getProposal(uint256 proposalId) external view returns (Proposal memory) {
        return _proposals[proposalId];
    }

    function quorum(uint256 proposalId) public view returns (uint256) {
        Proposal storage proposal = _proposals[proposalId];
        require(proposal.id != 0, "Voting: unknown proposal");

        uint256 total = token.totalStaked();
        if (total == 0) {
            return 0;
        }
        uint256 quadraticSupply = Math.sqrt(total);
        return (quadraticSupply * QUORUM_BPS) / 10_000;
    }

    function state(uint256 proposalId) public view returns (ProposalState) {
        Proposal storage proposal = _proposals[proposalId];
        if (proposal.id == 0) {
            return ProposalState.Unknown;
        }
        if (proposal.executed) {
            return ProposalState.Executed;
        }
        if (block.timestamp < proposal.discussionEndsAt) {
            return ProposalState.Discussion;
        }
        if (block.timestamp < proposal.voteEndsAt) {
            return ProposalState.Active;
        }

        uint256 totalVotes = proposal.forVotes + proposal.againstVotes + proposal.abstainVotes;
        if (totalVotes < quorum(proposalId)) {
            return ProposalState.Defeated;
        }
        if (proposal.forVotes <= proposal.againstVotes) {
            return ProposalState.Defeated;
        }
        return ProposalState.Succeeded;
    }
}
