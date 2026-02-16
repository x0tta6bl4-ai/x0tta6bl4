#!/usr/bin/env python3
"""
x0tta6bl4 DAO Voting Script

Create proposals, cast votes, check results via GovernanceEngine.
Supports quadratic voting (voting_power = sqrt(tokens)).

Usage:
  python3 dao-vote.py --propose --title "Update routing" --action topology_update --duration 300
  python3 dao-vote.py --vote --proposal-id PROP_ID --voter node-1 --choice yes --tokens 100
  python3 dao-vote.py --tally --proposal-id PROP_ID
  python3 dao-vote.py --status
"""

import argparse
import json
import os
import sys
import time
from math import sqrt
from pathlib import Path

# Ensure project root is in sys.path for src.* imports
_project_root = str(Path(__file__).resolve().parent.parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def get_governance():
    """Initialize GovernanceEngine."""
    try:
        from src.dao.governance import GovernanceEngine
        return GovernanceEngine(node_id="orchestrator"), "governance"
    except ImportError:
        pass

    try:
        from src.dao.fl_governance import FLGovernanceDAO
        return FLGovernanceDAO(total_supply=1_000_000), "fl_governance"
    except ImportError:
        pass

    print("ERROR: No governance module available")
    print("Install: src.dao.governance or src.dao.fl_governance")
    sys.exit(2)


def cmd_propose(args):
    """Create a new DAO proposal."""
    gov, gov_type = get_governance()

    if gov_type == "governance":
        from src.dao.governance import VoteType
        proposal = gov.create_proposal(
            title=args.title,
            description=args.description or f"Auto-generated: {args.action}",
            duration_seconds=args.duration,
            actions=[{"type": args.action}],
            quorum=args.quorum,
            threshold=args.threshold,
        )
        print(json.dumps({
            "status": "created",
            "proposal_id": proposal.id,
            "title": proposal.title,
            "voting_ends": time.strftime("%Y-%m-%d %H:%M:%S UTC",
                                         time.gmtime(time.time() + args.duration)),
            "quorum": args.quorum,
            "threshold": args.threshold,
            "quadratic_voting": True,
        }, indent=2))
    else:
        proposal_id = gov.propose(
            proposer=args.voter or "orchestrator",
            title=args.title,
            description=args.description or f"Auto-generated: {args.action}",
        )
        print(json.dumps({
            "status": "created",
            "proposal_id": proposal_id,
            "title": args.title,
        }, indent=2))


def cmd_vote(args):
    """Cast a vote on a proposal."""
    gov, gov_type = get_governance()

    choice_map = {"yes": "YES", "no": "NO", "abstain": "ABSTAIN",
                  "for": "YES", "against": "NO"}
    choice = choice_map.get(args.choice.lower(), "ABSTAIN")

    if gov_type == "governance":
        from src.dao.governance import VoteType
        vote_type = getattr(VoteType, choice, VoteType.ABSTAIN)
        success = gov.cast_vote(
            proposal_id=args.proposal_id,
            voter_id=args.voter,
            vote=vote_type,
            tokens=args.tokens,
        )
        voting_power = sqrt(args.tokens)
        print(json.dumps({
            "status": "voted" if success else "failed",
            "proposal_id": args.proposal_id,
            "voter": args.voter,
            "choice": choice,
            "tokens": args.tokens,
            "voting_power": round(voting_power, 2),
            "note": f"Quadratic voting: sqrt({args.tokens}) = {voting_power:.2f} votes",
        }, indent=2))
    else:
        from src.dao.fl_governance import VoteType
        vote_type = getattr(VoteType, "FOR" if choice == "YES" else choice, VoteType.ABSTAIN)
        gov.set_balance(args.voter, args.tokens)
        result = gov.vote(args.voter, int(args.proposal_id), vote_type)
        print(json.dumps({
            "status": "voted",
            "proposal_id": args.proposal_id,
            "voter": args.voter,
            "votes_received": result,
        }, indent=2))


def cmd_tally(args):
    """Tally votes on a proposal."""
    gov, gov_type = get_governance()

    if gov_type == "governance":
        gov.check_proposals()
        proposal = gov.proposals.get(args.proposal_id)
        if not proposal:
            print(f"ERROR: Proposal {args.proposal_id} not found")
            sys.exit(1)
        print(json.dumps({
            "proposal_id": proposal.id,
            "title": proposal.title,
            "state": proposal.state.value,
            "votes_for": proposal.votes_for if hasattr(proposal, "votes_for") else "N/A",
            "votes_against": proposal.votes_against if hasattr(proposal, "votes_against") else "N/A",
        }, indent=2))
    else:
        gov.tally_proposal(int(args.proposal_id))
        proposal = gov.proposals.get(int(args.proposal_id))
        if proposal:
            print(json.dumps({
                "proposal_id": args.proposal_id,
                "state": proposal.state.value,
                "for_votes": proposal.for_votes,
                "against_votes": proposal.against_votes,
            }, indent=2))


def cmd_status(args):
    """Show governance status."""
    gov, gov_type = get_governance()

    proposals = gov.proposals
    summary = []
    for pid, p in proposals.items():
        summary.append({
            "id": str(pid),
            "title": getattr(p, "title", "N/A"),
            "state": p.state.value if hasattr(p.state, "value") else str(p.state),
        })

    print(json.dumps({
        "governance_type": gov_type,
        "total_proposals": len(proposals),
        "proposals": summary,
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description="x0tta6bl4 DAO Voting")
    sub = parser.add_subparsers(dest="command")

    # Propose
    propose = parser.add_argument_group("propose")
    parser.add_argument("--propose", action="store_true")
    parser.add_argument("--title", default="Mesh topology update")
    parser.add_argument("--description", default=None)
    parser.add_argument("--action", default="topology_update")
    parser.add_argument("--duration", type=int, default=3600)
    parser.add_argument("--quorum", type=float, default=0.33)
    parser.add_argument("--threshold", type=float, default=0.5)

    # Vote
    parser.add_argument("--vote", action="store_true")
    parser.add_argument("--proposal-id", default=None)
    parser.add_argument("--voter", default="node-1")
    parser.add_argument("--choice", default="yes")
    parser.add_argument("--tokens", type=float, default=100)

    # Tally
    parser.add_argument("--tally", action="store_true")

    # Status
    parser.add_argument("--status", action="store_true")

    args = parser.parse_args()

    if args.propose:
        cmd_propose(args)
    elif args.vote:
        if not args.proposal_id:
            print("ERROR: --proposal-id required for voting")
            sys.exit(1)
        cmd_vote(args)
    elif args.tally:
        if not args.proposal_id:
            print("ERROR: --proposal-id required for tally")
            sys.exit(1)
        cmd_tally(args)
    elif args.status:
        cmd_status(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
