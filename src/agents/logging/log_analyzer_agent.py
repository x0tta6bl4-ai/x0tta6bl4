# 🤖 Log Analyzer Agent - x0tta6bl4
"""
Log Analyzer Agent - анализ логов на ошибки, паттерн detection и root cause analysis.
Интегрируется с существующим causal analysis engine.
"""

import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Уровень логирования."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class IssueSeverity(Enum):
    """Серьёзность обнаруженной проблемы."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class LogEntry:
    """Одна строка лога."""
    timestamp: datetime
    level: LogLevel
    source: str
    message: str
    metadata: dict = field(default_factory=dict)


@dataclass
class LogPattern:
    """Обнаруженный паттерн в логах."""
    pattern_id: str
    description: str
    regex: str
    occurrence_count: int
    first_seen: datetime
    last_seen: datetime
    severity: IssueSeverity


@dataclass
class DetectedIssue:
    """Обнаруженная проблема."""
    id: str
    title: str
    description: str
    severity: IssueSeverity
    root_cause: Optional[str]
    suggested_fix: str
    related_patterns: list[str]
    first_occurrence: datetime
    last_occurrence: datetime
    occurrence_count: int


class LogAnalyzerAgent:
    """
    Log Analyzer Agent для x0tta6bl4.
    
    Анализирует логи на ошибки, обнаруживает паттерны,
    проводит root cause analysis и даёт рекомендации по исправлению.
    """
    
    # Известные паттерны ошибок
    DEFAULT_PATTERNS = [
        {
            "id": "connection_timeout",
            "regex": r"connection (timed? ?out|reset|refused)",
            "description": "Проблемы с соединением",
            "severity": IssueSeverity.HIGH,
        },
        {
            "id": "memory_error",
            "regex": r"(out of memory|OOM|MemoryError|ENOMEM)",
            "description": "Ошибки памяти",
            "severity": IssueSeverity.CRITICAL,
        },
        {
            "id": "database_error",
            "regex": r"(database|postgres|sql) (error|timeout|connection)",
            "description": "Ошибки базы данных",
            "severity": IssueSeverity.HIGH,
        },
        {
            "id": "authentication_error",
            "regex": r"(authentication|auth) (failed|error|denied)",
            "description": "Ошибки аутентификации",
            "severity": IssueSeverity.MEDIUM,
        },
        {
            "id": "mesh_disconnect",
            "regex": r"(mesh|node) (disconnect|unreachable|down)",
            "description": "Проблемы с mesh сетью",
            "severity": IssueSeverity.HIGH,
        },
        {
            "id": "pqc_error",
            "regex": r"(pqc|post-quantum|crypto) (error|failed|invalid)",
            "description": "Ошибки пост-квантовой криптографии",
            "severity": IssueSeverity.CRITICAL,
        },
        {
            "id": "rate_limit",
            "regex": r"(rate limit|too many requests|429)",
            "description": "Превышение rate limit",
            "severity": IssueSeverity.LOW,
        },
        {
            "id": "spiffe_error",
            "regex": r"(spiffe SPIRE) (error|failed|invalid)",
            "description": "Ошибки SPIFFE/SPIRE identity",
            "severity": IssueSeverity.HIGH,
        },
    ]
    
    def __init__(self, config: Optional[dict] = None):
        """
        Инициализация Log Analyzer Agent.
        
        Args:
            config: Конфигурация агента
        """
        self.config = config or self._default_config()
        
        # Компилированные паттерны
        self.patterns: list[dict] = []
        self._compile_patterns()
        
        # Логи
        self.log_buffer: list[LogEntry] = []
        self.max_buffer_size = self.config.get("max_buffer_size", 10000)
        
        # Обнаруженные паттерны и проблемы
        self.detected_patterns: dict[str, LogPattern] = {}
        self.detected_issues: dict[str, DetectedIssue] = {}
        
        # Root cause rules
        self.root_cause_rules = self._build_root_cause_rules()
        
        logger.info("Log Analyzer Agent initialized")
    
    def _default_config(self) -> dict:
        """Дефолтная конфигурация."""
        return {
            "log_sources": [
                "api",
                "database", 
                "mesh",
                "security",
                "federated_learning",
            ],
            "check_interval_seconds": 60,
            "max_buffer_size": 10000,
            "min_occurrences_for_issue": 3,
            "pattern_window_minutes": 5,
        }
    
    def _compile_patterns(self) -> None:
        """Компиляция регулярных выражений для паттернов."""
        for pattern in self.DEFAULT_PATTERNS:
            compiled = pattern.copy()
            compiled["regex_compiled"] = re.compile(pattern["regex"], re.IGNORECASE)
            self.patterns.append(compiled)
    
    def _build_root_cause_rules(self) -> dict:
        """Построение правил для root cause analysis."""
        return {
            "connection_timeout": {
                "possible_causes": [
                    "Network connectivity issue",
                    "Service overload",
                    "Firewall blocking",
                    "DNS resolution failure",
                ],
                "fix": "Check network connectivity and service status",
            },
            "memory_error": {
                "possible_causes": [
                    "Memory leak in application",
                    "Insufficient resources",
                    "Large data processing",
                ],
                "fix": "Increase memory limits, check for leaks",
            },
            "database_error": {
                "possible_causes": [
                    "Database overload",
                    "Connection pool exhausted",
                    "Query timeout",
                    "Database unreachable",
                ],
                "fix": "Check database health and connection pool",
            },
            "pqc_error": {
                "possible_causes": [
                    "Invalid PQC key",
                    "Crypto library issue",
                    "Key rotation needed",
                ],
                "fix": "Verify PQC keys and crypto configuration",
            },
        }
    
    async def analyze_logs(self, logs: list[str]) -> dict:
        """
        Анализ списка логов.
        
        Args:
            logs: Список строк логов
            
        Returns:
            Результаты анализа
        """
        # Парсинг логов
        parsed_logs = []
        for log_line in logs:
            entry = self._parse_log_line(log_line)
            if entry:
                parsed_logs.append(entry)
        
        # Сохранение в буфер
        self.log_buffer.extend(parsed_logs)
        if len(self.log_buffer) > self.max_buffer_size:
            self.log_buffer = self.log_buffer[-self.max_buffer_size:]
        
        # Анализ паттернов
        patterns = await self._detect_patterns(parsed_logs)
        
        # Анализ проблем
        issues = await self._detect_issues(patterns)
        
        # Root cause analysis
        for issue in issues.values():
            if issue.root_cause is None:
                issue.root_cause = self._analyze_root_cause(issue)
        
        return {
            "patterns": patterns,
            "issues": issues,
            "summary": self._generate_summary(issues),
        }
    
    def _parse_log_line(self, line: str) -> Optional[LogEntry]:
        """Парсинг одной строки лога."""
        try:
            # Простой парсинг - ищем уровень
            level = LogLevel.INFO
            if re.search(r"\bERROR\b", line, re.IGNORECASE):
                level = LogLevel.ERROR
            elif re.search(r"\bWARN(?:ING)?\b", line, re.IGNORECASE):
                level = LogLevel.WARNING
            elif re.search(r"\bDEBUG\b", line, re.IGNORECASE):
                level = LogLevel.DEBUG
            elif re.search(r"\bCRITICAL\b", line, re.IGNORECASE):
                level = LogLevel.CRITICAL
            
            # Ищем источник
            source = "unknown"
            for src in self.config["log_sources"]:
                if src in line.lower():
                    source = src
                    break
            
            return LogEntry(
                timestamp=datetime.utcnow(),
                level=level,
                source=source,
                message=line,
            )
        except Exception as e:
            logger.debug(f"Failed to parse log line: {e}")
            return None
    
    async def _detect_patterns(self, logs: list[LogEntry]) -> dict[str, LogPattern]:
        """Обнаружение паттернов в логах."""
        now = datetime.utcnow()
        window = timedelta(minutes=self.config["pattern_window_minutes"])
        
        # Подсчёт вхождений паттернов
        pattern_counts: dict[str, list[datetime]] = defaultdict(list)
        
        for log in logs:
            for pattern in self.patterns:
                if pattern["regex_compiled"].search(log.message):
                    pattern_counts[pattern["id"]].append(log.timestamp)
        
        # Формирование обнаруженных паттернов
        detected = {}
        for pattern_id, timestamps in pattern_counts.items():
            if not timestamps:
                continue
            
            # Фильтр по окну
            recent = [t for t in timestamps if (now - t) <= window]
            if len(recent) < 2:
                continue
            
            pattern_info = next(p for p in self.patterns if p["id"] == pattern_id)
            
            detected[pattern_id] = LogPattern(
                pattern_id=pattern_id,
                description=pattern_info["description"],
                regex=pattern_info["regex"],
                occurrence_count=len(recent),
                first_seen=min(recent),
                last_seen=max(recent),
                severity=pattern_info["severity"],
            )
        
        self.detected_patterns = detected
        return detected
    
    async def _detect_issues(self, patterns: dict[str, LogPattern]) -> dict[str, DetectedIssue]:
        """Обнаружение проблем на основе паттернов."""
        issues = {}
        min_occurrences = self.config["min_occurrences_for_issue"]
        
        for pattern_id, pattern in patterns.items():
            if pattern.occurrence_count >= min_occurrences:
                issue_id = f"issue-{pattern_id}"
                
                if issue_id in self.detected_issues:
                    # Обновление существующей проблемы
                    issue = self.detected_issues[issue_id]
                    issue.occurrence_count = pattern.occurrence_count
                    issue.last_occurrence = pattern.last_seen
                else:
                    # Новая проблема
                    root_cause_rules = self.root_cause_rules.get(pattern_id, {})
                    
                    issue = DetectedIssue(
                        id=issue_id,
                        title=pattern.description,
                        description=f"Обнаружено {pattern.occurrence_count} вхождений паттерна '{pattern.description}'",
                        severity=pattern.severity,
                        root_cause=None,
                        suggested_fix=root_cause_rules.get("fix", "Investigate logs for root cause"),
                        related_patterns=[pattern_id],
                        first_occurrence=pattern.first_seen,
                        last_occurrence=pattern.last_seen,
                        occurrence_count=pattern.occurrence_count,
                    )
                    issues[issue_id] = issue
        
        self.detected_issues.update(issues)
        return issues
    
    def _analyze_root_cause(self, issue: DetectedIssue) -> str:
        """Анализ root cause для проблемы."""
        rules = self.root_cause_rules.get(issue.id.replace("issue-", ""), {})
        
        if not rules:
            return "Root cause unknown - manual investigation required"
        
        possible_causes = rules.get("possible_causes", [])
        
        # Простая эвристика - возвращаем первую наиболее вероятную причину
        return f"Likely cause: {possible_causes[0] if possible_causes else 'Unknown'}"
    
    def _generate_summary(self, issues: dict[str, DetectedIssue]) -> dict:
        """Генерация сводки по анализу."""
        severity_counts = defaultdict(int)
        for issue in issues.values():
            severity_counts[issue.severity.value] += 1
        
        return {
            "total_issues": len(issues),
            "by_severity": dict(severity_counts),
            "critical_issues": [
                {
                    "id": i.id,
                    "title": i.title,
                    "root_cause": i.root_cause,
                    "fix": i.suggested_fix,
                }
                for i in issues.values()
                if i.severity == IssueSeverity.CRITICAL
            ],
            "needs_attention": len([i for i in issues.values() if i.severity in (IssueSeverity.HIGH, IssueSeverity.CRITICAL)]),
        }
    
    async def get_current_status(self) -> dict:
        """Получение текущего статуса анализа."""
        return {
            "buffer_size": len(self.log_buffer),
            "detected_patterns": len(self.detected_patterns),
            "detected_issues": len(self.detected_issues),
            "patterns": [
                {
                    "id": p.pattern_id,
                    "description": p.description,
                    "occurrences": p.occurrence_count,
                    "severity": p.severity.value,
                }
                for p in self.detected_patterns.values()
            ],
            "issues": [
                {
                    "id": i.id,
                    "title": i.title,
                    "severity": i.severity.value,
                    "root_cause": i.root_cause,
                    "fix": i.suggested_fix,
                    "occurrences": i.occurrence_count,
                }
                for i in self.detected_issues.values()
            ],
        }
    
    def add_pattern(self, pattern_id: str, regex: str, description: str, severity: IssueSeverity) -> None:
        """Добавление нового паттерна для мониторинга."""
        compiled = re.compile(regex, re.IGNORECASE)
        self.patterns.append({
            "id": pattern_id,
            "regex": regex,
            "regex_compiled": compiled,
            "description": description,
            "severity": severity,
        })
        logger.info(f"Added custom pattern: {pattern_id}")


# Синглтон экземпляр
_log_analyzer_instance: Optional[LogAnalyzerAgent] = None


async def get_log_analyzer() -> LogAnalyzerAgent:
    """Получение синглтона Log Analyzer Agent."""
    global _log_analyzer_instance
    if _log_analyzer_instance is None:
        _log_analyzer_instance = LogAnalyzerAgent()
    return _log_analyzer_instance
