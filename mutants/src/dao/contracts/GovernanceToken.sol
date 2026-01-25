// SPDX-License-Identifier: MIT
pragma solidity ^0.8.9;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Snapshot.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/Pausable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Votes.sol";

/**
 * @title GovernanceToken
 * @dev x0tta6bl4 Governance Token (ERC-20 with voting)
 * 
 * Features:
 * - ERC20 standard token
 * - Burnable (token burn mechanism)
 * - Snapshot (voting power snapshots)
 * - Votes (voting weight tracking)
 * - Access Control (role-based permissions)
 * - Pausable (emergency stop capability)
 * - Capped supply (10M tokens max)
 * 
 * Token Details:
 * - Name: x0tta6bl4 Governance Token
 * - Symbol: X0OTTA
 * - Decimals: 18
 * - Max Supply: 10,000,000 tokens
 * - Mintable: Restricted to MINTER_ROLE
 * - Burnable: Any token holder can burn
 * - Voteable: Full voting power tracking
 */

contract GovernanceToken is
    ERC20,
    ERC20Burnable,
    ERC20Snapshot,
    AccessControl,
    Pausable,
    ERC20Votes
{
    // Role definitions
    bytes32 public constant SNAPSHOTTER_ROLE = keccak256("SNAPSHOTTER_ROLE");
    bytes32 public constant PAUSER_ROLE = keccak256("PAUSER_ROLE");
    bytes32 public constant MINTER_ROLE = keccak256("MINTER_ROLE");

    // Supply constants
    uint256 public constant MAX_SUPPLY = 10_000_000 * 10 ** 18; // 10M tokens

    // Events
    event TokensMinted(address indexed to, uint256 amount);
    event TokensBurned(address indexed from, uint256 amount);
    event SnapshotCreated(uint256 indexed snapshotId);

    /**
     * @dev Initialize governance token
     * - Grant admin role to deployer
     * - Grant minter role to deployer
     * - Grant pauser role to deployer
     * - Grant snapshotter role to deployer
     */
    constructor() ERC20("x0tta6bl4 Governance Token", "X0OTTA") ERC20Permit("x0tta6bl4 Governance Token") {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(MINTER_ROLE, msg.sender);
        _grantRole(PAUSER_ROLE, msg.sender);
        _grantRole(SNAPSHOTTER_ROLE, msg.sender);
    }

    /**
     * @dev Create snapshot of voting power
     * Only callable by SNAPSHOTTER_ROLE
     * @return snapshotId The ID of the snapshot created
     */
    function snapshot() public onlyRole(SNAPSHOTTER_ROLE) returns (uint256) {
        emit SnapshotCreated(_getCurrentSnapshotId() + 1);
        return _snapshot();
    }

    /**
     * @dev Pause token transfers
     * Only callable by PAUSER_ROLE (emergency use)
     */
    function pause() public onlyRole(PAUSER_ROLE) {
        _pause();
    }

    /**
     * @dev Unpause token transfers
     * Only callable by PAUSER_ROLE
     */
    function unpause() public onlyRole(PAUSER_ROLE) {
        _unpause();
    }

    /**
     * @dev Mint new tokens
     * Only callable by MINTER_ROLE
     * Cannot exceed MAX_SUPPLY
     * 
     * @param to Address to mint tokens to
     * @param amount Amount of tokens to mint
     */
    function mint(address to, uint256 amount) public onlyRole(MINTER_ROLE) {
        require(totalSupply() + amount <= MAX_SUPPLY, "GovernanceToken: Exceeds max supply");
        _mint(to, amount);
        emit TokensMinted(to, amount);
    }

    /**
     * @dev Burn tokens (override to emit event)
     * @param amount Amount of tokens to burn
     */
    function burn(uint256 amount) public override {
        super.burn(amount);
        emit TokensBurned(msg.sender, amount);
    }

    /**
     * @dev Burn tokens from another address
     * Requires approval
     * @param account Address to burn from
     * @param amount Amount of tokens to burn
     */
    function burnFrom(address account, uint256 amount) public override {
        super.burnFrom(account, amount);
        emit TokensBurned(account, amount);
    }

    /**
     * @dev Get voting power at specific block (for past votes)
     * @param account Address to check
     * @param blockNumber Block number
     * @return Voting power at that block
     */
    function getPastVotes(address account, uint256 blockNumber)
        public
        view
        override(ERC20Votes)
        returns (uint256)
    {
        return super.getPastVotes(account, blockNumber);
    }

    /**
     * @dev Get total voting power at specific block
     * @param blockNumber Block number
     * @return Total voting power at that block
     */
    function getPastTotalVotes(uint256 blockNumber)
        public
        view
        override(ERC20Votes)
        returns (uint256)
    {
        return super.getPastTotalVotes(blockNumber);
    }

    /**
     * @dev Delegate voting power
     * @param delegatee Address to delegate to
     */
    function delegate(address delegatee) public override(ERC20Votes) {
        super.delegate(delegatee);
    }

    /**
     * @dev Delegate with signature
     * @param delegatee Address to delegate to
     * @param nonce Nonce for signature
     * @param expiry Signature expiry
     * @param v Signature v
     * @param r Signature r
     * @param s Signature s
     */
    function delegateBySig(
        address delegatee,
        uint256 nonce,
        uint256 expiry,
        uint8 v,
        bytes32 r,
        bytes32 s
    ) public override(ERC20Votes) {
        super.delegateBySig(delegatee, nonce, expiry, v, r, s);
    }

    // ===== Internal Override Functions =====

    function _beforeTokenTransfer(
        address from,
        address to,
        uint256 amount
    ) internal override(ERC20, ERC20Snapshot) whenNotPaused {
        super._beforeTokenTransfer(from, to, amount);
    }

    function _update(
        address from,
        address to,
        uint256 amount
    ) internal override(ERC20, ERC20Votes) {
        super._update(from, to, amount);
    }

    function _nonces(address owner)
        internal
        view
        override(ERC20Permit, Nonces)
        returns (uint256)
    {
        return super._nonces(owner);
    }
}
