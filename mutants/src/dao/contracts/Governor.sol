// SPDX-License-Identifier: MIT
pragma solidity ^0.8.9;

import "@openzeppelin/contracts/governance/Governor.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorSettings.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorCountingSimple.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorVotes.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorVotesQuorumFraction.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorTimelockControl.sol";
import "./GovernanceToken.sol";
import "./Timelock.sol";

/**
 * @title X0TTA6BL4Governor
 * @dev OpenZeppelin Governor for x0tta6bl4 DAO
 * 
 * Governance Parameters:
 * - Voting Delay: 1 block (voting starts immediately)
 * - Voting Period: 50,400 blocks (~1 week on mainnet, ~8 hours on testnet)
 * - Proposal Threshold: 100 tokens (1e20 wei)
 * - Quorum: 10% of voting power
 * - Timelock: 2 days delay before execution
 * 
 * Voting Modes:
 * - FOR: 1 (support the proposal)
 * - AGAINST: 0 (oppose the proposal)
 * - ABSTAIN: 2 (abstain from voting)
 * 
 * Proposal Types:
 * - Parameter changes (voting period, quorum, etc.)
 * - Fund transfers (from treasury)
 * - Contract upgrades
 * - Emergency actions (pausing)
 */

contract X0TTA6BL4Governor is
    Governor,
    GovernorSettings,
    GovernorCountingSimple,
    GovernorVotes,
    GovernorVotesQuorumFraction,
    GovernorTimelockControl
{
    // Events
    event ProposalThresholdChanged(uint256 oldThreshold, uint256 newThreshold);
    event VotingDelayChanged(uint256 oldDelay, uint256 newDelay);
    event VotingPeriodChanged(uint256 oldPeriod, uint256 newPeriod);
    event QuorumChanged(uint256 oldQuorum, uint256 newQuorum);

    /**
     * @dev Initialize governor with:
     * - GovernanceToken for voting
     * - Timelock for execution delay
     * - Voting delay: 1 block
     * - Voting period: 50,400 blocks (~1 week)
     * - Proposal threshold: 100 tokens
     * - Quorum fraction: 10%
     * - Timelock delay: 2 days (TimelockController constructor)
     */
    constructor(
        GovernanceToken _token,
        TimelockController _timelock
    )
        Governor("x0tta6bl4 Governor")
        GovernorSettings(
            1,      // voting delay: 1 block
            50400,  // voting period: 50,400 blocks (~1 week)
            100e18  // proposal threshold: 100 tokens
        )
        GovernorVotes(_token)
        GovernorVotesQuorumFraction(10)  // quorum: 10%
        GovernorTimelockControl(_timelock)
    {}

    /**
     * @dev Get voting delay (blocks before voting starts)
     * Can be changed via proposal
     */
    function votingDelay()
        public
        view
        override(Governor, GovernorSettings)
        returns (uint256)
    {
        return super.votingDelay();
    }

    /**
     * @dev Get voting period (blocks for voting)
     * Can be changed via proposal
     */
    function votingPeriod()
        public
        view
        override(Governor, GovernorSettings)
        returns (uint256)
    {
        return super.votingPeriod();
    }

    /**
     * @dev Get quorum (minimum voting power required)
     */
    function quorum(uint256 blockNumber)
        public
        view
        override(Governor, GovernorVotesQuorumFraction)
        returns (uint256)
    {
        return super.quorum(blockNumber);
    }

    /**
     * @dev Get state of proposal
     */
    function state(uint256 proposalId)
        public
        view
        override(Governor, GovernorTimelockControl)
        returns (ProposalState)
    {
        return super.state(proposalId);
    }

    /**
     * @dev Get proposal deadline
     */
    function proposalDeadline(uint256 proposalId)
        public
        view
        override(Governor)
        returns (uint256)
    {
        return super.proposalDeadline(proposalId);
    }

    /**
     * @dev Get proposal snapshot (voting power snapshot block)
     */
    function proposalSnapshot(uint256 proposalId)
        public
        view
        override(Governor)
        returns (uint256)
    {
        return super.proposalSnapshot(proposalId);
    }

    /**
     * @dev Cancel proposal
     * Can be called by proposer or governance
     */
    function cancel(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash
    ) public override(Governor) returns (uint256) {
        return super.cancel(targets, values, calldatas, descriptionHash);
    }

    /**
     * @dev Execute proposal (after timelock delay)
     */
    function execute(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash
    ) public payable override(Governor, GovernorTimelockControl) returns (uint256) {
        return super.execute(targets, values, calldatas, descriptionHash);
    }

    /**
     * @dev Queue proposal for execution (transition to Queued state)
     */
    function queue(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash
    ) public override(Governor, GovernorTimelockControl) returns (uint256) {
        return super.queue(targets, values, calldatas, descriptionHash);
    }

    /**
     * @dev Get proposal threshold (tokens needed to create proposal)
     */
    function proposalThreshold()
        public
        view
        override(Governor, GovernorSettings)
        returns (uint256)
    {
        return super.proposalThreshold();
    }

    /**
     * @dev Check if an account has voting power
     */
    function hasVotes(address account, uint256 blockNumber)
        public
        view
        returns (bool)
    {
        return getVotes(account, blockNumber) > 0;
    }

    /**
     * @dev Get voting power at current block
     */
    function getVotesNow(address account)
        public
        view
        returns (uint256)
    {
        return getVotes(account, block.number - 1);
    }

    /**
     * @dev Check if proposal passed (for inspection)
     */
    function proposalPassed(uint256 proposalId)
        public
        view
        returns (bool)
    {
        ProposalState currentState = state(proposalId);
        return (currentState == ProposalState.Succeeded ||
                currentState == ProposalState.Queued ||
                currentState == ProposalState.Executed);
    }

    /**
     * @dev Get proposal vote counts
     */
    function proposalVotes(uint256 proposalId)
        public
        view
        returns (
            uint256 forVotes,
            uint256 againstVotes,
            uint256 abstainVotes
        )
    {
        (againstVotes, forVotes, abstainVotes) = proposalVotes(proposalId);
    }

    // ===== Internal Override Functions =====

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(Governor, GovernorTimelockControl)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }

    function _queueOperations(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash
    ) internal override(Governor, GovernorTimelockControl) {
        super._queueOperations(targets, values, calldatas, descriptionHash);
    }

    function _executeOperations(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash
    ) internal override(Governor, GovernorTimelockControl) {
        super._executeOperations(targets, values, calldatas, descriptionHash);
    }

    function _cancel(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash,
        address proposer
    ) internal override(Governor, GovernorTimelockControl) returns (uint48) {
        return super._cancel(targets, values, calldatas, descriptionHash, proposer);
    }

    function _executor()
        internal
        view
        override(Governor, GovernorTimelockControl)
        returns (address)
    {
        return super._executor();
    }
}
