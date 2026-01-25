#!/usr/bin/env python3
"""
x0tta6bl4 eBPF CLI - Command Line Interface for eBPF Management

Provides commands for:
- Viewing status of eBPF programs
- Loading/unloading programs
- Attaching/detaching from interfaces
- Viewing statistics and flows
- Health checks

Usage:
    x0tta6bl4-ebpf status
    x0tta6bl4-ebpf load <program.o>
    x0tta6bl4-ebpf attach <program_id> <interface>
    x0tta6bl4-ebpf stats
    x0tta6bl4-ebpf flows [--source <ip>] [--dest <ip>]
    x0tta6bl4-ebpf health
"""

import argparse
import asyncio
import json
import sys
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

# Local imports
try:
    from .orchestrator import EBPFOrchestrator, OrchestratorConfig, create_orchestrator
    from .loader import EBPFLoader, EBPFProgramType, EBPFAttachMode
    ORCHESTRATOR_AVAILABLE = True
except ImportError:
    ORCHESTRATOR_AVAILABLE = False

try:
    from .cilium_integration import CiliumLikeIntegration
    CILIUM_AVAILABLE = True
except ImportError:
    CILIUM_AVAILABLE = False

logger = logging.getLogger(__name__)


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def colorize(text: str, color: str) -> str:
    """Add color to text if terminal supports it"""
    if sys.stdout.isatty():
        return f"{color}{text}{Colors.ENDC}"
    return text


def print_header(text: str):
    """Print a header"""
    print(colorize(f"\n{'='*60}", Colors.CYAN))
    print(colorize(f"  {text}", Colors.BOLD))
    print(colorize(f"{'='*60}", Colors.CYAN))


def print_success(text: str):
    """Print success message"""
    print(colorize(f"✅ {text}", Colors.GREEN))


def print_error(text: str):
    """Print error message"""
    print(colorize(f"❌ {text}", Colors.RED))


def print_warning(text: str):
    """Print warning message"""
    print(colorize(f"⚠️  {text}", Colors.YELLOW))


def print_info(text: str):
    """Print info message"""
    print(colorize(f"ℹ️  {text}", Colors.BLUE))


class EBPFCLI:
    """Command Line Interface for eBPF management"""
    
    def __init__(self, interface: str = "eth0"):
        self.interface = interface
        self._loader: Optional[EBPFLoader] = None
        self._orchestrator: Optional[EBPFOrchestrator] = None
    
    @property
    def loader(self) -> EBPFLoader:
        """Lazy initialization of loader"""
        if self._loader is None:
            self._loader = EBPFLoader()
        return self._loader
    
    def cmd_status(self, args):
        """Show status of eBPF subsystem"""
        print_header("x0tta6bl4 eBPF Status")
        
        # Show loaded programs
        programs = self.loader.list_loaded_programs()
        
        print(f"\n{colorize('Loaded Programs:', Colors.BOLD)} {len(programs)}")
        if programs:
            print("-" * 50)
            for prog in programs:
                prog_id = prog.get('id', 'unknown')
                prog_type = prog.get('type', 'unknown')
                attached = prog.get('attached_to', 'not attached')
                
                status_color = Colors.GREEN if attached != 'not attached' else Colors.YELLOW
                print(f"  • {colorize(prog_id, Colors.CYAN)}")
                print(f"    Type: {prog_type}")
                print(f"    Status: {colorize(attached, status_color)}")
        else:
            print_info("No programs loaded")
        
        # Show interface attachments
        print(f"\n{colorize('Interface Attachments:', Colors.BOLD)}")
        print("-" * 50)
        
        for iface in [self.interface, 'lo']:
            progs = self.loader.get_interface_programs(iface)
            if progs:
                print(f"  {colorize(iface, Colors.CYAN)}: {len(progs)} program(s)")
                for prog_id in progs:
                    print(f"    └─ {prog_id}")
            else:
                print(f"  {iface}: no programs attached")
        
        # Show stats
        print(f"\n{colorize('Packet Statistics:', Colors.BOLD)}")
        print("-" * 50)
        stats = self.loader.get_stats()
        print(f"  Total packets:     {stats.get('total_packets', 0):,}")
        print(f"  Passed packets:    {stats.get('passed_packets', 0):,}")
        print(f"  Dropped packets:   {stats.get('dropped_packets', 0):,}")
        print(f"  Forwarded packets: {stats.get('forwarded_packets', 0):,}")
        
        # Calculate drop rate
        total = stats.get('total_packets', 0)
        dropped = stats.get('dropped_packets', 0)
        if total > 0:
            drop_rate = (dropped / total) * 100
            drop_color = Colors.GREEN if drop_rate < 1 else (Colors.YELLOW if drop_rate < 5 else Colors.RED)
            print(f"  Drop rate:         {colorize(f'{drop_rate:.2f}%', drop_color)}")
    
    def cmd_load(self, args):
        """Load an eBPF program"""
        program_path = args.program
        program_type = args.type or "xdp"
        
        print_header(f"Loading eBPF Program: {program_path}")
        
        try:
            prog_type = EBPFProgramType(program_type)
            program_id = self.loader.load_program(program_path, prog_type)
            
            print_success(f"Program loaded successfully")
            print(f"  Program ID: {colorize(program_id, Colors.CYAN)}")
            print(f"  Type: {program_type}")
            print_info(f"Use 'attach {program_id} <interface>' to attach to an interface")
            
        except Exception as e:
            print_error(f"Failed to load program: {e}")
            return 1
        
        return 0
    
    def cmd_unload(self, args):
        """Unload an eBPF program"""
        program_id = args.program_id
        
        print_header(f"Unloading eBPF Program: {program_id}")
        
        try:
            success = self.loader.unload_program(program_id)
            
            if success:
                print_success("Program unloaded successfully")
            else:
                print_error("Failed to unload program")
                return 1
                
        except Exception as e:
            print_error(f"Failed to unload program: {e}")
            return 1
        
        return 0
    
    def cmd_attach(self, args):
        """Attach a program to an interface"""
        program_id = args.program_id
        interface = args.interface or self.interface
        mode = args.mode or "skb"
        
        print_header(f"Attaching Program to Interface")
        print(f"  Program: {program_id}")
        print(f"  Interface: {interface}")
        print(f"  Mode: {mode}")
        
        try:
            attach_mode = EBPFAttachMode(mode)
            success = self.loader.attach_to_interface(program_id, interface, attach_mode)
            
            if success:
                print_success("Program attached successfully")
            else:
                print_error("Failed to attach program")
                return 1
                
        except Exception as e:
            print_error(f"Failed to attach program: {e}")
            return 1
        
        return 0
    
    def cmd_detach(self, args):
        """Detach a program from an interface"""
        program_id = args.program_id
        interface = args.interface or self.interface
        
        print_header(f"Detaching Program from Interface")
        print(f"  Program: {program_id}")
        print(f"  Interface: {interface}")
        
        try:
            success = self.loader.detach_from_interface(program_id, interface)
            
            if success:
                print_success("Program detached successfully")
            else:
                print_error("Failed to detach program")
                return 1
                
        except Exception as e:
            print_error(f"Failed to detach program: {e}")
            return 1
        
        return 0
    
    def cmd_stats(self, args):
        """Show detailed statistics"""
        print_header("eBPF Statistics")
        
        stats = self.loader.get_stats()
        
        # Format as table
        print(f"\n{'Metric':<25} {'Value':>15}")
        print("-" * 42)
        
        for key, value in stats.items():
            formatted_key = key.replace('_', ' ').title()
            print(f"{formatted_key:<25} {value:>15,}")
        
        # JSON output if requested
        if args.json:
            print(f"\n{colorize('JSON Output:', Colors.BOLD)}")
            print(json.dumps(stats, indent=2))
    
    def cmd_flows(self, args):
        """Show network flows (Hubble-like)"""
        print_header("Network Flows")
        
        if not CILIUM_AVAILABLE:
            print_warning("Cilium integration not available")
            print_info("Install cilium_integration module for flow observability")
            return 1
        
        try:
            cilium = CiliumLikeIntegration(
                interface=self.interface,
                enable_flow_observability=True
            )
            
            flows = cilium.get_hubble_like_flows(
                source_ip=args.source,
                destination_ip=args.dest,
                protocol=args.protocol,
                limit=args.limit or 20
            )
            
            if not flows:
                print_info("No flows recorded")
                return 0
            
            print(f"\n{'Time':<20} {'Source':<22} {'Dest':<22} {'Proto':<8} {'Verdict':<10}")
            print("-" * 85)
            
            for flow in flows:
                time_str = flow.get('time', '')[:19]
                source = f"{flow.get('source', {}).get('ip', '?')}:{flow.get('source', {}).get('port', '?')}"
                dest = f"{flow.get('destination', {}).get('ip', '?')}:{flow.get('destination', {}).get('port', '?')}"
                proto = flow.get('IP', {}).get('protocol', '?')
                verdict = flow.get('Verdict', '?')
                
                verdict_color = Colors.GREEN if verdict == 'forwarded' else Colors.RED
                print(f"{time_str:<20} {source:<22} {dest:<22} {proto:<8} {colorize(verdict, verdict_color):<10}")
            
            # JSON output if requested
            if args.json:
                print(f"\n{colorize('JSON Output:', Colors.BOLD)}")
                print(json.dumps(flows, indent=2, default=str))
                
        except Exception as e:
            print_error(f"Failed to get flows: {e}")
            return 1
        
        return 0
    
    def cmd_health(self, args):
        """Perform health check"""
        print_header("eBPF Health Check")
        
        if not ORCHESTRATOR_AVAILABLE:
            print_warning("Orchestrator not available, performing basic checks")
            
            # Basic health checks
            checks = []
            
            # Check loader
            try:
                programs = self.loader.list_loaded_programs()
                checks.append(('Loader', True, f'{len(programs)} programs'))
            except Exception as e:
                checks.append(('Loader', False, str(e)))
            
            # Check stats
            try:
                stats = self.loader.get_stats()
                checks.append(('Stats Collection', True, 'OK'))
            except Exception as e:
                checks.append(('Stats Collection', False, str(e)))
            
            # Print results
            print(f"\n{'Component':<25} {'Status':<10} {'Details'}")
            print("-" * 60)
            
            all_healthy = True
            for name, healthy, details in checks:
                status = colorize('✓ OK', Colors.GREEN) if healthy else colorize('✗ FAIL', Colors.RED)
                print(f"{name:<25} {status:<10} {details}")
                if not healthy:
                    all_healthy = False
            
            print()
            if all_healthy:
                print_success("All health checks passed")
            else:
                print_error("Some health checks failed")
                return 1
            
            return 0
        
        # Full health check with orchestrator
        try:
            orchestrator = create_orchestrator(interface=self.interface)
            health = orchestrator.health_check()
            
            print(f"\n{'Component':<25} {'Status':<10} {'Details'}")
            print("-" * 60)
            
            for name, check in health.get('checks', {}).items():
                status = check.get('status', 'unknown')
                status_str = colorize('✓ OK', Colors.GREEN) if status == 'healthy' else colorize('✗ FAIL', Colors.RED)
                
                details = []
                for k, v in check.items():
                    if k != 'status':
                        details.append(f"{k}={v}")
                
                print(f"{name:<25} {status_str:<10} {', '.join(details)}")
            
            print()
            if health.get('healthy', False):
                print_success("All health checks passed")
            else:
                print_error("Some health checks failed")
                return 1
                
        except Exception as e:
            print_error(f"Health check failed: {e}")
            return 1
        
        return 0
    
    def cmd_list_programs(self, args):
        """List available eBPF programs"""
        print_header("Available eBPF Programs")
        
        programs_dir = self.loader.programs_dir
        
        if not programs_dir.exists():
            print_warning(f"Programs directory not found: {programs_dir}")
            return 1
        
        programs = list(programs_dir.glob("*.o"))
        
        if not programs:
            print_info("No compiled eBPF programs found")
            print_info(f"Directory: {programs_dir}")
            return 0
        
        print(f"\nFound {len(programs)} program(s) in {programs_dir}:\n")
        
        for prog in sorted(programs):
            size = prog.stat().st_size
            mtime = datetime.fromtimestamp(prog.stat().st_mtime)
            
            # Determine type from filename
            if 'xdp' in prog.stem.lower():
                prog_type = 'XDP'
            elif 'tc' in prog.stem.lower():
                prog_type = 'TC'
            else:
                prog_type = 'Unknown'
            
            print(f"  {colorize(prog.name, Colors.CYAN)}")
            print(f"    Type: {prog_type}")
            print(f"    Size: {size:,} bytes")
            print(f"    Modified: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
        
        return 0


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        prog='x0tta6bl4-ebpf',
        description='x0tta6bl4 eBPF Management CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s status                    Show eBPF subsystem status
  %(prog)s load xdp_counter.o        Load an eBPF program
  %(prog)s attach prog_id eth0       Attach program to interface
  %(prog)s stats --json              Show statistics in JSON format
  %(prog)s flows --source 192.168.1.1  Show flows from specific IP
  %(prog)s health                    Perform health check
        """
    )
    
    parser.add_argument(
        '-i', '--interface',
        default='eth0',
        help='Default network interface (default: eth0)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # status command
    status_parser = subparsers.add_parser('status', help='Show eBPF subsystem status')
    
    # load command
    load_parser = subparsers.add_parser('load', help='Load an eBPF program')
    load_parser.add_argument('program', help='Path to eBPF program (.o file)')
    load_parser.add_argument('-t', '--type', choices=['xdp', 'tc'], help='Program type')
    
    # unload command
    unload_parser = subparsers.add_parser('unload', help='Unload an eBPF program')
    unload_parser.add_argument('program_id', help='Program ID to unload')
    
    # attach command
    attach_parser = subparsers.add_parser('attach', help='Attach program to interface')
    attach_parser.add_argument('program_id', help='Program ID')
    attach_parser.add_argument('interface', nargs='?', help='Network interface')
    attach_parser.add_argument('-m', '--mode', choices=['skb', 'drv', 'hw'], help='Attach mode')
    
    # detach command
    detach_parser = subparsers.add_parser('detach', help='Detach program from interface')
    detach_parser.add_argument('program_id', help='Program ID')
    detach_parser.add_argument('interface', nargs='?', help='Network interface')
    
    # stats command
    stats_parser = subparsers.add_parser('stats', help='Show statistics')
    stats_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # flows command
    flows_parser = subparsers.add_parser('flows', help='Show network flows')
    flows_parser.add_argument('--source', help='Filter by source IP')
    flows_parser.add_argument('--dest', help='Filter by destination IP')
    flows_parser.add_argument('--protocol', help='Filter by protocol')
    flows_parser.add_argument('--limit', type=int, default=20, help='Max flows to show')
    flows_parser.add_argument('--json', action='store_true', help='Output as JSON')
    
    # health command
    health_parser = subparsers.add_parser('health', help='Perform health check')
    
    # list command
    list_parser = subparsers.add_parser('list', help='List available eBPF programs')
    
    return parser


def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    if not args.command:
        parser.print_help()
        return 0
    
    # Create CLI instance
    cli = EBPFCLI(interface=args.interface)
    
    # Dispatch command
    command_map = {
        'status': cli.cmd_status,
        'load': cli.cmd_load,
        'unload': cli.cmd_unload,
        'attach': cli.cmd_attach,
        'detach': cli.cmd_detach,
        'stats': cli.cmd_stats,
        'flows': cli.cmd_flows,
        'health': cli.cmd_health,
        'list': cli.cmd_list_programs,
    }
    
    handler = command_map.get(args.command)
    if handler:
        return handler(args)
    else:
        print_error(f"Unknown command: {args.command}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
