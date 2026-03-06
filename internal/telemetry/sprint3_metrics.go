package telemetry

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	CrossClusterLatency = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "federation_cross_cluster_latency_seconds",
		Help:    "Cross-cluster latency p99",
		Buckets: []float64{0.05, 0.1, 0.2, 0.5, 1.0},
	})
	DaoProposalApprovedTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "dao_proposal_approved_total",
		Help: "Total DAO proposals approved",
	})
	TopologyAttestationsTotal = promauto.NewCounter(prometheus.CounterOpts{
		Name: "topology_attestations_total",
		Help: "Total on-chain topology attestations",
	})
	SLOErrorBudgetRemaining = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "slo_error_budget_remaining",
		Help: "SLO Error budget remaining for the month (percentage)",
	})
	DrRecoveryTimeSeconds = promauto.NewHistogram(prometheus.HistogramOpts{
		Name:    "dr_recovery_time_seconds",
		Help:    "Disaster recovery time in seconds",
		Buckets: []float64{10, 30, 60, 120, 300},
	})
)
