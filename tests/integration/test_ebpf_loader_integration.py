import os
import subprocess
import pytest

def test_ebpf_loader_dry_run():
    """Test eBPF Go loader dry-run verification and policy generation."""
    loader_path = "./ebpf/prod/loader_linux_amd64"
    policy_path = "./ebpf/prod/test_cilium_policy.yaml"
    
    # Remove old policy file if present
    if os.path.exists(policy_path):
        os.remove(policy_path)
        
    try:
        # Run loader in dry-run mode using bash wrapper
        cmd = [
            "bash",
            "-c",
            f"{loader_path} --dry-run --cilium-policy {policy_path}"
        ]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        # Verify exit status and output logs
        assert result.returncode == 0
        assert "verification-only mode" in result.stdout
        
        # Verify the policy file has been generated
        assert os.path.exists(policy_path)
        
        # Verify rendered YAML policy content
        with open(policy_path, "r") as f:
            content = f.read()
            assert "CiliumNetworkPolicy" in content
            assert "x0tta6bl4-prod-ebpf" in content
            
    finally:
        # Clean up files
        if os.path.exists(policy_path):
            os.remove(policy_path)
