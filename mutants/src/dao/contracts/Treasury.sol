// SPDX-License-Identifier: MIT
pragma solidity ^0.8.9;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title X0TTA6BL4Treasury
 * @dev Treasury contract for x0tta6bl4 DAO
 * 
 * Features:
 * - Holds ETH and ERC-20 tokens
 * - Only governance can withdraw funds
 * - Reentrancy protection
 * - Role-based access control
 * - Event tracking for all transfers
 * 
 * Governance (Timelock/Governor):
 * - Can withdraw ETH
 * - Can withdraw ERC-20 tokens
 * - Can change roles
 * 
 * Usage:
 * - Governance proposes: "Transfer 100 tokens to address X"
 * - After voting passes: Execute via Timelock
 * - Treasury receives transaction from Timelock (authorized caller)
 */

contract X0TTA6BL4Treasury is AccessControl, ReentrancyGuard {
    // Role definitions
    bytes32 public constant GOVERNANCE_ROLE = keccak256("GOVERNANCE_ROLE");

    // Events
    event Deposit(address indexed sender, uint256 amount);
    event Withdrawal(address indexed to, uint256 amount);
    event TokenWithdrawal(address indexed token, address indexed to, uint256 amount);
    event TokenDeposit(address indexed token, address indexed from, uint256 amount);

    /**
     * @dev Initialize treasury
     * - Set deployer as admin
     * - Set Timelock/Governor as GOVERNANCE_ROLE
     * 
     * @param governance Address of Timelock/Governor
     */
    constructor(address governance) {
        require(governance != address(0), "Treasury: Invalid governance address");
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(GOVERNANCE_ROLE, governance);
    }

    /**
     * @dev Receive ETH deposits
     */
    receive() external payable {
        emit Deposit(msg.sender, msg.value);
    }

    /**
     * @dev Fallback function
     */
    fallback() external payable {
        emit Deposit(msg.sender, msg.value);
    }

    /**
     * @dev Get ETH balance of treasury
     * @return Balance in wei
     */
    function getBalance() external view returns (uint256) {
        return address(this).balance;
    }

    /**
     * @dev Get ERC-20 token balance
     * @param token ERC-20 token address
     * @return Token balance
     */
    function getTokenBalance(address token) external view returns (uint256) {
        require(token != address(0), "Treasury: Invalid token address");
        return IERC20(token).balanceOf(address(this));
    }

    /**
     * @dev Withdraw ETH from treasury
     * Only callable by GOVERNANCE_ROLE (Timelock/Governor)
     * 
     * @param to Recipient address
     * @param amount Amount of ETH to withdraw
     */
    function withdrawETH(address payable to, uint256 amount)
        external
        onlyRole(GOVERNANCE_ROLE)
        nonReentrant
    {
        require(to != address(0), "Treasury: Invalid recipient");
        require(amount > 0, "Treasury: Amount must be > 0");
        require(amount <= address(this).balance, "Treasury: Insufficient balance");

        (bool success, ) = to.call{value: amount}("");
        require(success, "Treasury: Transfer failed");

        emit Withdrawal(to, amount);
    }

    /**
     * @dev Withdraw ERC-20 tokens from treasury
     * Only callable by GOVERNANCE_ROLE (Timelock/Governor)
     * 
     * @param token ERC-20 token address
     * @param to Recipient address
     * @param amount Amount of tokens to withdraw
     */
    function withdrawToken(
        address token,
        address to,
        uint256 amount
    ) external onlyRole(GOVERNANCE_ROLE) nonReentrant {
        require(token != address(0), "Treasury: Invalid token address");
        require(to != address(0), "Treasury: Invalid recipient");
        require(amount > 0, "Treasury: Amount must be > 0");

        uint256 balance = IERC20(token).balanceOf(address(this));
        require(amount <= balance, "Treasury: Insufficient token balance");

        bool success = IERC20(token).transfer(to, amount);
        require(success, "Treasury: Token transfer failed");

        emit TokenWithdrawal(token, to, amount);
    }

    /**
     * @dev Deposit ERC-20 tokens to treasury (anyone can deposit)
     * @param token ERC-20 token address
     * @param amount Amount of tokens to deposit
     */
    function depositToken(address token, uint256 amount) external {
        require(token != address(0), "Treasury: Invalid token address");
        require(amount > 0, "Treasury: Amount must be > 0");

        bool success = IERC20(token).transferFrom(msg.sender, address(this), amount);
        require(success, "Treasury: Token transfer failed");

        emit TokenDeposit(token, msg.sender, amount);
    }

    /**
     * @dev Grant governance role to address
     * Only callable by admin
     * 
     * @param governance Address to grant governance role
     */
    function addGovernance(address governance)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        require(governance != address(0), "Treasury: Invalid address");
        _grantRole(GOVERNANCE_ROLE, governance);
    }

    /**
     * @dev Revoke governance role from address
     * Only callable by admin
     * 
     * @param governance Address to revoke governance role
     */
    function removeGovernance(address governance)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        require(governance != address(0), "Treasury: Invalid address");
        _revokeRole(GOVERNANCE_ROLE, governance);
    }

    /**
     * @dev Check if address has governance role
     */
    function isGovernance(address account) external view returns (bool) {
        return hasRole(GOVERNANCE_ROLE, account);
    }
}
