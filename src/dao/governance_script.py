"""
x0tta6bl4 DAO Governance CLI — Base Sepolia (chain_id=84532)

Commands:
  propose   Create a new on-chain governance proposal
  vote      Cast a vote (for/against/abstain) on a proposal
  status    Show detailed status of a proposal
  execute   Execute a passed proposal
  list      List recent proposals

Environment variables:
  BASE_SEPOLIA_RPC          RPC URL (default: https://sepolia.base.org)
  MESH_GOVERNANCE_ADDRESS   MeshGovernance contract address
  X0T_TOKEN_ADDRESS         X0TToken contract address
  OPERATOR_PRIVATE_KEY      Hex private key for signing transactions (see SECURITY below)
  LEDGER_PATH               Audit trail JSONL (default: src/dao/deployments/audit.jsonl)

Deployment addresses are loaded from src/dao/deployments/base_sepolia.json if present.
"""

# ================================================================================
# SECURITY REQUIREMENTS FOR OPERATOR_PRIVATE_KEY (CRITICAL)
# ================================================================================
# The OPERATOR_PRIVATE_KEY controls governance operations on the blockchain.
# Requirements:
#   1. NEVER commit to version control
#   2. Use secrets manager in production (Vault, AWS Secrets Manager)
#   3. Use .env file that is gitignored for development
#   4. Key MUST be hex-encoded WITHOUT 0x prefix (64 characters)
#   5. Use dedicated wallet with minimal permissions
#   6. Consider HSM/MPC wallets in production
# Example: OPERATOR_PRIVATE_KEY=$(vault read -field=key secret/x0tta6bl4/governance)
# ================================================================================

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import click

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("dao.governance_script")

# ---------------------------------------------------------------------------
# Optional Web3 import
# ---------------------------------------------------------------------------
try:
    from web3 import Web3
    from web3.middleware import ExtraDataToPOAMiddleware

    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
CHAIN_ID = 84532  # Base Sepolia
DEFAULT_RPC = "https://sepolia.base.org"
DEPLOYMENTS_DIR = Path(__file__).parent / "deployments"
DEPLOYMENT_FILE = DEPLOYMENTS_DIR / "base_sepolia.json"
DEFAULT_LEDGER = DEPLOYMENTS_DIR / "audit.jsonl"

MESH_GOV_ABI_PATH = (
    Path(__file__).parent
    / "contracts"
    / "artifacts"
    / "contracts"
    / "MeshGovernance.sol"
    / "MeshGovernance.json"
)
X0T_ABI_PATH = (
    Path(__file__).parent
    / "contracts"
    / "artifacts"
    / "contracts"
    / "X0TToken.sol"
    / "X0TToken.json"
)

# Gas parameters for EIP-1559 on Base Sepolia
GAS_LIMIT_PROPOSE = 500_000
GAS_LIMIT_VOTE = 200_000
GAS_LIMIT_EXECUTE = 350_000
MAX_PRIORITY_FEE_GWEI = 1.5  # tip
MAX_FEE_GWEI = 10.0  # cap


# ---------------------------------------------------------------------------
# Proposal state enum
# ---------------------------------------------------------------------------
class ProposalState(IntEnum):
    PENDING = 0
    ACTIVE = 1
    PASSED = 2
    REJECTED = 3
    EXECUTED = 4


STATE_LABELS = {
    ProposalState.PENDING: "PENDING",
    ProposalState.ACTIVE: "ACTIVE",
    ProposalState.PASSED: "PASSED",
    ProposalState.REJECTED: "REJECTED",
    ProposalState.EXECUTED: "EXECUTED",
}


# ---------------------------------------------------------------------------
# Deployment config loader
# ---------------------------------------------------------------------------
def _load_deployment() -> Tuple[Optional[str], Optional[str]]:
    """Load contract addresses from file then env."""
    gov_addr: Optional[str] = None
    tok_addr: Optional[str] = None

    if DEPLOYMENT_FILE.exists():
        try:
            data = json.loads(DEPLOYMENT_FILE.read_text())
            gov_addr = data.get("MeshGovernance")
            tok_addr = data.get("X0TToken")
        except Exception as e:
            logger.warning("Could not parse %s: %s", DEPLOYMENT_FILE, e)

    gov_addr = os.getenv("MESH_GOVERNANCE_ADDRESS", gov_addr)
    tok_addr = os.getenv("X0T_TOKEN_ADDRESS", tok_addr)
    return gov_addr, tok_addr


def _save_deployment(gov_addr: str, tok_addr: str) -> None:
    DEPLOYMENT_FILE.parent.mkdir(parents=True, exist_ok=True)
    DEPLOYMENT_FILE.write_text(
        json.dumps(
            {
                "MeshGovernance": gov_addr,
                "X0TToken": tok_addr,
                "chainId": CHAIN_ID,
                "savedAt": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
    )


# ---------------------------------------------------------------------------
# ABI loader
# ---------------------------------------------------------------------------
def _load_abi(path: Path) -> list:
    if path.exists():
        return json.loads(path.read_text())["abi"]
    raise FileNotFoundError(f"ABI not found: {path}")


# ---------------------------------------------------------------------------
# EIP-1559 transaction builder
# ---------------------------------------------------------------------------
def _build_tx(
    w3: "Web3",
    fn,
    sender: str,
    gas: int,
    nonce: int = None,
) -> Dict[str, Any]:
    """Build EIP-1559 transaction dict for a contract function call."""
    latest = w3.eth.get_block("latest")
    base_fee = latest.get("baseFeePerGas", 0)
    max_priority = w3.to_wei(MAX_PRIORITY_FEE_GWEI, "gwei")
    max_fee = max(base_fee * 2 + max_priority, w3.to_wei(MAX_FEE_GWEI, "gwei"))
    
    # Try to estimate gas if possible, but never reduce below provided gas limit.
    try:
        estimated_gas = fn.estimate_gas({"from": sender})
        if isinstance(estimated_gas, (int, float)) and estimated_gas > 0:
            gas = max(gas, int(estimated_gas * 1.2))
    except Exception:
        pass
    
    # Use provided nonce or get from chain
    tx_nonce = nonce if nonce is not None else w3.eth.get_transaction_count(sender)

    return fn.build_transaction(
        {
            "from": sender,
            "nonce": tx_nonce,
            "gas": gas,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority,
            "chainId": CHAIN_ID,
        }
    )


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------
def _audit(record: Dict[str, Any], ledger_path: Optional[str] = None) -> None:
    """Append a JSONL record to the local audit ledger."""
    path = Path(ledger_path) if ledger_path else DEFAULT_LEDGER
    path.parent.mkdir(parents=True, exist_ok=True)
    record["_ts"] = datetime.now(timezone.utc).isoformat()
    with path.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# Human-readable proposal printer
# ---------------------------------------------------------------------------
def _print_proposal(proposal: Any, w3: "Web3") -> None:
    state = ProposalState(proposal[11])
    now = int(time.time())
    end_time = proposal[5]
    remaining = max(0, end_time - now)

    total_power = proposal[9]
    yes = proposal[6]
    no = proposal[7]
    abstain = proposal[8]

    quorum_pct = (yes + no + abstain) / total_power * 100 if total_power else 0
    yes_pct = yes / (yes + no) * 100 if (yes + no) else 0

    click.echo(f"\n{'='*60}")
    click.echo(f"  Proposal #{proposal[0]}  [{STATE_LABELS.get(state, '?')}]")
    click.echo(f"{'='*60}")
    click.echo(f"  Title     : {proposal[1]}")
    click.echo(f"  Proposer  : {proposal[3]}")
    click.echo(f"  Voting    : ends {datetime.fromtimestamp(end_time, tz=timezone.utc).isoformat()}")
    if remaining:
        click.echo(f"             ({remaining//3600}h {(remaining%3600)//60}m remaining)")
    click.echo(f"  Yes votes : {w3.from_wei(yes, 'ether'):.2f} X0T  ({yes_pct:.1f}%)")
    click.echo(f"  No votes  : {w3.from_wei(no, 'ether'):.2f} X0T")
    click.echo(f"  Abstain   : {w3.from_wei(abstain, 'ether'):.2f} X0T")
    click.echo(f"  Quorum    : {quorum_pct:.1f}% (need 50%)")
    click.echo(f"  Executed  : {'Yes' if proposal[10] else 'No'}")
    click.echo(f"{'='*60}\n")


# ---------------------------------------------------------------------------
# Shared CLI context
# ---------------------------------------------------------------------------
@dataclass
class CliCtx:
    w3: Any
    gov: Any  # Contract
    token: Any  # Contract
    account: Any  # LocalAccount | None
    private_key: Optional[str]
    ledger: Optional[str]
    _nonce: int = field(default=-1, repr=False)  # Cached nonce for transaction management
    
    @property
    def nonce(self) -> int:
        """Get current nonce, fetching from chain if not cached."""
        if self._nonce < 0:
            self._nonce = self.w3.eth.get_transaction_count(self.account.address)
        return self._nonce
    
    def increment_nonce(self) -> None:
        """Increment nonce after successful transaction."""
        self._nonce += 1
    
    def reset_nonce(self) -> None:
        """Reset cached nonce from chain."""
        self._nonce = -1


def _make_context(
    gov_address: str,
    token_address: str,
    private_key: Optional[str],
    rpc_url: str,
    ledger: Optional[str],
) -> CliCtx:
    if not WEB3_AVAILABLE:
        click.echo("ERROR: web3.py not installed. Run: pip install web3", err=True)
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(rpc_url))
    # PoA middleware needed for some L2s (Base uses Clique / OP-stack)
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    if not w3.is_connected():
        click.echo(f"ERROR: Cannot connect to {rpc_url}", err=True)
        sys.exit(1)

    chain_id = w3.eth.chain_id
    if chain_id != CHAIN_ID:
        click.echo(
            f"WARNING: Connected to chain {chain_id}, expected {CHAIN_ID} (Base Sepolia)",
            err=True,
        )

    gov_abi = _load_abi(MESH_GOV_ABI_PATH)
    tok_abi = _load_abi(X0T_ABI_PATH)

    gov_contract = w3.eth.contract(
        address=Web3.to_checksum_address(gov_address), abi=gov_abi
    )
    tok_contract = w3.eth.contract(
        address=Web3.to_checksum_address(token_address), abi=tok_abi
    )

    account = None
    if private_key:
        account = w3.eth.account.from_key(private_key)

    return CliCtx(
        w3=w3,
        gov=gov_contract,
        token=tok_contract,
        account=account,
        private_key=private_key,
        ledger=ledger,
    )


# ---------------------------------------------------------------------------
# CLI root
# ---------------------------------------------------------------------------
@click.group()
@click.option(
    "--rpc",
    default=lambda: os.getenv("BASE_SEPOLIA_RPC", DEFAULT_RPC),
    show_default=True,
    help="Base Sepolia RPC URL",
)
@click.option(
    "--governance-address",
    default=None,
    envvar="MESH_GOVERNANCE_ADDRESS",
    help="MeshGovernance contract address",
)
@click.option(
    "--token-address",
    default=None,
    envvar="X0T_TOKEN_ADDRESS",
    help="X0TToken contract address",
)
@click.option(
    "--private-key",
    default=None,
    envvar="OPERATOR_PRIVATE_KEY",
    help="Hex private key for signing (optional; read-only without it)",
)
@click.option(
    "--ledger",
    default=None,
    envvar="LEDGER_PATH",
    help="Audit trail JSONL file path",
)
@click.pass_context
def cli(ctx, rpc, governance_address, token_address, private_key, ledger):
    """x0tta6bl4 DAO Governance CLI — Base Sepolia"""
    ctx.ensure_object(dict)

    # Resolve addresses: CLI > env > deployment file
    dep_gov, dep_tok = _load_deployment()
    gov_addr = governance_address or dep_gov
    tok_addr = token_address or dep_tok

    if not gov_addr or not tok_addr:
        click.echo(
            "ERROR: Contract addresses required.\n"
            "Set MESH_GOVERNANCE_ADDRESS + X0T_TOKEN_ADDRESS, or run\n"
            "  governance_script.py set-deployment <gov_addr> <tok_addr>",
            err=True,
        )
        sys.exit(1)

    ctx.obj["ctx"] = _make_context(gov_addr, tok_addr, private_key, rpc, ledger)


# ---------------------------------------------------------------------------
# set-deployment (utility, no RPC needed)
# ---------------------------------------------------------------------------
@click.command("set-deployment")
@click.argument("governance_address")
@click.argument("token_address")
def set_deployment(governance_address, token_address):
    """Save contract addresses for Base Sepolia to deployments/base_sepolia.json."""
    _save_deployment(governance_address, token_address)
    click.echo(f"Saved to {DEPLOYMENT_FILE}")
    click.echo(f"  MeshGovernance : {governance_address}")
    click.echo(f"  X0TToken       : {token_address}")


cli.add_command(set_deployment)


# ---------------------------------------------------------------------------
# propose
# ---------------------------------------------------------------------------
@cli.command()
@click.option("--title", "-t", required=True, help="Proposal title")
@click.option("--description", "-d", required=True, help="Proposal description")
@click.option(
    "--duration",
    default=259200,
    show_default=True,
    help="Voting duration in seconds (default 3 days)",
)
@click.pass_context
def propose(ctx, title, description, duration):
    """Create a new governance proposal on-chain."""
    c: CliCtx = ctx.obj["ctx"]

    if not c.account:
        click.echo("ERROR: --private-key required to create proposals", err=True)
        sys.exit(1)

    click.echo(f"Creating proposal: {title!r}")
    click.echo(f"  Duration : {duration}s ({duration//3600}h)")
    click.echo(f"  Sender   : {c.account.address}")

    try:
        fn = c.gov.functions.createProposal(title, description, duration)
        tx_dict = _build_tx(c.w3, fn, c.account.address, GAS_LIMIT_PROPOSE, nonce=c.nonce)
        signed = c.w3.eth.account.sign_transaction(tx_dict, c.private_key)
        tx_hash = c.w3.eth.send_raw_transaction(signed.raw_transaction)

        click.echo(f"  Tx sent  : {tx_hash.hex()}")
        click.echo("  Waiting for confirmation...")

        receipt = c.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt["status"] != 1:
            click.echo("ERROR: Transaction reverted", err=True)
            c.reset_nonce()  # Reset nonce on failure
            sys.exit(1)
        
        # Increment nonce on success
        c.increment_nonce()

        # Proposal ID = proposalCount after creation
        proposal_id = c.gov.functions.proposalCount().call()
        click.echo(f"\nProposal #{proposal_id} created successfully!")
        click.echo(f"  Block    : {receipt['blockNumber']}")
        click.echo(f"  Gas used : {receipt['gasUsed']}")

        _audit(
            {
                "action": "propose",
                "proposal_id": proposal_id,
                "title": title,
                "duration": duration,
                "sender": c.account.address,
                "tx_hash": tx_hash.hex(),
                "block": receipt["blockNumber"],
            },
            c.ledger,
        )

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# vote
# ---------------------------------------------------------------------------
VOTE_MAP = {"for": 1, "against": 0, "abstain": 2, "yes": 1, "no": 0}


@cli.command()
@click.argument("proposal_id", type=int)
@click.argument("choice", type=click.Choice(["for", "against", "abstain", "yes", "no"]))
@click.pass_context
def vote(ctx, proposal_id, choice):
    """Cast a vote on proposal PROPOSAL_ID.

    CHOICE: for/yes (1), against/no (0), abstain (2)
    """
    c: CliCtx = ctx.obj["ctx"]

    if not c.account:
        click.echo("ERROR: --private-key required to vote", err=True)
        sys.exit(1)

    support = VOTE_MAP[choice]
    label = {0: "AGAINST", 1: "FOR", 2: "ABSTAIN"}[support]

    # Check voting power
    power = c.gov.functions.getVotingPower(c.account.address).call()
    if power == 0:
        click.echo(
            "WARNING: Your voting power is 0. Stake X0T tokens first.", err=True
        )

    click.echo(f"Voting {label} on proposal #{proposal_id}")
    click.echo(f"  Voter     : {c.account.address}")
    click.echo(f"  Power     : {c.w3.from_wei(power, 'ether'):.2f} X0T")

    try:
        fn = c.gov.functions.castVote(proposal_id, support)
        tx_dict = _build_tx(c.w3, fn, c.account.address, GAS_LIMIT_VOTE, nonce=c.nonce)
        signed = c.w3.eth.account.sign_transaction(tx_dict, c.private_key)
        tx_hash = c.w3.eth.send_raw_transaction(signed.raw_transaction)

        click.echo(f"  Tx sent   : {tx_hash.hex()}")
        click.echo("  Waiting for confirmation...")

        receipt = c.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

        if receipt["status"] != 1:
            click.echo("ERROR: Transaction reverted (already voted?)", err=True)
            c.reset_nonce()
            sys.exit(1)
        
        c.increment_nonce()
        click.echo(f"\nVote recorded! Block {receipt['blockNumber']}")

        _audit(
            {
                "action": "vote",
                "proposal_id": proposal_id,
                "choice": label,
                "support": support,
                "voter": c.account.address,
                "voting_power_wei": power,
                "tx_hash": tx_hash.hex(),
                "block": receipt["blockNumber"],
            },
            c.ledger,
        )

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------
@cli.command()
@click.argument("proposal_id", type=int)
@click.pass_context
def status(ctx, proposal_id):
    """Show detailed status of proposal PROPOSAL_ID."""
    c: CliCtx = ctx.obj["ctx"]

    try:
        proposal = c.gov.functions.getProposal(proposal_id).call()
        _print_proposal(proposal, c.w3)

        can_exec = c.gov.functions.canExecute(proposal_id).call()
        if can_exec:
            click.echo(">>> This proposal is ready to execute! Run: execute <id>")

        if c.account:
            voter_vote = c.gov.functions.getVote(proposal_id, c.account.address).call()
            has_voted = voter_vote[0]
            if has_voted:
                vote_label = {0: "AGAINST", 1: "FOR", 2: "ABSTAIN"}.get(voter_vote[1], "?")
                click.echo(f"    Your vote : {vote_label}")
            else:
                click.echo("    Your vote : not cast yet")
    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# execute
# ---------------------------------------------------------------------------
@cli.command()
@click.argument("proposal_id", type=int)
@click.pass_context
def execute(ctx, proposal_id):
    """Execute a passed proposal PROPOSAL_ID."""
    c: CliCtx = ctx.obj["ctx"]

    if not c.account:
        click.echo("ERROR: --private-key required to execute proposals", err=True)
        sys.exit(1)

    # Pre-flight check
    can_exec = c.gov.functions.canExecute(proposal_id).call()
    if not can_exec:
        proposal = c.gov.functions.getProposal(proposal_id).call()
        state = ProposalState(proposal[11])
        click.echo(
            f"ERROR: Proposal #{proposal_id} cannot be executed (state={STATE_LABELS.get(state, '?')})",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Executing proposal #{proposal_id}...")
    click.echo(f"  Executor : {c.account.address}")

    try:
        fn = c.gov.functions.executeProposal(proposal_id)
        tx_dict = _build_tx(c.w3, fn, c.account.address, GAS_LIMIT_EXECUTE, nonce=c.nonce)
        signed = c.w3.eth.account.sign_transaction(tx_dict, c.private_key)
        tx_hash = c.w3.eth.send_raw_transaction(signed.raw_transaction)

        click.echo(f"  Tx sent  : {tx_hash.hex()}")
        click.echo("  Waiting for confirmation...")

        receipt = c.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

        if receipt["status"] != 1:
            click.echo("ERROR: Execution reverted", err=True)
            c.reset_nonce()
            sys.exit(1)
        
        c.increment_nonce()
        click.echo(f"\nProposal #{proposal_id} executed! Block {receipt['blockNumber']}")

        _audit(
            {
                "action": "execute",
                "proposal_id": proposal_id,
                "executor": c.account.address,
                "tx_hash": tx_hash.hex(),
                "block": receipt["blockNumber"],
            },
            c.ledger,
        )

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------
@cli.command("list")
@click.option("--limit", default=10, show_default=True, help="Max proposals to show")
@click.pass_context
def list_proposals(ctx, limit):
    """List recent proposals."""
    c: CliCtx = ctx.obj["ctx"]

    try:
        total = c.gov.functions.proposalCount().call()
        click.echo(f"\nTotal proposals: {total}")

        if total == 0:
            click.echo("No proposals yet.")
            return

        start = max(1, total - limit + 1)

        click.echo(f"\n{'ID':<6} {'State':<12} {'Title':<40} {'Yes %':<8} {'Quorum %'}")
        click.echo("-" * 80)

        for pid in range(start, total + 1):
            try:
                p = c.gov.functions.getProposal(pid).call()
                state = ProposalState(p[11])
                total_power = p[9]
                yes = p[6]
                no = p[7]
                abstain = p[8]
                quorum_pct = (yes + no + abstain) / total_power * 100 if total_power else 0
                yes_pct = yes / (yes + no) * 100 if (yes + no) else 0
                title_short = p[1][:38] + ".." if len(p[1]) > 40 else p[1]
                click.echo(
                    f"{pid:<6} {STATE_LABELS.get(state, '?'):<12} {title_short:<40} "
                    f"{yes_pct:<8.1f} {quorum_pct:.1f}"
                )
            except Exception as e:
                click.echo(f"{pid:<6} ERROR: {e}")

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# info  (token + staking info for an address)
# ---------------------------------------------------------------------------
@cli.command()
@click.argument("address", required=False)
@click.pass_context
def info(ctx, address):
    """Show token balance, staking, and voting power for ADDRESS (defaults to signer)."""
    c: CliCtx = ctx.obj["ctx"]

    target = address
    if not target:
        if not c.account:
            click.echo("ERROR: Provide ADDRESS or --private-key", err=True)
            sys.exit(1)
        target = c.account.address

    try:
        target_cs = Web3.to_checksum_address(target)
        balance = c.token.functions.balanceOf(target_cs).call()
        staked = 0
        try:
            stake_info = c.token.functions.getStakeInfo(target_cs).call()
            staked = stake_info[0]
        except Exception:
            pass

        power = c.gov.functions.getVotingPower(target_cs).call()
        proposal_count = c.gov.functions.proposalCount().call()

        click.echo(f"\n  Address       : {target_cs}")
        click.echo(f"  X0T balance   : {c.w3.from_wei(balance, 'ether'):.4f} X0T")
        click.echo(f"  Staked        : {c.w3.from_wei(staked, 'ether'):.4f} X0T")
        click.echo(f"  Voting power  : {c.w3.from_wei(power, 'ether'):.4f}")
        click.echo(f"  Total proposals on-chain: {proposal_count}\n")

    except Exception as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    cli()
