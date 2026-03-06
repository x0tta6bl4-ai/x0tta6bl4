// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

contract X0TToken is ERC20, Ownable {
    constructor() ERC20("x0tta6bl4 Token", "X0T") {
        _mint(msg.sender, 1_000_000_000 * 10**decimals()); // 1 Billion Supply
    }
}
