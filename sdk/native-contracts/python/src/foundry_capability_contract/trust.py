"""Who may call an Optimization API, and for which tenant (Capability Contract v1).

Callers are services (OCP domain servers, Vertical backends), each with a bearer token. The API
holds only the tokens' sha256 digests, by caller name, in ``<PREFIX>_SERVICE_TOKENS``:

    NURSE_API_SERVICE_TOKENS='{"nurse-domain": "<sha256 hex>", "nurse-product": "<sha256 hex>"}'

A job, its result and its evaluations belong to the tenant named by ``X-OIP-Tenant-Id`` (the OIP
tenant the gateway verified, passed on by the domain server); another tenant's job is not found.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass

from fastapi import Header

from .errors import CapabilityError

__all__ = ["ServiceTrust", "TENANT_HEADER", "parse_service_tokens", "require_tenant"]

TENANT_HEADER = "X-OIP-Tenant-Id"
_TENANT = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")


def parse_service_tokens(raw: str | None, variable: str) -> dict[str, str]:
    """Caller name -> sha256 hex of its token; a malformed value raises (the API refuses to start)."""
    if raw is None or raw.strip() == "":
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"{variable} must be a JSON object of caller name to sha256 hex") from error
    if not isinstance(parsed, dict):
        raise ValueError(f"{variable} must be a JSON object of caller name to sha256 hex")
    tokens: dict[str, str] = {}
    for name, digest in parsed.items():
        if not isinstance(digest, str) or not _DIGEST.match(digest.lower()):
            raise ValueError(f"{variable} entry {name!r} is not a sha256 hex digest")
        tokens[str(name)] = digest.lower()
    return tokens


@dataclass(frozen=True)
class ServiceTrust:
    """The callers an API trusts."""

    tokens: Mapping[str, str]
    variable: str

    @classmethod
    def from_env(cls, prefix: str, env: Mapping[str, str] | None = None, *, required: bool = True) -> ServiceTrust:
        variable = f"{prefix}_SERVICE_TOKENS"
        source = os.environ if env is None else env
        tokens = parse_service_tokens(source.get(variable), variable)
        if required and not tokens:
            raise ValueError(f"{variable} is required: the API answers only callers with a service token")
        return cls(tokens=tokens, variable=variable)

    def caller_of(self, authorization: str | None) -> str:
        """The caller a bearer token names; 401 for none or an unknown one."""
        scheme, _, token = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise CapabilityError(401, "UNAUTHENTICATED", "a service bearer token is required")
        digest = hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
        found: str | None = None
        for name, expected in self.tokens.items():
            if hmac.compare_digest(digest, expected):
                found = name
        if found is None:
            raise CapabilityError(401, "UNAUTHENTICATED", "the service token is not known")
        return found

    def dependency(self):  # type: ignore[no-untyped-def]
        """A FastAPI dependency answering the caller's name."""

        def caller(authorization: str | None = Header(default=None)) -> str:
            return self.caller_of(authorization)

        return caller


def require_tenant(value: str | None) -> str:
    """The tenant a job belongs to; 400 without a well-formed one."""
    tenant = (value or "").strip()
    if not _TENANT.match(tenant):
        raise CapabilityError(400, "TENANT_REQUIRED", f"{TENANT_HEADER} must name the tenant (1-128 of A-Z a-z 0-9 . _ : -)", field_path=TENANT_HEADER)
    return tenant
