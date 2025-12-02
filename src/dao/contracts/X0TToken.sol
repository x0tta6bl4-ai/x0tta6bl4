// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Burnable.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";

/**
 * @title X0TToken - x0tta6bl4 Mesh Network Token
 * @author x0tta6bl4 Team
 * @notice ERC-20 токен для mesh-сети x0tta6bl4
 * 
 * ЭКОНОМИКА:
 * - Операторы нод стейкают X0T для участия в governance
 * - Ноды получают X0T за relay трафика (0.0001 X0T/relay)
 * - Пользователи платят X0T за ресурсы (bandwidth, storage, compute)
 * - Epoch rewards распределяются пропорционально stake × uptime
 * 
 * ОСОБЕННОСТИ:
 * - Burnable: 1% от resource payments сжигается (дефляция)
 * - Permit: gasless approvals (EIP-2612)
 * - Staking: встроенный механизм стейкинга
 */
contract X0TToken is ERC20, ERC20Burnable, ERC20Permit, Ownable, ReentrancyGuard {
    
    // ==================== КОНСТАНТЫ ====================
    
    uint256 public constant INITIAL_SUPPLY = 1_000_000_000 * 10**18;  // 1 billion X0T
    uint256 public constant MIN_STAKE = 100 * 10**18;                  // 100 X0T minimum stake
    uint256 public constant STAKE_LOCK_PERIOD = 1 days;                // 24h lock
    uint256 public constant REWARD_POOL_PER_EPOCH = 10_000 * 10**18;   // 10k X0T per epoch
    uint256 public constant EPOCH_DURATION = 1 hours;                  // 1 hour epochs
    
    // Resource pricing (in wei, 18 decimals)
    uint256 public constant PRICE_PER_RELAY = 0.0001 * 10**18;         // 0.0001 X0T
    uint256 public constant PRICE_PER_MB_BANDWIDTH = 0.001 * 10**18;   // 0.001 X0T
    uint256 public constant PRICE_PER_MB_STORAGE = 0.0001 * 10**18;    // 0.0001 X0T
    uint256 public constant FEE_PERCENT = 1;                           // 1% burned
    
    // ==================== СОСТОЯНИЕ ====================
    
    struct StakeInfo {
        uint256 amount;
        uint256 stakedAt;
        uint256 lockUntil;
    }
    
    mapping(address => StakeInfo) public stakes;
    address[] public stakers;
    mapping(address => bool) public isStaker;
    
    uint256 public totalStaked;
    uint256 public currentEpoch;
    uint256 public lastEpochTime;
    
    // Authorized relay nodes (can call payForRelay)
    mapping(address => bool) public authorizedRelayers;
    
    // ==================== СОБЫТИЯ ====================
    
    event Staked(address indexed user, uint256 amount, uint256 totalStaked);
    event Unstaked(address indexed user, uint256 amount, uint256 totalStaked);
    event RelayPaid(address indexed payer, address indexed relayer, uint256 amount, uint256 feeBurned);
    event ResourcePaid(address indexed payer, address indexed provider, uint256 amount, string resourceType);
    event EpochRewardsDistributed(uint256 indexed epoch, uint256 totalRewards, uint256 recipientCount);
    event RelayerAuthorized(address indexed relayer, bool authorized);
    
    // ==================== КОНСТРУКТОР ====================
    
    constructor() 
        ERC20("x0tta6bl4 Token", "X0T") 
        ERC20Permit("x0tta6bl4 Token")
        Ownable(msg.sender)
    {
        _mint(msg.sender, INITIAL_SUPPLY);
        lastEpochTime = block.timestamp;
        currentEpoch = 0;
    }
    
    // ==================== СТЕЙКИНГ ====================
    
    /**
     * @notice Застейкать токены для voting power и rewards
     * @param amount Количество токенов для стейка
     */
    function stake(uint256 amount) external nonReentrant {
        require(amount >= MIN_STAKE, "Below minimum stake");
        require(balanceOf(msg.sender) >= amount, "Insufficient balance");
        
        _transfer(msg.sender, address(this), amount);
        
        if (!isStaker[msg.sender]) {
            stakers.push(msg.sender);
            isStaker[msg.sender] = true;
        }
        
        StakeInfo storage info = stakes[msg.sender];
        info.amount += amount;
        info.stakedAt = block.timestamp;
        info.lockUntil = block.timestamp + STAKE_LOCK_PERIOD;
        
        totalStaked += amount;
        
        emit Staked(msg.sender, amount, info.amount);
    }
    
    /**
     * @notice Вывести застейканные токены (после lock периода)
     * @param amount Количество токенов для вывода
     */
    function unstake(uint256 amount) external nonReentrant {
        StakeInfo storage info = stakes[msg.sender];
        require(info.amount >= amount, "Insufficient stake");
        require(block.timestamp >= info.lockUntil, "Stake locked");
        
        info.amount -= amount;
        totalStaked -= amount;
        
        if (info.amount == 0) {
            isStaker[msg.sender] = false;
        }
        
        _transfer(address(this), msg.sender, amount);
        
        emit Unstaked(msg.sender, amount, info.amount);
    }
    
    /**
     * @notice Получить voting power пользователя
     * @param user Адрес пользователя
     * @return Voting power (= staked amount)
     */
    function votingPower(address user) external view returns (uint256) {
        return stakes[user].amount;
    }
    
    // ==================== RELAY REWARDS ====================
    
    /**
     * @notice Авторизовать/деавторизовать relay ноду
     * @param relayer Адрес relay ноды
     * @param authorized Статус авторизации
     */
    function setRelayerAuthorized(address relayer, bool authorized) external onlyOwner {
        authorizedRelayers[relayer] = authorized;
        emit RelayerAuthorized(relayer, authorized);
    }
    
    /**
     * @notice Оплатить relay (вызывается relay нодой)
     * @param payer Адрес отправителя пакета
     * @param relayCount Количество relay операций
     */
    function payForRelay(address payer, uint256 relayCount) external nonReentrant {
        require(authorizedRelayers[msg.sender], "Not authorized relayer");
        
        uint256 price = relayCount * PRICE_PER_RELAY;
        uint256 fee = (price * FEE_PERCENT) / 100;
        uint256 total = price + fee;
        
        require(balanceOf(payer) >= total, "Payer insufficient balance");
        
        // Transfer to relayer
        _transfer(payer, msg.sender, price);
        
        // Burn fee
        _burn(payer, fee);
        
        emit RelayPaid(payer, msg.sender, price, fee);
    }
    
    /**
     * @notice Оплатить ресурс (bandwidth, storage, etc.)
     * @param provider Адрес провайдера ресурса
     * @param amount Количество токенов
     * @param resourceType Тип ресурса ("bandwidth", "storage", "compute")
     */
    function payForResource(
        address provider, 
        uint256 amount,
        string calldata resourceType
    ) external nonReentrant {
        uint256 fee = (amount * FEE_PERCENT) / 100;
        uint256 total = amount + fee;
        
        require(balanceOf(msg.sender) >= total, "Insufficient balance");
        
        // Transfer to provider
        _transfer(msg.sender, provider, amount);
        
        // Burn fee
        _burn(msg.sender, fee);
        
        emit ResourcePaid(msg.sender, provider, amount, resourceType);
    }
    
    // ==================== EPOCH REWARDS ====================
    
    /**
     * @notice Распределить epoch rewards (вызывается owner/scheduler)
     * @param recipients Адреса получателей
     * @param uptimes Uptime каждого получателя (0-100, в процентах)
     */
    function distributeEpochRewards(
        address[] calldata recipients,
        uint256[] calldata uptimes
    ) external onlyOwner nonReentrant {
        require(block.timestamp >= lastEpochTime + EPOCH_DURATION, "Epoch not complete");
        require(recipients.length == uptimes.length, "Length mismatch");
        
        currentEpoch++;
        lastEpochTime = block.timestamp;
        
        // Calculate total weighted score
        uint256 totalScore = 0;
        uint256[] memory scores = new uint256[](recipients.length);
        
        for (uint256 i = 0; i < recipients.length; i++) {
            uint256 stakeAmount = stakes[recipients[i]].amount;
            scores[i] = (stakeAmount * uptimes[i]) / 100;
            totalScore += scores[i];
        }
        
        if (totalScore == 0) {
            emit EpochRewardsDistributed(currentEpoch, 0, 0);
            return;
        }
        
        // Distribute proportionally
        uint256 distributed = 0;
        uint256 recipientCount = 0;
        
        for (uint256 i = 0; i < recipients.length; i++) {
            if (scores[i] > 0) {
                uint256 reward = (scores[i] * REWARD_POOL_PER_EPOCH) / totalScore;
                if (reward > 0) {
                    _mint(recipients[i], reward);
                    distributed += reward;
                    recipientCount++;
                }
            }
        }
        
        emit EpochRewardsDistributed(currentEpoch, distributed, recipientCount);
    }
    
    // ==================== VIEW FUNCTIONS ====================
    
    /**
     * @notice Получить информацию о стейке пользователя
     */
    function getStakeInfo(address user) external view returns (
        uint256 amount,
        uint256 stakedAt,
        uint256 lockUntil,
        bool canUnstake
    ) {
        StakeInfo memory info = stakes[user];
        return (
            info.amount,
            info.stakedAt,
            info.lockUntil,
            block.timestamp >= info.lockUntil
        );
    }
    
    /**
     * @notice Получить количество стейкеров
     */
    function getStakerCount() external view returns (uint256) {
        return stakers.length;
    }
    
    /**
     * @notice Получить staking ratio (staked / total supply)
     */
    function getStakingRatio() external view returns (uint256) {
        if (totalSupply() == 0) return 0;
        return (totalStaked * 10000) / totalSupply(); // Returns basis points (100 = 1%)
    }
    
    /**
     * @notice Проверить, можно ли распределить epoch rewards
     */
    function canDistributeRewards() external view returns (bool) {
        return block.timestamp >= lastEpochTime + EPOCH_DURATION;
    }
}
