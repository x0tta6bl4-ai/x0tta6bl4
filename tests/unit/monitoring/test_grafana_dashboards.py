"""
Unit tests for Grafana Dashboard Definitions
"""

import pytest
import json
import tempfile
from pathlib import Path

try:
    from src.monitoring.grafana_dashboards import (
        GrafanaPanel,
        GrafanaDashboardBuilder,
        create_system_health_dashboard,
        create_ml_pipeline_dashboard,
        create_network_mesh_dashboard,
        create_security_dashboard,
        create_tracing_dashboard,
        export_dashboards_to_json,
        create_grafana_provisioning_config
    )
    GRAFANA_AVAILABLE = True
except ImportError:
    GRAFANA_AVAILABLE = False


@pytest.mark.skipif(not GRAFANA_AVAILABLE, reason="Grafana dashboards not available")
class TestGrafanaPanel:
    """Tests for GrafanaPanel"""
    
    def test_panel_initialization(self):
        """Test panel initialization"""
        panel = GrafanaPanel(
            title="Test Panel",
            type="graph",
            targets=[{'expr': 'test_metric', 'refId': 'A'}]
        )
        
        assert panel.title == "Test Panel"
        assert panel.type == "graph"
        assert len(panel.targets) == 1
    
    def test_panel_to_dict(self):
        """Test converting panel to dict"""
        panel = GrafanaPanel(
            title="Test Panel",
            type="timeseries",
            targets=[{'expr': 'test_metric', 'refId': 'A'}],
            options={'legend': {'showLegend': True}}
        )
        
        panel_dict = panel.to_dict()
        
        assert 'title' in panel_dict
        assert 'type' in panel_dict
        assert 'targets' in panel_dict
        assert 'options' in panel_dict


@pytest.mark.skipif(not GRAFANA_AVAILABLE, reason="Grafana dashboards not available")
class TestGrafanaDashboardBuilder:
    """Tests for GrafanaDashboardBuilder"""
    
    def test_builder_initialization(self):
        """Test dashboard builder initialization"""
        builder = GrafanaDashboardBuilder(
            title="Test Dashboard",
            uid="test_uid",
            description="Test description"
        )
        
        assert builder.title == "Test Dashboard"
        assert builder.uid == "test_uid"
        assert builder.description == "Test description"
        assert len(builder.panels) == 0
    
    def test_add_row(self):
        """Test adding a row"""
        builder = GrafanaDashboardBuilder("Test", "test")
        builder.add_row("Test Row")
        
        assert len(builder.panels) == 1
        assert builder.panels[0]['type'] == 'row'
        assert builder.panels[0]['title'] == 'Test Row'
    
    def test_add_metric_gauge(self):
        """Test adding gauge panel"""
        builder = GrafanaDashboardBuilder("Test", "test")
        builder.add_metric_gauge("CPU Usage", "cpu_usage", unit="percent")
        
        assert len(builder.panels) == 1
        assert builder.panels[0]['type'] == 'gauge'
        assert builder.panels[0]['title'] == 'CPU Usage'
    
    def test_add_time_series(self):
        """Test adding time series panel"""
        builder = GrafanaDashboardBuilder("Test", "test")
        builder.add_time_series(
            "Network I/O",
            [{'expr': 'network_bytes', 'refId': 'A'}]
        )
        
        assert len(builder.panels) == 1
        assert builder.panels[0]['type'] == 'timeseries'
    
    def test_add_stat_panel(self):
        """Test adding stat panel"""
        builder = GrafanaDashboardBuilder("Test", "test")
        builder.add_stat_panel("Active Nodes", "node_count", decimals=0)
        
        assert len(builder.panels) == 1
        assert builder.panels[0]['type'] == 'stat'
    
    def test_add_heatmap(self):
        """Test adding heatmap panel"""
        builder = GrafanaDashboardBuilder("Test", "test")
        builder.add_heatmap("Latency Heatmap", "latency_histogram")
        
        assert len(builder.panels) == 1
        assert builder.panels[0]['type'] == 'heatmap'
    
    def test_build_dashboard(self):
        """Test building dashboard"""
        builder = GrafanaDashboardBuilder("Test Dashboard", "test_uid")
        builder.add_row("Test Row")
        builder.add_stat_panel("Test Stat", "test_metric")
        
        dashboard = builder.build()
        
        assert dashboard['title'] == 'Test Dashboard'
        assert dashboard['uid'] == 'test_uid'
        assert 'panels' in dashboard
        assert len(dashboard['panels']) == 2
        assert dashboard['refresh'] == '30s'
    
    def test_builder_chainable(self):
        """Test that builder methods are chainable"""
        dashboard = (GrafanaDashboardBuilder("Test", "test")
            .add_row("Row 1")
            .add_stat_panel("Stat 1", "metric1")
            .add_row("Row 2")
            .add_metric_gauge("Gauge 1", "metric2")
            .build())
        
        assert len(dashboard['panels']) == 4


@pytest.mark.skipif(not GRAFANA_AVAILABLE, reason="Grafana dashboards not available")
class TestDashboardCreation:
    """Tests for dashboard creation functions"""
    
    def test_create_system_health_dashboard(self):
        """Test system health dashboard creation"""
        dashboard = create_system_health_dashboard()
        
        assert dashboard['title'] == 'x0tta6bl4 System Health'
        assert dashboard['uid'] == 'system_health'
        assert len(dashboard['panels']) > 0
    
    def test_create_ml_pipeline_dashboard(self):
        """Test ML pipeline dashboard creation"""
        dashboard = create_ml_pipeline_dashboard()
        
        assert dashboard['title'] == 'x0tta6bl4 ML Pipeline'
        assert dashboard['uid'] == 'ml_pipeline'
        assert len(dashboard['panels']) > 0
    
    def test_create_network_mesh_dashboard(self):
        """Test network mesh dashboard creation"""
        dashboard = create_network_mesh_dashboard()
        
        assert dashboard['title'] == 'x0tta6bl4 Network & Mesh'
        assert dashboard['uid'] == 'network_mesh'
        assert len(dashboard['panels']) > 0
    
    def test_create_security_dashboard(self):
        """Test security dashboard creation"""
        dashboard = create_security_dashboard()
        
        assert dashboard['title'] == 'x0tta6bl4 Security & Zero Trust'
        assert dashboard['uid'] == 'security_zerotrust'
        assert len(dashboard['panels']) > 0
    
    def test_create_tracing_dashboard(self):
        """Test tracing dashboard creation"""
        dashboard = create_tracing_dashboard()
        
        assert dashboard['title'] == 'x0tta6bl4 Distributed Tracing'
        assert dashboard['uid'] == 'distributed_tracing'
        assert len(dashboard['panels']) > 0


@pytest.mark.skipif(not GRAFANA_AVAILABLE, reason="Grafana dashboards not available")
class TestDashboardExport:
    """Tests for dashboard export"""
    
    def test_export_dashboards_to_json(self):
        """Test exporting dashboards to JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            success = export_dashboards_to_json(output_dir)
            
            assert success == True
            
            # Check files were created
            expected_files = [
                'system_health.json',
                'ml_pipeline.json',
                'network_mesh.json',
                'security_zerotrust.json',
                'distributed_tracing.json'
            ]
            
            for filename in expected_files:
                filepath = output_dir / filename
                assert filepath.exists(), f"File {filename} not created"
                
                # Verify JSON structure
                with open(filepath, 'r') as f:
                    data = json.load(f)
                    assert 'dashboard' in data
                    assert 'title' in data['dashboard']
                    assert 'panels' in data['dashboard']
    
    def test_export_dashboards_invalid_path(self):
        """Test export to invalid path"""
        output_dir = Path("/root/invalid_path_that_should_fail_xyz")
        success = export_dashboards_to_json(output_dir)
        
        # Should return False on permission error


@pytest.mark.skipif(not GRAFANA_AVAILABLE, reason="Grafana dashboards not available")
class TestGrafanaProvisioning:
    """Tests for Grafana provisioning configuration"""
    
    def test_create_provisioning_config(self):
        """Test provisioning config creation"""
        config = create_grafana_provisioning_config()
        
        assert 'apiVersion' in config
        assert config['apiVersion'] == 1
        assert 'providers' in config
        assert len(config['providers']) > 0
    
    def test_provisioning_config_custom_datasource(self):
        """Test provisioning config with custom datasource"""
        custom_url = "http://custom-prometheus:9090"
        config = create_grafana_provisioning_config(datasource_url=custom_url)
        
        assert 'providers' in config
        assert config['apiVersion'] == 1


@pytest.mark.skipif(not GRAFANA_AVAILABLE, reason="Grafana dashboards not available")
class TestDashboardMetrics:
    """Tests for dashboard metrics"""
    
    def test_dashboard_has_valid_metrics(self):
        """Test that all dashboards reference valid metrics"""
        dashboards = [
            create_system_health_dashboard(),
            create_ml_pipeline_dashboard(),
            create_network_mesh_dashboard(),
            create_security_dashboard(),
            create_tracing_dashboard()
        ]
        
        for dashboard in dashboards:
            # Each dashboard should have panels with targets
            assert 'panels' in dashboard
            assert len(dashboard['panels']) > 0
            
            # At least one panel should have targets
            has_targets = False
            for panel in dashboard['panels']:
                if 'targets' in panel and panel['targets']:
                    has_targets = True
                    break
            
            assert has_targets, f"Dashboard {dashboard['title']} has no targets"
    
    def test_dashboard_panel_targets_format(self):
        """Test that panel targets are properly formatted"""
        dashboard = create_system_health_dashboard()
        
        for panel in dashboard['panels']:
            if 'targets' in panel:
                for target in panel['targets']:
                    if 'expr' in target:  # Prometheus target
                        assert isinstance(target['expr'], str)
                        assert len(target['expr']) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
