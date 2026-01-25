"""
Tests for Canary Deployment CI/CD Integration.

Tests the extended CI/CD integration for canary deployment including:
- GitLab CI/CD rollback
- GitHub Actions rollback
- Jenkins rollback
- CircleCI rollback
- Azure DevOps rollback
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock
import httpx

from src.deployment.canary_deployment import CanaryDeployment, DeploymentConfig


class TestCanaryCICDIntegration:
    """Test canary deployment CI/CD integration."""
    
    @pytest.fixture
    def canary(self):
        """Create a canary deployment instance."""
        config = DeploymentConfig()
        return CanaryDeployment(config=config)
    
    @pytest.mark.asyncio
    async def test_gitlab_rollback(self, canary):
        """Test GitLab CI/CD rollback integration."""
        with patch.dict(os.environ, {
            'CI_SYSTEM': 'gitlab',
            'CI_PROJECT_ID': '123',
            'CI_PIPELINE_ID': '456',
            'GITLAB_TOKEN': 'test_token'
        }):
            with patch('httpx.post') as mock_post:
                # Mock cancel pipeline response
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {"status": "canceled"}
                
                # Mock rollback pipeline response
                mock_post.return_value.status_code = 201
                mock_post.return_value.json.return_value = {"id": 789}
                
                result = canary._trigger_cicd_rollback()
                
                # Verify rollback was triggered
                assert result is True
                assert mock_post.called
    
    @pytest.mark.asyncio
    async def test_github_actions_rollback(self, canary):
        """Test GitHub Actions rollback integration."""
        with patch.dict(os.environ, {
            'CI_SYSTEM': 'github',
            'GITHUB_REPOSITORY': 'user/repo',
            'GITHUB_TOKEN': 'test_token',
            'GITHUB_WORKFLOW_ID': 'rollback.yml'
        }):
            with patch('httpx.post') as mock_post:
                mock_post.return_value.status_code = 204
                
                result = canary._trigger_cicd_rollback()
                
                # Verify rollback was triggered
                assert result is True
                assert mock_post.called
                
                # Verify correct URL and headers
                call_args = mock_post.call_args
                assert 'github.com' in call_args[0][0]
                assert 'Authorization' in call_args[1]['headers']
    
    @pytest.mark.asyncio
    async def test_jenkins_rollback(self, canary):
        """Test Jenkins rollback integration."""
        with patch.dict(os.environ, {
            'CI_SYSTEM': 'jenkins',
            'JENKINS_URL': 'http://jenkins.example.com',
            'JENKINS_USER': 'user',
            'JENKINS_TOKEN': 'token',
            'JENKINS_JOB_NAME': 'x0tta6bl4-rollback'
        }):
            with patch('httpx.post') as mock_post:
                mock_post.return_value.status_code = 200
                
                result = canary._trigger_cicd_rollback()
                
                # Verify rollback was triggered
                assert result is True
                assert mock_post.called
                
                # Verify correct URL
                call_args = mock_post.call_args
                assert 'jenkins' in call_args[0][0]
                assert 'ROLLBACK' in call_args[1]['params']
    
    @pytest.mark.asyncio
    async def test_circleci_rollback(self, canary):
        """Test CircleCI rollback integration."""
        with patch.dict(os.environ, {
            'CI_SYSTEM': 'circleci',
            'CIRCLE_TOKEN': 'test_token',
            'CIRCLE_PROJECT_SLUG': 'gh/user/repo'
        }):
            with patch('httpx.post') as mock_post:
                mock_post.return_value.status_code = 201
                mock_post.return_value.json.return_value = {"id": "pipeline_id"}
                
                result = canary._trigger_cicd_rollback()
                
                # Verify rollback was triggered
                assert result is True
                assert mock_post.called
                
                # Verify correct URL
                call_args = mock_post.call_args
                assert 'circleci.com' in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_azure_devops_rollback(self, canary):
        """Test Azure DevOps rollback integration."""
        with patch.dict(os.environ, {
            'CI_SYSTEM': 'azure',
            'AZURE_DEVOPS_ORG': 'org',
            'AZURE_DEVOPS_PROJECT': 'project',
            'AZURE_DEVOPS_PAT': 'pat',
            'AZURE_PIPELINE_ID': '123'
        }):
            with patch('httpx.post') as mock_post:
                mock_post.return_value.status_code = 200
                mock_post.return_value.json.return_value = {"id": 456}
                
                result = canary._trigger_cicd_rollback()
                
                # Verify rollback was triggered
                assert result is True
                assert mock_post.called
                
                # Verify correct URL
                call_args = mock_post.call_args
                assert 'dev.azure.com' in call_args[0][0]
    
    def test_no_cicd_system(self, canary):
        """Test that no CI/CD system returns False."""
        with patch.dict(os.environ, {}, clear=True):
            result = canary._trigger_cicd_rollback()
            
            # Verify no rollback was triggered
            assert result is False
    
    @pytest.mark.asyncio
    async def test_gitlab_rollback_failure_handling(self, canary):
        """Test GitLab rollback failure handling."""
        with patch.dict(os.environ, {
            'CI_SYSTEM': 'gitlab',
            'CI_PROJECT_ID': '123',
            'CI_PIPELINE_ID': '456',
            'GITLAB_TOKEN': 'test_token'
        }):
            with patch('httpx.post') as mock_post:
                # Simulate API failure
                mock_post.side_effect = httpx.RequestError("Connection failed")
                
                result = canary._trigger_cicd_rollback()
                
                # Verify failure is handled gracefully
                assert result is False


