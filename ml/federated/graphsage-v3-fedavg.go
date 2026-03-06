package federated

import (
	"context"
	"errors"
	"fmt"
	"log"
	"sync"
	"time"

	metrics "x0tta6bl4/internal/metrics"
)

var (
	GlobalAccuracySimulated = metrics.NewGauge(metrics.GaugeOpts{
		Name: "federated_global_accuracy_simulated",
		Help: "GraphSAGE v3 global model accuracy (Simulated)",
	})
	RoundDuration = metrics.NewHistogram(metrics.HistogramOpts{
		Name:    "federated_round_duration_seconds",
		Help:    "Duration of a single FedAvg round across 3 clusters",
		Buckets: []float64{0.1, 0.5, 1, 5, 10, 30, 60},
	})
	PrivacyBudgetConsumedSimulated = metrics.NewGauge(metrics.GaugeOpts{
		Name: "federated_dp_privacy_budget_consumed_simulated",
		Help: "Simulated Differential Privacy budget consumed (Epsilon)",
	})
	FailedRounds = metrics.NewCounter(metrics.CounterOpts{
		Name: "federated_failed_rounds_total",
		Help: "Total number of failed federated learning rounds",
	})
)

// PrivacyEngine — абстракция для наложения шума и контроля бюджета приватности.
type PrivacyEngine interface {
	ApplyNoise(gradients []float32) ([]float32, error)
	GetConsumedBudget() float64
	IsSimulated() bool
}

// DPMechanism описывает будущий backend для реальной DP-библиотеки.
type DPMechanism interface {
	Apply(gradients []float32, epsilon float64, delta float64) ([]float32, float64, error)
}

type FederationConfig struct {
	MaxEpsilon     float64
	Delta          float64
	Sigma          float64
	RequiredPeers  int
	GradientLength int
}

type FedAvgServer struct {
	mu             sync.Mutex
	config         FederationConfig
	privacyEngine  PrivacyEngine
	localGradients map[string][]float32
	globalModel    []float32
	activePeers    map[string]bool
	failedRounds   uint64
}

func NewFedAvgServer(cfg FederationConfig, initialModel []float32, engine PrivacyEngine) *FedAvgServer {
	if engine == nil {
		engine = &NoPrivacyEngine{}
	}
	return &FedAvgServer{
		config:         cfg,
		privacyEngine:  engine,
		globalModel:    cloneGradients(initialModel),
		localGradients: make(map[string][]float32),
		activePeers:    make(map[string]bool),
	}
}

// RegisterPeer авторизует участника для текущего раунда.
func (s *FedAvgServer) RegisterPeer(peerID string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.activePeers[peerID] = true
}

// ReceiveUpdate обрабатывает входящие градиенты с применением выбранного PrivacyEngine.
func (s *FedAvgServer) ReceiveUpdate(ctx context.Context, peerID string, gradients []float32) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if err := ctx.Err(); err != nil {
		s.recordRoundFailure()
		return err
	}
	if !s.activePeers[peerID] {
		s.recordRoundFailure()
		return fmt.Errorf("unauthorized peer: %s", peerID)
	}
	if len(gradients) != s.config.GradientLength {
		s.recordRoundFailure()
		return fmt.Errorf("malformed update: expected length %d, got %d", s.config.GradientLength, len(gradients))
	}
	if _, exists := s.localGradients[peerID]; exists {
		s.recordRoundFailure()
		return fmt.Errorf("duplicate update from peer: %s", peerID)
	}

	// Наложение шума через PrivacyEngine (реальный или симулированный)
	noisyGradients, err := s.privacyEngine.ApplyNoise(gradients)
	if err != nil {
		s.recordRoundFailure()
		return fmt.Errorf("privacy engine error: %w", err)
	}

	s.localGradients[peerID] = noisyGradients

	if len(s.localGradients) >= s.config.RequiredPeers {
		return s.aggregate()
	}
	return nil
}

func (s *FedAvgServer) aggregate() error {
	start := time.Now()
	numGradients := len(s.localGradients)
	if numGradients == 0 {
		s.recordRoundFailure()
		return errors.New("aggregate called without gradients")
	}
	for i := 0; i < s.config.GradientLength; i++ {
		var sum float32
		for _, grad := range s.localGradients {
			sum += grad[i]
		}
		s.globalModel[i] = sum / float32(numGradients)
	}

	// Обновление метрик бюджета приватности
	budget := s.privacyEngine.GetConsumedBudget()
	if s.privacyEngine.IsSimulated() {
		PrivacyBudgetConsumedSimulated.Set(budget)
	}

	if budget > s.config.MaxEpsilon {
		log.Printf("[SECURITY] Privacy budget exceeded: %f", budget)
	}

	// Имитация улучшения точности глобальной модели
	newAcc := 0.94 + (budget * 0.01) // SIMULATED
	GlobalAccuracySimulated.Set(newAcc)

	s.localGradients = make(map[string][]float32)
	RoundDuration.Observe(time.Since(start).Seconds())
	return nil
}

func (s *FedAvgServer) GetGlobalModel() []float32 {
	s.mu.Lock()
	defer s.mu.Unlock()
	return cloneGradients(s.globalModel)
}

func (s *FedAvgServer) GetFailedRounds() uint64 {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.failedRounds
}

func (s *FedAvgServer) recordRoundFailure() {
	s.failedRounds++
	FailedRounds.Inc()
}

// SimulatedDPNoiseEngine — реализация симулированного шума для POC.
type SimulatedDPNoiseEngine struct {
	Sigma   float64
	Current float64
}

func (e *SimulatedDPNoiseEngine) ApplyNoise(gradients []float32) ([]float32, error) {
	if e.Sigma < 0 {
		return nil, errors.New("invalid simulated DP config: sigma must be >= 0 (SIMULATED)")
	}

	noisy := make([]float32, len(gradients))
	for i, v := range gradients {
		// Deterministic pseudo-noise keeps POC validation reproducible.
		eNoise := float32((i%7)-3) / 5000.0 * float32(e.Sigma)
		noisy[i] = v + eNoise
	}
	e.Current += 0.05 // Имитация расхода бюджета
	return noisy, nil
}

func (e *SimulatedDPNoiseEngine) GetConsumedBudget() float64 { return e.Current }
func (e *SimulatedDPNoiseEngine) IsSimulated() bool          { return true }

// NoPrivacyEngine — реализация без шума для тестирования и отладки.
type NoPrivacyEngine struct{}

func (e *NoPrivacyEngine) ApplyNoise(gradients []float32) ([]float32, error) {
	return cloneGradients(gradients), nil
}
func (e *NoPrivacyEngine) GetConsumedBudget() float64 { return 0.0 }
func (e *NoPrivacyEngine) IsSimulated() bool          { return false }

// FutureRealDPEngine — testable scaffold для будущей интеграции реальной DP библиотеки.
type FutureRealDPEngine struct {
	Mechanism   DPMechanism
	EpsilonStep float64
	Delta       float64
	Consumed    float64
}

func NewFutureRealDPEngine(mechanism DPMechanism, epsilonStep, delta float64) *FutureRealDPEngine {
	return &FutureRealDPEngine{
		Mechanism:   mechanism,
		EpsilonStep: epsilonStep,
		Delta:       delta,
	}
}

func (e *FutureRealDPEngine) ApplyNoise(gradients []float32) ([]float32, error) {
	if e.Mechanism == nil {
		return nil, errors.New("FutureRealDPEngine mechanism not configured (NOT VERIFIED)")
	}
	if e.EpsilonStep <= 0 {
		return nil, errors.New("FutureRealDPEngine epsilon step must be > 0")
	}

	noisy, consumed, err := e.Mechanism.Apply(cloneGradients(gradients), e.EpsilonStep, e.Delta)
	if err != nil {
		return nil, fmt.Errorf("FutureRealDPEngine mechanism failed: %w", err)
	}
	if len(noisy) != len(gradients) {
		return nil, fmt.Errorf("invalid FutureRealDPEngine response: expected %d gradients, got %d", len(gradients), len(noisy))
	}
	if consumed < 0 {
		return nil, errors.New("invalid FutureRealDPEngine response: negative consumed budget")
	}

	e.Consumed += consumed
	return noisy, nil
}

func (e *FutureRealDPEngine) GetConsumedBudget() float64 { return e.Consumed }
func (e *FutureRealDPEngine) IsSimulated() bool          { return false }

func cloneGradients(src []float32) []float32 {
	dst := make([]float32, len(src))
	copy(dst, src)
	return dst
}
