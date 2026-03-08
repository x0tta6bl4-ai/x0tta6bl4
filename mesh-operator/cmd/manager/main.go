package main

import (
	"flag"
	"os"

	"k8s.io/apimachinery/pkg/runtime"
	utilruntime "k8s.io/apimachinery/pkg/util/runtime"
	clientgoscheme "k8s.io/client-go/kubernetes/scheme"
	ctrl "sigs.k8s.io/controller-runtime"
	"sigs.k8s.io/controller-runtime/pkg/healthz"
	"sigs.k8s.io/controller-runtime/pkg/log/zap"
	metricsserver "sigs.k8s.io/controller-runtime/pkg/metrics/server"
	webhookserver "sigs.k8s.io/controller-runtime/pkg/webhook"

	meshv1alpha1 "github.com/x0tta6bl4/mesh-operator/api/v1alpha1"
	"github.com/x0tta6bl4/mesh-operator/controllers"
)

func main() {
	scheme := runtime.NewScheme()
	utilruntime.Must(clientgoscheme.AddToScheme(scheme))
	utilruntime.Must(meshv1alpha1.AddToScheme(scheme))

	var (
		leaderElect             bool
		leaderElectionNamespace string
		metricsAddr             string
		healthProbeAddr         string
		enableWebhooks          bool
		webhookPort             int
		webhookCertDir          string
	)

	flag.BoolVar(&leaderElect, "leader-elect", true, "Enable leader election for controller manager")
	flag.StringVar(&leaderElectionNamespace, "leader-elect-namespace", "", "Namespace for leader election leases")
	flag.StringVar(&metricsAddr, "metrics-bind-address", ":9090", "Address where the metrics endpoint binds")
	flag.StringVar(&healthProbeAddr, "health-probe-bind-address", ":8081", "Address where the health probes bind")
	flag.BoolVar(&enableWebhooks, "enable-webhooks", false, "Enable admission webhooks for MeshCluster")
	flag.IntVar(&webhookPort, "webhook-port", 9443, "Webhook server port")
	flag.StringVar(&webhookCertDir, "webhook-cert-dir", "/tmp/k8s-webhook-server/serving-certs", "Directory containing webhook TLS certs")

	zapOpts := zap.Options{Development: false}
	zapOpts.BindFlags(flag.CommandLine)
	flag.Parse()

	ctrl.SetLogger(zap.New(zap.UseFlagOptions(&zapOpts)))

	options := ctrl.Options{
		Scheme: scheme,
		Metrics: metricsserver.Options{
			BindAddress: metricsAddr,
		},
		HealthProbeBindAddress:  healthProbeAddr,
		LeaderElection:          leaderElect,
		LeaderElectionID:        "mesh-operator.x0tta6bl4.io",
		LeaderElectionNamespace: leaderElectionNamespace,
	}
	if enableWebhooks {
		options.WebhookServer = webhookserver.NewServer(webhookserver.Options{
			Port:    webhookPort,
			CertDir: webhookCertDir,
		})
	}

	manager, err := ctrl.NewManager(ctrl.GetConfigOrDie(), options)
	if err != nil {
		ctrl.Log.Error(err, "unable to create manager")
		os.Exit(1)
	}

	reconciler := &controllers.MeshClusterReconciler{
		Client:   manager.GetClient(),
		Scheme:   manager.GetScheme(),
		Recorder: manager.GetEventRecorderFor("meshcluster-controller"),
	}
	if err := reconciler.SetupWithManager(manager); err != nil {
		ctrl.Log.Error(err, "unable to create controller", "controller", "MeshCluster")
		os.Exit(1)
	}
	if enableWebhooks {
		if err := (&meshv1alpha1.MeshCluster{}).SetupWebhookWithManager(manager); err != nil {
			ctrl.Log.Error(err, "unable to create webhook", "webhook", "MeshCluster")
			os.Exit(1)
		}
	}

	if err := manager.AddHealthzCheck("healthz", healthz.Ping); err != nil {
		ctrl.Log.Error(err, "unable to set up health check")
		os.Exit(1)
	}
	if err := manager.AddReadyzCheck("readyz", healthz.Ping); err != nil {
		ctrl.Log.Error(err, "unable to set up ready check")
		os.Exit(1)
	}

	ctrl.Log.Info("starting mesh-operator manager")
	if err := manager.Start(ctrl.SetupSignalHandler()); err != nil {
		ctrl.Log.Error(err, "problem running manager")
		os.Exit(1)
	}
}
