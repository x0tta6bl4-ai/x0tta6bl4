"""
FL Governance - Управление моделями через DAO.

Позволяет сообществу голосовать за обновления AI моделей.
Использует квадратичное голосование для защиты от "китов".
"""
import time
import math
import hashlib
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class VoteType(Enum):
    AGAINST = 0  # Против
    FOR = 1      # За
    ABSTAIN = 2  # Воздержался


class ProposalState(Enum):
    PENDING = "pending"
    ACTIVE = "active"
    PASSED = "passed"
    REJECTED = "rejected"
    EXECUTED = "executed"
    CANCELLED = "cancelled"


@dataclass
class Proposal:
    id: int
    proposer: str
    title: str
    description: str
    ipfs_hash: str
    model_version: int
    start_time: float
    end_time: float
    for_votes: int = 0
    against_votes: int = 0
    abstain_votes: int = 0
    state: ProposalState = ProposalState.PENDING
    executed: bool = False


@dataclass
class VoteRecord:
    voter: str
    proposal_id: int
    vote_type: VoteType
    tokens_used: int
    quadratic_votes: int
    timestamp: float


class IPFSSimulator:
    """Симулятор IPFS для хранения моделей."""
    
    def __init__(self):
        self.storage: Dict[str, Any] = {}
    
    def upload(self, data: Any) -> str:
        content = str(data).encode()
        cid = "Qm" + hashlib.sha256(content).hexdigest()[:44]
        self.storage[cid] = data
        return cid
    
    def download(self, cid: str) -> Any:
        return self.storage.get(cid)


class QuadraticVoting:
    """
    Квадратичное голосование: votes = √tokens
    
    Защита от китов:
    - 10,000 токенов = √10,000 = 100 голосов
    - 100 людей × 100 токенов = 100 × √100 = 1,000 голосов
    """
    
    @staticmethod
    def calculate_votes(tokens: int) -> int:
        return int(math.sqrt(max(0, tokens)))
    
    @staticmethod
    def tokens_for_votes(votes: int) -> int:
        return votes * votes


class FLGovernanceDAO:
    """DAO для управления FL моделями."""
    
    QUORUM_PERCENTAGE = 33
    SUPERMAJORITY_PERCENTAGE = 67
    VOTING_PERIOD_SECONDS = 7 * 24 * 3600
    MIN_PROPOSAL_THRESHOLD = 1000
    
    def __init__(self, total_supply: int = 1_000_000):
        self.total_supply = total_supply
        self.proposals: Dict[int, Proposal] = {}
        self.proposal_count = 0
        self.votes: Dict[int, List[VoteRecord]] = {}
        self.balances: Dict[str, int] = {}
        self.voted: Dict[str, set] = {}  # voter -> set of proposal_ids
        
        self.current_model_version = 0
        self.current_model_ipfs = ""
        self.current_model_weights: Optional[List[float]] = None
        
        self.ipfs = IPFSSimulator()
        self.on_model_updated: Optional[Callable] = None
    
    def set_balance(self, address: str, tokens: int) -> None:
        self.balances[address] = tokens
    
    def get_balance(self, address: str) -> int:
        return self.balances.get(address, 0)
    
    def propose(
        self,
        proposer: str,
        title: str,
        description: str,
        model_weights: List[float],
        model_version: int
    ) -> int:
        """Создать предложение об обновлении модели."""
        if self.get_balance(proposer) < self.MIN_PROPOSAL_THRESHOLD:
            raise ValueError("Нужно минимум 1000 токенов")
        
        if model_version <= self.current_model_version:
            raise ValueError("Версия должна быть выше текущей")
        
        ipfs_hash = self.ipfs.upload(model_weights)
        
        self.proposal_count += 1
        now = time.time()
        
        proposal = Proposal(
            id=self.proposal_count,
            proposer=proposer,
            title=title,
            description=description,
            ipfs_hash=ipfs_hash,
            model_version=model_version,
            start_time=now,
            end_time=now + self.VOTING_PERIOD_SECONDS,
            state=ProposalState.ACTIVE
        )
        
        self.proposals[proposal.id] = proposal
        self.votes[proposal.id] = []
        
        logger.info(f"Предложение #{proposal.id}: {title}")
        return proposal.id
    
    def vote(
        self,
        voter: str,
        proposal_id: int,
        vote_type: VoteType
    ) -> int:
        """Проголосовать. Возвращает количество голосов."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            raise ValueError("Предложение не найдено")
        
        if proposal.state != ProposalState.ACTIVE:
            raise ValueError("Голосование не активно")
        
        if voter not in self.voted:
            self.voted[voter] = set()
        
        if proposal_id in self.voted[voter]:
            raise ValueError("Уже проголосовали")
        
        tokens = self.get_balance(voter)
        if tokens <= 0:
            raise ValueError("Нет токенов")
        
        votes = QuadraticVoting.calculate_votes(tokens)
        
        self.voted[voter].add(proposal_id)
        
        if vote_type == VoteType.FOR:
            proposal.for_votes += votes
        elif vote_type == VoteType.AGAINST:
            proposal.against_votes += votes
        else:
            proposal.abstain_votes += votes
        
        record = VoteRecord(
            voter=voter,
            proposal_id=proposal_id,
            vote_type=vote_type,
            tokens_used=tokens,
            quadratic_votes=votes,
            timestamp=time.time()
        )
        self.votes[proposal_id].append(record)
        
        logger.info(f"{voter}: {votes} голосов {vote_type.name}")
        return votes
    
    def check_quorum(self, proposal_id: int) -> bool:
        """
        Проверить достижение кворума.
        
        Кворум = минимальное участие для валидности голосования.
        Мы проверяем, что суммарные голоса >= 10% от √(total_supply).
        """
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False
        
        total_votes = proposal.for_votes + proposal.against_votes + proposal.abstain_votes
        # Кворум = 10% от квадратного корня total_supply
        min_quorum = QuadraticVoting.calculate_votes(self.total_supply) // 10
        return total_votes >= max(min_quorum, 50)  # Минимум 50 голосов
    
    def check_supermajority(self, proposal_id: int) -> bool:
        """Проверить супербольшинство (67% ЗА)."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False
        
        total_decisive = proposal.for_votes + proposal.against_votes
        if total_decisive == 0:
            return False
        
        support_pct = proposal.for_votes * 100 // total_decisive
        return support_pct >= self.SUPERMAJORITY_PERCENTAGE
    
    def execute(self, proposal_id: int) -> bool:
        """Исполнить принятое предложение."""
        proposal = self.proposals.get(proposal_id)
        if not proposal or proposal.executed:
            return False
        
        if not self.check_quorum(proposal_id):
            proposal.state = ProposalState.REJECTED
            return False
        
        if not self.check_supermajority(proposal_id):
            proposal.state = ProposalState.REJECTED
            return False
        
        # Принято!
        proposal.state = ProposalState.PASSED
        proposal.executed = True
        
        self.current_model_version = proposal.model_version
        self.current_model_ipfs = proposal.ipfs_hash
        self.current_model_weights = self.ipfs.download(proposal.ipfs_hash)
        
        proposal.state = ProposalState.EXECUTED
        
        if self.on_model_updated:
            self.on_model_updated(proposal.model_version, self.current_model_weights)
        
        logger.info(f"Модель обновлена до v{proposal.model_version}")
        return True
    
    def cancel(self, proposal_id: int, reason: str) -> bool:
        """Экстренная отмена предложения."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return False
        
        proposal.state = ProposalState.CANCELLED
        logger.warning(f"Предложение #{proposal_id} отменено: {reason}")
        return True
    
    def get_stats(self, proposal_id: int) -> Dict[str, Any]:
        """Получить статистику голосования."""
        proposal = self.proposals.get(proposal_id)
        if not proposal:
            return {}
        
        total = proposal.for_votes + proposal.against_votes
        support_pct = proposal.for_votes * 100 // total if total > 0 else 0
        
        return {
            "proposal_id": proposal_id,
            "title": proposal.title,
            "state": proposal.state.value,
            "for_votes": proposal.for_votes,
            "against_votes": proposal.against_votes,
            "abstain_votes": proposal.abstain_votes,
            "support_percentage": support_pct,
            "quorum_reached": self.check_quorum(proposal_id),
            "supermajority_reached": self.check_supermajority(proposal_id),
            "voters_count": len(self.votes.get(proposal_id, []))
        }
