"""Domain-neutral API execution. Native jobs are an optional binding."""
from .service import ExecutionService, ExecutionError

__all__ = ["ExecutionService", "ExecutionError"]
