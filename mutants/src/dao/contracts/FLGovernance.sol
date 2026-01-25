// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title FLGovernance - Federated Learning Model Governance
 * @author x0tta6bl4 Team
 * @notice Управление обновлениями FL моделей через DAO голосование
 * 
 * ПРОСТЫМИ СЛОВАМИ:
 * Это "умный контракт" - программа, которая живёт в блокчейне.
 * Она позволяет сообществу голосовать за обновления AI моделей.
 * 
 * Пример использования:
 * 1. Алиса предлагает: "Обновить модель маршрутизации до v5"
 * 2. Все держатели токенов голосуют
 * 3. Если 67% ЗА и проголосовало 33% токенов → модель обновляется
 */

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

contract FLGovernance is ReentrancyGuard {
    
    // ==================== ТИПЫ ДАННЫХ ====================
    
    /**
     * Состояния предложения (как этапы жизни):
     * 
     * PENDING → ACTIVE → PASSED/REJECTED → EXECUTED/CANCELLED
     *    ↑         ↑           ↑                  ↑
     *  Создано  Голосование  Результат      Исполнено
     */
    enum ProposalState {
        PENDING,    // Ожидает начала голосования
        ACTIVE,     // Голосование идёт
        PASSED,     // Принято (достаточно голосов ЗА)
        REJECTED,   // Отклонено (недостаточно голосов)
        EXECUTED,   // Исполнено (модель обновлена)
        CANCELLED   // Отменено (экстренная ситуация)
    }
    
    /**
     * Предложение на голосование
     * 
     * Содержит всю информацию о предлагаемом изменении модели
     */
    struct Proposal {
        uint256 id;                  // Уникальный номер
        address proposer;            // Кто предложил
        string title;                // Название ("Обновление модели v5")
        string description;          // Описание изменений
        string ipfsHash;             // Где хранится модель (IPFS)
        uint256 modelVersion;        // Версия модели (5)
        uint256 startTime;           // Когда начинается голосование
        uint256 endTime;             // Когда заканчивается
        uint256 forVotes;            // Голосов ЗА (квадратичные)
        uint256 againstVotes;        // Голосов ПРОТИВ
        uint256 abstainVotes;        // Воздержались
        ProposalState state;         // Текущее состояние
        bool executed;               // Исполнено ли
    }
    
    // ==================== ПЕРЕМЕННЫЕ ====================
    
    // Токен для голосования (у кого больше токенов - больше влияния)
    IERC20 public governanceToken;
    
    // Текущая версия модели
    uint256 public currentModelVersion;
    
    // IPFS хеш текущей модели
    string public currentModelIPFS;
    
    // Все предложения
    mapping(uint256 => Proposal) public proposals;
    uint256 public proposalCount;
    
    // Кто как голосовал (proposalId => voter => voted)
    mapping(uint256 => mapping(address => bool)) public hasVoted;
    
    // Сколько токенов использовал при голосовании
    mapping(uint256 => mapping(address => uint256)) public votingPower;
    
    // ==================== НАСТРОЙКИ ====================
    
    /**
     * QUORUM (кворум) = 33%
     * 
     * Что это: Минимум 33% всех токенов должны проголосовать.
     * Зачем: Защита от ситуации, когда 3 человека ночью
     *        приняли решение за всех.
     * 
     * Пример:
     * - Всего токенов: 1,000,000
     * - Нужно минимум: 330,000 токенов проголосовало
     */
    uint256 public constant QUORUM_PERCENTAGE = 33;
    
    /**
     * SUPERMAJORITY = 67%
     * 
     * Что это: Нужно 67% голосов ЗА (не 50%+1).
     * Зачем: Важные решения требуют широкого согласия.
     *        Простое большинство (51%) недостаточно.
     * 
     * Пример:
     * - Проголосовало: 400,000 токенов
     * - Нужно ЗА: 268,000 (67% от 400,000)
     */
    uint256 public constant SUPERMAJORITY_PERCENTAGE = 67;
    
    /**
     * VOTING_PERIOD = 7 дней
     * 
     * Сколько времени длится голосование.
     * Достаточно, чтобы все успели принять решение.
     */
    uint256 public constant VOTING_PERIOD = 7 days;
    
    /**
     * MIN_PROPOSAL_THRESHOLD = 1000 токенов
     * 
     * Минимум токенов, чтобы создать предложение.
     * Защита от спама: нельзя создать 1000 мусорных предложений.
     */
    uint256 public constant MIN_PROPOSAL_THRESHOLD = 1000 * 10**18;
    
    // Адреса с правом экстренной отмены
    mapping(address => bool) public guardians;
    address public admin;
    
    // ==================== СОБЫТИЯ ====================
    // (Логи, которые можно читать из Python)
    
    event ProposalCreated(
        uint256 indexed proposalId,
        address indexed proposer,
        string title,
        uint256 modelVersion
    );
    
    event VoteCast(
        uint256 indexed proposalId,
        address indexed voter,
        uint8 support,      // 0=против, 1=за, 2=воздержался
        uint256 votes       // Квадратичные голоса
    );
    
    event ProposalExecuted(
        uint256 indexed proposalId,
        uint256 newModelVersion,
        string ipfsHash
    );
    
    event ProposalCancelled(uint256 indexed proposalId, string reason);
    
    // ==================== КОНСТРУКТОР ====================
    
    constructor(address _token) {
        governanceToken = IERC20(_token);
        admin = msg.sender;
        guardians[msg.sender] = true;
        currentModelVersion = 0;
    }
    
    // ==================== МОДИФИКАТОРЫ ====================
    
    modifier onlyAdmin() {
        require(msg.sender == admin, "Only admin");
        _;
    }
    
    modifier onlyGuardian() {
        require(guardians[msg.sender], "Only guardian");
        _;
    }
    
    // ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
    
    /**
     * @notice Создать предложение об обновлении модели
     * 
     * ПРИМЕР:
     * propose(
     *   "Улучшенная маршрутизация v5",
     *   "Добавлена поддержка...",
     *   "QmXxxx...",  // IPFS хеш
     *   5             // Версия 5
     * )
     */
    function propose(
        string calldata title,
        string calldata description,
        string calldata ipfsHash,
        uint256 modelVersion
    ) external returns (uint256) {
        // Проверяем, что у создателя достаточно токенов
        require(
            governanceToken.balanceOf(msg.sender) >= MIN_PROPOSAL_THRESHOLD,
            "Need 1000+ tokens to propose"
        );
        
        // Проверяем, что версия новее текущей
        require(
            modelVersion > currentModelVersion,
            "Version must be higher"
        );
        
        proposalCount++;
        uint256 proposalId = proposalCount;
        
        proposals[proposalId] = Proposal({
            id: proposalId,
            proposer: msg.sender,
            title: title,
            description: description,
            ipfsHash: ipfsHash,
            modelVersion: modelVersion,
            startTime: block.timestamp,
            endTime: block.timestamp + VOTING_PERIOD,
            forVotes: 0,
            againstVotes: 0,
            abstainVotes: 0,
            state: ProposalState.ACTIVE,
            executed: false
        });
        
        emit ProposalCreated(proposalId, msg.sender, title, modelVersion);
        
        return proposalId;
    }
    
    /**
     * @notice Проголосовать за предложение
     * 
     * КВАДРАТИЧНОЕ ГОЛОСОВАНИЕ:
     * 
     * Обычное:     100 токенов = 100 голосов
     * Квадратичное: 100 токенов = √100 = 10 голосов
     * 
     * Почему это справедливее:
     * - Богач с 10,000 токенов: √10000 = 100 голосов
     * - 100 обычных людей по 100 токенов: 100 × √100 = 1000 голосов
     * 
     * Группа маленьких держателей сильнее одного кита!
     * 
     * @param proposalId Номер предложения
     * @param support 0=против, 1=за, 2=воздержался
     */
    function vote(uint256 proposalId, uint8 support) external nonReentrant {
        Proposal storage proposal = proposals[proposalId];
        
        // Проверки
        require(proposal.state == ProposalState.ACTIVE, "Not active");
        require(block.timestamp <= proposal.endTime, "Voting ended");
        require(!hasVoted[proposalId][msg.sender], "Already voted");
        require(support <= 2, "Invalid vote type");
        
        // Сколько токенов у голосующего
        uint256 tokenBalance = governanceToken.balanceOf(msg.sender);
        require(tokenBalance > 0, "No tokens");
        
        // КВАДРАТИЧНОЕ ГОЛОСОВАНИЕ: √(токены)
        // Используем Babylonian method для sqrt
        uint256 votes = sqrt(tokenBalance);
        
        // Записываем голос
        hasVoted[proposalId][msg.sender] = true;
        votingPower[proposalId][msg.sender] = votes;
        
        // Добавляем к соответствующему счётчику
        if (support == 1) {
            proposal.forVotes += votes;
        } else if (support == 0) {
            proposal.againstVotes += votes;
        } else {
            proposal.abstainVotes += votes;
        }
        
        emit VoteCast(proposalId, msg.sender, support, votes);
    }
    
    /**
     * @notice Исполнить принятое предложение
     * 
     * Может вызвать кто угодно после окончания голосования.
     * Проверяет кворум и supermajority.
     */
    function execute(uint256 proposalId) external nonReentrant {
        Proposal storage proposal = proposals[proposalId];
        
        require(proposal.state == ProposalState.ACTIVE, "Not active");
        require(block.timestamp > proposal.endTime, "Voting not ended");
        require(!proposal.executed, "Already executed");
        
        uint256 totalVotes = proposal.forVotes + proposal.againstVotes + proposal.abstainVotes;
        uint256 totalSupply = governanceToken.totalSupply();
        
        // Проверка QUORUM (33% токенов проголосовало)
        // Сравниваем квадратичные голоса с √(33% от supply)
        uint256 quorumVotes = sqrt(totalSupply * QUORUM_PERCENTAGE / 100);
        bool quorumReached = totalVotes >= quorumVotes;
        
        // Проверка SUPERMAJORITY (67% ЗА)
        uint256 supportPercentage = 0;
        if (proposal.forVotes + proposal.againstVotes > 0) {
            supportPercentage = proposal.forVotes * 100 / 
                (proposal.forVotes + proposal.againstVotes);
        }
        bool supermajorityReached = supportPercentage >= SUPERMAJORITY_PERCENTAGE;
        
        if (quorumReached && supermajorityReached) {
            // ПРИНЯТО! Обновляем модель
            proposal.state = ProposalState.PASSED;
            proposal.executed = true;
            currentModelVersion = proposal.modelVersion;
            currentModelIPFS = proposal.ipfsHash;
            
            emit ProposalExecuted(
                proposalId,
                proposal.modelVersion,
                proposal.ipfsHash
            );
        } else {
            // ОТКЛОНЕНО
            proposal.state = ProposalState.REJECTED;
        }
    }
    
    /**
     * @notice Экстренная отмена (только для guardians)
     * 
     * Используется если обнаружена уязвимость в предлагаемой модели.
     */
    function cancel(uint256 proposalId, string calldata reason) 
        external 
        onlyGuardian 
    {
        Proposal storage proposal = proposals[proposalId];
        require(
            proposal.state == ProposalState.ACTIVE || 
            proposal.state == ProposalState.PASSED,
            "Cannot cancel"
        );
        
        proposal.state = ProposalState.CANCELLED;
        emit ProposalCancelled(proposalId, reason);
    }
    
    // ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
    
    /**
     * @notice Квадратный корень (метод Вавилона)
     * 
     * Как это работает:
     * 1. Начинаем с приближения x = y/2
     * 2. Улучшаем: x = (x + y/x) / 2
     * 3. Повторяем до сходимости
     * 
     * Пример: √100
     * 1. x = 50
     * 2. x = (50 + 100/50) / 2 = 26
     * 3. x = (26 + 100/26) / 2 = 14.9
     * 4. x = (14.9 + 100/14.9) / 2 = 10.8
     * 5. x = 10.04 → 10 ✓
     */
    function sqrt(uint256 y) internal pure returns (uint256 z) {
        if (y > 3) {
            z = y;
            uint256 x = y / 2 + 1;
            while (x < z) {
                z = x;
                x = (y / x + x) / 2;
            }
        } else if (y != 0) {
            z = 1;
        }
    }
    
    /**
     * @notice Получить информацию о предложении
     */
    function getProposal(uint256 proposalId) external view returns (
        address proposer,
        string memory title,
        string memory ipfsHash,
        uint256 modelVersion,
        uint256 forVotes,
        uint256 againstVotes,
        ProposalState state
    ) {
        Proposal storage p = proposals[proposalId];
        return (
            p.proposer,
            p.title,
            p.ipfsHash,
            p.modelVersion,
            p.forVotes,
            p.againstVotes,
            p.state
        );
    }
    
    /**
     * @notice Проверить, достигнут ли кворум
     */
    function isQuorumReached(uint256 proposalId) external view returns (bool) {
        Proposal storage p = proposals[proposalId];
        uint256 totalVotes = p.forVotes + p.againstVotes + p.abstainVotes;
        uint256 quorumVotes = sqrt(governanceToken.totalSupply() * QUORUM_PERCENTAGE / 100);
        return totalVotes >= quorumVotes;
    }
    
    // ==================== АДМИН ФУНКЦИИ ====================
    
    function addGuardian(address guardian) external onlyAdmin {
        guardians[guardian] = true;
    }
    
    function removeGuardian(address guardian) external onlyAdmin {
        guardians[guardian] = false;
    }
}
