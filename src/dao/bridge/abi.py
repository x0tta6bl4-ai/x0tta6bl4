"""
X0TToken/X0TBridge ABI (minimal, only what we need).
"""

CONTRACT_ABI = [
    # Events
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "user", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "totalStaked", "type": "uint256"},
        ],
        "name": "Staked",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "user", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "totalStaked", "type": "uint256"},
        ],
        "name": "Unstaked",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "from", "type": "address"},
            {"indexed": True, "name": "to", "type": "address"},
            {"indexed": False, "name": "value", "type": "uint256"},
        ],
        "name": "Transfer",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "payer", "type": "address"},
            {"indexed": True, "name": "relayer", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "feeBurned", "type": "uint256"},
        ],
        "name": "RelayPaid",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "epoch", "type": "uint256"},
            {"indexed": False, "name": "totalRewards", "type": "uint256"},
            {"indexed": False, "name": "recipientCount", "type": "uint256"},
        ],
        "name": "EpochRewardsDistributed",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "escrowId", "type": "bytes32"},
            {"indexed": True, "name": "payer", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "EscrowCreated",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "escrowId", "type": "bytes32"},
            {"indexed": True, "name": "recipient", "type": "address"},
        ],
        "name": "EscrowReleased",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "depositId", "type": "bytes32"},
            {"indexed": True, "name": "depositor", "type": "address"},
            {"indexed": True, "name": "recipient", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
            {"indexed": False, "name": "nodeIdHash", "type": "bytes32"},
            {"indexed": False, "name": "meshNodeId", "type": "string"},
        ],
        "name": "BridgeDeposit",
        "type": "event",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "releaseId", "type": "bytes32"},
            {"indexed": True, "name": "recipient", "type": "address"},
            {"indexed": False, "name": "amount", "type": "uint256"},
        ],
        "name": "BridgeRelease",
        "type": "event",
    },
    # Read functions
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "user", "type": "address"}],
        "name": "votingPower",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "totalStaked",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "currentEpoch",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "canDistributeRewards",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    # Write functions
    {
        "inputs": [
            {"name": "recipients", "type": "address[]"},
            {"name": "uptimes", "type": "uint256[]"},
        ],
        "name": "distributeEpochRewards",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "relayer", "type": "address"},
            {"name": "authorized", "type": "bool"},
        ],
        "name": "setRelayerAuthorized",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "recipient", "type": "address"},
            {"name": "meshNodeId", "type": "string"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "depositFor",
        "outputs": [{"name": "depositId", "type": "bytes32"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "releaseId", "type": "bytes32"},
            {"name": "recipient", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "releaseToChain",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
]
