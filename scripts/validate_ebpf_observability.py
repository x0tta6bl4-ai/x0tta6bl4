# scripts/validate_ebpf_observability.py
import asyncio
import os
import sys
import subprocess
import time
import logging
from typing import Optional, Dict

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.network.ebpf.loader import EBPFLoader, EBPFProgramType, EBPFAttachMode, EBPFLoadError, EBPFAttachError
from src.monitoring.alerting import send_alert, AlertSeverity

logger = logging.getLogger("ebpf_validation")
logging.basicConfig(level=logging.INFO)

async def check_command_exists(command: str) -> bool:
    """Checks if a given command exists in the system."""
    try:
        subprocess.run(["which", command], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False

async def validate_ebpf_observability(
    program_c_path: str = "src/network/ebpf/programs/xdp_counter.c",
    program_o_path: str = "src/network/ebpf/programs/xdp_counter.o",
    interface: str = "lo" # Use loopback for testing
):
    """
    Validates the eBPF Observability system in a staging-like environment.
    
    This script assumes a compatible kernel and eBPF development tools are available.
    """
    print("--- Starting eBPF Observability Validation Script ---")
    
    node_id = os.getenv("NODE_ID", "validation-node")
    
    # 1. Check for necessary tools
    print("\n1. Checking for necessary eBPF tools...")
    tools_needed = ["clang", "bpftool", "ip"]
    all_tools_present = True
    for tool in tools_needed:
        if not await check_command_exists(tool):
            logger.error(f"❌ Required tool '{tool}' not found. Please install it.")
            all_tools_present = False
        else:
            logger.info(f"✅ Tool '{tool}' found.")
    
    if not all_tools_present:
        await send_alert(
            alert_name="EBPF_Validation_PrerequisitesMissing",
            severity=AlertSeverity.CRITICAL,
            message=f"eBPF validation failed: Missing required tools. Check logs.",
            labels={"node_id": node_id, "stage": "prerequisites"},
            annotations={"runbook_url": "/docs/monitoring/ebpf_troubleshooting.md"}
        )
        print("--- eBPF Observability Validation Failed (Prerequisites) ---")
        return

    # 2. Compile eBPF C program to .o
    print(f"\n2. Compiling eBPF C program: {program_c_path} to {program_o_path}...")
    try:
        # Assuming kernel headers are in /usr/src/linux-headers-$(uname -r)/include
        uname_r_output = subprocess.run(["uname", "-r"], check=True, capture_output=True, text=True).stdout.strip()
        kernel_headers_path = f"/usr/src/linux-headers-{uname_r_output}/include"
        
        compile_cmd = [
            "clang", "-O2", "-g", "-target", "bpf",
            "-I", kernel_headers_path, # Include kernel headers
            "-c", program_c_path,
            "-o", program_o_path
        ]
        
        subprocess.run(compile_cmd, check=True, capture_output=True, text=True)
        logger.info(f"✅ eBPF program compiled successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to compile eBPF program: {e}")
        await send_alert(
            alert_name="EBPF_CompileFailure",
            severity=AlertSeverity.CRITICAL,
            message=f"eBPF program compilation failed for {program_c_path}: {e}",
            labels={"node_id": node_id, "program": program_c_path},
            annotations={"runbook_url": "/docs/monitoring/ebpf_troubleshooting.md"}
        )
        print("--- eBPF Observability Validation Failed (Compilation) ---")
        return
    
    # 3. Initialize EBPFLoader
    print("\n3. Initializing EBPFLoader...")
    ebpf_loader: Optional[EBPFLoader] = None
    try:
        ebpf_loader = EBPFLoader()
        logger.info("✅ EBPFLoader initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to initialize EBPFLoader: {e}")
        await send_alert(
            alert_name="EBPF_LoaderInitFailure",
            severity=AlertSeverity.CRITICAL,
            message=f"Failed to initialize EBPFLoader: {e}",
            labels={"node_id": node_id},
            annotations={"runbook_url": "/docs/monitoring/ebpf_troubleshooting.md"}
        )
        print("--- eBPF Observability Validation Failed (Loader Init) ---")
        return
    
    program_id: Optional[str] = None
    try:
        # 4. Load eBPF program
        print(f"\n4. Loading eBPF program: {program_o_path}...")
        program_id = ebpf_loader.load_program(program_o_path, EBPFProgramType.XDP)
        logger.info(f"✅ eBPF program loaded with ID: {program_id}")
        
        # 5. Attach eBPF program
        print(f"\n5. Attaching eBPF program {program_id} to interface {interface}...")
        success = ebpf_loader.attach_to_interface(program_id, interface, EBPFAttachMode.SKB)
        if success:
            logger.info(f"✅ eBPF program {program_id} attached to {interface} successfully.")
        else:
            raise EBPFAttachError("Attachment returned False.")
        
        # 6. Verify eBPF program (optional, could involve traffic generation and reading map)
        print("\n6. Verifying eBPF program (simplified)...")
        # For xdp_counter, we could send some packets and read the map.
        # For this validation script, we'll just check ip link show.
        try:
            result = subprocess.run(
                ["ip", "link", "show", "dev", interface],
                check=True, capture_output=True, text=True
            ).stdout
            if "xdp" in result:
                logger.info(f"✅ 'xdp' found in 'ip link show dev {interface}' output. Program likely attached.")
            else:
                logger.warning(f"⚠️ 'xdp' NOT found in 'ip link show dev {interface}' output. Program might not be active.")
        except Exception as e:
            logger.error(f"❌ Failed to verify attachment via ip link: {e}")

        # 7. Simulate some traffic (optional)
        print("\n7. Simulating some traffic on loopback interface...")
        try:
            subprocess.run(["ping", "-c", "3", "127.0.0.1"], check=True, capture_output=True, text=True)
            logger.info("✅ Ping packets sent.")
        except Exception as e:
            logger.warning(f"⚠️ Failed to send ping packets: {e}")
        
    except (EBPFLoadError, EBPFAttachError, Exception) as e:
        logger.error(f"❌ eBPF program operation failed: {e}")
        await send_alert(
            alert_name="EBPF_Program_OperationFailure",
            severity=AlertSeverity.CRITICAL,
            message=f"eBPF program {program_o_path} operation failed on {interface}: {e}",
            labels={"node_id": node_id, "program": program_o_path, "interface": interface},
            annotations={"runbook_url": "/docs/monitoring/ebpf_troubleshooting.md"}
        )
        print("--- eBPF Observability Validation Failed (Operation) ---")
        return
    finally:
        # 8. Detach and unload eBPF program
        if ebpf_loader and program_id:
            print(f"\n8. Detaching and unloading eBPF program {program_id}...")
            try:
                if ebpf_loader.detach_from_interface(program_id, interface):
                    logger.info(f"✅ eBPF program {program_id} detached from {interface}.")
                else:
                    logger.warning(f"⚠️ Failed to detach eBPF program {program_id} from {interface}.")
                
                if ebpf_loader.unload_program(program_id):
                    logger.info(f"✅ eBPF program {program_id} unloaded.")
                else:
                    logger.warning(f"⚠️ Failed to unload eBPF program {program_id}.")
            except Exception as e:
                logger.error(f"❌ Error during eBPF program cleanup: {e}")
                await send_alert(
                    alert_name="EBPF_CleanupFailure",
                    severity=AlertSeverity.ERROR,
                    message=f"Failed to cleanup eBPF program {program_id} on {interface}: {e}",
                    labels={"node_id": node_id, "program": program_id, "interface": interface},
                    annotations={"runbook_url": "/docs/monitoring/ebpf_troubleshooting.md"}
                )

    print("\n--- eBPF Observability Validation Script Finished ---")
    await send_alert(
        alert_name="EBPF_Validation_Success",
        severity=AlertSeverity.INFO,
        message=f"eBPF Observability validation completed successfully for {program_o_path} on {interface}.",
        labels={"node_id": node_id, "program": program_o_path, "interface": interface}
    )

if __name__ == "__main__":
    asyncio.run(validate_ebpf_observability())
