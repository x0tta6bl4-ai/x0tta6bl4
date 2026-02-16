"""
Tests for Policy Engine module.
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from src.security.policy_engine import (Attribute, AttributeType,
                                        PolicyCondition, PolicyEffect,
                                        PolicyPriority)


class TestPolicyEffect:
    """Tests for PolicyEffect enum."""

    def test_allow_effect(self):
        """Test ALLOW effect value."""
        assert PolicyEffect.ALLOW.value == "allow"

    def test_deny_effect(self):
        """Test DENY effect value."""
        assert PolicyEffect.DENY.value == "deny"

    def test_audit_effect(self):
        """Test AUDIT effect value."""
        assert PolicyEffect.AUDIT.value == "audit"

    def test_challenge_effect(self):
        """Test CHALLENGE effect value."""
        assert PolicyEffect.CHALLENGE.value == "challenge"

    def test_all_effects_defined(self):
        """Test all effects are defined."""
        effects = list(PolicyEffect)
        assert len(effects) == 4


class TestPolicyPriority:
    """Tests for PolicyPriority enum."""

    def test_priority_order(self):
        """Test priority ordering (lower = higher priority)."""
        assert PolicyPriority.EMERGENCY.value < PolicyPriority.CRITICAL.value
        assert PolicyPriority.CRITICAL.value < PolicyPriority.HIGH.value
        assert PolicyPriority.HIGH.value < PolicyPriority.NORMAL.value
        assert PolicyPriority.NORMAL.value < PolicyPriority.LOW.value
        assert PolicyPriority.LOW.value < PolicyPriority.DEFAULT.value

    def test_emergency_priority(self):
        """Test EMERGENCY has highest priority (lowest value)."""
        assert PolicyPriority.EMERGENCY.value == 0

    def test_default_priority(self):
        """Test DEFAULT has lowest priority."""
        assert PolicyPriority.DEFAULT.value == 50

    def test_all_priorities_defined(self):
        """Test all priorities are defined."""
        priorities = list(PolicyPriority)
        assert len(priorities) == 6


class TestAttributeType:
    """Tests for AttributeType enum."""

    def test_subject_type(self):
        """Test SUBJECT type value."""
        assert AttributeType.SUBJECT.value == "subject"

    def test_resource_type(self):
        """Test RESOURCE type value."""
        assert AttributeType.RESOURCE.value == "resource"

    def test_action_type(self):
        """Test ACTION type value."""
        assert AttributeType.ACTION.value == "action"

    def test_environment_type(self):
        """Test ENVIRONMENT type value."""
        assert AttributeType.ENVIRONMENT.value == "environment"

    def test_all_types_defined(self):
        """Test all types are defined."""
        types = list(AttributeType)
        assert len(types) == 4


class TestAttribute:
    """Tests for Attribute dataclass."""

    def test_attribute_creation(self):
        """Test Attribute creation."""
        attr = Attribute(type=AttributeType.SUBJECT, name="user_id", value="user123")

        assert attr.type == AttributeType.SUBJECT
        assert attr.name == "user_id"
        assert attr.value == "user123"

    def test_matches_exact_value(self):
        """Test matches with exact value."""
        attr = Attribute(type=AttributeType.SUBJECT, name="role", value="admin")

        assert attr.matches("admin") is True
        assert attr.matches("user") is False

    def test_matches_wildcard(self):
        """Test matches with wildcard pattern."""
        attr = Attribute(type=AttributeType.SUBJECT, name="role", value="any-value")

        assert attr.matches("*") is True

    def test_matches_regex_pattern(self):
        """Test matches with regex pattern."""
        attr = Attribute(
            type=AttributeType.SUBJECT, name="email", value="user@example.com"
        )

        assert attr.matches("regex:.*@example\\.com") is True
        assert attr.matches("regex:.*@other\\.com") is False

    def test_matches_list(self):
        """Test matches with list of values."""
        attr = Attribute(type=AttributeType.ACTION, name="method", value="GET")

        assert attr.matches(["GET", "POST", "PUT"]) is True
        assert attr.matches(["DELETE", "PATCH"]) is False

    def test_matches_gt_operator(self):
        """Test matches with greater than operator."""
        attr = Attribute(type=AttributeType.ENVIRONMENT, name="risk_score", value=75)

        assert attr.matches({"gt": 50}) is True
        assert attr.matches({"gt": 80}) is False

    def test_matches_lt_operator(self):
        """Test matches with less than operator."""
        attr = Attribute(type=AttributeType.ENVIRONMENT, name="latency", value=50)

        assert attr.matches({"lt": 100}) is True
        assert attr.matches({"lt": 25}) is False

    def test_matches_gte_operator(self):
        """Test matches with greater than or equal operator."""
        attr = Attribute(type=AttributeType.ENVIRONMENT, name="trust_level", value=5)

        assert attr.matches({"gte": 5}) is True
        assert attr.matches({"gte": 6}) is False

    def test_matches_lte_operator(self):
        """Test matches with less than or equal operator."""
        attr = Attribute(type=AttributeType.ENVIRONMENT, name="connections", value=10)

        assert attr.matches({"lte": 10}) is True
        assert attr.matches({"lte": 5}) is False

    def test_matches_in_operator(self):
        """Test matches with in operator."""
        attr = Attribute(type=AttributeType.RESOURCE, name="region", value="us-east-1")

        assert attr.matches({"in": ["us-east-1", "us-west-2"]}) is True
        assert attr.matches({"in": ["eu-west-1", "ap-south-1"]}) is False

    def test_matches_not_in_operator(self):
        """Test matches with not_in operator."""
        attr = Attribute(type=AttributeType.RESOURCE, name="status", value="active")

        assert attr.matches({"not_in": ["blocked", "suspended"]}) is True
        assert attr.matches({"not_in": ["active", "pending"]}) is False


class TestPolicyCondition:
    """Tests for PolicyCondition dataclass."""

    def test_condition_creation(self):
        """Test PolicyCondition creation."""
        condition = PolicyCondition(
            attribute_type=AttributeType.SUBJECT,
            attribute_name="role",
            operator="eq",
            value="admin",
        )

        assert condition.attribute_type == AttributeType.SUBJECT
        assert condition.attribute_name == "role"
        assert condition.operator == "eq"
        assert condition.value == "admin"

    def test_evaluate_exists_true(self):
        """Test evaluate with exists operator (attribute present)."""
        condition = PolicyCondition(
            attribute_type=AttributeType.SUBJECT,
            attribute_name="user_id",
            operator="exists",
            value=True,
        )

        # Create an attribute that should match
        attr = Attribute(type=AttributeType.SUBJECT, name="user_id", value="user123")
        attributes = {"subject.user_id": attr}

        result = condition.evaluate(attributes)
        assert result is True

    def test_evaluate_exists_false(self):
        """Test evaluate with exists operator (attribute absent)."""
        condition = PolicyCondition(
            attribute_type=AttributeType.SUBJECT,
            attribute_name="user_id",
            operator="exists",
            value=True,
        )

        # Empty attributes - should not match
        attributes = {}

        result = condition.evaluate(attributes)
        assert result is False

    def test_evaluate_with_missing_attribute(self):
        """Test evaluate when attribute is missing."""
        condition = PolicyCondition(
            attribute_type=AttributeType.SUBJECT,
            attribute_name="missing_attr",
            operator="eq",
            value="some_value",
        )

        attributes = {}
        result = condition.evaluate(attributes)

        # Missing attribute, exists check is false
        assert result is False


class TestPolicyIntegration:
    """Integration tests for policy components."""

    def test_attribute_in_condition(self):
        """Test using attribute with condition evaluation."""
        attr = Attribute(type=AttributeType.SUBJECT, name="role", value="admin")

        condition = PolicyCondition(
            attribute_type=AttributeType.SUBJECT,
            attribute_name="role",
            operator="exists",
            value=True,
        )

        attributes = {"subject.role": attr}
        result = condition.evaluate(attributes)

        assert result is True

    def test_multiple_attributes(self):
        """Test with multiple attributes."""
        attrs = {
            "subject.role": Attribute(AttributeType.SUBJECT, "role", "admin"),
            "subject.department": Attribute(
                AttributeType.SUBJECT, "department", "engineering"
            ),
            "resource.type": Attribute(AttributeType.RESOURCE, "type", "database"),
            "action.method": Attribute(AttributeType.ACTION, "method", "read"),
        }

        # Condition checking for role existence
        condition = PolicyCondition(
            attribute_type=AttributeType.SUBJECT,
            attribute_name="role",
            operator="exists",
            value=True,
        )

        assert condition.evaluate(attrs) is True

    def test_policy_priority_comparison(self):
        """Test comparing policy priorities."""
        priorities = [
            PolicyPriority.DEFAULT,
            PolicyPriority.EMERGENCY,
            PolicyPriority.NORMAL,
            PolicyPriority.HIGH,
        ]

        # Sort by priority (lower value = higher priority)
        sorted_priorities = sorted(priorities, key=lambda p: p.value)

        assert sorted_priorities[0] == PolicyPriority.EMERGENCY
        assert sorted_priorities[-1] == PolicyPriority.DEFAULT
