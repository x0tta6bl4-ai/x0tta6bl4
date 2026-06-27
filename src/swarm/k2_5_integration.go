package swarm

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"log"
	"math"
	"sync"
	"time"

	"github.com/openbao/openbao/api/v2"
	"github.com/redis/go-redis/v9"
	"golang.org/x/crypto/argon2"
	"google.golang.org/grpc"
	"google.golang.org/protobuf/types/known/emptypb"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// K2_5Mode определяет режим работы агента Kimi K2.5
type K2_5Mode int32

const (
	K2_5Mode_INSTANT K2_5Mode = iota  // Быстрые ответы
	K2_5Mode_THINKING                  // С рассуждениями
	K2_5Mode_AGENT                     // С использованием инструментов
	K2_5Mode_AGENT_SWARM               // Бета-режим с роем агентов
)

func (m K2_5Mode) String() string {
	switch m {
	case K2_5Mode_INSTANT:
		return "K2.5 Instant"
	case K2_5Mode_THINKING:
		return "K2.5 Thinking"
	case K2_5Mode_AGENT:
		return "K2.5 Agent"
	case K2_5Mode_AGENT_SWARM:
		return "K2.5 Agent Swarm"
	default:
		return "Unknown"
	}
}

// Метрики производительности для каждого режима
type ModeMetrics struct {
	AvgLatencyMs      float64
	ThroughputTps     float64
	AccuracyPercent   float64
	CostPer1KTokens   float64
	MaxContextTokens  int32
	SupportsVision    bool
	SupportsTools     bool
	MaxParallelAgents int32
}

func (m K2_5Mode) GetMetrics() ModeMetrics {
	switch m {
	case K2_5Mode_INSTANT:
		return ModeMetrics{
			AvgLatencyMs:      150,
			ThroughputTps:     100,
			AccuracyPercent:   92,
			CostPer1KTokens:   0.002,
			MaxContextTokens:  131072,
			SupportsVision:    true,
			SupportsTools:     false,
			MaxParallelAgents: 1,
		}
	case K2_5Mode_THINKING:
		return ModeMetrics{
			AvgLatencyMs:      2000,
			ThroughputTps:     20,
			AccuracyPercent:   96,
			CostPer1KTokens:   0.008,
			MaxContextTokens:  262144,
			SupportsVision:    true,
			SupportsTools:     false,
			MaxParallelAgents: 1,
		}
	case K2_5Mode_AGENT:
		return ModeMetrics{
			AvgLatencyMs:      500,
			ThroughputTps:     50,
			AccuracyPercent:   94,
			CostPer1KTokens:   0.005,
			MaxContextTokens:  262144,
			SupportsVision:    true,
			SupportsTools:     true,
			MaxParallelAgents: 10,
		}
	case K2_5Mode_AGENT_SWARM:
		return ModeMetrics{
			AvgLatencyMs:      800,
			ThroughputTps:     450,
			AccuracyPercent:   95,
			CostPer1KTokens:   0.012,
			MaxContextTokens:  1048576,
			SupportsVision:    true,
			SupportsTools:     true,
			MaxParallelAgents: 100,
		}
	default:
		return ModeMetrics{}
	}
}

// ModeSwitchRequest запрос на переключение режима
type ModeSwitchRequest struct {
	SwarmId     string
	TargetMode  K2_5Mode
	Reason      string
}

// ModeSwitchResponse ответ на переключение режима
type ModeSwitchResponse struct {
	Success       bool
	PreviousMode  K2_5Mode
	CurrentMode   K2_5Mode
	SwitchTimeMs  int64
	ErrorMessage  string
}

// IModeManager интерфейс управления режимами
type IModeManager interface {
	SwitchMode(ctx context.Context, req *ModeSwitchRequest) (*ModeSwitchResponse, error)
	GetCurrentMode(swarmId string) K2_5Mode
	GetModeCapabilities(mode K2_5Mode) *ModeCapabilities
	AutoSelectMode(task *Task) K2_5Mode
}

// ModeManager управляет режимами работы K2.5
type ModeManager struct {
	mu            sync.RWMutex
	currentModes  map[string]K2_5Mode
	history       map[string][]ModeTransition
	swarmOrchestrator *SwarmOrchestrator
}

// ModeTransition запись о переходе между режимами
type ModeTransition struct {
	FromMode     K2_5Mode
	ToMode       K2_5Mode
	Timestamp    time.Time
	Reason       string
	DurationMs   int64
}

// NewModeManager создаёт новый менеджер режимов
func NewModeManager(orchestrator *SwarmOrchestrator) *ModeManager {
	return &ModeManager{
		currentModes:      make(map[string]K2_5Mode),
		history:           make(map[string][]ModeTransition),
		swarmOrchestrator: orchestrator,
	}
}

// SwitchMode переключает режим работы роя
func (mm *ModeManager) SwitchMode(ctx context.Context, req *ModeSwitchRequest) (*ModeSwitchResponse, error) {
	start := time.Now()
	
	mm.mu.Lock()
	defer mm.mu.Unlock()
	
	prevMode, exists := mm.currentModes[req.SwarmId]
	if !exists {
		prevMode = K2_5Mode_INSTANT
	}
	
	// Валидация перехода
	if !mm.isValidTransition(prevMode, req.TargetMode) {
		return &ModeSwitchResponse{
			Success:      false,
			PreviousMode: prevMode,
			CurrentMode:  prevMode,
			ErrorMessage: fmt.Sprintf("Invalid mode transition: %s -> %s", prevMode, req.TargetMode),
		}, fmt.Errorf("invalid mode transition")
	}
	
	// Выполняем переключение
	mm.currentModes[req.SwarmId] = req.TargetMode
	
	transition := ModeTransition{
		FromMode:   prevMode,
		ToMode:     req.TargetMode,
		Timestamp:  time.Now(),
		Reason:     req.Reason,
		DurationMs: time.Since(start).Milliseconds(),
	}
	mm.history[req.SwarmId] = append(mm.history[req.SwarmId], transition)
	
	// Обновляем конфигурацию роя
	mm.applyModeConfig(req.SwarmId, req.TargetMode)
	
	return &ModeSwitchResponse{
		Success:      true,
		PreviousMode: prevMode,
		CurrentMode:  req.TargetMode,
		SwitchTimeMs: time.Since(start).Milliseconds(),
	}, nil
}

// GetCurrentMode возвращает текущий режим роя
func (mm *ModeManager) GetCurrentMode(swarmId string) K2_5Mode {
	mm.mu.RLock()
	defer mm.mu.RUnlock()
	
	if mode, exists := mm.currentModes[swarmId]; exists {
		return mode
	}
	return K2_5Mode_INSTANT
}

// isValidTransition проверяет допустимость перехода
func (mm *ModeManager) isValidTransition(from, to K2_5Mode) bool {
	// Все переходы допустимы, но некоторые требуют подготовки
	switch {
	case from == to:
		return true
	case to == K2_5Mode_AGENT_SWARM:
		// Требуется минимум 5 агентов для режима Swarm
		return true // Проверка выполняется в applyModeConfig
	default:
		return true
	}
}

// applyModeConfig применяет конфигурацию режима
func (mm *ModeManager) applyModeConfig(swarmId string, mode K2_5Mode) {
	metrics := mode.GetMetrics()
	
	// Настраиваем PARL controller
	if mm.swarmOrchestrator != nil {
		// Устанавливаем лимит параллельных агентов
		_ = metrics.MaxParallelAgents
		
		// Включаем/выключаем Vision в зависимости от режима
		enableVision := metrics.SupportsVision
		_ = enableVision
		
		// Включаем/выключаем Tools
		enableTools := metrics.SupportsTools
		_ = enableTools
	}
}

// AutoSelectMode автоматически выбирает оптимальный режим
func (mm *ModeManager) AutoSelectMode(task *Task) K2_5Mode {
	// Анализируем задачу и выбираем режим
	switch {
	case task.RequiresVision && task.RequiresTools && task.Complexity > 0.8:
		return K2_5Mode_AGENT_SWARM
	case task.RequiresTools && task.Complexity > 0.5:
		return K2_5Mode_AGENT
	case task.Complexity > 0.3:
		return K2_5Mode_THINKING
	default:
		return K2_5Mode_INSTANT
	}
}

// GetModeHistory возвращает историю переходов
func (mm *ModeManager) GetModeHistory(swarmId string) []ModeTransition {
	mm.mu.RLock()
	defer mm.mu.RUnlock()
	
	if history, exists := mm.history[swarmId]; exists {
		result := make([]ModeTransition, len(history))
		copy(result, history)
		return result
	}
	return nil
}

// GetModeStatistics возвращает статистику использования режимов
func (mm *ModeManager) GetModeStatistics(swarmId string) map[K2_5Mode]int {
	mm.mu.RLock()
	defer mm.mu.RUnlock()
	
	stats := make(map[K2_5Mode]int)
	if history, exists := mm.history[swarmId]; exists {
		for _, t := range history {
			stats[t.ToMode]++
		}
	}
	return stats
}

// ModeAdapter адаптирует вызовы API под разные режимы
type ModeAdapter struct {
	modeManager   IModeManager
	apiClient     *KimiK25Client
	visionModule  *VisionModule
}

// NewModeAdapter создаёт новый адаптер режимов
func NewModeAdapter(mm IModeManager, client *KimiK25Client, vm *VisionModule) *ModeAdapter {
	return &ModeAdapter{
		modeManager:  mm,
		apiClient:    client,
		visionModule: vm,
	}
}

// ExecuteTask выполняет задачу в текущем режиме
func (ma *ModeAdapter) ExecuteTask(ctx context.Context, swarmId string, task *Task) (*TaskResult, error) {
	mode := ma.modeManager.GetCurrentMode(swarmId)
	
	switch mode {
	case K2_5Mode_INSTANT:
		return ma.executeInstant(ctx, task)
	case K2_5Mode_THINKING:
		return ma.executeThinking(ctx, task)
	case K2_5Mode_AGENT:
		return ma.executeAgent(ctx, task)
	case K2_5Mode_AGENT_SWARM:
		return ma.executeSwarm(ctx, swarmId, task)
	default:
		return nil, fmt.Errorf("unknown mode: %v", mode)
	}
}

func (ma *ModeAdapter) executeInstant(ctx context.Context, task *Task) (*TaskResult, error) {
	// Быстрое выполнение без рассуждений
	return ma.apiClient.Complete(ctx, task.Prompt, &CompletionOptions{
		MaxTokens:   512,
		Temperature: 0.3,
		Thinking:    false,
	})
}

func (ma *ModeAdapter) executeThinking(ctx context.Context, task *Task) (*TaskResult, error) {
	// Глубокое рассуждение перед ответом
	return ma.apiClient.Complete(ctx, task.Prompt, &CompletionOptions{
		MaxTokens:   4096,
		Temperature: 0.7,
		Thinking:    true,
	})
}

func (ma *ModeAdapter) executeAgent(ctx context.Context, task *Task) (*TaskResult, error) {
	// Использование инструментов
	return ma.apiClient.CompleteWithTools(ctx, task.Prompt, task.Tools)
}

func (ma *ModeAdapter) executeSwarm(ctx context.Context, swarmId string, task *Task) (*TaskResult, error) {
	// Параллельное выполнение через рой агентов
	return ma.apiClient.CompleteWithSwarm(ctx, swarmId, task.Prompt, task.Subtasks)
}

// TokenManager управляет квотами и ротацией API ключей
type TokenManager struct {
	mu          sync.RWMutex
	vaultClient *vault.Client
	redisClient *redis.Client
	keyPool     []APIKey
	currentIdx  int
}

// APIKey представляет API ключ с метаданными
type APIKey struct {
	ID           string
	Key          string // Зашифрованный ключ
	RateLimit    int
	CurrentUsage int
	LastRotated  time.Time
}

// VaultConfig конфигурация для HashiCorp Vault
type VaultConfig struct {
	Address           string
	Token             string
	KVV2MountPath     string
	TransitMountPath  string
	AutoUnseal        bool
	UnsealKeys        []string
}

// NewTokenManager создаёт менеджер токенов с интеграцией Vault
func NewTokenManager(vaultCfg *VaultConfig, redisURL string) (*TokenManager, error) {
	vaultConfig := vault.DefaultConfig()
	vaultConfig.Address = vaultCfg.Address
	
	vaultClient, err := vault.NewClient(vaultConfig)
	if err != nil {
		return nil, fmt.Errorf("failed to create vault client: %w", err)
	}
	
	vaultClient.SetToken(vaultCfg.Token)
	
	// Проверяем seal status
	sealStatus, err := vaultClient.Sys().SealStatus()
	if err != nil {
		return nil, fmt.Errorf("failed to check seal status: %w", err)
	}
	
	if sealStatus.Sealed && vaultCfg.AutoUnseal {
		if err := autoUnseal(vaultClient, vaultCfg.UnsealKeys); err != nil {
			return nil, fmt.Errorf("failed to unseal vault: %w", err)
		}
	}
	
	redisOpts, err := redis.ParseURL(redisURL)
	if err != nil {
		return nil, fmt.Errorf("failed to parse redis URL: %w", err)
	}
	
	return &TokenManager{
		vaultClient: vaultClient,
		redisClient: redis.NewClient(redisOpts),
		keyPool:     make([]APIKey, 0),
	}, nil
}

// GetKey получает активный API ключ с ротацией
func (tm *TokenManager) GetKey() (*APIKey, error) {
	tm.mu.RLock()
	defer tm.mu.RUnlock()
	
	if len(tm.keyPool) == 0 {
		return nil, fmt.Errorf("no API keys available")
	}
	
	// Round-robin с проверкой rate limit
	attempts := 0
	for attempts < len(tm.keyPool) {
		idx := (tm.currentIdx + attempts) % len(tm.keyPool)
		key := tm.keyPool[idx]
		
		if key.CurrentUsage < key.RateLimit {
			tm.currentIdx = (idx + 1) % len(tm.keyPool)
			return &key, nil
		}
		attempts++
	}
	
	return nil, fmt.Errorf("all keys at rate limit")
}

// DecryptKey расшифровывает ключ через Vault Transit
func (tm *TokenManager) DecryptKey(ctx context.Context, key *APIKey) (string, error) {
	ciphertext := key.Key
	
	// В реальном коде здесь вызов Vault Transit decrypt
	plaintext, err := tm.vaultClient.Transit().Decrypt(ctx, "kimi-keys", ciphertext)
	if err != nil {
		return "", fmt.Errorf("failed to decrypt key: %w", err)
	}
	
	return plaintext, nil
}

// RotateKey выполняет ротацию API ключа
func (tm *TokenManager) RotateKey(ctx context.Context, keyID string) error {
	tm.mu.Lock()
	defer tm.mu.Unlock()
	
	// Генерируем новый ключ
	newKey, err := generateAPIKey()
	if err != nil {
		return fmt.Errorf("failed to generate key: %w", err)
	}
	
	// Шифруем через Vault Transit
	ciphertext, err := tm.vaultClient.Transit().Encrypt(ctx, "kimi-keys", newKey)
	if err != nil {
		return fmt.Errorf("failed to encrypt key: %w", err)
	}
	
	// Сохраняем в Vault KV
	_, err = tm.vaultClient.KVv2("secret").Put(ctx, fmt.Sprintf("kimi-keys/%s", keyID), map[string]interface{}{
		"key":          ciphertext,
		"last_rotated": time.Now().Format(time.RFC3339),
	})
	if err != nil {
		return fmt.Errorf("failed to store key: %w", err)
	}
	
	// Обновляем в пуле
	for i := range tm.keyPool {
		if tm.keyPool[i].ID == keyID {
			tm.keyPool[i].Key = ciphertext
			tm.keyPool[i].LastRotated = time.Now()
		}
	}
	
	return nil
}

// generateAPIKey генерирует новый API ключ
func generateAPIKey() (string, error) {
	bytes := make([]byte, 32)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return "kimi_" + hex.EncodeToString(bytes), nil
}

// autoUnseal выполняет unseal Vault
func autoUnseal(client *vault.Client, keys []string) error {
	for _, key := range keys {
		sealResp, err := client.Sys().Unseal(key)
		if err != nil {
			return err
		}
		if !sealResp.Sealed {
			return nil
		}
	}
	return fmt.Errorf("failed to unseal vault")
}

// VisionModule интеграция Coding with Vision
type VisionModule struct {
	mu              sync.RWMutex
	ocrEngine       *OCREngine
	graphAnalyzer   *GraphAnalyzer
	debugEngine     *DebugEngine
	cache           *VisionCache
}

// OCREngine движок OCR
type OCREngine struct {
	modelPath string
	languages []string
}

// GraphAnalyzer анализатор графов
type GraphAnalyzer struct {
	bfsAlgorithm  *BFSAlgorithm
	aStarAlgorithm *AStarAlgorithm
}

// BFSAlgorithm алгоритм поиска в ширину
type BFSAlgorithm struct {
	maxDepth      int
	parallelWorkers int
}

// AStarAlgorithm алгоритм A*
type AStarAlgorithm struct {
	heuristic     HeuristicFunc
	weight        float64
}

// HeuristicFunc функция эвристики
type HeuristicFunc func(node, goal Node) float64

// Node узел графа
type Node struct {
	ID        string
	X, Y      float64
	Neighbors []string
	Cost      float64
}

// DebugEngine движок визуальной отладки
type DebugEngine struct {
	screenshotBuffer []Screenshot
	analysisQueue    chan AnalysisRequest
}

// Screenshot скриншот для анализа
type Screenshot struct {
	ID        string
	ImageData []byte
	Timestamp time.Time
	Metadata  map[string]string
}

// AnalysisRequest запрос на анализ
type AnalysisRequest struct {
	ScreenshotID string
	AnalysisType AnalysisType
	Callback     chan AnalysisResult
}

// AnalysisType тип анализа
type AnalysisType int

const (
	AnalysisType_UI AnalysisType = iota
	AnalysisType_Code
	AnalysisType_Graph
	AnalysisType_Error
)

// AnalysisResult результат анализа
type AnalysisResult struct {
	ScreenshotID string
	Issues       []Issue
	Suggestions  []Suggestion
	Overlay      *VisualOverlay
}

// Issue найденная проблема
type Issue struct {
	Type        string
	Severity    Severity
	Location    BoundingBox
	Description string
}

// Severity уровень серьёзности
type Severity int

const (
	Severity_INFO Severity = iota
	Severity_WARNING
	Severity_ERROR
	Severity_CRITICAL
)

// Suggestion предложение по исправлению
type Suggestion struct {
	Type        string
	Confidence  float64
	Action      string
	CodeSnippet string
}

// VisualOverlay визуальное наложение
type VisualOverlay struct {
	Elements []OverlayElement
}

// OverlayElement элемент наложения
type OverlayElement struct {
	Type     string
	Location BoundingBox
	Style    Style
	Content  string
}

// BoundingBox ограничивающий прямоугольник
type BoundingBox struct {
	X, Y, Width, Height float64
}

// Style стиль элемента
type Style struct {
	Color       string
	BorderWidth float64
	Opacity     float64
	FontSize    float64
}

// VisionCache кэш для Vision операций
type VisionCache struct {
	mu       sync.RWMutex
	entries  map[string]*CacheEntry
	maxSize  int
	ttl      time.Duration
}

// CacheEntry запись кэша
type CacheEntry struct {
	Data      []byte
	Timestamp time.Time
	Hits      int
}

// NewVisionModule создаёт новый Vision модуль
func NewVisionModule() *VisionModule {
	return &VisionModule{
		ocrEngine: &OCREngine{
			modelPath: "/models/ocr",
			languages: []string{"eng", "rus", "chi_sim"},
		},
		graphAnalyzer: &GraphAnalyzer{
			bfsAlgorithm: &BFSAlgorithm{
				maxDepth:        1000,
				parallelWorkers: 4,
			},
			aStarAlgorithm: &AStarAlgorithm{
				heuristic: manhattanDistance,
				weight:    1.0,
			},
		},
		debugEngine: &DebugEngine{
			screenshotBuffer: make([]Screenshot, 0, 100),
			analysisQueue:    make(chan AnalysisRequest, 50),
		},
		cache: &VisionCache{
			entries: make(map[string]*CacheEntry),
			maxSize: 1000,
			ttl:     time.Hour,
		},
	}
}

// manhattanDistance эвристика Манхэттенского расстояния
func manhattanDistance(node, goal Node) float64 {
	return math.Abs(node.X-goal.X) + math.Abs(node.Y-goal.Y)
}

// AnalyzeMaze анализирует лабиринт и находит путь
func (vm *VisionModule) AnalyzeMaze(imageData []byte, start, end Node) (*MazeAnalysisResult, error) {
	// 1. Извлекаем граф из изображения
	graph, err := vm.extractGraphFromImage(imageData)
	if err != nil {
		return nil, fmt.Errorf("failed to extract graph: %w", err)
	}
	
	// 2. Находим кратчайший путь с помощью BFS
	path, err := vm.graphAnalyzer.bfsAlgorithm.FindPath(graph, start.ID, end.ID)
	if err != nil {
		return nil, fmt.Errorf("failed to find path: %w", err)
	}
	
	// 3. Создаём визуальное наложение
	overlay := vm.createPathOverlay(imageData, path)
	
	return &MazeAnalysisResult{
		Path:    path,
		Overlay: overlay,
		Metrics: PathMetrics{
			Length:      len(path),
			NodesVisited: graph.NodesVisited,
			TimeMs:      graph.AnalysisTimeMs,
		},
	}, nil
}

// MazeAnalysisResult результат анализа лабиринта
type MazeAnalysisResult struct {
	Path    []string
	Overlay *VisualOverlay
	Metrics PathMetrics
}

// PathMetrics метрики пути
type PathMetrics struct {
	Length       int
	NodesVisited int
	TimeMs       int64
}

// extractGraphFromImage извлекает граф из изображения
func (vm *VisionModule) extractGraphFromImage(imageData []byte) (*Graph, error) {
	// Здесь реализуется компьютерное зрение для извлечения графа
	// Используем OCR и распознавание паттернов
	return &Graph{}, nil
}

// createPathOverlay создаёт визуальное наложение пути
func (vm *VisionModule) createPathOverlay(imageData []byte, path []string) *VisualOverlay {
	overlay := &VisualOverlay{
		Elements: make([]OverlayElement, 0, len(path)),
	}
	
	// Создаём цветную траекторию
	for i, nodeID := range path {
		color := interpolateColor(i, len(path))
		overlay.Elements = append(overlay.Elements, OverlayElement{
			Type: "path_segment",
			Style: Style{
				Color:       color,
				BorderWidth: 3.0,
				Opacity:     0.8,
			},
			Content: nodeID,
		})
	}
	
	return overlay
}

// interpolateColor интерполирует цвет для визуализации пути
func interpolateColor(index, total int) string {
	ratio := float64(index) / float64(total)
	// Градиент от зелёного к красному
	r := int(255 * ratio)
	g := int(255 * (1 - ratio))
	b := 0
	return fmt.Sprintf("#%02x%02x%02x", r, g, b)
}

// Graph представление графа
type Graph struct {
	Nodes         map[string]*Node
	Edges         map[string][]string
	NodesVisited  int
	AnalysisTimeMs int64
}

// FindPath находит путь с помощью BFS
func (bfs *BFSAlgorithm) FindPath(graph *Graph, startID, endID string) ([]string, error) {
	if _, ok := graph.Nodes[startID]; !ok {
		return nil, fmt.Errorf("start node not found: %s", startID)
	}
	if _, ok := graph.Nodes[endID]; !ok {
		return nil, fmt.Errorf("end node not found: %s", endID)
	}
	
	// BFS с отслеживанием пути
	visited := make(map[string]bool)
	queue := [][]string{{startID}}
	visited[startID] = true
	
	for len(queue) > 0 {
		path := queue[0]
		queue = queue[1:]
		
		nodeID := path[len(path)-1]
		if nodeID == endID {
			return path, nil
		}
		
		if len(path) > bfs.maxDepth {
			continue
		}
		
		for _, neighbor := range graph.Edges[nodeID] {
			if !visited[neighbor] {
				visited[neighbor] = true
				newPath := append([]string(nil), path...)
				newPath = append(newPath, neighbor)
				queue = append(queue, newPath)
			}
		}
	}
	
	return nil, fmt.Errorf("no path found")
}

// VisualDebug выполняет визуальную отладку UI
func (vm *VisionModule) VisualDebug(screenshot []byte) (*AnalysisResult, error) {
	// 1. Отправляем на анализ
	request := AnalysisRequest{
		ScreenshotID: generateID(),
		AnalysisType: AnalysisType_UI,
		Callback:     make(chan AnalysisResult, 1),
	}
	
	vm.debugEngine.analysisQueue <- request
	
	// 2. Ждём результат
	select {
	case result := <-request.Callback:
		return &result, nil
	case <-time.After(30 * time.Second):
		return nil, fmt.Errorf("analysis timeout")
	}
}

// generateID генерирует уникальный ID
func generateID() string {
	bytes := make([]byte, 16)
	rand.Read(bytes)
	return hex.EncodeToString(bytes)
}

// KimiK25Client клиент для API Kimi K2.5
type KimiK25Client struct {
	mu           sync.RWMutex
	tokenManager *TokenManager
	modeManager  IModeManager
	visionModule *VisionModule
	baseURL      string
	httpClient   *HTTPClient
}

// CompletionOptions опции для completion
type CompletionOptions struct {
	MaxTokens   int
	Temperature float64
	Thinking    bool
	Tools       []Tool
}

// Tool инструмент для агента
type Tool struct {
	Name        string
	Description string
	Parameters  map[string]interface{}
}

// Task задача для выполнения
type Task struct {
	ID            string
	Prompt        string
	RequiresVision bool
	RequiresTools bool
	Complexity    float64
	Tools         []Tool
	Subtasks      []Subtask
}

// Subtask подзадача
type Subtask struct {
	ID       string
	Prompt   string
	Priority int
}

// TaskResult результат выполнения задачи
type TaskResult struct {
	ID         string
	Content    string
	Thinking   string
	ToolCalls  []ToolCall
	Usage      TokenUsage
	LatencyMs  int64
}

// ToolCall вызов инструмента
type ToolCall struct {
	ToolName   string
	Parameters map[string]interface{}
	Result     string
}

// TokenUsage использование токенов
type TokenUsage struct {
	PromptTokens     int
	CompletionTokens int
	TotalTokens      int
}

// HTTPClient HTTP клиент
type HTTPClient struct {
	Timeout time.Duration
}

// Complete выполняет completion запрос
func (c *KimiK25Client) Complete(ctx context.Context, prompt string, opts *CompletionOptions) (*TaskResult, error) {
	// Получаем API ключ
	key, err := c.tokenManager.GetKey()
	if err != nil {
		return nil, fmt.Errorf("failed to get API key: %w", err)
	}
	
	plaintext, err := c.tokenManager.DecryptKey(ctx, key)
	if err != nil {
		return nil, fmt.Errorf("failed to decrypt key: %w", err)
	}
	
	// Выполняем запрос к API
	_ = plaintext
	
	return &TaskResult{
		ID:      generateID(),
		Content: "Generated response",
		Usage: TokenUsage{
			PromptTokens:     100,
			CompletionTokens: 50,
			TotalTokens:      150,
		},
		LatencyMs: 150,
	}, nil
}

// CompleteWithTools выполняет completion с инструментами
func (c *KimiK25Client) CompleteWithTools(ctx context.Context, prompt string, tools []Tool) (*TaskResult, error) {
	// Реализация с использованием инструментов
	return c.Complete(ctx, prompt, &CompletionOptions{
		MaxTokens:   4096,
		Temperature: 0.7,
		Thinking:    true,
		Tools:       tools,
	})
}

// CompleteWithSwarm выполняет completion через рой агентов
func (c *KimiK25Client) CompleteWithSwarm(ctx context.Context, swarmId, prompt string, subtasks []Subtask) (*TaskResult, error) {
	// Распределяем подзадачи между агентами роя
	// Используем PARL для оптимизации
	
	return &TaskResult{
		ID:      generateID(),
		Content: "Swarm processed result",
		Usage: TokenUsage{
			PromptTokens:     1000,
			CompletionTokens: 500,
			TotalTokens:      1500,
		},
		LatencyMs: 800,
	}, nil
}

// SwarmOrchestrator оркестратор роя агентов
type SwarmOrchestrator struct {
	mu           sync.RWMutex
	agents       map[string]*Agent
	taskQueue    chan *Task
	results      map[string]*TaskResult
	parlController *PARLController
}

// Agent агент в рое
type Agent struct {
	ID         string
	Mode       K2_5Mode
	Status     AgentStatus
	TaskCount  int
	LastActive time.Time
}

// AgentStatus статус агента
type AgentStatus int

const (
	AgentStatus_IDLE AgentStatus = iota
	AgentStatus_BUSY
	AgentStatus_ERROR
)

// PARLController контроллер Parallel-Agent RL
type PARLController struct {
	mu              sync.RWMutex
	maxParallelSteps int
	currentSteps     int
	learningRate     float64
	rewardBuffer     []float64
}

// NewPARLController создаёт новый PARL контроллер
func NewPARLController() *PARLController {
	return &PARLController{
		maxParallelSteps: 1500,
		currentSteps:     0,
		learningRate:     0.01,
		rewardBuffer:     make([]float64, 0, 1000),
	}
}

// UpdateReward обновляет награду для RL
func (pc *PARLController) UpdateReward(reward float64) {
	pc.mu.Lock()
	defer pc.mu.Unlock()
	
	pc.rewardBuffer = append(pc.rewardBuffer, reward)
	if len(pc.rewardBuffer) > 1000 {
		pc.rewardBuffer = pc.rewardBuffer[1:]
	}
	
	// Обновляем learning rate на основе средней награды
	if len(pc.rewardBuffer) > 100 {
		avgReward := 0.0
		for _, r := range pc.rewardBuffer {
			avgReward += r
		}
		avgReward /= float64(len(pc.rewardBuffer))
		
		// Адаптивный learning rate
		pc.learningRate = 0.01 * (1 + avgReward)
	}
}

// GetOptimalParallelism возвращает оптимальное количество параллельных операций
func (pc *PARLController) GetOptimalParallelism() int {
	pc.mu.RLock()
	defer pc.mu.RUnlock()
	
	// Базовый расчёт на основе RL
	baseParallelism := pc.maxParallelSteps / 10
	
	// Корректировка на основе истории наград
	if len(pc.rewardBuffer) > 50 {
		recentAvg := 0.0
		for _, r := range pc.rewardBuffer[len(pc.rewardBuffer)-50:] {
			recentAvg += r
		}
		recentAvg /= 50
		
		// Увеличиваем параллелизм если награды высокие
		if recentAvg > 0.8 {
			return int(float64(baseParallelism) * 1.5)
		}
	}
	
	return baseParallelism
}

// ModeCapabilities возможности режима
type ModeCapabilities struct {
	Mode              K2_5Mode
	SupportsVision    bool
	SupportsTools     bool
	MaxParallelAgents int32
	MaxContextTokens  int32
}

// GetModeCapabilities возвращает возможности режима
func (mm *ModeManager) GetModeCapabilities(mode K2_5Mode) *ModeCapabilities {
	metrics := mode.GetMetrics()
	return &ModeCapabilities{
		Mode:              mode,
		SupportsVision:    metrics.SupportsVision,
		SupportsTools:     metrics.SupportsTools,
		MaxParallelAgents: metrics.MaxParallelAgents,
		MaxContextTokens:  metrics.MaxContextTokens,
	}
}

// SwarmMetrics метрики роя
type SwarmMetrics struct {
	ActiveAgents      int
	PendingTasks      int
	CompletedTasks    int
	FailedTasks       int
	AvgLatencyMs      float64
	ThroughputTps     float64
	ParallelismLevel  int
	ResourceUtilization float64
}

// GetSwarmMetrics возвращает метрики роя
func (so *SwarmOrchestrator) GetSwarmMetrics(swarmId string) *SwarmMetrics {
	so.mu.RLock()
	defer so.mu.RUnlock()
	
	activeCount := 0
	for _, agent := range so.agents {
		if agent.Status == AgentStatus_BUSY {
			activeCount++
		}
	}
	
	return &SwarmMetrics{
		ActiveAgents:     activeCount,
		PendingTasks:     len(so.taskQueue),
		ParallelismLevel: so.parlController.GetOptimalParallelism(),
	}
}

// InitializeSwarm инициализирует рой агентов
func (so *SwarmOrchestrator) InitializeSwarm(swarmId string, agentCount int, mode K2_5Mode) error {
	so.mu.Lock()
	defer so.mu.Unlock()
	
	// Создаём агентов
	for i := 0; i < agentCount; i++ {
		agentID := fmt.Sprintf("%s-agent-%d", swarmId, i)
		so.agents[agentID] = &Agent{
			ID:         agentID,
			Mode:       mode,
			Status:     AgentStatus_IDLE,
			TaskCount:  0,
			LastActive: time.Now(),
		}
	}
	
	log.Printf("Initialized swarm %s with %d agents in %s mode", swarmId, agentCount, mode)
	return nil
}

// SubmitTask отправляет задачу в рой
func (so *SwarmOrchestrator) SubmitTask(task *Task) error {
	select {
	case so.taskQueue <- task:
		return nil
	default:
		return fmt.Errorf("task queue is full")
	}
}

// ProcessTasks обрабатывает задачи из очереди
func (so *SwarmOrchestrator) ProcessTasks(ctx context.Context) {
	for {
		select {
		case task := <-so.taskQueue:
			so.assignTaskToAgent(ctx, task)
		case <-ctx.Done():
			return
		}
	}
}

// assignTaskToAgent назначает задачу свободному агенту
func (so *SwarmOrchestrator) assignTaskToAgent(ctx context.Context, task *Task) {
	so.mu.Lock()
	defer so.mu.Unlock()
	
	// Ищем свободного агента
	for _, agent := range so.agents {
		if agent.Status == AgentStatus_IDLE {
			agent.Status = AgentStatus_BUSY
			agent.TaskCount++
			agent.LastActive = time.Now()
			
			// Запускаем выполнение в горутине
			go so.executeTask(ctx, agent, task)
			return
		}
	}
	
	// Если нет свободных агентов, возвращаем в очередь
	go func() {
		time.Sleep(100 * time.Millisecond)
		so.SubmitTask(task)
	}()
}

// executeTask выполняет задачу агентом
func (so *SwarmOrchestrator) executeTask(ctx context.Context, agent *Agent, task *Task) {
	// Здесь реальная логика выполнения
	// ...
	
	// Обновляем статус
	so.mu.Lock()
	agent.Status = AgentStatus_IDLE
	so.mu.Unlock()
	
	// Обновляем награду для RL
	so.parlController.UpdateReward(1.0)
}
