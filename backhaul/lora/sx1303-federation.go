package lora

import (
	"fmt"
	"log"
	"time"

	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	GatewayHealthStatus = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "lora_gateway_health_status",
		Help: "LoRaWAN Gateway operational status (1=OK, 0=FAIL)",
	})
	LastRSSI = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "lora_last_packet_rssi_dbm",
		Help: "RSSI of the last received LoRa packet in dBm",
	})
)

// TelemetrySource — расширенный интерфейс для SX1303.
type TelemetrySource interface {
	GetSignalMetrics() (rssi float64, snr float64, err error)
	CheckHardwareHealth() error
	IsSimulated() bool
}

type Router struct {
	ThresholdKm float64
	Telemetry   TelemetrySource
}

func NewRouter(threshold float64, t TelemetrySource) *Router {
	return &Router{ThresholdKm: threshold, Telemetry: t}
}

// DecideRoute теперь учитывает здоровье шлюза и пороги сигнала.
func (r *Router) DecideRoute(distanceKm float64) BackhaulType {
	RouteDecisionsTotal.Inc()

	// 1. Проверка здоровья (Critical Path)
	if err := r.Telemetry.CheckHardwareHealth(); err != nil {
		log.Printf("[Backhaul] CRITICAL: Gateway failure: %v. Falling back to Satellite.", err)
		GatewayHealthStatus.Set(0)
		return Satellite
	}
	GatewayHealthStatus.Set(1)

	// 2. Получение метрик
	rssi, snr, err := r.Telemetry.GetSignalMetrics()
	if err != nil {
		log.Printf("[Backhaul] Telemetry error: %v. Using distance fallback.", err)
		if distanceKm < r.ThresholdKm { return LoRa }
		return Satellite
	}

	LastRSSI.Set(rssi)

	// 3. Детерминированная логика выбора
	if distanceKm < 2.0 && rssi > -80.0 {
		return FiveG
	}
	// Для LoRa важен не только RSSI, но и SNR (порог для SX1303 обычно -15dB)
	if distanceKm < r.ThresholdKm && rssi > -118.0 && snr > -12.0 {
		return LoRa
	}
	
	return Satellite
}

// RealSX1303Telemetry — каркас для интеграции с libloragw.
type RealSX1303Telemetry struct {
	DevicePath string
}

func (s *RealSX1303Telemetry) GetSignalMetrics() (float64, float64, error) {
	// В будущем здесь: вызвать CGO-биндинг lgw_receive()
	return 0, 0, fmt.Errorf("SX1303 HAL (libloragw) not linked (NOT VERIFIED)")
}

func (s *RealSX1303Telemetry) CheckHardwareHealth() error {
	// В будущем здесь: проверка SPI соединения и состояния концентратора
	return fmt.Errorf("Hardware health check not implemented (NOT VERIFIED)")
}

func (s *RealSX1303Telemetry) IsSimulated() bool { return false }
