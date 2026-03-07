// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract Treasury is ReentrancyGuard {
    uint256 public constant REQUIRED_OWNERS = 5;
    uint256 public constant REQUIRED_THRESHOLD = 3;

    struct Transaction {
        address to;
        uint256 value;
        bytes data;
        bool executed;
        uint8 confirmations;
    }

    address[] private _owners;
    mapping(address => bool) public isOwner;
    Transaction[] private _transactions;
    mapping(uint256 => mapping(address => bool)) public isConfirmed;

    event Deposit(address indexed sender, uint256 value);
    event TransactionSubmitted(
        uint256 indexed transactionId,
        address indexed submitter,
        address indexed to,
        uint256 value,
        bytes data
    );
    event TransactionConfirmed(uint256 indexed transactionId, address indexed owner);
    event TransactionRevoked(uint256 indexed transactionId, address indexed owner);
    event TransactionExecuted(uint256 indexed transactionId, address indexed executor);

    modifier onlyOwner() {
        require(isOwner[msg.sender], "Treasury: not owner");
        _;
    }

    constructor(address[REQUIRED_OWNERS] memory owners_) payable {
        for (uint256 i = 0; i < owners_.length; i++) {
            address owner = owners_[i];
            require(owner != address(0), "Treasury: zero owner");
            require(!isOwner[owner], "Treasury: duplicate owner");
            isOwner[owner] = true;
            _owners.push(owner);
        }
    }

    receive() external payable {
        emit Deposit(msg.sender, msg.value);
    }

    function getOwners() external view returns (address[] memory) {
        return _owners;
    }

    function transactionCount() external view returns (uint256) {
        return _transactions.length;
    }

    function getTransaction(uint256 transactionId) external view returns (Transaction memory) {
        require(transactionId < _transactions.length, "Treasury: unknown transaction");
        return _transactions[transactionId];
    }

    function submitTransaction(address to, uint256 value, bytes calldata data)
        external
        onlyOwner
        returns (uint256 transactionId)
    {
        require(to != address(0), "Treasury: target required");

        transactionId = _transactions.length;
        _transactions.push(Transaction({
            to: to,
            value: value,
            data: data,
            executed: false,
            confirmations: 0
        }));

        emit TransactionSubmitted(transactionId, msg.sender, to, value, data);
        _confirm(transactionId, msg.sender);
    }

    function confirmTransaction(uint256 transactionId) external onlyOwner {
        _confirm(transactionId, msg.sender);
    }

    function revokeConfirmation(uint256 transactionId) external onlyOwner {
        require(transactionId < _transactions.length, "Treasury: unknown transaction");
        Transaction storage txn = _transactions[transactionId];
        require(!txn.executed, "Treasury: already executed");
        require(isConfirmed[transactionId][msg.sender], "Treasury: not confirmed");

        isConfirmed[transactionId][msg.sender] = false;
        txn.confirmations -= 1;

        emit TransactionRevoked(transactionId, msg.sender);
    }

    function executeTransaction(uint256 transactionId) external onlyOwner nonReentrant {
        require(transactionId < _transactions.length, "Treasury: unknown transaction");
        Transaction storage txn = _transactions[transactionId];
        require(!txn.executed, "Treasury: already executed");
        require(txn.confirmations >= REQUIRED_THRESHOLD, "Treasury: insufficient confirmations");

        txn.executed = true;
        (bool success, ) = txn.to.call{value: txn.value}(txn.data);
        require(success, "Treasury: execution failed");

        emit TransactionExecuted(transactionId, msg.sender);
    }

    function _confirm(uint256 transactionId, address owner) internal {
        require(transactionId < _transactions.length, "Treasury: unknown transaction");
        Transaction storage txn = _transactions[transactionId];
        require(!txn.executed, "Treasury: already executed");
        require(!isConfirmed[transactionId][owner], "Treasury: already confirmed");

        isConfirmed[transactionId][owner] = true;
        txn.confirmations += 1;

        emit TransactionConfirmed(transactionId, owner);
    }
}
