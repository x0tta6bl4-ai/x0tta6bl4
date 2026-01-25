"""
Тесты FL Governance DAO.

Проверяем:
1. Квадратичное голосование работает правильно
2. Кворум и супербольшинство проверяются
3. Модель обновляется после успешного голосования
"""
import pytest
import sys

sys.path.insert(0, '/mnt/AC74CC2974CBF3DC')

from src.dao.fl_governance import (
    FLGovernanceDAO,
    QuadraticVoting,
    VoteType,
    ProposalState,
    IPFSSimulator
)


class TestQuadraticVoting:
    """Тесты квадратичного голосования."""
    
    def test_basic_calculation(self):
        """√100 = 10 голосов."""
        assert QuadraticVoting.calculate_votes(100) == 10
    
    def test_large_holder(self):
        """Кит с 10,000 токенов = 100 голосов (не 10,000!)."""
        assert QuadraticVoting.calculate_votes(10000) == 100
    
    def test_small_holder(self):
        """1 токен = 1 голос."""
        assert QuadraticVoting.calculate_votes(1) == 1
    
    def test_zero_tokens(self):
        """0 токенов = 0 голосов."""
        assert QuadraticVoting.calculate_votes(0) == 0
    
    def test_reverse_calculation(self):
        """10 голосов требует 100 токенов."""
        assert QuadraticVoting.tokens_for_votes(10) == 100


class TestIPFSSimulator:
    """Тесты симулятора IPFS."""
    
    def test_upload_download(self):
        """Загрузка и скачивание работают."""
        ipfs = IPFSSimulator()
        
        data = [1.0, 2.0, 3.0]
        cid = ipfs.upload(data)
        
        assert cid.startswith("Qm")
        assert ipfs.download(cid) == data
    
    def test_different_data_different_cid(self):
        """Разные данные = разные CID."""
        ipfs = IPFSSimulator()
        
        cid1 = ipfs.upload([1, 2, 3])
        cid2 = ipfs.upload([4, 5, 6])
        
        assert cid1 != cid2


class TestFLGovernanceDAO:
    """Тесты основного DAO."""
    
    @pytest.fixture
    def dao(self):
        """Создать DAO с тестовыми балансами."""
        dao = FLGovernanceDAO(total_supply=1_000_000)
        
        # Раздаём токены
        dao.set_balance("alice", 10_000)   # √10000 = 100 голосов
        dao.set_balance("bob", 400)        # √400 = 20 голосов
        dao.set_balance("carol", 100)      # √100 = 10 голосов
        dao.set_balance("dave", 100)       # √100 = 10 голосов
        dao.set_balance("whale", 100_000)  # √100000 = 316 голосов
        
        return dao
    
    def test_propose_requires_tokens(self, dao):
        """Нужно минимум 1000 токенов для предложения."""
        with pytest.raises(ValueError, match="1000"):
            dao.propose(
                proposer="carol",  # Только 100 токенов
                title="Test",
                description="Test",
                model_weights=[0.1],
                model_version=1
            )
    
    def test_propose_success(self, dao):
        """Предложение создаётся успешно."""
        proposal_id = dao.propose(
            proposer="alice",  # 10,000 токенов
            title="Модель v1",
            description="Первая версия",
            model_weights=[0.1, 0.2],
            model_version=1
        )
        
        assert proposal_id == 1
        assert dao.proposals[1].state == ProposalState.ACTIVE
    
    def test_vote_quadratic(self, dao):
        """Голоса считаются квадратично."""
        dao.propose("alice", "Test", "Test", [0.1], 1)
        
        votes = dao.vote("bob", 1, VoteType.FOR)
        
        assert votes == 20  # √400 = 20
    
    def test_no_double_voting(self, dao):
        """Нельзя голосовать дважды."""
        dao.propose("alice", "Test", "Test", [0.1], 1)
        dao.vote("bob", 1, VoteType.FOR)
        
        with pytest.raises(ValueError, match="Уже"):
            dao.vote("bob", 1, VoteType.AGAINST)
    
    def test_quorum_check(self, dao):
        """Проверка кворума (33%)."""
        dao.propose("alice", "Test", "Test", [0.1], 1)
        
        # Один голос недостаточно
        dao.vote("carol", 1, VoteType.FOR)  # 10 голосов
        assert not dao.check_quorum(1)
        
        # Кит голосует
        dao.vote("whale", 1, VoteType.FOR)  # 316 голосов
        assert dao.check_quorum(1)
    
    def test_supermajority_check(self, dao):
        """Проверка супербольшинства (67%)."""
        dao.propose("alice", "Test", "Test", [0.1], 1)
        
        # 50/50 - недостаточно
        dao.vote("bob", 1, VoteType.FOR)     # 20
        dao.vote("alice", 1, VoteType.AGAINST)  # 100
        
        assert not dao.check_supermajority(1)
    
    def test_execute_success(self, dao):
        """Успешное исполнение предложения."""
        weights = [0.5, 0.6, 0.7]
        dao.propose("alice", "Модель v1", "Desc", weights, 1)
        
        # Достаточно голосов ЗА
        dao.vote("whale", 1, VoteType.FOR)   # 316
        dao.vote("alice", 1, VoteType.FOR)   # 100
        dao.vote("bob", 1, VoteType.FOR)     # 20
        
        result = dao.execute(1)
        
        assert result is True
        assert dao.current_model_version == 1
        assert dao.current_model_weights == weights
    
    def test_execute_rejected(self, dao):
        """Отклонение при недостатке голосов."""
        dao.propose("alice", "Test", "Desc", [0.1], 1)
        
        dao.vote("alice", 1, VoteType.AGAINST)  # 100 против
        dao.vote("bob", 1, VoteType.FOR)        # 20 за
        
        result = dao.execute(1)
        
        assert result is False
        assert dao.proposals[1].state == ProposalState.REJECTED
    
    def test_cancel_proposal(self, dao):
        """Экстренная отмена."""
        dao.propose("alice", "Test", "Desc", [0.1], 1)
        
        dao.cancel(1, "Обнаружена уязвимость")
        
        assert dao.proposals[1].state == ProposalState.CANCELLED
    
    def test_stats(self, dao):
        """Получение статистики."""
        dao.propose("alice", "Test", "Desc", [0.1], 1)
        dao.vote("whale", 1, VoteType.FOR)
        dao.vote("alice", 1, VoteType.AGAINST)
        
        stats = dao.get_stats(1)
        
        assert stats["for_votes"] == 316
        assert stats["against_votes"] == 100
        assert stats["voters_count"] == 2
    
    def test_model_update_callback(self, dao):
        """Callback вызывается при обновлении модели."""
        updated = []
        dao.on_model_updated = lambda v, w: updated.append((v, w))
        
        dao.propose("alice", "Test", "Desc", [1.0, 2.0], 1)
        dao.vote("whale", 1, VoteType.FOR)
        dao.vote("alice", 1, VoteType.FOR)
        dao.execute(1)
        
        assert len(updated) == 1
        assert updated[0][0] == 1  # version
        assert updated[0][1] == [1.0, 2.0]  # weights


class TestQuadraticVotingFairness:
    """Проверяем честность квадратичного голосования."""
    
    def test_community_beats_whale(self):
        """100 мелких держателей сильнее одного кита."""
        # Кит с 10,000 токенов
        whale_votes = QuadraticVoting.calculate_votes(10_000)
        
        # 100 людей по 100 токенов
        community_votes = 100 * QuadraticVoting.calculate_votes(100)
        
        assert community_votes > whale_votes
        # 1000 > 100 - сообщество в 10 раз сильнее!
    
    def test_dao_whale_scenario(self):
        """Реальный сценарий: кит vs сообщество."""
        dao = FLGovernanceDAO()
        
        # Кит
        dao.set_balance("whale", 100_000)
        
        # Сообщество (50 человек по 500 токенов)
        for i in range(50):
            dao.set_balance(f"user_{i}", 500)
        
        # Предложение
        dao.set_balance("proposer", 1000)
        dao.propose("proposer", "Test", "Desc", [0.1], 1)
        
        # Кит против
        dao.vote("whale", 1, VoteType.AGAINST)
        
        # Сообщество за
        for i in range(50):
            dao.vote(f"user_{i}", 1, VoteType.FOR)
        
        # Сообщество побеждает!
        assert dao.check_supermajority(1)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
