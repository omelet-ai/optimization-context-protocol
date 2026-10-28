"""Health, readiness and version of an Optimization API (Capability Contract v1).

    GET /health    the process answers (no dependency is checked)
    GET /ready     every readiness check passes (the database and its migrations, the registry,
                   the solver); 503 otherwise, naming the failing checks but no address or error text
    GET /version   the service, its API/compiler/engine/registry versions, the catalog digest and
                   the build (APP_VERSION, else "local")
None of them needs a token: load balancers and deploy pipelines call them.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

__all__ = ["ReadinessCheck", "ops_router"]

log = logging.getLogger("foundry_capability_contract.ops")


@dataclass(frozen=True)
class ReadinessCheck:
    name: str
    #: True when ready; raising counts as not ready (the error goes to the log only)
    check: Callable[[], bool]


def ops_router(*, service: str, versions: Callable[[], dict[str, Any]], checks: list[ReadinessCheck], include_health: bool = True) -> APIRouter:
    """``include_health=False`` keeps an API's own /health (it must answer at least {"status": "ok",
    "service"}), for an API that had one before the contract."""
    router = APIRouter()

    if include_health:

        @router.get("/health")
        def health() -> dict[str, Any]:
            return {"status": "ok", "service": service}

    @router.get("/ready")
    def ready() -> JSONResponse:
        results: list[dict[str, Any]] = []
        for item in checks:
            try:
                ok = bool(item.check())
            except Exception:  # noqa: BLE001 - logged, never answered
                log.exception("readiness check %s failed", item.name)
                ok = False
            results.append({"name": item.name, "ok": ok})
        ready_now = all(result["ok"] for result in results)
        return JSONResponse(status_code=200 if ready_now else 503, content={"ready": ready_now, "service": service, "checks": results})

    @router.get("/version")
    def version() -> dict[str, Any]:
        build = (os.environ.get("APP_VERSION") or "").strip() or "local"
        return {"service": service, **versions(), "build": build}

    return router
