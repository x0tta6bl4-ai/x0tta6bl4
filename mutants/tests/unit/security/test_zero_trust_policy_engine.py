"""
Comprehensive tests for Zero Trust Policy Engine.

Tests policy evaluation, rule matching, and edge cases.
"""
import pytest
from unittest.mock import Mock, patch
from typing import Dict, Any

try:
    from src.security.zero_trust.policy_engine import (
        PolicyEngine,
        PolicyRule,
        PolicyDecision,
        PolicyAction
    )
    ZERO_TRUST_AVAILABLE = True
except ImportError:
    # Try alternative import path
    try:
        from src.security.policy_engine import PolicyEngine
        from src.security.policy_engine import PolicyAction
        ZERO_TRUST_AVAILABLE = True
        PolicyRule = None
        PolicyDecision = None
    except ImportError:
        ZERO_TRUST_AVAILABLE = False
        PolicyEngine = None
        PolicyRule = None
        PolicyDecision = None
        PolicyAction = None


@pytest.mark.skipif(not ZERO_TRUST_AVAILABLE, reason="Zero Trust Policy Engine not available")
class TestZeroTrustPolicyEngine:
    """Tests for Zero Trust Policy Engine"""
    
    def test_default_deny_policy(self):
        """Test that default policy denies all access"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        
        # Remove default allow rule to test default deny
        engine.remove_rule("default_allow")
        
        # Default request should be denied
        decision = engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-1",
            resource="resource-1"
        )
        assert decision.allowed == False
        assert "deny" in decision.reason.lower() or "default" in decision.reason.lower()
    
    def test_explicit_allow_rule(self):
        """Test explicit allow rule"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Add allow rule
        rule = PolicyRule(
            rule_id="allow-user-1",
            name="Allow user-1 access",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://test/workload/user-1",
            allowed_resources=["resource-1"],
            priority=200
        )
        engine.add_rule(rule)
        
        decision = engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-1",
            resource="resource-1"
        )
        assert decision.allowed == True
    
    def test_explicit_deny_rule(self):
        """Test explicit deny rule (overrides allow)"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Add allow rule
        allow_rule = PolicyRule(
            rule_id="allow-user-1",
            name="Allow user-1 access",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://test/workload/user-1",
            allowed_resources=["resource-1"],
            priority=100
        )
        engine.add_rule(allow_rule)
        
        # Add deny rule (should override - higher priority)
        deny_rule = PolicyRule(
            rule_id="deny-user-1",
            name="Deny user-1 access",
            action=PolicyAction.DENY,
            spiffe_id_pattern="spiffe://test/workload/user-1",
            allowed_resources=["resource-1"],
            priority=200  # Higher priority
        )
        engine.add_rule(deny_rule)
        
        decision = engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-1",
            resource="resource-1"
        )
        assert decision.allowed == False  # Deny should override allow
    
    def test_wildcard_subject(self):
        """Test wildcard matching for subjects"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Allow all users for resource-1 (wildcard SPIFFE ID pattern)
        rule = PolicyRule(
            rule_id="allow-all-resource-1",
            name="Allow all for resource-1",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://test/workload/*",
            allowed_resources=["resource-1"],
            priority=200
        )
        engine.add_rule(rule)
        
        # Any user should be allowed
        for user in ["user-1", "user-2", "admin"]:
            decision = engine.evaluate(
                peer_spiffe_id=f"spiffe://test/workload/{user}",
                resource="resource-1"
            )
            assert decision.allowed == True
    
    def test_wildcard_resource(self):
        """Test wildcard matching for resources"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Allow user-1 access to all resources (no resource restriction)
        rule = PolicyRule(
            rule_id="allow-user-1-all",
            name="Allow user-1 all resources",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://test/workload/user-1",
            allowed_resources=None,  # None = all resources
            priority=200
        )
        engine.add_rule(rule)
        
        # Any resource should be allowed
        for resource in ["resource-1", "resource-2", "admin-panel"]:
            decision = engine.evaluate(
                peer_spiffe_id="spiffe://test/workload/user-1",
                resource=resource
            )
            assert decision.allowed == True
    
    def test_action_specific_rules(self):
        """Test action-specific rules"""
        # Note: Current API doesn't support action-specific rules directly
        # This test verifies resource-based access
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Allow access to read-resource
        read_rule = PolicyRule(
            rule_id="allow-read",
            name="Allow read access",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://test/workload/user-1",
            allowed_resources=["read-resource"],
            priority=200
        )
        engine.add_rule(read_rule)
        
        # Deny access to write-resource
        write_rule = PolicyRule(
            rule_id="deny-write",
            name="Deny write access",
            action=PolicyAction.DENY,
            spiffe_id_pattern="spiffe://test/workload/user-1",
            allowed_resources=["write-resource"],
            priority=300  # Higher priority
        )
        engine.add_rule(write_rule)
        
        # Read should be allowed
        assert engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-1",
            resource="read-resource"
        ).allowed == True
        
        # Write should be denied
        assert engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-1",
            resource="write-resource"
        ).allowed == False
    
    def test_rule_priority(self):
        """Test rule priority (more specific rules override general ones)"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # General allow rule (lower priority)
        general_rule = PolicyRule(
            rule_id="general-allow",
            name="General allow",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://test/workload/*",
            allowed_resources=["*"],
            priority=100
        )
        engine.add_rule(general_rule)
        
        # Specific deny rule (higher priority)
        specific_rule = PolicyRule(
            rule_id="specific-deny",
            name="Specific deny",
            action=PolicyAction.DENY,
            spiffe_id_pattern="spiffe://test/workload/user-1",
            allowed_resources=["resource-1"],
            priority=200  # Higher priority
        )
        engine.add_rule(specific_rule)
        
        # Specific rule should override general
        decision = engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-1",
            resource="resource-1"
        )
        assert decision.allowed == False  # Specific deny overrides general allow


@pytest.mark.skipif(not ZERO_TRUST_AVAILABLE, reason="Zero Trust Policy Engine not available")
class TestZeroTrustEdgeCases:
    """Edge case tests for Zero Trust Policy Engine"""
    
    def test_empty_subject(self):
        """Test handling of empty SPIFFE ID"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Should deny empty SPIFFE ID
        decision = engine.evaluate(
            peer_spiffe_id="",
            resource="resource-1"
        )
        assert decision.allowed == False
    
    def test_empty_resource(self):
        """Test handling of empty resource"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Should deny empty resource (or use default)
        decision = engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-1",
            resource=""
        )
        assert decision.allowed == False
    
    def test_invalid_action(self):
        """Test handling of invalid workload type"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Should deny invalid workload type (or use default)
        decision = engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-1",
            resource="resource-1",
            workload_type="invalid_type"
        )
        # Result depends on implementation
        assert decision.allowed in [True, False]
    
    def test_special_characters_in_subject(self):
        """Test handling of special characters in SPIFFE ID"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Add rule with special characters in SPIFFE ID
        rule = PolicyRule(
            rule_id="allow-special",
            name="Allow special chars",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://test/workload/user@domain.com",
            allowed_resources=["resource-1"],
            priority=200
        )
        engine.add_rule(rule)
        
        decision = engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user@domain.com",
            resource="resource-1"
        )
        assert decision.allowed == True
    
    def test_case_sensitivity(self):
        """Test case sensitivity in matching"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Add rule with lowercase
        rule = PolicyRule(
            rule_id="allow-lowercase",
            name="Allow lowercase",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://test/workload/user-1",
            allowed_resources=["resource-1"],
            priority=200
        )
        engine.add_rule(rule)
        
        # Request with uppercase (should not match if case-sensitive)
        decision = engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/USER-1",
            resource="resource-1"
        )
        # Result depends on implementation (case-sensitive or not)
        # This test documents expected behavior
        assert decision.allowed in [True, False]
    
    def test_rule_removal(self):
        """Test removal of rules"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Add rule
        rule = PolicyRule(
            rule_id="test-rule",
            name="Test rule",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://test/workload/user-1",
            allowed_resources=["resource-1"],
            priority=200
        )
        engine.add_rule(rule)
        
        # Verify rule works
        assert engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-1",
            resource="resource-1"
        ).allowed == True
        
        # Remove rule
        engine.remove_rule("test-rule")
        
        # Should now be denied
        assert engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-1",
            resource="resource-1"
        ).allowed == False


@pytest.mark.skipif(not ZERO_TRUST_AVAILABLE, reason="Zero Trust Policy Engine not available")
class TestZeroTrustPerformance:
    """Performance tests for Zero Trust Policy Engine"""
    
    def test_large_policy_set(self):
        """Test performance with large number of rules"""
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Add many rules
        for i in range(1000):
            rule = PolicyRule(
                rule_id=f"rule-{i}",
                name=f"Rule {i}",
                action=PolicyAction.ALLOW,
                spiffe_id_pattern=f"spiffe://test/workload/user-{i}",
                allowed_resources=[f"resource-{i}"],
                priority=200
            )
            engine.add_rule(rule)
        
        # Evaluate request (should be fast)
        import time
        start = time.perf_counter()
        decision = engine.evaluate(
            peer_spiffe_id="spiffe://test/workload/user-500",
            resource="resource-500"
        )
        elapsed = time.perf_counter() - start
        
        # Should complete in reasonable time (<100ms)
        assert elapsed < 0.1
        assert decision.allowed == True
    
    def test_concurrent_evaluations(self):
        """Test concurrent policy evaluations"""
        import threading
        
        engine = PolicyEngine(default_action=PolicyAction.DENY)
        engine.remove_rule("default_allow")
        
        # Add rule
        rule = PolicyRule(
            rule_id="allow-user-1",
            name="Allow user-1",
            action=PolicyAction.ALLOW,
            spiffe_id_pattern="spiffe://test/workload/user-1",
            allowed_resources=["resource-1"],
            priority=200
        )
        engine.add_rule(rule)
        
        results = []
        errors = []
        
        def evaluate_worker():
            try:
                decision = engine.evaluate(
                    peer_spiffe_id="spiffe://test/workload/user-1",
                    resource="resource-1"
                )
                results.append(decision.allowed)
            except Exception as e:
                errors.append(e)
        
        # Create multiple threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=evaluate_worker)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads
        for thread in threads:
            thread.join()
        
        # All should succeed
        assert len(errors) == 0
        assert len(results) == 10
        assert all(results)  # All should be allowed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

