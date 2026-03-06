package test

import (
	"math"
	"testing"

	"x0tta6bl4/ml/federated"
)

func TestDPGradientClipping(t *testing.T) {
	// Инициализация движка с жестким порогом клиппинга
	engine := &federated.GaussianDPNoiseEngine{
		Sigma:    0.0, // Выключаем шум для точной проверки клиппинга
		ClipNorm: 2.0, // Ограничение L2-нормы
	}

	// Тест 1: Градиенты внутри нормы (не должны усекаться)
	gradNormal := []float32{1.0, 1.0} // L2-норма = sqrt(2) = ~1.41
	noisy1, _ := engine.ApplyNoise(gradNormal)

	if noisy1[0] != 1.0 || noisy1[1] != 1.0 {
		t.Errorf("Gradients within ClipNorm were altered: %v", noisy1)
	}

	// Тест 2: Градиенты превышают норму (должны быть усечены)
	gradHuge := []float32{3.0, 4.0} // L2-норма = sqrt(9 + 16) = 5.0
	noisy2, _ := engine.ApplyNoise(gradHuge)

	// Ожидаемый коэффициент: ClipNorm / L2Norm = 2.0 / 5.0 = 0.4
	// Ожидаемые значения: 3.0 * 0.4 = 1.2, 4.0 * 0.4 = 1.6
	if math.Abs(float64(noisy2[0]-1.2)) > 0.001 || math.Abs(float64(noisy2[1]-1.6)) > 0.001 {
		t.Errorf("Gradients exceeding ClipNorm were not properly clipped: %v", noisy2)
	}
}
