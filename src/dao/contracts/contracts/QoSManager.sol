// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * Mirror of /mnt/projects/dao/qos/stake-multiplier.sol for Hardhat-based tests.
 * Hardhat 2.x doesn't compile sources outside the project root, so this file
 * keeps the same runtime logic for reproducible contract tests.
 * NOT VERIFIED: this still uses wallet balance as a stake proxy, not a
 * dedicated staking contract.
 */
interface IX0TQoSToken {
    function balanceOf(address account) external view returns (uint256);
    function allowance(address owner, address spender) external view returns (uint256);
    function transferFrom(address from, address to, uint256 value) external returns (bool);
}

contract QoSManager {
    uint256 public constant BASE_MULTIPLIER = 100;
    uint256 public constant COST_UNIT = 1e15;
    uint256 public constant STAKE_PROXY_NORMALIZER = 1e14;

    IX0TQoSToken public immutable token;

    event SliceAllocated(address indexed user, uint256 desiredBandwidth, uint256 priority, uint256 cost);

    constructor(address tokenAddress) {
        require(tokenAddress != address(0), "Token address required");
        token = IX0TQoSToken(tokenAddress);
    }

    function getBandwidthMultiplier(address user) public view returns (uint256) {
        uint256 stakeProxy = token.balanceOf(user);
        if (stakeProxy == 0) {
            return BASE_MULTIPLIER;
        }

        return sqrt(stakeProxy / STAKE_PROXY_NORMALIZER) + BASE_MULTIPLIER;
    }

    function quotePremiumSliceCost(uint256 desiredBandwidth) public pure returns (uint256) {
        require(desiredBandwidth > 0, "Bandwidth must be > 0");
        return (desiredBandwidth * desiredBandwidth) * COST_UNIT;
    }

    function allocatePremiumSlice(uint256 desiredBandwidth) external {
        uint256 cost = quotePremiumSliceCost(desiredBandwidth);

        require(token.balanceOf(msg.sender) >= cost, "Insufficient X0T balance");
        require(token.allowance(msg.sender, address(this)) >= cost, "Insufficient X0T allowance");
        require(token.transferFrom(msg.sender, address(this), cost), "X0T transfer failed");

        uint256 priority = getBandwidthMultiplier(msg.sender);
        emit SliceAllocated(msg.sender, desiredBandwidth, priority, cost);
    }

    function sqrt(uint256 x) internal pure returns (uint256 y) {
        if (x == 0) {
            return 0;
        }

        uint256 z = (x + 1) / 2;
        y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
    }
}
