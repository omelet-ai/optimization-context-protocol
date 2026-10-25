"""Optional HTTP port. Transport uncertainty never triggers a solve retry."""

import json
import hashlib
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler
from .contract import OCPError, envelope, parse_json


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise OCPError("INVALID_ENDPOINT",message="Redirects are not supported")


class HTTPAdapter:
    def __init__(self, endpoint, timeout=10, token=None):
        parsed=urlparse(endpoint)
        if parsed.scheme!="https" and not (parsed.scheme=="http" and parsed.hostname=="127.0.0.1"):
            raise OCPError("INVALID_ENDPOINT",message="HTTPS required outside loopback")
        if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"","/"}:
            raise OCPError("INVALID_ENDPOINT")
        self.endpoint=endpoint.rstrip("/")
        if token is not None and (not isinstance(token,str) or not token or any(c in token for c in "\r\n")):
            raise OCPError("INVALID_CREDENTIAL")
        self._token=token
        self.timeout=timeout
        self.opener=build_opener(NoRedirect(),ProxyHandler({}))

    def call(self, operation, payload=None):
        headers={"Content-Type":"application/json"}
        if self._token: headers["Authorization"]="Bearer "+self._token
        if operation=="execute" and self._token and isinstance(payload,dict):
            headers["Idempotency-Key"]=hashlib.sha256(payload["request_id"].encode()).hexdigest()
        request=Request(self.endpoint+"/v1/"+operation,
                        data=None if payload is None else json.dumps(payload,allow_nan=False).encode(),
                        headers=headers)
        try:
            try: response=self.opener.open(request,timeout=self.timeout)
            except HTTPError as error: response=error
            with response:
                if response.headers.get_content_type()!="application/json": raise OCPError("INVALID_RESPONSE")
                raw=response.read(1048577)
                if len(raw)>1048576: raise OCPError("INVALID_RESPONSE")
                result=parse_json(raw.decode("utf-8")); envelope(result)
                if response.status>=300 and result["kind"]!="failure": raise OCPError("INVALID_RESPONSE")
                return result
        except (URLError,TimeoutError,ConnectionError,UnicodeError):
            raise OCPError("TRANSPORT_UNCERTAIN",message="No response; execution outcome unknown, do not retry automatically") from None

    def describe(self): return self.call("capability")
    def requirements(self, configuration): return self.call("requirements",{"configuration":configuration})
    def validate(self, request): return self.call("validate",request)
    def execute(self, request): return self.call("execute",request)
    def evaluate(self, request, solution): return self.call("evaluate",{"request":request,"solution":solution})
