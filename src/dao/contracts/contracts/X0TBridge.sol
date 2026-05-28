// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/utils/Pausable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title X0TBridge
 * @notice Escrows X0T on Base Sepolia and emits deposit events for the mesh
 *         operator. Authorized bridge operators can release escrowed X0T back
 *         to chain after off-chain settlement.
 */
contract X0TBridge is Ownable, Pausable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    uint256 public constant MAX_MESH_NODE_ID_BYTES = 128;

    IERC20 public immutable x0t;
    uint256 public depositNonce;

    mapping(address => bool) public bridgeOperators;
    mapping(bytes32 => bool) public processedReleases;

    event BridgeDeposit(
        bytes32 indexed depositId,
        address indexed depositor,
        address indexed recipient,
        uint256 amount,
        bytes32 nodeIdHash,
        string meshNodeId
    );
    event BridgeRelease(bytes32 indexed releaseId, address indexed recipient, uint256 amount);
    event BridgeOperatorUpdated(address indexed operator, bool authorized);

    error ZeroAddress();
    error ZeroAmount();
    error EmptyMeshNodeId();
    error MeshNodeIdTooLong();
    error NotBridgeOperator();
    error EmptyReleaseId();
    error ReleaseAlreadyProcessed();

    constructor(IERC20 x0t_, address initialOperator) Ownable(msg.sender) {
        if (address(x0t_) == address(0)) {
            revert ZeroAddress();
        }
        x0t = x0t_;

        if (initialOperator != address(0)) {
            bridgeOperators[initialOperator] = true;
            emit BridgeOperatorUpdated(initialOperator, true);
        }
    }

    modifier onlyBridgeOperator() {
        if (!bridgeOperators[msg.sender]) {
            revert NotBridgeOperator();
        }
        _;
    }

    function setBridgeOperator(address operator, bool authorized) external onlyOwner {
        if (operator == address(0)) {
            revert ZeroAddress();
        }
        bridgeOperators[operator] = authorized;
        emit BridgeOperatorUpdated(operator, authorized);
    }

    function pause() external onlyOwner {
        _pause();
    }

    function unpause() external onlyOwner {
        _unpause();
    }

    function depositForMesh(
        string calldata meshNodeId,
        uint256 amount
    ) external returns (bytes32) {
        return depositFor(msg.sender, meshNodeId, amount);
    }

    function depositFor(
        address recipient,
        string calldata meshNodeId,
        uint256 amount
    ) public nonReentrant whenNotPaused returns (bytes32 depositId) {
        if (recipient == address(0)) {
            revert ZeroAddress();
        }
        if (amount == 0) {
            revert ZeroAmount();
        }

        bytes memory meshNodeIdBytes = bytes(meshNodeId);
        if (meshNodeIdBytes.length == 0) {
            revert EmptyMeshNodeId();
        }
        if (meshNodeIdBytes.length > MAX_MESH_NODE_ID_BYTES) {
            revert MeshNodeIdTooLong();
        }

        uint256 nonce = ++depositNonce;
        bytes32 nodeIdHash = keccak256(meshNodeIdBytes);
        depositId = keccak256(
            abi.encode(
                block.chainid,
                address(this),
                msg.sender,
                recipient,
                amount,
                nodeIdHash,
                nonce
            )
        );

        x0t.safeTransferFrom(msg.sender, address(this), amount);

        emit BridgeDeposit(depositId, msg.sender, recipient, amount, nodeIdHash, meshNodeId);
    }

    function releaseToChain(
        bytes32 releaseId,
        address recipient,
        uint256 amount
    ) external onlyBridgeOperator nonReentrant whenNotPaused {
        if (releaseId == bytes32(0)) {
            revert EmptyReleaseId();
        }
        if (recipient == address(0)) {
            revert ZeroAddress();
        }
        if (amount == 0) {
            revert ZeroAmount();
        }
        if (processedReleases[releaseId]) {
            revert ReleaseAlreadyProcessed();
        }

        processedReleases[releaseId] = true;
        x0t.safeTransfer(recipient, amount);

        emit BridgeRelease(releaseId, recipient, amount);
    }
}
