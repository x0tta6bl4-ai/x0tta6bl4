#!/usr/bin/env python3
"""
Charter Admin CLI Tool
For audit committee to validate, view, and audit charter policies

Usage:
  charter-admin validate <policy.yaml>              - Validate policy syntax and structure
  charter-admin show <policy.yaml>                  - Display policy in human-readable format
  charter-admin metrics <policy.yaml>               - List whitelisted and forbidden metrics
  charter-admin audit <policy.yaml>                 - Run complete audit with recommendations
  charter-admin report <policy.yaml>                - Generate detailed JSON validation report
  charter-admin compare <policy1.yaml> <policy2.yaml> - Compare two policies
  charter-admin enforce <policy.yaml> [metrics]    - Enforce metrics against policy (with optional metrics file)
"""

import sys
from pathlib import Path
from typing import List, Dict, Any
import json
import argparse

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.westworld.anti_delos_charter import CharterPolicyValidator


class CharterAdminCLI:
    """Command-line interface for charter policy administration"""
    
    def __init__(self):
        self.validator = CharterPolicyValidator()
    
    def validate(self, policy_file: str) -> int:
        """Validate a charter policy file"""
        try:
            policy = self.validator.load_policy(policy_file)
            is_valid, errors = self.validator.validate_policy(policy)
            
            print(f"\n{'='*70}")
            print(f"CHARTER VALIDATION REPORT")
            print(f"{'='*70}\n")
            
            print(f"Policy File: {policy_file}")
            print(f"Name: {policy.get('charter', {}).get('name', 'N/A')}")
            print(f"Version: {policy.get('charter', {}).get('version', 'N/A')}")
            print(f"Environment: {policy.get('charter', {}).get('metadata', {}).get('environment', 'N/A')}")
            print(f"Status: {policy.get('charter', {}).get('metadata', {}).get('status', 'N/A')}")
            
            print(f"\nValidation Result: {'✓ PASS' if is_valid else '✗ FAIL'}")
            
            if errors:
                print(f"\nErrors found ({len(errors)}):")
                for i, error in enumerate(errors, 1):
                    print(f"  {i}. {error}")
                return 1
            else:
                print("\nAll validations passed!")
                return 0
        
        except FileNotFoundError:
            print(f"✗ Error: Policy file not found: {policy_file}")
            return 1
        except Exception as e:
            print(f"✗ Error: {e}")
            return 1
    
    def show(self, policy_file: str) -> int:
        """Display policy in human-readable format"""
        try:
            policy = self.validator.load_policy(policy_file)
            
            print(f"\n{'='*70}")
            print(f"CHARTER POLICY: {policy.get('charter', {}).get('name', 'Unknown')}")
            print(f"{'='*70}\n")
            
            # Charter section
            charter = policy.get('charter', {})
            print(f"Charter Details:")
            print(f"  Version: {charter.get('version', 'N/A')}")
            print(f"  Environment: {charter.get('metadata', {}).get('environment', 'N/A')}")
            print(f"  Status: {charter.get('metadata', {}).get('status', 'N/A')}")
            print(f"  Effective Date: {charter.get('effective_date', 'N/A')}")
            
            # Access control
            print(f"\nAccess Control Roles:")
            ac = policy.get('access_control', {})
            for role_set in ac.get('read_access', []):
                print(f"  - {role_set.get('role', 'unknown')}: read access configured")
            
            # Metrics summary
            whitelist = self.validator.get_whitelisted_metrics(policy)
            forbidden = self.validator.get_forbidden_metrics(policy)
            print(f"\nMetrics:")
            print(f"  Whitelisted: {len(whitelist)} metrics")
            print(f"  Forbidden: {len(forbidden)} metrics")
            
            return 0
        
        except FileNotFoundError:
            print(f"✗ Error: Policy file not found: {policy_file}")
            return 1
        except Exception as e:
            print(f"✗ Error: {e}")
            return 1
    
    def metrics(self, policy_file: str) -> int:
        """List whitelisted and forbidden metrics"""
        try:
            policy = self.validator.load_policy(policy_file)
            whitelist = self.validator.get_whitelisted_metrics(policy)
            forbidden = self.validator.get_forbidden_metrics(policy)
            
            print(f"\n{'='*70}")
            print(f"CHARTER METRICS: {policy.get('charter', {}).get('name', 'Unknown')}")
            print(f"{'='*70}\n")
            
            print(f"WHITELISTED METRICS ({len(whitelist)}):")
            for i, metric in enumerate(whitelist, 1):
                print(f"  {i:2d}. {metric}")
            
            print(f"\nFORBIDDEN METRICS ({len(forbidden)}):")
            for i, metric in enumerate(forbidden, 1):
                print(f"  {i:2d}. {metric} (CRITICAL/HIGH penalty)")
            
            print(f"\nSummary:")
            print(f"  Total allowed: {len(whitelist)}")
            print(f"  Total blocked: {len(forbidden)}")
            print(f"  Coverage: {len(whitelist)} metrics actively protected")
            
            return 0
        
        except FileNotFoundError:
            print(f"✗ Error: Policy file not found: {policy_file}")
            return 1
        except Exception as e:
            print(f"✗ Error: {e}")
            return 1
    
    def audit(self, policy_file: str) -> int:
        """Run complete audit with recommendations"""
        try:
            policy = self.validator.load_policy(policy_file)
            
            # Generate comprehensive validation report
            report = self.validator.generate_validation_report(policy)
            
            print(f"\n{'='*70}")
            print(f"CHARTER AUDIT REPORT")
            print(f"{'='*70}\n")
            
            print(f"Policy: {report['policy_name']}")
            print(f"Environment: {report['environment']}")
            print(f"Timestamp: {report['timestamp']}")
            
            # Validation status
            print(f"\n1. Validation Status: {report['overall_status']}")
            if report['errors']:
                print(f"   Errors found ({report['total_errors']}):")
                for error in report['errors']:
                    print(f"   - {error}")
            else:
                print(f"   ✓ All validations passed")
            
            # Security assessment
            print(f"\n2. Security Assessment:")
            print(f"   - Whitelisted metrics: {report['metrics']['whitelisted']}")
            print(f"   - Forbidden metrics: {report['metrics']['forbidden']}")
            print(f"   - Read access roles: {report['access_control']['read_roles']}")
            print(f"   - Write access roles: {report['access_control']['write_roles']}")
            print(f"   - Violation severity levels: {report['violation_levels']}")
            print(f"   - Whistleblower policy: {'✓ Enabled' if report['has_whistleblower_policy'] else '✗ Missing'}")
            print(f"   - Emergency override: {'✓ Configured' if report['has_emergency_override'] else '✗ Missing'}")
            
            # Recommendations
            if report['recommendations']:
                print(f"\n3. Recommendations ({len(report['recommendations'])}):")
                for i, rec in enumerate(report['recommendations'], 1):
                    print(f"   {i}. {rec}")
            else:
                print(f"\n3. Recommendations: None - policy is well-configured")
            
            return 0 if report['overall_status'] == 'PASS' else 1
        
        except FileNotFoundError:
            print(f"✗ Error: Policy file not found: {policy_file}")
            return 1
        except Exception as e:
            print(f"✗ Error: {e}")
            return 1
    
    def report(self, policy_file: str) -> int:
        """Generate detailed validation report in JSON format"""
        try:
            policy = self.validator.load_policy(policy_file)
            report = self.validator.generate_validation_report(policy)
            
            print(json.dumps(report, indent=2))
            
            return 0 if report['overall_status'] == 'PASS' else 1
        
        except FileNotFoundError:
            print(f"✗ Error: Policy file not found: {policy_file}")
            return 1
        except Exception as e:
            print(f"✗ Error: {e}")
            return 1
    
    def compare(self, policy1_file: str, policy2_file: str) -> int:
        """Compare two policies"""
        try:
            policy1 = self.validator.load_policy(policy1_file)
            policy2 = self.validator.load_policy(policy2_file)
            
            name1 = policy1.get('charter', {}).get('name', 'Policy 1')
            name2 = policy2.get('charter', {}).get('name', 'Policy 2')
            
            print(f"\n{'='*70}")
            print(f"CHARTER POLICY COMPARISON")
            print(f"{'='*70}\n")
            
            print(f"Policy 1: {name1}")
            print(f"Policy 2: {name2}\n")
            
            # Environment comparison
            env1 = policy1.get('charter', {}).get('metadata', {}).get('environment', 'N/A')
            env2 = policy2.get('charter', {}).get('metadata', {}).get('environment', 'N/A')
            print(f"Environment: {env1} vs {env2}")
            
            # Metrics comparison
            metrics1 = set(self.validator.get_whitelisted_metrics(policy1))
            metrics2 = set(self.validator.get_whitelisted_metrics(policy2))
            
            print(f"Whitelisted metrics:")
            print(f"  Policy 1: {len(metrics1)} metrics")
            print(f"  Policy 2: {len(metrics2)} metrics")
            
            if metrics1 == metrics2:
                print(f"  Status: ✓ Identical")
            else:
                added = metrics2 - metrics1
                removed = metrics1 - metrics2
                if added:
                    print(f"  Added in Policy 2: {added}")
                if removed:
                    print(f"  Removed in Policy 2: {removed}")
            
            # Forbidden metrics comparison
            forbidden1 = set(self.validator.get_forbidden_metrics(policy1))
            forbidden2 = set(self.validator.get_forbidden_metrics(policy2))
            
            print(f"Forbidden metrics:")
            print(f"  Policy 1: {len(forbidden1)} metrics")
            print(f"  Policy 2: {len(forbidden2)} metrics")
            
            if forbidden1 == forbidden2:
                print(f"  Status: ✓ Identical")
            
            # Access control comparison
            print(f"\nAccess Control:")
            ac1 = policy1.get('access_control', {})
            ac2 = policy2.get('access_control', {})
            
            roles1 = set(r.get('role') for r in ac1.get('read_access', []))
            roles2 = set(r.get('role') for r in ac2.get('read_access', []))
            print(f"  Policy 1 roles: {roles1}")
            print(f"  Policy 2 roles: {roles2}")
            
            return 0
        
        except FileNotFoundError as e:
            print(f"✗ Error: Policy file not found: {e}")
            return 1
        except Exception as e:
            print(f"✗ Error: {e}")
            return 1
    
    def _get_protection_level(self, environment: str) -> str:
        """Get human-readable protection level"""
        levels = {
            'development': 'LOW (dev only)',
            'staging': 'MEDIUM (pre-production)',
            'production': 'HIGH (production-grade)'
        }
        return levels.get(environment, 'UNKNOWN')
    
    def _generate_recommendations(self, policy: Dict[str, Any]) -> List[str]:
        """Generate security recommendations based on policy"""
        recommendations = []
        
        env = policy.get('charter', {}).get('metadata', {}).get('environment', '')
        
        # Check if DAO vote required in prod
        if env == 'production':
            override = policy.get('emergency_override', {})
            if not override.get('requires_dao_vote', False):
                recommendations.append("Production policy should require DAO vote for emergency override")
        
        # Check audit trail immutability in prod
        if env == 'production':
            audit = policy.get('violation_policy', {}).get('audit_trail', {})
            if not audit.get('immutable', False):
                recommendations.append("Production audit trail should be immutable")
            if not audit.get('signing_required', False):
                recommendations.append("Production audit trail should require cryptographic signing")
        
        # Check whistleblower policy
        whistle = policy.get('whistleblower_policy', {})
        if not whistle.get('anonymous_reporting', False):
            recommendations.append("Enable anonymous reporting for whistleblower protection")
        
        if env == 'production' and not whistle.get('bounty_enabled', False):
            recommendations.append("Production policy should enable whistleblower bounties")
        
        return recommendations
    
    def enforce(self, policy_file: str, metrics_file: str = None, output_format: str = 'text') -> int:
        """Проверка метрик на соответствие политике.
        
        Args:
            policy_file: Путь к файлу политики
            metrics_file: Путь к файлу с метриками (JSON)
            output_format: Формат вывода ('json' или 'text')
            
        Returns:
            Код возврата (0 - успех, 1 - ошибка)
        """
        import json
        from datetime import datetime
        
        try:
            policy = self.validator.load_policy(policy_file)
            validator = CharterPolicyValidator()
            validator.policy = policy
            enforcer = validator.create_enforcer()
            
            # Если metrics_file не указан, использовать примеры
            if metrics_file is None:
                metrics = [
                    {
                        'metric_name': 'latency_p50',
                        'value': 42,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'demo_node',
                    },
                    {
                        'metric_name': 'user_location',  # Запрещённая!
                        'value': 1,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'attacker',
                    },
                ]
            else:
                with open(metrics_file, 'r') as f:
                    metrics = json.load(f)
                    if not isinstance(metrics, list):
                        metrics = [metrics]
            
            # Валидация метрик
            result = enforcer.validate_metrics(metrics)
            
            if output_format == 'json':
                # JSON output
                output = {
                    'status': 'PASS' if result['all_valid'] else 'FAIL',
                    'timestamp': datetime.now().isoformat(),
                    'policy_name': policy.get('charter', {}).get('metadata', {}).get('name'),
                    'metrics_processed': result['total_metrics'],
                    'passed': result['passed'],
                    'blocked': result['blocked'],
                    'errors': result['errors'],
                    'violations': result['violations'],
                }
                print(json.dumps(output, indent=2))
            else:
                # Text output
                print(f"\n{'='*70}")
                print(f"METRIC ENFORCEMENT REPORT")
                print(f"{'='*70}\n")
                print(f"Policy: {policy.get('charter', {}).get('metadata', {}).get('name')}")
                print(f"Timestamp: {datetime.now().isoformat()}\n")
                
                print(f"Validation Results:")
                print(f"  Total Metrics: {result['total_metrics']}")
                print(f"  Passed: {result['passed']}")
                print(f"  Blocked: {result['blocked']}")
                print(f"  Errors: {result['errors']}")
                print(f"  Status: {'✓ PASS' if result['all_valid'] else '✗ FAIL'}\n")
                
                if result['blocked'] > 0:
                    print(f"Blocked Metrics:")
                    for res in result['detailed_results']:
                        if res['enforcement_action'] == 'BLOCK':
                            print(f"  - {res['metric_name']}: {res['reason']}")
                    print()
                
                if result['violations']:
                    print(f"Violations Detected: {len(result['violations'])}")
                    for violation in result['violations']:
                        print(f"\n  Metric: {violation['metric_name']}")
                        print(f"  Attempts: {violation['attempt_count']} in {violation['time_window']}")
                        print(f"  Severity: {violation['severity']}")
                        print(f"  Action: {violation['recommended_action']}")
                    print()
            
            return 0 if result['all_valid'] else 1
        
        except FileNotFoundError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in metrics file - {e}", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Charter Admin CLI - Audit and manage charter policies',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate policy syntax and structure')
    validate_parser.add_argument('policy', help='Path to policy file')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Display policy in human-readable format')
    show_parser.add_argument('policy', help='Path to policy file')
    
    # Metrics command
    metrics_parser = subparsers.add_parser('metrics', help='List whitelisted and forbidden metrics')
    metrics_parser.add_argument('policy', help='Path to policy file')
    
    # Audit command
    audit_parser = subparsers.add_parser('audit', help='Run complete audit with recommendations')
    audit_parser.add_argument('policy', help='Path to policy file')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two policies')
    compare_parser.add_argument('policy1', help='First policy file')
    compare_parser.add_argument('policy2', help='Second policy file')
    
    # Report command
    report_parser = subparsers.add_parser('report', help='Generate detailed validation report (JSON)')
    report_parser.add_argument('policy', help='Path to policy file')
    
    # Enforce command
    enforce_parser = subparsers.add_parser('enforce', help='Enforce metrics against policy')
    enforce_parser.add_argument('policy', help='Path to policy file')
    enforce_parser.add_argument('metrics', nargs='?', help='Path to metrics file (JSON) - optional')
    enforce_parser.add_argument('--format', choices=['json', 'text'], default='text',
                               help='Output format (default: text)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    cli = CharterAdminCLI()
    
    if args.command == 'validate':
        return cli.validate(args.policy)
    elif args.command == 'show':
        return cli.show(args.policy)
    elif args.command == 'metrics':
        return cli.metrics(args.policy)
    elif args.command == 'audit':
        return cli.audit(args.policy)
    elif args.command == 'report':
        return cli.report(args.policy)
    elif args.command == 'compare':
        return cli.compare(args.policy1, args.policy2)
    elif args.command == 'enforce':
        metrics_file = getattr(args, 'metrics', None)
        output_format = getattr(args, 'format', 'text')
        return cli.enforce(args.policy, metrics_file, output_format)
    else:
        parser.print_help()
        return 1


if __name__ == '__main__':
    sys.exit(main())
