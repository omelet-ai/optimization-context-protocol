"""Installed-project entrypoint; domain code stays inside authored content."""
import argparse
import importlib
import json
import os
from pathlib import Path
import re
import sys

from ocp_candidate.contract import parse_json
from ocp_candidate.server_package import lint_package, PackageError


def _factory_reference(reference):
    if not isinstance(reference, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*", reference):
        raise ValueError("CONNECTOR_FACTORY_REQUIRED")
    return reference.split(":")


def _factory(reference):
    module, name = _factory_reference(reference)
    factory = getattr(importlib.import_module(module), name, None)
    if not callable(factory): raise ValueError("CONNECTOR_FACTORY_INVALID")
    return factory


def _transport_settings(settings, config_path, state_override, *, load_credentials=True):
    """Validate local transport settings before creating files or a connector."""
    state = state_override or settings.get("state_directory")
    if not isinstance(state, str) or not state: raise ValueError("STATE_DIRECTORY_REQUIRED")
    state_path = Path(state).expanduser()
    if not state_path.is_absolute(): state_path = config_path.parent / state_path
    roots = settings.get("allowed_local_roots", [])
    if not isinstance(roots, list) or any(not isinstance(p, str) or not p for p in roots):
        raise ValueError("LOCAL_ROOTS_INVALID")
    resolved = []
    for root in roots:
        path = Path(root).expanduser()
        if not path.is_absolute(): path = config_path.parent / path
        if not path.is_dir(): raise ValueError("LOCAL_ROOT_NOT_DIRECTORY")
        resolved.append(str(path.resolve()))
    if settings.get("transport", "stdio") == "streamable-http":
        from ocp_runtime.execution.jobs import Principal
        name = settings.get("http_auth_environment_variable")
        if not isinstance(name, str) or not name: raise ValueError("HTTP_AUTHENTICATION_REQUIRED")
        identities = parse_json(os.environ.get(name, "{}")) if load_credentials else {}
        if load_credentials and (not isinstance(identities, dict) or not identities): raise ValueError("HTTP_AUTHENTICATION_REQUIRED")
        tokens = {}
        for token, identity in identities.items():
            if (not token or not isinstance(identity, dict) or set(identity) != {"tenant", "caller", "scopes"}
                or any(not isinstance(identity[k], str) or not identity[k] for k in ("tenant", "caller"))
                or not isinstance(identity["scopes"], list) or any(not isinstance(s, str) or s not in {"read", "execute", "cancel"} for s in identity["scopes"])):
                raise ValueError("HTTP_IDENTITIES_INVALID")
            tokens[token] = Principal(identity["tenant"], identity["caller"], frozenset(identity["scopes"]))
        port = settings.get("http_port", 8000)
        if type(port) is not int or not 1024 <= port <= 65535: raise ValueError("HTTP_PORT_INVALID")
    else:
        tokens, port = {}, None
    return state_path.resolve(), resolved, tokens, port


def _converters(descriptor, bundle):
    """Check advertised file preparation without converting or invoking an API."""
    from ocp_runtime.inputs import InputConverter
    converters = bundle.get("converters", {})
    if not isinstance(converters, dict): raise ValueError("CONVERTER_REGISTRY_INVALID")
    formats = list(descriptor.get("input_formats", []))
    for operation in descriptor.get("extensions", {}).get("ocp.operations", {}).get("operations", []):
        formats.extend(operation.get("input_formats", []))
    for definition in formats:
        name = definition.get("converter")
        if name is None: continue
        converter = converters.get(name)
        if not isinstance(converter, InputConverter) or not callable(converter.convert):
            raise ValueError("CONVERTER_NOT_REGISTERED")
        if converter.id != name or converter.version != definition.get("converter_version"):
            raise ValueError("CONVERTER_VERSION_MISMATCH")
    return converters


def project_main(project, argv=None, *, package=None):
    parser = argparse.ArgumentParser(description="Inspect an authored OCP Server")
    parser.add_argument("command", choices=("check", "describe", "doctor", "serve", "host-config"), nargs="?", default="check")
    parser.add_argument("--config")
    parser.add_argument("--state")
    args = parser.parse_args(argv)
    try:
        descriptor = parse_json((Path(project) / "content/manifest.json").read_text())
        if descriptor.get("configured") is False:
            result = {"status": "UNCONFIGURED", "execute_calls": 0,
                      "next": "Define your API descriptor and connector in content/; then run check."}
            code = 2
        else:
            checked = lint_package(descriptor, supported_extensions=("ocp.operations",))
            if args.command in {"check", "describe"}:
                result = {"status": "VALID", "api_agreement_checked": checked["api_agreement_checked"],
                          "execute_calls": 0, "descriptor": descriptor} if args.command == "describe" else checked
                code = 0
            else:
                if not args.config:
                    raise ValueError("CONFIG_PATH_REQUIRED")
                config_path = Path(args.config).resolve(strict=True)
                settings = parse_json(config_path.read_text())
                if not isinstance(settings, dict): raise ValueError("CONFIG_OBJECT_REQUIRED")
                allowed = {"api_endpoint", "credential_environment_variable", "connector_factory", "transport",
                           "http_port", "http_auth_environment_variable", "state_directory", "allowed_local_roots"}
                if set(settings) - allowed: raise ValueError("CONFIG_FIELD_UNSUPPORTED")
                transport = settings.get("transport", "stdio")
                if transport not in {"stdio", "streamable-http"}: raise ValueError("TRANSPORT_UNSUPPORTED")
                _factory_reference(settings.get("connector_factory"))
                if args.command == "host-config":
                    _, _, _, port = _transport_settings(settings, config_path, args.state, load_credentials=False)
                    if transport == "stdio":
                        command = ["-B", "-m", package + ".server"] if package else ["-B", str(Path(project) / "server.py")]
                        command += ["serve", "--config", str(config_path)]
                        if args.state: command += ["--state", str(Path(args.state).resolve())]
                        result = {"mcpServers": {descriptor["id"]: {"command": sys.executable, "args": command}}}
                    else:
                        result = {"url": "http://127.0.0.1:" + str(port) + "/mcp",
                                  "authentication": "Supply a bearer credential through your host's secret settings"}
                    code = 0
                else:
                    from ocp_runtime.execution import ExecutionService
                    from ocp_runtime.bindings.mcp import BindingRuntime, create_mcp, http_app
                    state, roots, tokens, port = _transport_settings(settings, config_path, args.state)
                    if transport == "streamable-http": import uvicorn
                    name = settings.get("credential_environment_variable")
                    if name and (not isinstance(name, str) or not os.environ.get(name)):
                        raise ValueError("CREDENTIAL_ENVIRONMENT_VARIABLE_MISSING")
                    bundle = _factory(settings.get("connector_factory"))(dict(settings))
                    if not isinstance(bundle, dict) or "connector" not in bundle: raise ValueError("CONNECTOR_BUNDLE_INVALID")
                    converters = _converters(descriptor, bundle)
                    service = ExecutionService(descriptor, bundle["connector"], checker=bundle.get("checker"))
                    operations = None
                    if "ocp.operations" in descriptor["extensions"]:
                        from ocp_runtime.operations import OperationService
                        operations = OperationService(descriptor, bundle.get("operations", {}), optimization=service,
                            journal=state / "operations.sqlite" if args.command == "serve" else None)
                    if args.command == "doctor":
                        result = {"status": "READY", "api_agreement_checked": True, "execute_calls": 0,
                                  "transport": transport, "checker_available": service.checker is not None,
                                  "state_directory": str(state), "local_file_roots": roots}
                        code = 0
                    else:
                        runtime = BindingRuntime({descriptor["id"]: service}, state,
                                                 local_roots=roots,
                                                 operation_services={descriptor["id"]: operations} if operations is not None else None,
                                                 converters={descriptor["id"]: converters})
                        server = create_mcp(runtime, transport=transport)
                        if transport == "stdio":
                            server.run(transport="stdio")
                        else:
                            uvicorn.run(http_app(server, tokens.get), host="127.0.0.1", port=port, log_level="warning")
                        return 0
    except (ValueError, OSError, PackageError) as error:
        label = getattr(error, "code", None)
        if label is None and isinstance(error, ValueError) and re.fullmatch(r"[A-Z_]+", str(error)):
            label = str(error)
        result = {"status": "INVALID_PROJECT", "code": label or type(error).__name__, "execute_calls": 0}
        result["next"] = {
            "CONFIG_PATH_REQUIRED": "Pass --config with your local JSON configuration file.",
            "CONNECTOR_FACTORY_REQUIRED": "Set connector_factory to your installed content module:function.",
            "CONNECTOR_FACTORY_INVALID": "Check that the configured module exports the named callable.",
            "STATE_DIRECTORY_REQUIRED": "Set state_directory in configuration; relative paths resolve beside that file.",
            "CREDENTIAL_ENVIRONMENT_VARIABLE_MISSING": "Set the named credential in the server process environment.",
            "HTTP_AUTHENTICATION_REQUIRED": "Set http_auth_environment_variable to the name of a configured identity JSON secret.",
            "HTTP_PORT_INVALID": "Set http_port to an integer between 1024 and 65535.",
            "CONVERTER_NOT_REGISTERED": "Register every advertised file converter in the installed connector bundle.",
            "CONVERTER_VERSION_MISMATCH": "Match each registered converter ID and version to its advertised input format.",
            "CONVERTER_REGISTRY_INVALID": "Return converters as a mapping of converter IDs to InputConverter instances.",
            "API_UNAVAILABLE": "Check api_endpoint, engine availability and network access; no solve was submitted by doctor.",
        }.get(result["code"], "Check the descriptor, configuration and installed connector; inspect the named error before retrying.")
        code = 2
    except ImportError:
        result, code = {"status": "DEPENDENCY_MISSING", "next": "Install this domain package, its declared dependencies and the matching ocp-candidate[server] runtime; check connector_factory. Generic servers do not require native-contract packages.", "execute_calls": 0}, 2
    print(json.dumps(result, ensure_ascii=False), file=sys.stderr if args.command == "serve" else sys.stdout)
    return code
