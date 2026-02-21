"""
Command Bus - CQRS command handling infrastructure.

Provides command dispatch, validation, and handler registration
for the Command side of CQRS.
"""

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Generic, List, Optional, Type, TypeVar

logger = logging.getLogger(__name__)

TCommand = TypeVar('TCommand', bound='Command')
TResult = TypeVar('TResult')


@dataclass
class Command:
    """Base class for all commands."""
    command_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    command_type: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.command_type:
            self.command_type = self.__class__.__name__


@dataclass
class CommandResult(Generic[TResult]):
    """Result of command execution."""
    success: bool
    result: Optional[TResult] = None
    error: Optional[str] = None
    events: List[Any] = field(default_factory=list)
    events_produced: int = 0
    execution_time_ms: float = 0.0

    def __post_init__(self):
        if self.events_produced == 0 and self.events:
            self.events_produced = len(self.events)


class CommandHandler(ABC, Generic[TCommand, TResult]):
    """Abstract base class for command handlers."""
    
    @abstractmethod
    async def handle(self, command: TCommand) -> CommandResult[TResult]:
        """Handle the command and return result."""
        pass
    
    def validate(self, command: TCommand) -> Optional[str]:
        """Validate command before handling. Returns error message or None."""
        return None


class CommandMiddleware:
    """Middleware for command processing."""
    
    async def before_execute(self, command: Command) -> Optional[CommandResult]:
        """Called before command execution. Return result to short-circuit."""
        return None
    
    async def after_execute(
        self,
        command: Command,
        result: CommandResult
    ) -> CommandResult:
        """Called after command execution. Can modify result."""
        return result
    
    async def on_error(
        self,
        command: Command,
        error: Exception
    ) -> Optional[CommandResult]:
        """Called on error. Return result to handle error."""
        return None


class LoggingMiddleware(CommandMiddleware):
    """Middleware that logs command execution."""
    
    async def before_execute(self, command: Command) -> Optional[CommandResult]:
        logger.info(f"Executing command: {command.command_type} [{command.command_id}]")
        return None
    
    async def after_execute(
        self,
        command: Command,
        result: CommandResult
    ) -> CommandResult:
        status = "succeeded" if result.success else "failed"
        logger.info(
            f"Command {command.command_type} [{command.command_id}] {status} "
            f"in {result.execution_time_ms:.2f}ms"
        )
        return result


class ValidationMiddleware(CommandMiddleware):
    """Middleware that validates commands."""
    
    def __init__(self):
        self._validators: Dict[str, Callable] = {}
    
    def register_validator(
        self,
        command_type: str,
        validator: Callable[[Command], Optional[str]]
    ) -> None:
        """Register a validator for a command type."""
        self._validators[command_type] = validator
    
    async def before_execute(self, command: Command) -> Optional[CommandResult]:
        validator = self._validators.get(command.command_type)
        if validator:
            error = validator(command)
            if error:
                return CommandResult(
                    success=False,
                    error=f"Validation failed: {error}"
                )
        return None


class RetryMiddleware(CommandMiddleware):
    """Middleware that retries failed commands."""
    
    def __init__(
        self,
        max_retries: int = 3,
        retry_delay_ms: float = 100.0,
        exponential_backoff: bool = True,
    ):
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.exponential_backoff = exponential_backoff
        self._retryable_errors: List[Type[Exception]] = []
    
    def add_retryable_error(self, error_type: Type[Exception]) -> None:
        """Add an error type that should trigger retry."""
        self._retryable_errors.append(error_type)
    
    async def on_error(
        self,
        command: Command,
        error: Exception
    ) -> Optional[CommandResult]:
        # Check if error is retryable
        is_retryable = any(
            isinstance(error, et) for et in self._retryable_errors
        )
        
        if not is_retryable:
            return None
        
        # Get retry count from metadata
        retry_count = command.metadata.get("_retry_count", 0)
        
        if retry_count >= self.max_retries:
            return None
        
        # Increment retry count
        command.metadata["_retry_count"] = retry_count + 1
        
        # Calculate delay
        delay = self.retry_delay_ms
        if self.exponential_backoff:
            delay = delay * (2 ** retry_count)
        
        logger.warning(
            f"Retrying command {command.command_id} "
            f"(attempt {retry_count + 1}/{self.max_retries}) after {delay}ms"
        )
        
        await asyncio.sleep(delay / 1000.0)
        
        return None  # Return None to let the bus retry


class CommandBus:
    """
    Command bus for CQRS command dispatch.
    
    Features:
    - Command handler registration
    - Middleware support
    - Async command execution
    - Command validation
    """
    
    def __init__(self):
        self._handlers: Dict[str, CommandHandler] = {}
        self._middlewares: List[CommandMiddleware] = []
        self._command_types: Dict[str, Type[Command]] = {}
    
    def register_handler(
        self,
        command_type: Type[TCommand],
        handler: CommandHandler[TCommand, TResult]
    ) -> None:
        """Register a handler for a command type."""
        type_name = command_type.__name__
        self._handlers[type_name] = handler
        self._command_types[type_name] = command_type
        logger.debug(f"Registered handler for command: {type_name}")
    
    def unregister_handler(self, command_type: Type[Command]) -> None:
        """Unregister a handler."""
        type_name = command_type.__name__
        self._handlers.pop(type_name, None)
        self._command_types.pop(type_name, None)
    
    def add_middleware(self, middleware: CommandMiddleware) -> None:
        """Add middleware to the pipeline."""
        self._middlewares.append(middleware)
    
    def remove_middleware(self, middleware: CommandMiddleware) -> None:
        """Remove middleware from the pipeline."""
        if middleware in self._middlewares:
            self._middlewares.remove(middleware)
    
    async def execute(self, command: Command) -> CommandResult:
        """Execute a command through the pipeline."""
        import time
        
        start_time = time.time()
        
        # Ensure command type is set
        if not command.command_type:
            command.command_type = command.__class__.__name__
        
        # Run before middleware
        for middleware in self._middlewares:
            result = await middleware.before_execute(command)
            if result is not None:
                return result
        
        # Get handler
        handler = self._handlers.get(command.command_type)
        if not handler:
            result = CommandResult(
                success=False,
                error=f"No handler registered for command: {command.command_type}"
            )
            return await self._run_after_middleware(command, result)
        
        # Validate
        validation_error = handler.validate(command)
        if validation_error:
            result = CommandResult(
                success=False,
                error=f"Validation failed: {validation_error}"
            )
            return await self._run_after_middleware(command, result)
        
        # Execute
        try:
            result = await handler.handle(command)
            result.execution_time_ms = (time.time() - start_time) * 1000
            return await self._run_after_middleware(command, result)
            
        except Exception as e:
            # Run error middleware
            for middleware in self._middlewares:
                error_result = await middleware.on_error(command, e)
                if error_result is not None:
                    return error_result
            
            result = CommandResult(
                success=False,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000
            )
            return await self._run_after_middleware(command, result)
    
    async def _run_after_middleware(
        self,
        command: Command,
        result: CommandResult
    ) -> CommandResult:
        """Run after middleware."""
        for middleware in self._middlewares:
            result = await middleware.after_execute(command, result)
        return result
    
    async def execute_batch(
        self,
        commands: List[Command],
        stop_on_failure: bool = False,
    ) -> List[CommandResult]:
        """Execute multiple commands."""
        results = []
        
        for command in commands:
            result = await self.execute(command)
            results.append(result)
            
            if stop_on_failure and not result.success:
                break
        
        return results
    
    def get_registered_commands(self) -> List[str]:
        """Get list of registered command types."""
        return list(self._handlers.keys())

    def get_registered_handlers(self) -> Dict[str, Any]:
        """Compatibility API for endpoints/tests."""
        return dict(self._handlers)
    
    def has_handler(self, command_type: str) -> bool:
        """Check if a handler is registered."""
        return command_type in self._handlers


# Decorator for registering handlers
def command_handler(command_type: Type[Command]):
    """Decorator to register a function as a command handler."""
    def decorator(func: Callable):
        # Create a handler wrapper
        class FunctionHandler(CommandHandler):
            async def handle(self, command: Command):
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(command)
                    else:
                        result = func(command)
                    return CommandResult(success=True, result=result)
                except Exception as e:
                    return CommandResult(success=False, error=str(e))
        
        handler = FunctionHandler()
        # Store reference for later registration
        func._command_handler = (command_type, handler)
        return func
    
    return decorator


# Common commands
@dataclass
class CreateAggregateCommand(Command):
    """Command to create a new aggregate."""
    aggregate_type: str = ""
    initial_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UpdateAggregateCommand(Command):
    """Command to update an aggregate."""
    aggregate_id: str = ""
    updates: Dict[str, Any] = field(default_factory=dict)
    expected_version: Optional[int] = None


@dataclass
class DeleteAggregateCommand(Command):
    """Command to delete an aggregate."""
    aggregate_id: str = ""
    reason: Optional[str] = None
