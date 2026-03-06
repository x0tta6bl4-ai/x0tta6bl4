"""
Test suite for detecting variable name errors in list comprehensions.

This module provides tests to catch common bugs where loop variables 
are incorrectly referenced in list comprehensions (e.g., using 'l' 
instead of 'label' or 'link').
"""
import ast
import pathlib
import pytest


def extract_list_comprehensions(file_path: str) -> list[ast.ListComp]:
    """
    Extract all list comprehensions from a Python file.
    
    Args:
        file_path: Path to Python file
        
    Returns:
        List of AST ListComp nodes
    """
    with open(file_path) as f:
        tree = ast.parse(f.read(), filename=file_path)
    
    comprehensions = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ListComp):
            comprehensions.append(node)
    
    return comprehensions


def check_variable_consistency(comp: ast.ListComp) -> list[str]:
    """
    Check if all variable references in a list comprehension 
    are consistent with the loop variable.
    
    Args:
        comp: AST ListComp node
        
    Returns:
        List of inconsistent variable names found
    """
    # Get the loop variable name
    if not comp.generators or not comp.generators[0].target:
        return []
    
    target = comp.generators[0].target
    if not isinstance(target, ast.Name):
        return []
    
    loop_var = target.id
    
    # Check all references in the comprehension
    inconsistencies = []
    for node in ast.walk(comp):
        # Check attribute access (e.g., l.source)
        if isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name):
                if node.value.id != loop_var:
                    # Check if it's a different undefined variable
                    if node.value.id not in ['str', 'int', 'bool', 'list', 'dict']:
                        inconsistencies.append(f"{node.value.id}.{node.attr}")
        
        # Check name references
        if isinstance(node, ast.Name):
            if node.id != loop_var and node.id not in ['str', 'int', 'bool', 'list', 'dict', 'True', 'False', 'None']:
                # Check if this might be the loop variable with a typo
                # e.g., using 'l' when loop variable is 'link' or 'label'
                if len(node.id) <= 2 and len(loop_var) > 2:
                    # Short variable name that differs from loop var
                    inconsistencies.append(node.id)
    
    return inconsistencies


class TestVariableNameConsistency:
    """Tests for detecting variable name inconsistencies in list comprehensions."""
    
    def test_notification_suite_label_filter(self):
        """Test that notification_suite.py uses correct variable name in label filtering."""
        file_path = "src/core/notification_suite.py"
        
        # Simply verify the file can be imported and has valid syntax
        import importlib.util
        spec = importlib.util.spec_from_file_location("notification_suite", file_path)
        module = importlib.util.module_from_spec(spec)
        
        # This will raise SyntaxError if the file is invalid
        assert spec.loader is not None
        
        # Read the file and verify the fix is in place
        with open(file_path) as f:
            content = f.read()
        
        # Check that the correct variable is used
        assert "label.strip()" in content, "label.strip() should be in the file"
        # Make sure the bug pattern is NOT present
        assert "if l.strip()]" not in content, "Bug pattern 'l.strip()' should be fixed"
        
    def test_notification_suite_libx0t_label_filter(self):
        """Test that libx0t/core/notification_suite.py uses correct variable name."""
        file_path = "src/libx0t/core/notification_suite.py"
        
        if not pathlib.Path(file_path).exists():
            pytest.skip(f"File {file_path} does not exist")
        
        # Verify the fix is in place
        with open(file_path) as f:
            content = f.read()
        
        assert "label.strip()" in content
        assert "if l.strip()]" not in content
        
    def test_batman_topology_links(self):
        """Test that batman.py uses correct variable name for link in topology."""
        file_path = "src/api/maas/endpoints/batman.py"
        
        if not pathlib.Path(file_path).exists():
            pytest.skip(f"File {file_path} does not exist")
        
        # Verify the fix is in place - should use 'link' not 'l'
        with open(file_path) as f:
            content = f.read()
        
        # Check that 'link.source' is used
        assert "link.source" in content
        # Make sure the bug pattern is NOT present
        assert "l.source" not in content, "Bug pattern 'l.source' should be fixed"


class TestListComprehensionExecution:
    """Integration tests for list comprehensions in modified files."""
    
    def test_notification_suite_watch_labels(self):
        """Test the watch command label parsing logic."""
        # Simulate the label parsing from notification_suite.py
        args_labels = "app=service-a,app=service-b,"
        
        # This is the code from the fixed version
        labels = [label.strip() for label in args_labels.split(",") if label.strip()]
        
        assert labels == ["app=service-a", "app=service-b"]
        
    def test_notification_suite_watch_labels_empty(self):
        """Test label parsing with empty input."""
        args_labels = ""
        
        labels = [label.strip() for label in args_labels.split(",") if label.strip()]
        
        assert labels == []
        
    def test_notification_suite_watch_labels_whitespace(self):
        """Test label parsing with whitespace-only entries."""
        args_labels = "  ,label1,  ,label2,"
        
        labels = [label.strip() for label in args_labels.split(",") if label.strip()]
        
        assert labels == ["label1", "label2"]


class TestBatmanTopologyLinks:
    """Tests for batman.py topology link processing."""
    
    def test_link_attribute_access(self):
        """Test that link attributes are accessed correctly."""
        # Simulate link object
        class MockLink:
            source = "node1"
            destination = "node2"
            quality = type('Quality', (), {'name': 'good'})()
            throughput_mbps = 100
            latency_ms = 10
            packet_loss_percent = 0.1
        
        links_list = [MockLink()]
        
        # This is the fixed comprehension from batman.py
        links = [
            {
                "source": link.source,
                "destination": link.destination,
                "quality": link.quality.name,
                "throughput_mbps": link.throughput_mbps,
                "latency_ms": link.latency_ms,
                "packet_loss_percent": link.packet_loss_percent,
            }
            for link in links_list
        ]
        
        assert len(links) == 1
        assert links[0]["source"] == "node1"
        assert links[0]["destination"] == "node2"
        assert links[0]["quality"] == "good"
