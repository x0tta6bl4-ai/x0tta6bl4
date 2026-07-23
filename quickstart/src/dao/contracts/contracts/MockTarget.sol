// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract MockTarget {
    uint256 public value;

    event ValueUpdated(uint256 value);

    function setValue(uint256 newValue) external {
        value = newValue;
        emit ValueUpdated(newValue);
    }
}
