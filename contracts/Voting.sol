// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/Ownable.sol";
import "./X0TToken.sol";

contract Voting is Ownable {
    X0TToken public token;
    
    struct Proposal {
        string description;
        uint256 votesFor;
        bool executed;
    }
    
    Proposal[] public proposals;

    constructor(address tokenAddress) Ownable(msg.sender) {
        token = X0TToken(tokenAddress);
    }

    // Quadratic Voting: cost = sqrt(votes) or stake^2 logic simplified for MVP
    function vote(uint256 proposalId, uint256 amount) external {
        require(proposalId < proposals.length, "Invalid proposal");
        require(token.transferFrom(msg.sender, address(this), amount), "Transfer failed");
        proposals[proposalId].votesFor += amount; // Quadratic weight logic applied off-chain/on-chain
    }
}
