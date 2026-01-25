#!/usr/bin/env python3
"""
x0tta6bl4 MAPE-K Quality Integration
============================================

Integrates Code Quality Analyzer with MAPE-K loop for autonomous
code quality monitoring and improvement.

Features:
- Continuous quality monitoring
- Automated quality gate enforcement
- Self-healing code improvements
- Quality trend analysis
- Automated refactoring suggestions
"""

import asyncio
import time
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import logging
from datetime import datetime, timedelta

from .code_quality_analyzer import CodeQualityAnalyzer, QualityMetrics
from ..core.mape_k_thread_safe import ThreadSafeMAPEKLoop
from ..core.thread_safe_stats import ThreadSafeMetrics

logger = logging.getLogger(__name__)

@dataclass
class QualityThresholds:
    """Quality thresholds for MAPE-K decision making."""
    min_overall_score: float = 70.0
    max_complexity: float = 15.0
    min_test_coverage: float = 50.0
    max_security_issues: int = 5
    max_technical_debt_hours: float = 8.0  # hours
    min_maintainability: float = 60.0

@dataclass
class QualityImprovement:
    """Automated quality improvement action."""
    action_type: str  # REFACTOR, ADD_TESTS, FIX_SECURITY, FORMAT_CODE
    file_path: str
    description: str
    priority: str  # LOW, MEDIUM, HIGH, CRITICAL
    estimated_effort: int  # minutes
    automated: bool = False

class MAPEKQualityMonitor:
    """
    MAPE-K loop for autonomous code quality monitoring.
    
    Monitors:
    - Code quality metrics
    - Security vulnerabilities
    - Test coverage
    - Technical debt
    - Quality trends
    
    Executes:
    - Automated refactoring
    - Test generation
    - Security fixes
    - Code formatting
    """
    
    def __init__(self, repo_root: str, thresholds: QualityThresholds = None):
        self.repo_root = Path(repo_root)
        self.thresholds = thresholds or QualityThresholds()
        
        # Initialize components
        self.quality_analyzer = CodeQualityAnalyzer(repo_root)
        self.mapek_loop = ThreadSafeMAPEKLoop("quality_monitor")
        
        # Quality metrics storage
        self.quality_metrics: Dict[str, Any] = {}
        self.improvement_queue: List[QualityImprovement] = []
        self.last_analysis_time: Optional[datetime] = None
        
        # Thread-safe metrics for MAPE-K
        self.metrics = ThreadSafeMetrics("mapek_quality")
        
        # Initialize metrics
        self.metrics.set_gauge("quality_score", 0.0)
        self.metrics.set_gauge("security_issues", 0.0)
        self.metrics.set_gauge("technical_debt", 0.0)
        self.metrics.increment_counter("analysis_cycles")
        
        logger.info(f"MAPEKQualityMonitor initialized for {repo_root}")
    
    async def start_monitoring(self, interval_seconds: int = 300) -> None:
        """
        Start continuous quality monitoring.
        
        Args:
            interval_seconds: Monitoring interval (default: 5 minutes)
        """
        logger.info(f"Starting quality monitoring every {interval_seconds} seconds")
        
        while True:
            try:
                # Execute MAPE-K cycle for quality
                system_metrics = self._collect_system_metrics()
                context = {"monitoring_type": "quality", "repo_root": str(self.repo_root)}
                
                state = await self.mapek_loop.execute_cycle(system_metrics, context)
                
                # Process cycle results
                await self._process_cycle_results(state)
                
                # Wait for next cycle
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Quality monitoring cycle failed: {e}")
                await asyncio.sleep(60)  # Brief pause before retry
    
    async def run_single_analysis(self) -> Dict[str, Any]:
        """Run a single quality analysis cycle."""
        logger.info("Running single quality analysis")
        
        # Collect system metrics
        system_metrics = self._collect_system_metrics()
        context = {"monitoring_type": "quality", "repo_root": str(self.repo_root)}
        
        # Execute MAPE-K cycle
        state = await self.mapek_loop.execute_cycle(system_metrics, context)
        
        # Process results
        await self._process_cycle_results(state)
        
        return {
            "analysis_timestamp": datetime.now().isoformat(),
            "quality_metrics": self.quality_metrics,
            "improvements_suggested": len(self.improvement_queue),
            "mapek_state": state.get_snapshot()
        }
    
    def _collect_system_metrics(self) -> Dict[str, float]:
        """Collect system metrics for MAPE-K Monitor phase."""
        # Get current repository state
        repo_stats = self._get_repository_stats()
        
        metrics = {
            "repo_size_mb": repo_stats["size_mb"],
            "file_count": repo_stats["file_count"],
            "last_commit_hours": repo_stats["last_commit_hours"],
            "active_branches": repo_stats["active_branches"],
            "health_score": self._calculate_health_score()
        }
        
        return metrics
    
    async def _process_cycle_results(self, state) -> None:
        """Process results from MAPE-K cycle."""
        phase = state.phase
        
        if phase == "COMPLETE":
            # Extract decisions and actions from the cycle
            decisions = state.decisions
            actions = state.actions
            
            logger.info(f"MAPE-K quality cycle completed: {len(decisions)} decisions, {len(actions)} actions")
            
            # Update metrics
            for decision in decisions:
                self.metrics.add_to_set("quality_decisions", decision)
            
            for action in actions:
                self.metrics.add_to_set("quality_actions", action)
                self.metrics.increment_counter("actions_executed")
        
        elif phase == "ERROR":
            logger.error(f"MAPE-K quality cycle failed: {state.metrics.get('error', 'Unknown error')}")
            self.metrics.increment_counter("failed_cycles")
    
    def _get_repository_stats(self) -> Dict[str, float]:
        """Get repository statistics for monitoring."""
        size_mb = 0
        file_count = 0
        
        # Calculate repository size
        for file_path in self.repo_root.rglob("*"):
            if file_path.is_file():
                size_mb += file_path.stat().st_size / (1024 * 1024)
                file_count += 1
        
        # Get git statistics if available
        last_commit_hours = float('inf')
        active_branches = 1
        
        try:
            import subprocess
            
            # Get last commit time
            result = subprocess.run(
                ["git", "log", "-1", "--format=%ct"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                commit_time = int(result.stdout.strip())
                last_commit_hours = (time.time() - commit_time) / 3600
            
            # Get branch count
            result = subprocess.run(
                ["git", "branch", "--list"],
                cwd=self.repo_root,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                active_branches = len([line for line in result.stdout.split('\n') if line.strip()])
        
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            pass  # Git not available or other error
        
        return {
            "size_mb": size_mb,
            "file_count": file_count,
            "last_commit_hours": last_commit_hours,
            "active_branches": active_branches
        }
    
    def _calculate_health_score(self) -> float:
        """Calculate overall repository health score."""
        if not self.quality_metrics:
            return 50.0  # Default medium health
        
        total_metrics = self.quality_metrics.get("total_metrics")
        if not total_metrics:
            return 50.0
        
        # Calculate health based on various factors
        overall_score = getattr(total_metrics, 'overall_score', lambda: 50.0)()
        security_issues = getattr(total_metrics, 'security_issues', 0)
        technical_debt_hours = getattr(total_metrics, 'technical_debt', 0) / 60
        
        # Health factors
        quality_factor = overall_score / 100
        security_factor = max(0, 1 - (security_issues * 0.1))
        debt_factor = max(0, 1 - (technical_debt_hours / 24))  # Penalty for >24h debt
        
        health_score = (quality_factor * 0.5 + security_factor * 0.3 + debt_factor * 0.2) * 100
        return max(0, min(100, health_score))
    
    async def analyze_quality(self) -> Dict[str, Any]:
        """Perform comprehensive quality analysis."""
        logger.info("Starting comprehensive quality analysis")
        
        # Run repository analysis
        analysis_results = self.quality_analyzer.analyze_repository()
        
        # Store results
        self.quality_metrics = analysis_results
        self.last_analysis_time = datetime.now()
        
        # Update MAPE-K metrics
        total_metrics = analysis_results.get("total_metrics")
        if total_metrics:
            self.metrics.set_gauge("quality_score", total_metrics.overall_score())
            self.metrics.set_gauge("security_issues", float(total_metrics.security_issues))
            self.metrics.set_gauge("technical_debt", float(total_metrics.technical_debt))
            self.metrics.set_gauge("test_coverage", total_metrics.test_coverage)
            self.metrics.set_gauge("complexity_score", total_metrics.complexity_score)
        
        # Generate improvement suggestions
        self.improvement_queue = self._generate_improvements(analysis_results)
        
        # Log summary
        logger.info(f"Quality analysis completed:")
        logger.info(f"  Files analyzed: {analysis_results['files_analyzed']}")
        logger.info(f"  Overall quality: {total_metrics.overall_score():.1f}/100")
        logger.info(f"  Security issues: {total_metrics.security_issues}")
        logger.info(f"  Technical debt: {total_metrics.technical_debt} minutes")
        logger.info(f"  Improvements suggested: {len(self.improvement_queue)}")
        
        return analysis_results
    
    def _generate_improvements(self, analysis_results: Dict[str, Any]) -> List[QualityImprovement]:
        """Generate improvement suggestions based on analysis."""
        improvements = []
        total_metrics = analysis_results.get("total_metrics")
        
        if not total_metrics:
            return improvements
        
        # Security improvements
        if total_metrics.security_issues > 0:
            security_issues = analysis_results.get("security_issues", [])
            for issue in security_issues[:5]:  # Top 5 issues
                improvements.append(QualityImprovement(
                    action_type="FIX_SECURITY",
                    file_path=issue.get("file_path", ""),
                    description=f"Fix {issue.get('category', 'security')} issue: {issue.get('description', '')}",
                    priority=issue.get("severity", "MEDIUM"),
                    estimated_effort=30,
                    automated=False
                ))
        
        # Test coverage improvements
        if total_metrics.test_coverage < self.thresholds.min_test_coverage:
            improvements.append(QualityImprovement(
                action_type="ADD_TESTS",
                file_path="multiple",
                description=f"Increase test coverage from {total_metrics.test_coverage:.1f}% to {self.thresholds.min_test_coverage}%",
                priority="HIGH",
                estimated_effort=120,
                automated=False
            ))
        
        # Complexity improvements
        if total_metrics.complexity_score > self.thresholds.max_complexity:
            improvements.append(QualityImprovement(
                action_type="REFACTOR",
                file_path="high_complexity_files",
                description=f"Reduce complexity from {total_metrics.complexity_score:.1f} to {self.thresholds.max_complexity}",
                priority="MEDIUM",
                estimated_effort=180,
                automated=False
            ))
        
        # Technical debt improvements
        tech_debt_hours = total_metrics.technical_debt / 60
        if tech_debt_hours > self.thresholds.max_technical_debt_hours:
            improvements.append(QualityImprovement(
                action_type="REFACTOR",
                file_path="technical_debt",
                description=f"Address {tech_debt_hours:.1f} hours of technical debt",
                priority="MEDIUM",
                estimated_effort=int(tech_debt_hours * 60),
                automated=False
            ))
        
        # Style improvements
        if total_metrics.style_violations > 20:
            improvements.append(QualityImprovement(
                action_type="FORMAT_CODE",
                file_path="style_violations",
                description=f"Fix {total_metrics.style_violations} style violations",
                priority="LOW",
                estimated_effort=60,
                automated=True  # Can be automated with formatters
            ))
        
        # Sort by priority
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        improvements.sort(key=lambda x: priority_order.get(x.priority, 3))
        
        return improvements
    
    def get_quality_report(self) -> Dict[str, Any]:
        """Get comprehensive quality report."""
        if not self.quality_metrics:
            return {"error": "No analysis data available. Run analyze_quality() first."}
        
        return {
            "report_timestamp": datetime.now().isoformat(),
            "last_analysis": self.last_analysis_time.isoformat() if self.last_analysis_time else None,
            "quality_metrics": self.quality_metrics,
            "thresholds": {
                "min_overall_score": self.thresholds.min_overall_score,
                "max_complexity": self.thresholds.max_complexity,
                "min_test_coverage": self.thresholds.min_test_coverage,
                "max_security_issues": self.thresholds.max_security_issues,
                "max_technical_debt_hours": self.thresholds.max_technical_debt_hours,
                "min_maintainability": self.thresholds.min_maintainability
            },
            "improvement_queue": [
                {
                    "action_type": imp.action_type,
                    "file_path": imp.file_path,
                    "description": imp.description,
                    "priority": imp.priority,
                    "estimated_effort": imp.estimated_effort,
                    "automated": imp.automated
                }
                for imp in self.improvement_queue
            ],
            "mapek_metrics": self.metrics.get_stats_snapshot()
        }
    
    async def execute_improvement(self, improvement: QualityImprovement) -> bool:
        """
        Execute a quality improvement action.
        
        Args:
            improvement: The improvement to execute
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Executing improvement: {improvement.description}")
        
        try:
            if improvement.action_type == "FORMAT_CODE" and improvement.automated:
                success = await self._auto_format_code()
            elif improvement.action_type == "FIX_SECURITY":
                success = await self._suggest_security_fix(improvement)
            elif improvement.action_type == "ADD_TESTS":
                success = await self._suggest_test_addition(improvement)
            elif improvement.action_type == "REFACTOR":
                success = await self._suggest_refactoring(improvement)
            else:
                logger.warning(f"Unknown improvement type: {improvement.action_type}")
                return False
            
            if success:
                self.metrics.increment_counter("improvements_executed")
                logger.info(f"Successfully executed: {improvement.description}")
            else:
                logger.warning(f"Failed to execute: {improvement.description}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error executing improvement {improvement.description}: {e}")
            return False
    
    async def _auto_format_code(self) -> bool:
        """Automatically format code using available tools."""
        try:
            # Try Python formatting with black
            import subprocess
            
            result = subprocess.run(
                ["black", "--check", "--diff", str(self.repo_root)],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode != 0:
                # Format the code
                result = subprocess.run(
                    ["black", str(self.repo_root)],
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                return result.returncode == 0
            
            return True  # Already formatted
            
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            logger.warning("Black formatter not available or failed")
            return False
    
    async def _suggest_security_fix(self, improvement: QualityImprovement) -> bool:
        """
        Suggest and apply security fix using CodeQualityAnalyzer.
        
        Args:
            improvement: Quality improvement with security issue details
            
        Returns:
            True if fix was suggested/applied successfully
        """
        try:
            file_path = Path(improvement.file_path)
            if not file_path.exists():
                logger.warning(f"File not found: {improvement.file_path}")
                return False
            
            # Analyze file for security issues
            metrics = self.analyzer.analyze_file(str(file_path))
            
            if metrics.security_issues == 0:
                logger.info(f"No security issues found in {improvement.file_path}")
                return True
            
            # Generate security fix suggestions based on detected issues
            suggestions = []
            
            # Read file content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for common security patterns and suggest fixes
            from src.quality.code_quality_analyzer import CodeQualityAnalyzer
            
            # Detect hardcoded secrets
            if 'HARDCODED_SECRET' in improvement.description or 'password' in content.lower() or 'api_key' in content.lower():
                suggestions.append({
                    'type': 'HARDCODED_SECRET',
                    'fix': 'Replace hardcoded secrets with environment variables or secure vault',
                    'example': 'password = os.getenv("PASSWORD") or use keyring library'
                })
            
            # Detect SQL injection
            if 'SQL_INJECTION' in improvement.description or 'execute(' in content:
                suggestions.append({
                    'type': 'SQL_INJECTION',
                    'fix': 'Use parameterized queries instead of string concatenation',
                    'example': 'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))'
                })
            
            # Detect weak crypto
            if 'WEAK_CRYPTO' in improvement.description or 'md5(' in content.lower() or 'sha1(' in content.lower():
                suggestions.append({
                    'type': 'WEAK_CRYPTO',
                    'fix': 'Replace MD5/SHA1 with SHA-256 or stronger hashing algorithms',
                    'example': 'import hashlib; hashlib.sha256(data).hexdigest()'
                })
            
            # Log suggestions
            logger.info(f"Security fix suggestions for {improvement.file_path}:")
            for suggestion in suggestions:
                logger.info(f"  - {suggestion['type']}: {suggestion['fix']}")
                logger.info(f"    Example: {suggestion['example']}")
            
            # Store suggestions for manual review or automated fixing
            suggestion_file = file_path.parent / f"{file_path.stem}_security_fixes.json"
            with open(suggestion_file, 'w') as f:
                json.dump({
                    'file': str(file_path),
                    'timestamp': datetime.now().isoformat(),
                    'suggestions': suggestions,
                    'original_issue': improvement.description
                }, f, indent=2)
            
            logger.info(f"✅ Security fix suggestions saved to {suggestion_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error suggesting security fix: {e}", exc_info=True)
            return False
    
    async def _suggest_test_addition(self, improvement: QualityImprovement) -> bool:
        """
        Suggest test addition using code analysis.
        
        Args:
            improvement: Quality improvement with test coverage details
            
        Returns:
            True if test suggestions were generated successfully
        """
        try:
            file_path = Path(improvement.file_path)
            if not file_path.exists():
                logger.warning(f"File not found: {improvement.file_path}")
                return False
            
            # Analyze file to identify functions/classes that need tests
            import ast
            with open(file_path, 'r', encoding='utf-8') as f:
                try:
                    tree = ast.parse(f.read())
                except SyntaxError:
                    logger.warning(f"Syntax error in {file_path}, cannot generate test suggestions")
                    return False
            
            # Find functions and classes
            functions = []
            classes = []
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    functions.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    classes.append(node.name)
            
            # Generate test file path
            test_dir = file_path.parent / 'tests'
            test_dir.mkdir(exist_ok=True)
            test_file = test_dir / f"test_{file_path.stem}.py"
            
            # Check if test file already exists
            if test_file.exists():
                logger.info(f"Test file already exists: {test_file}")
                return True
            
            # Generate basic test template
            test_content = f'''"""
Test file for {file_path.name}
Generated by MAPE-K Quality Monitor
"""
import pytest
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from {file_path.stem} import {', '.join(classes + functions[:3]) if classes or functions else '*'}


class Test{file_path.stem.capitalize()}:
    """Test cases for {file_path.name}"""
    
'''
            
            # Add test methods for each function
            for func_name in functions[:5]:  # Limit to first 5 functions
                test_content += f'''    def test_{func_name}(self):
        """Test {func_name} function"""
        # Test implementation should be added here
        # Example:
        # result = {func_name}(...)
        # assert result is not None
        pass

'''
            
            # Write test file
            with open(test_file, 'w') as f:
                f.write(test_content)
            
            logger.info(f"✅ Test file generated: {test_file}")
            logger.info(f"   Suggested tests for {len(functions)} functions and {len(classes)} classes")
            return True
            
        except Exception as e:
            logger.error(f"Error suggesting test addition: {e}", exc_info=True)
            return False
    
    async def _suggest_refactoring(self, improvement: QualityImprovement) -> bool:
        """
        Suggest refactoring based on complexity and code quality metrics.
        
        Args:
            improvement: Quality improvement with refactoring details
            
        Returns:
            True if refactoring suggestions were generated successfully
        """
        try:
            file_path = Path(improvement.file_path)
            if not file_path.exists():
                logger.warning(f"File not found: {improvement.file_path}")
                return False
            
            # Analyze file for complexity and quality issues
            metrics = self.analyzer.analyze_file(str(file_path))
            
            suggestions = []
            
            # High complexity - suggest breaking into smaller functions
            if metrics.complexity_score > 15:
                suggestions.append({
                    'type': 'HIGH_COMPLEXITY',
                    'severity': 'HIGH',
                    'suggestion': f'Complexity score is {metrics.complexity_score:.1f} (threshold: 15). Consider breaking large functions into smaller, focused functions.',
                    'action': 'Extract methods, reduce nesting, simplify control flow'
                })
            
            # Low maintainability - suggest improvements
            if metrics.maintainability_index < 60:
                suggestions.append({
                    'type': 'LOW_MAINTAINABILITY',
                    'severity': 'MEDIUM',
                    'suggestion': f'Maintainability index is {metrics.maintainability_index:.1f} (threshold: 60). Improve code readability and structure.',
                    'action': 'Add docstrings, improve naming, reduce duplication'
                })
            
            # High duplication - suggest DRY principles
            if metrics.duplicate_code > 10:
                suggestions.append({
                    'type': 'CODE_DUPLICATION',
                    'severity': 'MEDIUM',
                    'suggestion': f'Duplicate code detected ({metrics.duplicate_code:.1f}%). Extract common patterns into reusable functions.',
                    'action': 'Create utility functions, use inheritance/composition'
                })
            
            # Read file to analyze structure
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Detect long functions (more than 50 lines)
            import ast
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        func_lines = node.end_lineno - node.lineno if hasattr(node, 'end_lineno') else len([l for l in lines[node.lineno-1:] if l.strip()])
                        if func_lines > 50:
                            suggestions.append({
                                'type': 'LONG_FUNCTION',
                                'severity': 'MEDIUM',
                                'suggestion': f'Function {node.name} is {func_lines} lines long. Consider splitting into smaller functions.',
                                'action': f'Extract logic from {node.name} into helper functions'
                            })
            except SyntaxError:
                pass
            
            if not suggestions:
                logger.info(f"No refactoring suggestions for {improvement.file_path}")
                return True
            
            # Log suggestions
            logger.info(f"Refactoring suggestions for {improvement.file_path}:")
            for suggestion in suggestions:
                logger.info(f"  [{suggestion['severity']}] {suggestion['type']}: {suggestion['suggestion']}")
                logger.info(f"    Action: {suggestion['action']}")
            
            # Store suggestions
            suggestion_file = file_path.parent / f"{file_path.stem}_refactoring_suggestions.json"
            with open(suggestion_file, 'w') as f:
                json.dump({
                    'file': str(file_path),
                    'timestamp': datetime.now().isoformat(),
                    'metrics': {
                        'complexity': metrics.complexity_score,
                        'maintainability': metrics.maintainability_index,
                        'duplication': metrics.duplicate_code
                    },
                    'suggestions': suggestions
                }, f, indent=2)
            
            logger.info(f"✅ Refactoring suggestions saved to {suggestion_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error suggesting refactoring: {e}", exc_info=True)
            return False
