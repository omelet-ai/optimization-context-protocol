"""The error envelope of Capability Contract v1, and the FastAPI handlers that produce it.

Every error answers ``{"code", "message", "requestId", "retryable", "fieldPath"?, "issues"}`` with an
HTTP status that matches the code. The request id comes from the caller's ``x-request-id`` (an OCP
domain server sends its call's correlation id) or is made here, and is echoed in the response.
"""

from __future__ import annotations

import re
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

__all__ = ["DEFAULT_MAX_BODY_BYTES", "CapabilityError", "error_body", "install_error_handlers", "request_id_of"]

_REQUEST_ID = re.compile(r"^[\w.:-]{1,128}$")


class CapabilityError(Exception):
    """An error the API answers with the contract's envelope."""

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        field_path: str | None = None,
        issues: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.retryable = retryable
        self.field_path = field_path
        self.issues = issues or []


def request_id_of(request: Request) -> str:
    """The request's id: its usable ``x-request-id``, or one made for it (kept on request.state)."""
    existing = getattr(request.state, "request_id", None)
    if existing:
        return existing
    candidate = (request.headers.get("x-request-id") or "").strip()
    request_id = candidate if _REQUEST_ID.match(candidate) else uuid.uuid4().hex
    request.state.request_id = request_id
    return request_id


def error_body(
    code: str,
    message: str,
    request_id: str,
    *,
    retryable: bool = False,
    field_path: str | None = None,
    issues: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {"code": code, "message": message, "requestId": request_id, "retryable": retryable, "issues": issues or []}
    if field_path is not None:
        body["fieldPath"] = field_path
    return body


def _respond(request: Request, status: int, body: dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=status, content=body, headers={"x-request-id": body["requestId"]})


_STATUS_CODES = {400: "BAD_REQUEST", 401: "UNAUTHENTICATED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 409: "CONFLICT", 413: "PAYLOAD_TOO_LARGE", 415: "UNSUPPORTED_MEDIA_TYPE", 422: "INVALID_REQUEST"}


#: the default largest body (Content-Length) an API reads; a chunked body is the ingress's to cap
DEFAULT_MAX_BODY_BYTES = 32 * 1024 * 1024


def install_error_handlers(app: FastAPI, *, max_body_bytes: int = DEFAULT_MAX_BODY_BYTES) -> None:
    """Answer every error with the envelope, echo the request id on every response, and refuse a
    body whose Content-Length is over ``max_body_bytes`` (413) before reading it."""

    @app.middleware("http")
    async def _request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request_id_of(request)
        declared = (request.headers.get("content-length") or "").strip()
        if declared.isdigit() and int(declared) > max_body_bytes:
            return _respond(request, 413, error_body("PAYLOAD_TOO_LARGE", f"the body is over {max_body_bytes} bytes", request_id))
        response = await call_next(request)
        response.headers.setdefault("x-request-id", request_id)
        return response

    @app.exception_handler(CapabilityError)
    async def _capability_error(request: Request, error: CapabilityError) -> JSONResponse:
        return _respond(
            request,
            error.status,
            error_body(error.code, error.message, request_id_of(request), retryable=error.retryable, field_path=error.field_path, issues=error.issues),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, error: RequestValidationError) -> JSONResponse:
        issues = [
            {"code": str(item.get("type", "invalid")), "message": str(item.get("msg", "")), "fieldPath": ".".join(str(part) for part in item.get("loc", ()))}
            for item in error.errors()
        ]
        first = issues[0]["fieldPath"] if issues else None
        return _respond(request, 422, error_body("INVALID_REQUEST", "the request does not match the contract", request_id_of(request), field_path=first, issues=issues))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, error: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_CODES.get(error.status_code, "HTTP_ERROR")
        return _respond(request, error.status_code, error_body(code, str(error.detail), request_id_of(request)))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, error: Exception) -> JSONResponse:
        # Never the exception text: it may carry inputs or internals.
        return _respond(request, 500, error_body("INTERNAL", "the request failed inside the API", request_id_of(request), retryable=True))
