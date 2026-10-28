"""What an Optimization API reads at start (Capability Contract v1): its callers, its job store and
its solver workers. A missing or malformed value stops the start; no message names a token or the
database address.

    <PREFIX>_SERVICE_TOKENS   callers' token digests, {"name": "<sha256 hex>"} (required)
    <PREFIX>_DATABASE_URL     PostgreSQL of the job store (required unless the store is memory)
    <PREFIX>_JOB_STORE        postgres (default) | memory (tests and local runs; never production)
    <PREFIX>_WORKERS          solver workers in this process (default 2)
    APP_ENV                   production | development (default) | test

An API names its prefix in a subclass:

    class Settings(ApiSettings):
        env_prefix = "ROUTING_API"
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import ClassVar, Self

from .jobs.memory import MemoryJobStore
from .jobs.model import JobStore
from .trust import ServiceTrust

__all__ = ["ApiSettings"]


@dataclass(frozen=True)
class ApiSettings:
    #: the API's variable prefix, named by a subclass
    env_prefix: ClassVar[str] = ""

    trust: ServiceTrust
    job_store_kind: str
    database_url: str | None
    workers: int
    environment: str

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Self:
        prefix = cls.env_prefix
        if not prefix:
            raise TypeError("ApiSettings.from_env needs a subclass that names env_prefix")
        source = os.environ if env is None else env
        environment = (source.get("APP_ENV") or "development").strip()
        trust = ServiceTrust.from_env(prefix, source)
        kind = (source.get(f"{prefix}_JOB_STORE") or "postgres").strip()
        if kind not in ("postgres", "memory"):
            raise ValueError(f"{prefix}_JOB_STORE must be postgres or memory")
        if kind == "memory" and environment == "production":
            raise ValueError(f"{prefix}_JOB_STORE=memory is for tests and local runs: production keeps jobs in PostgreSQL")
        database_url = (source.get(f"{prefix}_DATABASE_URL") or "").strip() or None
        if kind == "postgres" and database_url is None:
            raise ValueError(f"{prefix}_DATABASE_URL is required for the PostgreSQL job store")
        raw_workers = (source.get(f"{prefix}_WORKERS") or "2").strip()
        if not raw_workers.isdigit() or not 1 <= int(raw_workers) <= 64:
            raise ValueError(f"{prefix}_WORKERS must be a whole number from 1 to 64")
        return cls(trust=trust, job_store_kind=kind, database_url=database_url, workers=int(raw_workers), environment=environment)

    def job_store(self) -> JobStore:
        if self.job_store_kind == "memory":
            return MemoryJobStore()
        from .jobs.postgres import PostgresJobStore

        return PostgresJobStore(self.database_url or "")

    def __repr__(self) -> str:
        # The database URL carries its password: never in a log line or an error.
        return f"{type(self).__name__}(callers={sorted(self.trust.tokens)}, job_store={self.job_store_kind}, workers={self.workers}, environment={self.environment})"
