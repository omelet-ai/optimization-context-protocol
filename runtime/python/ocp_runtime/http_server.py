"""Loopback-only reference HTTP binding. No public service deployment is implied."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

from ocp_candidate.contract import OCPError, failure, parse_json
from .service import Service

MAX_BODY = 131072


def create_server(adapter, port=0, service=None):
    service = Service(adapter) if service is None else service
    slots = threading.BoundedSemaphore(4)

    class BoundedServer(ThreadingHTTPServer):
        # Limit threads before accepting request headers; handler-level slots
        # alone cannot bound slow or unauthenticated connections.
        connections = threading.BoundedSemaphore(8)

        def process_request(self, request, client_address):
            if not self.connections.acquire(blocking=False):
                self.shutdown_request(request); return
            try: super().process_request(request,client_address)
            except BaseException:
                self.connections.release(); raise

        def process_request_thread(self, request, client_address):
            try: super().process_request_thread(request,client_address)
            finally: self.connections.release()

        def handle_error(self,request,client_address):
            pass  # No raw request, exception, or key in serving logs.

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.0"

        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, format, *args):
            pass  # Payloads and headers are deliberately not logged.

        def respond(self, value, status=200):
            raw = json.dumps(value,allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(raw)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(raw)

        def error(self, status, code):
            self.respond(failure("invalid-request",OCPError(code,message=code)),status)

        def allowed(self):
            # No browser ambient authority, DNS rebinding or cross-origin invocation.
            if (self.headers.get_all("Host",[]) != ["127.0.0.1:" + str(self.server.server_port)]
                or self.headers.get("Origin") or any(len(self.headers.get_all(name,[]))>1 for name in ("Authorization","Idempotency-Key"))):
                self.error(403,"FORBIDDEN"); return False
            return True

        def do_GET(self):
            if not self.allowed(): return
            if self.path != "/v1/capability": self.error(404,"NOT_FOUND"); return
            self.respond(service.dispatch("describe",**self.context()))

        def context(self):
            authorization=self.headers.get("Authorization","")
            return {"token":authorization[7:] if authorization.startswith("Bearer ") else None,
                    "idempotency_key":self.headers.get("Idempotency-Key")}

        def do_POST(self):
            if not self.allowed(): return
            if self.path not in {"/v1/requirements","/v1/validate","/v1/execute","/v1/evaluate"}:
                self.error(404,"NOT_FOUND"); return
            if self.headers.get_content_type() != "application/json": self.error(415,"INVALID_CONTENT_TYPE"); return
            sizes = self.headers.get_all("Content-Length", [])
            if self.headers.get("Transfer-Encoding") or len(sizes)!=1 or not sizes[0].isdigit():
                self.error(400,"INVALID_FRAMING"); return
            size = int(sizes[0])
            if not 0 < size <= MAX_BODY: self.error(413,"LIMIT_EXCEEDED"); return
            if not slots.acquire(blocking=False): self.error(429,"CONCURRENCY_LIMIT"); return
            try:
                raw = self.rfile.read(size)
                if len(raw)!=size: raise OCPError("INVALID_REQUEST")
                payload = parse_json(raw.decode("utf-8"))
                self.respond(service.dispatch(self.path.rsplit("/",1)[1],payload,**self.context()))
            except (OCPError,UnicodeError):
                self.error(400,"INVALID_JSON")
            except (TimeoutError,ConnectionError):
                self.close_connection = True
            finally:
                slots.release()

    server = BoundedServer(("127.0.0.1",port),Handler)
    server.daemon_threads = True
    return server


def main():
    from ocp_routing import RoutingAdapter, ORToolsBackend
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port",type=int,default=0)
    args=parser.parse_args()
    server=create_server(RoutingAdapter(ORToolsBackend()),args.port)
    print(json.dumps({"url":"http://127.0.0.1:"+str(server.server_port)}),flush=True)
    try: server.serve_forever()
    finally: server.server_close()


if __name__ == "__main__": main()
