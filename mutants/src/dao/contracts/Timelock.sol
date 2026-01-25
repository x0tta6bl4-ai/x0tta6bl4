// SPDX-License-Identifier: MIT
pragma solidity ^0.8.9;

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
     * @dev Initialize timelock with:
     * - 2-day delay (172,800 seconds)
     * - proposers: [Governor contract]
     * - executors: [Governor contract, any address (0x0)]
     * - admin: [deployer]
     * 
     * Note: Set proposer/executor based on Governor address
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

    /**
     * @dev Get minimum delay
     */
    function getMinDelay() public view returns (uint256) {
        return minDelay;
    }

    /**
     * @dev Check if operation is ready
     */
    function isOperationReady(bytes32 id) public view returns (bool) {
        return super.isOperationReady(id);
    }

    /**
     * @dev Check if operation is done
     */
    function isOperationDone(bytes32 id) public view returns (bool) {
        return super.isOperationDone(id);
    }

    /**
     * @dev Get operation state
     */
    function getOperationState(bytes32 id) public view returns (OperationState) {
        return super.getOperationState(id);
    }
}
