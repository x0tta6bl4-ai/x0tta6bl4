// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./X0TToken.sol";

/**
 * @title MeshGovernance - On-chain DAO Governance for x0tta6bl4
 * @author x0tta6bl4 Team
 * @notice Decentralized governance with quadratic voting
 * 
 * FEATURES:
 * - Create proposals with actions
 * - Quadratic voting (voting power = sqrt(tokens))
 * - Proposal execution
 * - Quorum and threshold requirements
 * - Time-locked proposals
 */
contract MeshGovernance is Ownable, ReentrancyGuard {
    
    // ==================== КОНСТАНТЫ ====================
    
    uint256 public constant MIN_PROPOSAL_DURATION = 1 days;
    uint256 public constant MAX_PROPOSAL_DURATION = 30 days;
    uint256 public constant QUORUM_BASIS_POINTS = 5000;  // 50%
    uint256 public constant THRESHOLD_BASIS_POINTS = 5000;  // 50% + 1
    
    // ==================== СОСТОЯНИЕ ====================
    
    X0TToken public token;
    
    struct Proposal {
        uint256 id;
        string title;
        string description;
        address proposer;
        uint256 startTime;
        uint256 endTime;
        uint256 yesVotes;
        uint256 noVotes;
        uint256 abstainVotes;
        uint256 totalVotingPower;
        bool executed;
        ProposalState state;
    }
    
    enum ProposalState {
        Pending,
        Active,
        Passed,
        Rejected,
        Executed
    }
    
    struct Vote {
        bool hasVoted;
        uint8 support;  // 0 = against, 1 = for, 2 = abstain
        uint256 votingPower;
    }
    
    mapping(uint256 => Proposal) public proposals;
    mapping(uint256 => mapping(address => Vote)) public votes;
    mapping(address => bool) public authorizedExecutors;
    
    uint256 public proposalCount;
    uint256 public votingDelay;  // Time before proposal becomes active
    uint256 public votingPeriod;  // Default voting duration
    
    // ==================== СОБЫТИЯ ====================
    
    event ProposalCreated(
        uint256 indexed proposalId,
        address indexed proposer,
        string title,
        uint256 startTime,
        uint256 endTime
    );
    
    event VoteCast(
        uint256 indexed proposalId,
        address indexed voter,
        uint8 support,
        uint256 votingPower
    );
    
    event ProposalExecuted(uint256 indexed proposalId);
    event ProposalStateChanged(uint256 indexed proposalId, ProposalState newState);
    event ExecutorAuthorized(address indexed executor, bool authorized);
    
    // ==================== КОНСТРУКТОР ====================
    
    constructor(address _token) Ownable(msg.sender) {
        token = X0TToken(_token);
        votingDelay = 1 hours;
        votingPeriod = 3 days;
        authorizedExecutors[msg.sender] = true;
    }
    
    // ==================== PROPOSAL MANAGEMENT ====================
    
    /**
     * @notice Create a new governance proposal
     * @param title Proposal title
     * @param description Proposal description
     * @param duration Voting duration in seconds
     */
    function createProposal(
        string memory title,
        string memory description,
        uint256 duration
    ) external returns (uint256) {
        require(bytes(title).length > 0, "Title required");
        require(duration >= MIN_PROPOSAL_DURATION, "Duration too short");
        require(duration <= MAX_PROPOSAL_DURATION, "Duration too long");
        
        // Check proposer has minimum voting power
        uint256 proposerPower = getVotingPower(msg.sender);
        require(proposerPower > 0, "No voting power");
        
        proposalCount++;
        uint256 proposalId = proposalCount;
        
        uint256 startTime = block.timestamp + votingDelay;
        uint256 endTime = startTime + duration;
        
        proposals[proposalId] = Proposal({
            id: proposalId,
            title: title,
            description: description,
            proposer: msg.sender,
            startTime: startTime,
            endTime: endTime,
            yesVotes: 0,
            noVotes: 0,
            abstainVotes: 0,
            totalVotingPower: 0,
            executed: false,
            state: ProposalState.Pending
        });
        
        emit ProposalCreated(proposalId, msg.sender, title, startTime, endTime);
        
        return proposalId;
    }
    
    /**
     * @notice Cast a vote on a proposal (quadratic voting)
     * @param proposalId Proposal ID
     * @param support 0 = against, 1 = for, 2 = abstain
     */
    function castVote(uint256 proposalId, uint8 support) external {
        require(support <= 2, "Invalid vote");
        require(proposalId > 0 && proposalId <= proposalCount, "Invalid proposal");
        
        Proposal storage proposal = proposals[proposalId];
        require(block.timestamp >= proposal.startTime, "Voting not started");
        require(block.timestamp < proposal.endTime, "Voting ended");
        require(proposal.state == ProposalState.Active || proposal.state == ProposalState.Pending, "Proposal not active");
        
        require(!votes[proposalId][msg.sender].hasVoted, "Already voted");
        
        uint256 votingPower = getVotingPower(msg.sender);
        require(votingPower > 0, "No voting power");
        
        // Quadratic voting: power = sqrt(tokens)
        // Using Babylonian method for sqrt calculation
        uint256 quadraticPower = sqrt(votingPower);
        
        votes[proposalId][msg.sender] = Vote({
            hasVoted: true,
            support: support,
            votingPower: quadraticPower
        });
        
        if (support == 1) {
            proposal.yesVotes += quadraticPower;
        } else if (support == 0) {
            proposal.noVotes += quadraticPower;
        } else {
            proposal.abstainVotes += quadraticPower;
        }
        
        proposal.totalVotingPower += quadraticPower;
        
        // Update state if voting started
        if (proposal.state == ProposalState.Pending && block.timestamp >= proposal.startTime) {
            proposal.state = ProposalState.Active;
            emit ProposalStateChanged(proposalId, ProposalState.Active);
        }
        
        emit VoteCast(proposalId, msg.sender, support, quadraticPower);
    }
    
    /**
     * @notice Execute a proposal (if passed)
     * @param proposalId Proposal ID
     */
    function executeProposal(uint256 proposalId) external {
        require(proposalId > 0 && proposalId <= proposalCount, "Invalid proposal");
        
        Proposal storage proposal = proposals[proposalId];
        require(block.timestamp >= proposal.endTime, "Voting not ended");
        require(!proposal.executed, "Already executed");
        require(proposal.state == ProposalState.Active || proposal.state == ProposalState.Passed, "Cannot execute");
        
        // Check quorum
        uint256 totalStaked = token.totalStaked();
        uint256 quorumRequired = (totalStaked * QUORUM_BASIS_POINTS) / 10000;
        require(proposal.totalVotingPower >= quorumRequired, "Quorum not met");
        
        // Check threshold
        uint256 totalVotes = proposal.yesVotes + proposal.noVotes;
        if (totalVotes > 0) {
            uint256 yesPercentage = (proposal.yesVotes * 10000) / totalVotes;
            require(yesPercentage >= THRESHOLD_BASIS_POINTS, "Threshold not met");
        }
        
        proposal.state = ProposalState.Passed;
        proposal.executed = true;
        
        emit ProposalStateChanged(proposalId, ProposalState.Passed);
        emit ProposalExecuted(proposalId);
        
        // Execute proposal actions (call external contracts, etc.)
        // Note: For now, execution is just marking as executed
        // Future: Add action execution logic here
    }
    
    /**
     * @notice Reject a proposal (if quorum not met or threshold not reached)
     * @param proposalId Proposal ID
     */
    function rejectProposal(uint256 proposalId) external {
        require(proposalId > 0 && proposalId <= proposalCount, "Invalid proposal");
        
        Proposal storage proposal = proposals[proposalId];
        require(block.timestamp >= proposal.endTime, "Voting not ended");
        require(proposal.state == ProposalState.Active, "Not active");
        
        uint256 totalStaked = token.totalStaked();
        uint256 quorumRequired = (totalStaked * QUORUM_BASIS_POINTS) / 10000;
        
        if (proposal.totalVotingPower < quorumRequired) {
            proposal.state = ProposalState.Rejected;
            emit ProposalStateChanged(proposalId, ProposalState.Rejected);
            return;
        }
        
        uint256 totalVotes = proposal.yesVotes + proposal.noVotes;
        if (totalVotes > 0) {
            uint256 yesPercentage = (proposal.yesVotes * 10000) / totalVotes;
            if (yesPercentage < THRESHOLD_BASIS_POINTS) {
                proposal.state = ProposalState.Rejected;
                emit ProposalStateChanged(proposalId, ProposalState.Rejected);
            }
        }
    }
    
    // ==================== VIEW FUNCTIONS ====================
    
    /**
     * @notice Get voting power of an address (based on staked tokens)
     */
    function getVotingPower(address voter) public view returns (uint256) {
        return token.votingPower(voter);
    }
    
    // ==================== INTERNAL FUNCTIONS ====================
    
    /**
     * @notice Calculate square root using Babylonian method
     * @param x The number to calculate sqrt for
     * @return sqrt The square root of x
     */
    function sqrt(uint256 x) internal pure returns (uint256) {
        if (x == 0) return 0;
        if (x == 1) return 1;
        
        uint256 z = (x + 1) / 2;
        uint256 y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
        return y;
    }
    
    // ==================== VIEW FUNCTIONS ====================
    
    /**
     * @notice Get proposal details
     */
    function getProposal(uint256 proposalId) external view returns (
        uint256 id,
        string memory title,
        string memory description,
        address proposer,
        uint256 startTime,
        uint256 endTime,
        uint256 yesVotes,
        uint256 noVotes,
        uint256 abstainVotes,
        uint256 totalVotingPower,
        bool executed,
        ProposalState state
    ) {
        Proposal memory proposal = proposals[proposalId];
        return (
            proposal.id,
            proposal.title,
            proposal.description,
            proposal.proposer,
            proposal.startTime,
            proposal.endTime,
            proposal.yesVotes,
            proposal.noVotes,
            proposal.abstainVotes,
            proposal.totalVotingPower,
            proposal.executed,
            proposal.state
        );
    }
    
    /**
     * @notice Get vote of a voter on a proposal
     */
    function getVote(uint256 proposalId, address voter) external view returns (
        bool hasVoted,
        uint8 support,
        uint256 votingPower
    ) {
        Vote memory vote = votes[proposalId][voter];
        return (vote.hasVoted, vote.support, vote.votingPower);
    }
    
    /**
     * @notice Check if proposal can be executed
     */
    function canExecute(uint256 proposalId) external view returns (bool) {
        if (proposalId == 0 || proposalId > proposalCount) return false;
        
        Proposal memory proposal = proposals[proposalId];
        if (block.timestamp < proposal.endTime) return false;
        if (proposal.executed) return false;
        if (proposal.state != ProposalState.Active && proposal.state != ProposalState.Passed) return false;
        
        uint256 totalStaked = token.totalStaked();
        uint256 quorumRequired = (totalStaked * QUORUM_BASIS_POINTS) / 10000;
        if (proposal.totalVotingPower < quorumRequired) return false;
        
        uint256 totalVotes = proposal.yesVotes + proposal.noVotes;
        if (totalVotes == 0) return false;
        
        uint256 yesPercentage = (proposal.yesVotes * 10000) / totalVotes;
        return yesPercentage >= THRESHOLD_BASIS_POINTS;
    }
    
    // ==================== ADMIN FUNCTIONS ====================
    
    /**
     * @notice Authorize/unauthorize an executor
     */
    function setExecutorAuthorized(address executor, bool authorized) external onlyOwner {
        authorizedExecutors[executor] = authorized;
        emit ExecutorAuthorized(executor, authorized);
    }
    
    /**
     * @notice Update voting delay
     */
    function setVotingDelay(uint256 newDelay) external onlyOwner {
        votingDelay = newDelay;
    }
    
    /**
     * @notice Update voting period
     */
    function setVotingPeriod(uint256 newPeriod) external onlyOwner {
        votingPeriod = newPeriod;
    }
}

