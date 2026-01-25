#!/usr/bin/env python3
"""
x0tta6bl4 Code Quality Analyzer
============================================

Automated code quality analysis for MAPE-K integration.
Analyzes codebase quality metrics and provides actionable insights.

Features:
- Multi-language support (Python, JavaScript, Rust, Go)
- Complexity analysis
- Security vulnerability detection
- Code style compliance
- Technical debt assessment
- Trend analysis
"""

import os
import ast
import json
import time
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, Counter
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

@dataclass
class QualityMetrics:
    """Code quality metrics for a file or component."""
    file_path: str
    language: str
    lines_of_code: int
    complexity_score: float
    maintainability_index: float
    test_coverage: float
    security_issues: int
    style_violations: int
    duplicate_code: float
    technical_debt: int  # minutes
    timestamp: datetime = field(default_factory=datetime.now)
    
    def overall_score(self) -> float:
        """Calculate overall quality score (0-100)."""
        scores = [
            max(0, 100 - self.complexity_score * 2),  # Complexity penalty
            self.maintainability_index,
            self.test_coverage,
            max(0, 100 - self.security_issues * 10),  # Security penalty
            max(0, 100 - self.style_violations * 5),  # Style penalty
            max(0, 100 - self.duplicate_code * 20),  # Duplication penalty
        ]
        return sum(scores) / len(scores)

class CodeQualityAnalyzer:
    """
    Comprehensive code quality analyzer.
    
    Supports multiple analysis techniques:
    - AST parsing for Python
    - Regex patterns for security issues
    - Complexity metrics calculation
    - Style checking integration
    - Test coverage analysis
    """
    
    def __init__(self, repo_root: str):
        self.repo_root = Path(repo_root)
        self.quality_history: List[Dict] = []
        self.max_history_size = 100
        
        # Security patterns for vulnerability detection
        self.security_patterns = {
            'HARDCODED_SECRET': [
                r'password\s*=\s*["\'][^"\']+["\']',
                r'api_key\s*=\s*["\'][^"\']+["\']',
                r'secret\s*=\s*["\'][^"\']+["\']',
                r'token\s*=\s*["\'][^"\']+["\']',
            ],
            'SQL_INJECTION': [
                r'execute\s*\(\s*["\'].*%s["\']',
                r'cursor\.execute\s*\(\s*["\'].*\+.*["\']',
                r'f["\'].*SELECT.*{.*}.*["\']',
            ],
            'XSS': [
                r'innerHTML\s*=',
                r'outerHTML\s*=',
                r'document\.write\s*\(',
            ],
            'PATH_TRAVERSAL': [
                r'open\s*\(\s*.*\+\s*.*\)',
                r'file\s*\(\s*.*\+\s*.*\)',
                r'Path\s*\(\s*.*\+\s*.*\)',
            ],
            'WEAK_CRYPTO': [
                r'md5\s*\(',
                r'sha1\s*\(',
                r'DES\s*\(',
                r'RC4\s*\(',
            ]
        }
        
        logger.info(f"CodeQualityAnalyzer initialized for {repo_root}")
    
    def analyze_file(self, file_path: str) -> QualityMetrics:
        """Analyze a single file for quality metrics."""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        language = self._detect_language(path)
        
        # Read file content
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()
        
        # Calculate metrics
        lines_of_code = self._count_lines_of_code(content)
        complexity_score = self._calculate_complexity(content, language)
        maintainability_index = self._calculate_maintainability(content, language)
        test_coverage = self._estimate_test_coverage(path, content)
        security_issues = len(self._detect_security_issues(content, file_path))
        style_violations = self._check_style_compliance(content, language)
        duplicate_code = self._detect_duplicates(content)
        technical_debt = self._calculate_technical_debt(
            complexity_score, security_issues, style_violations
        )
        
        return QualityMetrics(
            file_path=str(path),
            language=language,
            lines_of_code=lines_of_code,
            complexity_score=complexity_score,
            maintainability_index=maintainability_index,
            test_coverage=test_coverage,
            security_issues=security_issues,
            style_violations=style_violations,
            duplicate_code=duplicate_code,
            technical_debt=technical_debt
        )
    
    def analyze_repository(self) -> Dict[str, Any]:
        """Analyze entire repository for quality metrics."""
        include_patterns = ['*.py', '*.js', '*.ts', '*.go', '*.rs']
        exclude_patterns = [
            '*_test.py', '*_test.js', '*test.go', '*test.rs',
            'node_modules/*', 'vendor/*', 'target/*', '__pycache__/*',
            '.git/*', '*.egg-info/*'
        ]
        
        results = {
            'timestamp': datetime.now().isoformat(),
            'repository': str(self.repo_root),
            'files_analyzed': 0,
            'total_metrics': None,
            'language_breakdown': defaultdict(lambda: {
                'files': 0,
                'lines': 0,
                'avg_quality': 0.0,
                'security_issues': 0
            }),
            'security_issues': [],
            'quality_trends': self._get_recent_trends(),
            'recommendations': []
        }
        
        # Find files to analyze
        files_to_analyze = []
        for pattern in include_patterns:
            files_to_analyze.extend(self.repo_root.rglob(pattern))
        
        # Filter out excluded patterns
        filtered_files = []
        for file_path in files_to_analyze:
            if file_path.is_file():
                exclude = False
                for exclude_pattern in exclude_patterns:
                    if file_path.match(exclude_pattern):
                        exclude = True
                        break
                if not exclude:
                    filtered_files.append(file_path)
        
        logger.info(f"Analyzing {len(filtered_files)} files")
        
        # Analyze each file
        file_metrics = []
        total_metrics = QualityMetrics(
            file_path='TOTAL',
            language='ALL',
            lines_of_code=0,
            complexity_score=0.0,
            maintainability_index=0.0,
            test_coverage=0.0,
            security_issues=0,
            style_violations=0,
            duplicate_code=0.0,
            technical_debt=0
        )
        
        for file_path in filtered_files:
            try:
                metrics = self.analyze_file(str(file_path))
                file_metrics.append(metrics)
                
                # Update totals
                results['files_analyzed'] += 1
                total_metrics.lines_of_code += metrics.lines_of_code
                total_metrics.complexity_score += metrics.complexity_score
                total_metrics.maintainability_index += metrics.maintainability_index
                total_metrics.test_coverage += metrics.test_coverage
                total_metrics.security_issues += metrics.security_issues
                total_metrics.style_violations += metrics.style_violations
                total_metrics.duplicate_code += metrics.duplicate_code
                total_metrics.technical_debt += metrics.technical_debt
                
                # Update language breakdown
                lang_data = results['language_breakdown'][metrics.language]
                lang_data['files'] += 1
                lang_data['lines'] += metrics.lines_of_code
                lang_data['security_issues'] += metrics.security_issues
                
                # Collect security issues
                if metrics.security_issues > 0:
                    issues = self._detect_security_issues(
                        file_path.read_text(encoding='utf-8', errors='ignore'),
                        str(file_path)
                    )
                    results['security_issues'].extend(issues)
                
            except Exception as e:
                logger.warning(f"Failed to analyze {file_path}: {e}")
        
        # Calculate averages
        if results['files_analyzed'] > 0:
            n = results['files_analyzed']
            total_metrics.complexity_score /= n
            total_metrics.maintainability_index /= n
            total_metrics.test_coverage /= n
            total_metrics.duplicate_code /= n
            
            # Language averages
            for lang, data in results['language_breakdown'].items():
                if data['files'] > 0:
                    lang_files = [m for m in file_metrics if m.language == lang]
                    data['avg_quality'] = sum(m.overall_score() for m in lang_files) / len(lang_files)
        
        results['total_metrics'] = total_metrics
        results['recommendations'] = self._generate_recommendations(total_metrics)
        
        # Update trend history
        self._update_trend_history(total_metrics)
        
        return results
    
    def _detect_language(self, file_path: Path) -> str:
        """Detect programming language from file extension."""
        extension_map = {
            '.py': 'PYTHON',
            '.js': 'JAVASCRIPT',
            '.ts': 'TYPESCRIPT',
            '.jsx': 'JAVASCRIPT',
            '.tsx': 'TYPESCRIPT',
            '.go': 'GO',
            '.rs': 'RUST',
            '.c': 'C',
            '.cpp': 'CPP',
            '.h': 'C',
            '.hpp': 'CPP',
            '.java': 'JAVA',
            '.rb': 'RUBY',
            '.php': 'PHP',
            '.cs': 'CSHARP',
        }
        
        ext = file_path.suffix.lower()
        return extension_map.get(ext, 'UNKNOWN')
    
    def _count_lines_of_code(self, content: str) -> int:
        """Count non-empty, non-comment lines of code."""
        lines = content.split('\n')
        loc = 0
        
        in_multiline_comment = False
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Handle multiline comments
            if '"""' in line or "'''" in line:
                in_multiline_comment = not in_multiline_comment
                continue
            
            if in_multiline_comment:
                continue
            
            # Skip single-line comments
            if line.startswith('#') or line.startswith('//') or line.startswith('/*'):
                continue
            
            loc += 1
        
        return loc
    
    def _calculate_complexity(self, content: str, language: str) -> float:
        """Calculate cyclomatic complexity score."""
        if language == 'PYTHON':
            return self._python_complexity(content)
        else:
            return self._generic_complexity(content)
    
    def _python_complexity(self, content: str) -> float:
        """Calculate Python-specific complexity."""
        try:
            tree = ast.parse(content)
            complexity = 1
            
            for node in ast.walk(tree):
                if isinstance(node, (ast.If, ast.While, ast.For, ast.AsyncFor)):
                    complexity += 1
                elif isinstance(node, ast.ExceptHandler):
                    complexity += 1
                elif isinstance(node, (ast.With, ast.AsyncWith)):
                    complexity += 1
                elif isinstance(node, ast.BoolOp):
                    complexity += len(node.values) - 1
            
            return float(complexity)
        except SyntaxError:
            return self._generic_complexity(content)
    
    def _generic_complexity(self, content: str) -> float:
        """Generic complexity calculation using regex patterns."""
        complexity = 1  # Base complexity
        
        complexity_patterns = [
            r'\bif\s+.*:',
            r'\belif\s+.*:',
            r'\bfor\s+.*:',
            r'\bwhile\s+.*:',
            r'\bexcept\s+.*:',
            r'\bwith\s+.*:',
            r'\band\s+',
            r'\bor\s+',
        ]
        
        for pattern in complexity_patterns:
            complexity += len(re.findall(pattern, content, re.MULTILINE))
        
        return float(complexity)
    
    def _calculate_maintainability(self, content: str, language: str) -> float:
        """Calculate maintainability index (0-100)."""
        loc = self._count_lines_of_code(content)
        complexity = self._calculate_complexity(content, language)
        
        # Simplified maintainability index
        if loc == 0:
            return 100.0
        
        # Factors that reduce maintainability
        volume_factor = min(1.0, loc / 1000)  # Large files are harder to maintain
        complexity_factor = min(1.0, complexity / 20)  # High complexity reduces maintainability
        
        maintainability = 100 * (1 - volume_factor * 0.3 - complexity_factor * 0.4)
        return max(0, min(100, maintainability))
    
    def _estimate_test_coverage(self, file_path: Path, content: str) -> float:
        """Estimate test coverage based on test files and assertions."""
        # Look for corresponding test files
        test_patterns = [
            f"test_{file_path.name}",
            f"{file_path.stem}_test{file_path.suffix}",
            f"{file_path.stem}_spec{file_path.suffix}"
        ]
        
        has_test_file = False
        for pattern in test_patterns:
            if (file_path.parent / pattern).exists():
                has_test_file = True
                break
        
        # Check for test indicators in the code
        test_indicators = [
            r'\bdef test_',
            r'\bit\s*\(',
            r'\btest\s*\(',
            r'\bdescribe\s*\(',
            r'\bassert\s+',
            r'\bexpect\s*\(',
        ]
        
        test_count = sum(len(re.findall(pattern, content)) for pattern in test_indicators)
        
        # Simple coverage estimation
        if has_test_file:
            base_coverage = 60.0
        else:
            base_coverage = 20.0
        
        # Bonus for test indicators
        coverage_bonus = min(40.0, test_count * 5.0)
        
        return min(100.0, base_coverage + coverage_bonus)
    
    def _detect_security_issues(self, content: str, file_path: str) -> List[Dict]:
        """Detect security vulnerabilities using pattern matching."""
        issues = []
        lines = content.split('\n')
        
        for category, patterns in self.security_patterns.items():
            for pattern in patterns:
                for line_num, line in enumerate(lines, 1):
                    matches = re.finditer(pattern, line, re.IGNORECASE)
                    for match in matches:
                        severity = self._determine_severity(category)
                        
                        issue = {
                            'file_path': file_path,
                            'line_number': line_num,
                            'severity': severity,
                            'category': category,
                            'description': f"Potential {category.replace('_', ' ')} vulnerability",
                            'code_snippet': line.strip()
                        }
                        issues.append(issue)
        
        return issues
    
    def _determine_severity(self, category: str) -> str:
        """Determine severity level for security issue category."""
        severity_map = {
            'HARDCODED_SECRET': 'HIGH',
            'SQL_INJECTION': 'CRITICAL',
            'XSS': 'HIGH',
            'PATH_TRAVERSAL': 'HIGH',
            'WEAK_CRYPTO': 'MEDIUM',
        }
        return severity_map.get(category, 'LOW')
    
    def _check_style_compliance(self, content: str, language: str) -> int:
        """Check code style compliance (returns violation count)."""
        violations = 0
        
        # Generic style checks
        style_patterns = [
            (r'\s+$', 'Trailing whitespace'),
            (r'\t', 'Tab characters'),
            (r'.{120,}', 'Line too long (>120 chars)'),
        ]
        
        for pattern, description in style_patterns:
            violations += len(re.findall(pattern, content, re.MULTILINE))
        
        # Language-specific checks
        if language == 'PYTHON':
            violations += self._python_style_checks(content)
        
        return violations
    
    def _python_style_checks(self, content: str) -> int:
        """Python-specific style checks."""
        violations = 0
        
        # PEP 8 style violations
        violations += len(re.findall(r'class\s+[a-z]', content))  # Class name should be CamelCase
        violations += len(re.findall(r'def\s+[A-Z]', content))  # Function name should be snake_case
        violations += len(re.findall(r'import\s+\*', content))  # Wildcard import
        
        return violations
    
    def _detect_duplicates(self, content: str) -> float:
        """Detect code duplication (returns percentage)."""
        lines = [line.strip() for line in content.split('\n') if line.strip()]
        
        if len(lines) < 10:
            return 0.0
        
        # Simple duplicate detection using line similarity
        duplicates = 0
        compared_pairs = 0
        
        for i in range(len(lines)):
            for j in range(i + 1, len(lines)):
                if len(lines[i]) > 10 and len(lines[j]) > 10:
                    similarity = self._line_similarity(lines[i], lines[j])
                    if similarity > 0.8:
                        duplicates += 1
                    compared_pairs += 1
        
        if compared_pairs == 0:
            return 0.0
        
        return (duplicates / compared_pairs) * 100
    
    def _line_similarity(self, line1: str, line2: str) -> float:
        """Calculate similarity between two lines."""
        words1 = set(line1.split())
        words2 = set(line2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    def _calculate_technical_debt(self, complexity: float, security_issues: int, style_violations: int) -> int:
        """Calculate technical debt in minutes."""
        # Base debt from complexity
        complexity_debt = max(0, (complexity - 10) * 5)  # 5 min per complexity point above 10
        
        # Security debt
        security_debt = security_issues * 30  # 30 min per security issue
        
        # Style debt
        style_debt = style_violations * 2  # 2 min per style violation
        
        return int(complexity_debt + security_debt + style_debt)
    
    def _generate_recommendations(self, metrics: QualityMetrics) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []
        
        # Overall quality recommendations
        if metrics.overall_score() < 70:
            recommendations.append("Overall code quality is below threshold. Consider refactoring complex areas.")
        
        # Security recommendations
        if metrics.security_issues > 0:
            recommendations.append(f"Found {metrics.security_issues} security issues. Address critical vulnerabilities first.")
        
        # Test coverage recommendations
        if metrics.test_coverage < 50:
            recommendations.append("Test coverage is low. Add unit tests for critical components.")
        
        # Complexity recommendations
        if metrics.complexity_score > 15:
            recommendations.append("High complexity detected. Consider breaking down large functions.")
        
        # Maintainability recommendations
        if metrics.maintainability_index < 60:
            recommendations.append("Maintainability index is low. Improve code structure and documentation.")
        
        # Style recommendations
        if metrics.style_violations > 50:
            recommendations.append("Many style violations found. Run code formatter and linter.")
        
        return recommendations
    
    def _update_trend_history(self, metrics: QualityMetrics) -> None:
        """Update quality trend history."""
        trend = {
            'timestamp': datetime.now().isoformat(),
            'overall_score': metrics.overall_score(),
            'complexity': metrics.complexity_score,
            'security_issues': float(metrics.security_issues),
            'coverage': metrics.test_coverage,
            'technical_debt': float(metrics.technical_debt)
        }
        
        self.quality_history.append(trend)
        
        # Maintain history size
        if len(self.quality_history) > self.max_history_size:
            self.quality_history = self.quality_history[-self.max_history_size:]
    
    def _get_recent_trends(self, limit: int = 10) -> List[Dict]:
        """Get recent quality trends."""
        recent = self.quality_history[-limit:] if limit else self.quality_history
        return recent
