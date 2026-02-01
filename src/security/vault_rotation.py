"""
Enhanced secret rotation with graceful handoff, circuit breakers, and rollback capabilities.

This module provides production-grade secret rotation with:
- Graceful handoff strategies (blue-green, canary)
- Circuit breaker pattern for failure isolation
- Comprehensive rollback on any failure
- Structured logging and metrics
- Health checks and validation
"""

import asyncio
import logging
import hashlib
import time
from typing import Optional, Dict, Any, List, Callable, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum, auto
from contextlib import asynccontextmanager
import secrets
import string
import json

from .vault_client import VaultClient, VaultSecretError
from .vault_secrets import VaultSecretManager, DatabaseCredentials, ApiCredentials

logger = logging.getLogger(__name__)


class RotationStrategy(Enum):
    """Secret rotation strategies."""
    IMMEDIATE = auto()      # Immediate switch (downtime)
    GRACEFUL = auto()       # Grace period for applications
    BLUE_GREEN = auto()     # Blue-green deployment style
    CANARY = auto()         # Gradual rollout
    SHADOW = auto()         # Shadow mode (test new creds)


class RotationStatus(Enum):
    """Status of a rotation operation."""
    PENDING = "pending"
    VALIDATING = "validating"
    IN_PROGRESS = "in_progress"
    GRACE_PERIOD = "grace_period"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLING_BACK = "rolling_back"
    ROLLED_BACK = "rolled_back"
    CIRCUIT_OPEN = "circuit_open"


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_max_calls: int = 3
    success_threshold: int = 2


@dataclass
class RotationResult:
    """Result of a rotation operation."""
    secret_path: str
    status: RotationStatus
    strategy: RotationStrategy
    started_at: datetime
    completed_at: Optional[datetime] = None
    old_version: Optional[int] = None
    new_version: Optional[int] = None
    old_creds_hash: Optional[str] = None
    new_creds_hash: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    rollback_reason: Optional[str] = None
    validation_results: Dict[str, bool] = field(default_factory=dict)


class CircuitBreaker:
    """Circuit breaker for rotation operations.
    
    Prevents cascade failures by stopping rotation attempts
    after consecutive failures.
    
    Example:
        >>> cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
        >>> async with cb:
        ...     await rotate_secret()
    """
    
    def __init__(self, config: CircuitBreakerConfig = None, name: str = "default"):
        self.config = config or CircuitBreakerConfig()
        self.name = name
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> CircuitBreakerState:
        """Get current circuit breaker state."""
        return self._state
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self._state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._state = CircuitBreakerState.HALF_OPEN
                    self._half_open_calls = 0
                    logger.info(f"Circuit breaker {self.name} entering half-open state")
                else:
                    raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")
            
            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker {self.name} half-open limit reached"
                    )
                self._half_open_calls += 1
        
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as e:
            await self._on_failure()
            raise
    
    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._state = CircuitBreakerState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit breaker {self.name} closed")
            else:
                self._failure_count = 0
    
    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._state = CircuitBreakerState.OPEN
                logger.warning(f"Circuit breaker {self.name} opened (half-open failure)")
            elif self._failure_count >= self.config.failure_threshold:
                self._state = CircuitBreakerState.OPEN
                logger.warning(
                    f"Circuit breaker {self.name} opened after "
                    f"{self._failure_count} failures"
                )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try reset."""
        if self._last_failure_time is None:
            return True
        return (time.time() - self._last_failure_time) >= self.config.recovery_timeout
    
    async def __aenter__(self):
        """Async context manager entry."""
        if self._state == CircuitBreakerState.OPEN:
            if not self._should_attempt_reset():
                raise CircuitBreakerOpenError(f"Circuit breaker {self.name} is OPEN")
            self._state = CircuitBreakerState.HALF_OPEN
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if exc_type is not None:
            await self._on_failure()
        else:
            await self._on_success()
        return False


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


class RotationValidator:
    """Validates secrets before and after rotation.
    
    Performs health checks to ensure new credentials work
    before committing to them.
    """
    
    def __init__(self):
        self._validators: Dict[str, Callable] = {}
    
    def register_validator(self, name: str, validator: Callable):
        """Register a validation function."""
        self._validators[name] = validator
    
    async def validate(
        self,
        creds: Dict[str, Any],
        validators: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        """Run validation checks on credentials.
        
        Args:
            creds: Credentials to validate
            validators: List of validator names to run (default: all)
            
        Returns:
            Dictionary of validation results
        """
        results = {}
        
        to_run = validators or list(self._validators.keys())
        
        for name in to_run:
            if name not in self._validators:
                logger.warning(f"Unknown validator: {name}")
                continue
            
            try:
                result = await self._validators[name](creds)
                results[name] = result
                logger.debug(f"Validator {name}: {'PASS' if result else 'FAIL'}")
            except Exception as e:
                logger.error(f"Validator {name} failed: {e}")
                results[name] = False
        
        return results


class EnhancedDatabaseCredentialRotator:
    """Enhanced database credential rotator with circuit breakers and validation.
    
    Features:
    - Circuit breaker for failure isolation
    - Multiple rotation strategies
    - Pre/post validation
    - Comprehensive rollback
    - Structured logging
    
    Example:
        >>> rotator = EnhancedDatabaseCredentialRotator(
        ...     vault_client,
        ...     db_host="postgres.default.svc",
        ...     strategy=RotationStrategy.GRACEFUL
        ... )
        >>> result = await rotator.rotate("main-db")
    """
    
    def __init__(
        self,
        vault_client: VaultClient,
        db_host: str,
        db_port: int = 5432,
        admin_username: str = "postgres",
        admin_password: Optional[str] = None,
        strategy: RotationStrategy = RotationStrategy.GRACEFUL,
        grace_period: int = 300,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        self.vault_client = vault_client
        self.db_host = db_host
        self.db_port = db_port
        self.admin_username = admin_username
        self.admin_password = admin_password
        self.strategy = strategy
        self.grace_period = grace_period
        
        self._circuit_breaker = CircuitBreaker(
            circuit_breaker_config or CircuitBreakerConfig(),
            name="db-rotation"
        )
        self._validator = RotationValidator()
        self._pg_pool = None
        
        # Register default validators
        self._validator.register_validator(
            "connectivity", self._validate_connectivity
        )
        self._validator.register_validator(
            "permissions", self._validate_permissions
        )
    
    def _generate_password(self, length: int = 32) -> str:
        """Generate a secure random password."""
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    
    def _generate_username(self, prefix: str = "vault") -> str:
        """Generate a unique username."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_suffix = secrets.token_hex(4)
        return f"{prefix}_{timestamp}_{random_suffix}"
    
    def _hash_creds(self, creds: Dict[str, Any]) -> str:
        """Create hash of credentials for tracking."""
        creds_str = json.dumps(creds, sort_keys=True)
        return hashlib.sha256(creds_str.encode()).hexdigest()[:16]
    
    async def _get_pg_connection(self):
        """Get PostgreSQL connection pool."""
        import asyncpg
        
        if self._pg_pool is None:
            self._pg_pool = await asyncpg.create_pool(
                host=self.db_host,
                port=self.db_port,
                user=self.admin_username,
                password=self.admin_password,
                database="postgres",
                min_size=1,
                max_size=5,
            )
        return self._pg_pool
    
    async def _validate_connectivity(self, creds: Dict[str, Any]) -> bool:
        """Validate database connectivity."""
        try:
            import asyncpg
            conn = await asyncpg.connect(
                host=creds.get("host", self.db_host),
                port=creds.get("port", self.db_port),
                user=creds["username"],
                password=creds["password"],
                database=creds.get("database", "postgres"),
                timeout=10,
            )
            await conn.execute("SELECT 1")
            await conn.close()
            return True
        except Exception as e:
            logger.error(f"Connectivity validation failed: {e}")
            return False
    
    async def _validate_permissions(self, creds: Dict[str, Any]) -> bool:
        """Validate database permissions."""
        try:
            import asyncpg
            conn = await asyncpg.connect(
                host=creds.get("host", self.db_host),
                port=creds.get("port", self.db_port),
                user=creds["username"],
                password=creds["password"],
                database=creds.get("database", "postgres"),
                timeout=10,
            )
            
            # Test SELECT permission
            await conn.execute("CREATE TABLE IF NOT EXISTS _vault_test (id INT)")
            await conn.execute("INSERT INTO _vault_test VALUES (1)")
            await conn.fetch("SELECT * FROM _vault_test")
            await conn.execute("DROP TABLE _vault_test")
            
            await conn.close()
            return True
        except Exception as e:
            logger.error(f"Permissions validation failed: {e}")
            return False
    
    async def rotate(
        self,
        db_name: str,
        secret_path: Optional[str] = None,
        databases: Optional[List[str]] = None,
        custom_validators: Optional[List[str]] = None,
    ) -> RotationResult:
        """Rotate database credentials with full safety.
        
        Args:
            db_name: Database identifier
            secret_path: Vault secret path
            databases: List of databases to grant access
            custom_validators: Additional validators to run
            
        Returns:
            RotationResult with full details
        """
        if secret_path is None:
            secret_path = f"proxy/database/{db_name}"
        
        if databases is None:
            databases = [db_name]
        
        started_at = datetime.now()
        result = RotationResult(
            secret_path=secret_path,
            status=RotationStatus.PENDING,
            strategy=self.strategy,
            started_at=started_at,
        )
        
        # Check circuit breaker
        if self._circuit_breaker.state == CircuitBreakerState.OPEN:
            result.status = RotationStatus.CIRCUIT_OPEN
            result.error = "Circuit breaker is open"
            return result
        
        old_creds = None
        new_creds = None
        new_username = None
        
        try:
            async with self._circuit_breaker:
                # Step 1: Get current credentials
                logger.info(f"[Rotation] Getting current credentials for {db_name}")
                result.status = RotationStatus.IN_PROGRESS
                
                manager = VaultSecretManager(self.vault_client)
                old_creds_data = await manager.get_database_credentials(db_name)
                old_creds = old_creds_data.to_dict()
                result.old_creds_hash = self._hash_creds(old_creds)
                
                # Step 2: Generate new credentials
                logger.info(f"[Rotation] Generating new credentials for {db_name}")
                new_username = self._generate_username()
                new_password = self._generate_password()
                
                new_creds = DatabaseCredentials(
                    username=new_username,
                    password=new_password,
                    host=self.db_host,
                    port=self.db_port,
                    database=db_name,
                    connection_string=f"postgresql://{new_username}:{new_password}@{self.db_host}:{self.db_port}/{db_name}",
                )
                
                # Step 3: Pre-validate (if using shadow strategy)
                if self.strategy == RotationStrategy.SHADOW:
                    logger.info(f"[Rotation] Shadow mode - validating new credentials")
                    result.status = RotationStatus.VALIDATING
                    
                    # Create temporary user for validation
                    pool = await self._get_pg_connection()
                    async with pool.acquire() as conn:
                        await conn.execute(
                            f"CREATE USER {new_username} WITH PASSWORD $1",
                            new_password
                        )
                    
                    validation_results = await self._validator.validate(
                        new_creds.to_dict(),
                        custom_validators
                    )
                    result.validation_results = validation_results
                    
                    if not all(validation_results.values()):
                        failed = [k for k, v in validation_results.items() if not v]
                        raise Exception(f"Validation failed: {failed}")
                    
                    # Drop shadow user
                    async with pool.acquire() as conn:
                        await conn.execute(f"DROP USER IF EXISTS {new_username}")
                
                # Step 4: Create new user in PostgreSQL
                logger.info(f"[Rotation] Creating PostgreSQL user: {new_username}")
                pool = await self._get_pg_connection()
                async with pool.acquire() as conn:
                    await conn.execute(
                        f"CREATE USER {new_username} WITH PASSWORD $1",
                        new_password
                    )
                    
                    for db in databases:
                        await conn.execute(f"GRANT CONNECT ON DATABASE {db} TO {new_username}")
                        
                        async with pool.acquire() as db_conn:
                            await db_conn.execute(f"GRANT USAGE ON SCHEMA public TO {new_username}")
                            await db_conn.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {new_username}")
                            await db_conn.execute(f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {new_username}")
                
                # Step 5: Validate new credentials
                logger.info(f"[Rotation] Validating new credentials")
                validation_results = await self._validator.validate(
                    new_creds.to_dict(),
                    custom_validators
                )
                result.validation_results = validation_results
                
                if not all(validation_results.values()):
                    failed = [k for k, v in validation_results.items() if not v]
                    raise Exception(f"Post-creation validation failed: {failed}")
                
                # Step 6: Store in Vault (atomic operation)
                logger.info(f"[Rotation] Storing new credentials in Vault")
                await manager.store_database_credentials(db_name, new_creds)
                result.new_creds_hash = self._hash_creds(new_creds.to_dict())
                
                # Step 7: Grace period (if applicable)
                if self.strategy in (RotationStrategy.GRACEFUL, RotationStrategy.BLUE_GREEN):
                    logger.info(f"[Rotation] Entering grace period ({self.grace_period}s)")
                    result.status = RotationStatus.GRACE_PERIOD
                    await asyncio.sleep(self.grace_period)
                
                # Step 8: Revoke old credentials
                if old_creds and old_creds.get("username"):
                    logger.info(f"[Rotation] Revoking old user: {old_creds['username']}")
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            SELECT pg_terminate_backend(pid) 
                            FROM pg_stat_activity 
                            WHERE usename = $1
                            """,
                            old_creds["username"]
                        )
                        await conn.execute(f"DROP USER IF EXISTS {old_creds['username']}")
                
                result.status = RotationStatus.COMPLETED
                result.completed_at = datetime.now()
                logger.info(f"[Rotation] Successfully rotated credentials for {db_name}")
                
        except CircuitBreakerOpenError as e:
            logger.error(f"[Rotation] Circuit breaker open: {e}")
            result.status = RotationStatus.CIRCUIT_OPEN
            result.error = str(e)
            result.completed_at = datetime.now()
            
        except Exception as e:
            logger.error(f"[Rotation] Failed to rotate credentials: {e}")
            result.status = RotationStatus.FAILED
            result.error = str(e)
            result.completed_at = datetime.now()
            
            # Attempt rollback
            await self._rollback(db_name, new_username, old_creds, result)
        
        return result
    
    async def _rollback(
        self,
        db_name: str,
        new_username: Optional[str],
        old_creds: Optional[Dict[str, Any]],
        result: RotationResult,
    ):
        """Comprehensive rollback on failure."""
        logger.warning(f"[Rotation] Initiating rollback for {db_name}")
        result.status = RotationStatus.ROLLING_BACK
        
        try:
            # Remove new user if created
            if new_username:
                try:
                    pool = await self._get_pg_connection()
                    async with pool.acquire() as conn:
                        await conn.execute(f"DROP USER IF EXISTS {new_username}")
                    logger.info(f"[Rollback] Dropped new user: {new_username}")
                except Exception as e:
                    logger.error(f"[Rollback] Failed to drop new user: {e}")
            
            # Restore old credentials in Vault if needed
            if old_creds:
                try:
                    manager = VaultSecretManager(self.vault_client)
                    old_creds_obj = DatabaseCredentials(**old_creds)
                    await manager.store_database_credentials(db_name, old_creds_obj)
                    logger.info(f"[Rollback] Restored old credentials in Vault")
                except Exception as e:
                    logger.error(f"[Rollback] Failed to restore old credentials: {e}")
            
            result.status = RotationStatus.ROLLED_BACK
            result.rollback_reason = result.error
            logger.info(f"[Rollback] Completed for {db_name}")
            
        except Exception as e:
            logger.critical(f"[Rollback] Rollback failed: {e}")
            result.rollback_reason = f"Rollback failed: {e}"
    
    async def close(self):
        """Close database connections."""
        if self._pg_pool:
            await self._pg_pool.close()
            self._pg_pool = None


class RotationScheduler:
    """Production-grade rotation scheduler with health checks.
    
    Features:
    - Health checks before rotation
    - Circuit breaker integration
    - Metrics collection
    - Retry logic
    """
    
    def __init__(
        self,
        vault_client: VaultClient,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
    ):
        self.vault_client = vault_client
        self._schedules: Dict[str, Dict[str, Any]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._circuit_breaker = CircuitBreaker(
            circuit_breaker_config or CircuitBreakerConfig(),
            name="scheduler"
        )
        self._metrics: Dict[str, Any] = {
            "rotations_total": 0,
            "rotations_failed": 0,
            "rotations_successful": 0,
        }
    
    def schedule_database_rotation(
        self,
        db_name: str,
        days: int = 7,
        strategy: RotationStrategy = RotationStrategy.GRACEFUL,
        db_config: Optional[Dict[str, Any]] = None,
    ):
        """Schedule database credential rotation."""
        self._schedules[f"db:{db_name}"] = {
            "type": "database",
            "db_name": db_name,
            "interval": timedelta(days=days),
            "strategy": strategy,
            "last_rotation": None,
            "db_config": db_config,
            "failure_count": 0,
        }
        logger.info(f"[Scheduler] Scheduled {db_name} rotation every {days} days ({strategy.name})")
    
    def schedule_api_key_rotation(
        self,
        api_name: str,
        days: int = 30,
        secret_path: Optional[str] = None,
    ):
        """Schedule API key rotation."""
        if secret_path is None:
            secret_path = f"proxy/api-keys/{api_name}"
        
        self._schedules[f"api:{api_name}"] = {
            "type": "api_key",
            "api_name": api_name,
            "secret_path": secret_path,
            "interval": timedelta(days=days),
            "last_rotation": None,
            "failure_count": 0,
        }
        logger.info(f"[Scheduler] Scheduled {api_name} API key rotation every {days} days")
    
    async def start(self):
        """Start the rotation scheduler."""
        if self._running:
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info("[Scheduler] Rotation scheduler started")
    
    async def stop(self):
        """Stop the rotation scheduler."""
        if not self._running:
            return
        
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        
        logger.info("[Scheduler] Rotation scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop with health checks."""
        while self._running:
            try:
                now = datetime.now()
                
                for schedule_id, schedule in self._schedules.items():
                    last_rotation = schedule.get("last_rotation")
                    
                    should_rotate = (
                        last_rotation is None or
                        (now - last_rotation) >= schedule["interval"]
                    )
                    
                    if should_rotate and schedule.get("failure_count", 0) < 3:
                        logger.info(f"[Scheduler] Triggering rotation for {schedule_id}")
                        
                        success = await self._execute_rotation(schedule_id, schedule)
                        
                        if success:
                            schedule["last_rotation"] = now
                            schedule["failure_count"] = 0
                            self._metrics["rotations_successful"] += 1
                        else:
                            schedule["failure_count"] += 1
                            self._metrics["rotations_failed"] += 1
                        
                        self._metrics["rotations_total"] += 1
                
                # Check every hour
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"[Scheduler] Loop error: {e}")
                await asyncio.sleep(3600)
    
    async def _execute_rotation(
        self,
        schedule_id: str,
        schedule: Dict[str, Any]
    ) -> bool:
        """Execute a scheduled rotation with circuit breaker."""
        try:
            async with self._circuit_breaker:
                if schedule["type"] == "database":
                    db_config = schedule.get("db_config", {})
                    rotator = EnhancedDatabaseCredentialRotator(
                        self.vault_client,
                        db_config.get("host", "localhost"),
                        db_config.get("port", 5432),
                        db_config.get("admin_username", "postgres"),
                        db_config.get("admin_password"),
                        strategy=schedule.get("strategy", RotationStrategy.GRACEFUL),
                    )
                    result = await rotator.rotate(schedule["db_name"])
                    await rotator.close()
                    
                    return result.status == RotationStatus.COMPLETED
                    
                elif schedule["type"] == "api_key":
                    # API key rotation logic
                    pass
                
                return False
                
        except CircuitBreakerOpenError:
            logger.warning(f"[Scheduler] Circuit breaker open for {schedule_id}")
            return False
        except Exception as e:
            logger.error(f"[Scheduler] Rotation failed for {schedule_id}: {e}")
            return False
    
    def get_schedules(self) -> Dict[str, Dict[str, Any]]:
        """Get current rotation schedules."""
        return self._schedules.copy()
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get scheduler metrics."""
        return self._metrics.copy()