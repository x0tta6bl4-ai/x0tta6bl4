import logging
import time
from typing import Optional

from src.dao.fl_governance import Proposal, VoteType
from src.llm.local_llm import LocalLLM

logger = logging.getLogger(__name__)


class AgentVoter:
    """
    AI Agent that participates in DAO governance.
    Uses LocalLLM to analyze proposals and decide how to vote.
    """

    def __init__(self, agent_name: str, llm: Optional[LocalLLM] = None):
        self.agent_name = agent_name
        self.llm = llm
        # Default persona if LLM is missing
        self.persona = "a cautious guardian of the mesh network"

    def decide_vote(self, proposal: Proposal) -> VoteType:
        """
        Analyze proposal and return vote decision.
        """
        if not self.llm or not self.llm.is_ready():
            logger.warning(f"{self.agent_name} has no LLM, abstaining.")
            return VoteType.ABSTAIN

        prompt = (
            f"You are {self.agent_name}, {self.persona}.\n"
            f"Proposal ID: {proposal.id}\n"
            f"Title: {proposal.title}\n"
            f"Description: {proposal.description}\n"
            f"Model Version: {proposal.model_version}\n"
            f"Should you vote FOR, AGAINST, or ABSTAIN? Provide a one-word answer followed by a short rationale."
        )

        try:
            response = self.llm.generate(prompt, max_tokens=64, temperature=0.3)
            logger.info(f"{self.agent_name} reasoning: {response}")

            normalized = response.upper()
            if "FOR" in normalized:
                return VoteType.FOR
            elif "AGAINST" in normalized:
                return VoteType.AGAINST
            else:
                return VoteType.ABSTAIN

        except Exception as e:
            logger.error(f"{self.agent_name} failed to decide: {e}")
            return VoteType.ABSTAIN
