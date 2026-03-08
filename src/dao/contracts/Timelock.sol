// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import "@openzeppelin/contracts/governance/TimelockController.sol";

/**
 * @title X0TTA6BL4Timelock
 * @dev TimelockController for x0tta6bl4 DAO
 * 
 * Features:
 * - 2-day delay before execution
 * - Queue transactions before execution
 * - Cancel transactions if needed
 * - Role-based access control
 * 
 * Roles:
 * - TIMELOCK_ADMIN_ROLE: Can manage other roles
 * - PROPOSER_ROLE: Can propose (queue) transactions
 * - EXECUTOR_ROLE: Can execute transactions
 * - CANCELLER_ROLE: Can cancel transactions
 * 
 * Delay: 2 days (172,800 seconds)
 * 
 * Usage:
 * 1. Governor proposes transaction -> queued in Timelock
 * 2. Wait 2 days
 * 3. Governor executes transaction
 */

contract X0TTA6BL4Timelock is TimelockController {
    /**
     * @dev Initialize Timelock with:
     * - minDelay: Minimum delay before execution
     * - proposers: Addresses allowed to propose (usually Governor)
     * - executors: Addresses allowed to execute (usually zero address for anyone)
     * - admin: Admin address (usually Governor or deployer)
     */
    constructor(
        address[] memory proposers,
        address[] memory executors,
        address admin
    )
        TimelockController(
            2 days,  // minDelay: 172,800 seconds = 2 days
            proposers,
            executors,
            admin
        )
    {}

    // The functions isOperationReady, isOperationDone, getOperationState
    // and getMinDelay are inherently provided by TimelockController.
    // Explicit overriding without changing functionality is not required
    // and leads to compiler errors in OpenZeppelin v5.
}
