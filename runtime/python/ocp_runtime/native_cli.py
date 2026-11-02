"""Start, configure and diagnose an installed local native MCP server."""
import argparse
import asyncio
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import sys


BASE_TOOLS = frozenset('ocp_native_' + name for name in (
    'context', 'requirements', 'validate', 'submit', 'job', 'result', 'evaluate', 'cancel'))
PACKAGES = (
    ('ocp-candidate', 'ocp_runtime.native_mcp'),
    ('ocp-foundry-contracts-candidate', 'foundry_capability_contract'),
    ('jsonschema', 'jsonschema'), ('mcp', 'mcp'), ('ortools', 'ortools.sat.python.cp_model'),
    ('fastapi', 'fastapi'), ('uvicorn', 'uvicorn'),
)
INSTALL_HINT = 'Install the complete reviewed native kit with Python 3.12 into a fresh environment; use that environment\'s Python.'


class SetupError(ValueError):
    def __init__(self, code, hint):
        self.code, self.hint = code, hint
        super().__init__(code)


def mode_flags(*, verification=False, evidence=False, domains=None):
    if domains is not None and (not isinstance(domains, (list, tuple)) or not domains
            or any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9-]*', name) for name in domains)
            or len(set(domains)) != len(domains)):
        raise SetupError('INVALID_DOMAIN_SELECTION', 'Select each advertised built-in domain once with --domain.')
    return ((['--verification'] if verification or evidence else []) + (['--evidence'] if evidence else [])
            + [part for name in (domains or []) for part in ('--domain', name)])


def configuration(*, verification=False, evidence=False, name='ocp-native-local', domains=None):
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', name):
        raise SetupError('INVALID_SERVER_NAME', 'Use 1-64 ASCII letters, digits, underscores or hyphens, starting with a letter.')
    # Do not resolve the venv symlink to its base Python: that loses dependencies.
    return {'mcpServers': {name: {'command': str(Path(sys.executable).absolute()),
        'args': ['-I', '-B', '-m', 'ocp_runtime.native_mcp'] + mode_flags(verification=verification, evidence=evidence, domains=domains)}}}


def environment_report(*, verification=False, evidence=False, domains=None):
    verification = verification or evidence
    report = {'status': 'PASS', 'scope': 'Local interpreter, package imports and resources only',
        'python': str(Path(sys.executable).absolute()), 'python_version': sys.version.split()[0],
        'platform': sys.platform, 'packages': {}, 'issues': [], 'probe': {'status': 'NOT_RUN'},
        'model_calls': 0, 'solve_calls': 0}
    report['features'] = {'verification': {'enabled': verification, 'version': None},
                          'evidence': {'enabled': evidence, 'version': None},
                          'expected_tool_count': 11 if evidence else 9 if verification else 8}
    if sys.version_info[:2] != (3, 12):
        report['issues'].append({'code': 'PYTHON_3_12_REQUIRED', 'hint': INSTALL_HINT})
    if os.name != 'posix':
        report['issues'].append({'code': 'PLATFORM_NOT_SUPPORTED', 'hint': 'Use the local reference on macOS or Linux.'})
    packages = PACKAGES + ((('ocp-conformance-candidate', 'conformance.assessment'),) if verification else ())
    for distribution, module in packages:
        try:
            report['packages'][distribution] = version(distribution)
        except PackageNotFoundError:
            report['packages'][distribution] = None
            report['issues'].append({'code': 'MISSING_DEPENDENCY', 'package': distribution, 'hint': INSTALL_HINT})
            continue
        try:
            import_module(module)
        except Exception as error:
            report['issues'].append({'code': 'DEPENDENCY_IMPORT_FAILED', 'package': distribution,
                'error_type': type(error).__name__, 'hint': INSTALL_HINT})
    if not report['issues']:
        try:
            from ocp_candidate.native import native_contract
            from ocp_runtime.native_server import reference_domains
            native_contract()
            registrations = reference_domains(domains)
            report['domains'] = [item.domain.problem_type for item in registrations]
            report['profiles'] = {item.domain.problem_type: item.domain.capabilities()['domainProfile'] for item in registrations}
            report['contracts'] = {'native': '1', 'domain_payload': 'ocp-core-request/0.1.0'}
            if verification:
                from conformance.assessment import builtin_checkers
                from ocp_runtime.native_verification import VERIFICATION_VERSION
                builtin_checkers()
                report['features']['verification']['version'] = VERIFICATION_VERSION
            if evidence:
                from ocp_runtime.native_evidence import EvidenceService, EVIDENCE_VERSION
                from conformance.preparation import REQUIREMENTS_SCHEMA
                from ocp_runtime.native_evidence_registry import IDENTITY_SCHEMA
                from foundry_capability_contract import MemoryJobStore
                service = EvidenceService({item.domain.problem_type: item.domain for item in registrations}, MemoryJobStore())
                if service.context()['requirements_schema'] != IDENTITY_SCHEMA:
                    raise ValueError('EVIDENCE_RESOURCES_MISMATCH')
                if 'worker-scheduling' in service.clients:
                    worker_catalog = service.clients['worker-scheduling'].capabilities()
                    if service.context('worker-scheduling', worker_catalog)['requirements_schema'] != REQUIREMENTS_SCHEMA:
                        raise ValueError('EVIDENCE_RESOURCES_MISMATCH')
                report['features']['evidence']['version'] = EVIDENCE_VERSION
        except Exception as error:
            invalid_selection = isinstance(error, ValueError) and str(error) == 'INVALID_DOMAIN_SELECTION'
            report['issues'].append({'code': 'INVALID_DOMAIN_SELECTION' if invalid_selection else 'INSTALLED_RESOURCES_INVALID',
                                    'error_type': type(error).__name__,
                                    'hint': 'Select distinct supported domains: routing-basic, worker-scheduling, inventory-replenishment.' if invalid_selection else INSTALL_HINT})
    if report['issues']:
        report['status'] = 'FAIL'
    return report


def check_features(content, *, verification=False, evidence=False, domains, domain=None, profile=None):
    """Discovery must match the selected installed binding, including its scope."""
    if ('verification' in content) != bool(verification) or ('evidence' in content) != bool(evidence):
        raise SetupError('MCP_FEATURE_MISMATCH', 'The server features differ from the requested mode; reconnect to this installation.')
    if verification:
        from ocp_runtime.native_verification import VERIFICATION_VERSION
        if not isinstance(content['verification'], dict) or content['verification'].get('version') != VERIFICATION_VERSION:
            raise SetupError('MCP_FEATURE_MISMATCH', 'The verification version differs; reinstall a matching kit.')
    if evidence:
        from ocp_runtime.native_evidence import EVIDENCE_VERSION
        value = content['evidence']
        scope = value.get('capability_scope', {}) if isinstance(value, dict) else {}
        if (not isinstance(value, dict) or value.get('version') != EVIDENCE_VERSION
                or not isinstance(scope, dict) or not all(key in scope for key in
                    ('configured_domains', 'selected_domain', 'selected_profile', 'catalog_scope'))
                or scope.get('configured_domains') != domains
                or scope.get('selected_domain') != domain or scope.get('selected_profile') != profile
                or scope.get('catalog_scope') != ('SELECTED_DOMAIN_ONLY' if domain else 'DOMAIN_INDEX')):
            raise SetupError('MCP_FEATURE_MISMATCH', 'The evidence version or domain scope differs; reconnect to a matching kit.')


async def probe_stdio(*, verification=False, evidence=False, timeout=30, domains=None):
    """Only discovery: no input data, solve, credentials or tenant arguments."""
    from mcp import Client, StdioServerParameters
    verification = verification or evidence
    selected_domains = domains
    config = configuration(verification=verification, evidence=evidence, domains=domains)['mcpServers']['ocp-native-local']
    parameters = StdioServerParameters(command=config['command'], args=config['args'],
        env={'PATH': os.defpath, 'HOME': str(Path.home()), 'PYTHONDONTWRITEBYTECODE': '1'})
    # The client context enters and exits in one task, including timeout cleanup.
    async with Client(parameters, read_timeout_seconds=timeout) as client:
        tools = [tool.name for tool in (await client.list_tools()).tools]
        expected = (BASE_TOOLS | ({'ocp_native_verify'} if verification else set())
                    | ({'ocp_native_prepare', 'ocp_native_explain'} if evidence else set()))
        if len(tools) != len(expected) or set(tools) != expected:
            raise SetupError('MCP_TOOL_MISMATCH', 'The installed reference tool set differs; reinstall a complete matching kit.')
        async def context(arguments):
            response = await client.call_tool('ocp_native_context', arguments)
            if response.is_error or not isinstance(response.structured_content, dict):
                raise SetupError('MCP_CONTEXT_FAILED', 'Discovery failed; inspect local server stderr and the installed package versions.')
            return response.structured_content
        listing = await context({})
        domains = listing.get('availableDomains')
        if not isinstance(domains, list) or not domains or any(not isinstance(d, str) for d in domains) or len(set(domains)) != len(domains):
            raise SetupError('MCP_CONTEXT_INVALID', 'The server returned an invalid domain list; reinstall a matching kit.')
        if selected_domains is not None and set(domains) != set(selected_domains):
            raise SetupError('MCP_DOMAIN_MISMATCH', 'The server exposes different domains; reconnect using the generated configuration.')
        check_features(listing, verification=verification, evidence=evidence, domains=domains)
        catalogs = []
        for domain in domains:
            detail = await context({'domain': domain})
            catalog = detail.get('catalog')
            if not isinstance(catalog, dict) or not all(catalog.get(field) for field in (
                'domainProfile', 'catalogDigest', 'input_schema', 'requestTemplate', 'selectionTemplate')):
                raise SetupError('MCP_CONTEXT_INVALID', 'A domain catalog is incomplete; inspect the installed profile resources.')
            if detail.get('availableDomains') != domains:
                raise SetupError('MCP_CONTEXT_INVALID', 'The domain list changed during discovery; inspect server configuration.')
            check_features(detail, verification=verification, evidence=evidence, domains=domains,
                           domain=domain, profile=catalog['domainProfile'])
            catalogs.append({'domain': domain, 'profile': catalog['domainProfile'], 'catalog_digest': catalog['catalogDigest']})
        return {'status': 'PASS', 'scope': 'Actual stdio initialization, tool listing and catalog discovery only',
                'tools': sorted(tools), 'catalogs': catalogs, 'solve_calls': 0,
                'feature_versions': {name: listing[name]['version'] for name in ('verification','evidence') if name in listing}}


def doctor(*, verification=False, evidence=False, probe=False, timeout=30, domains=None):
    report = environment_report(verification=verification, evidence=evidence, domains=domains)
    if probe and report['status'] == 'PASS':
        try:
            async def bounded():
                return await asyncio.wait_for(probe_stdio(verification=verification, evidence=evidence, timeout=timeout, domains=domains), timeout=timeout)
            report['probe'] = asyncio.run(bounded())
        except Exception as error:
            # The stdio client's task group can wrap a single discovery error.
            # Preserve its actionable diagnostic without hiding mixed failures.
            cause = error
            while isinstance(cause, BaseExceptionGroup) and len(cause.exceptions) == 1:
                cause = cause.exceptions[0]
            if isinstance(cause, SetupError):
                code, hint = cause.code, cause.hint
            elif isinstance(cause, TimeoutError):
                code, hint = 'MCP_PROBE_TIMEOUT', 'Server startup or discovery exceeded the limit; inspect stderr and retry after correcting the cause.'
            else:
                code, hint = 'MCP_PROBE_FAILED', 'Check localhost permissions and local server stderr, then rerun doctor --probe.'
            report['probe'] = {'status': 'FAIL', 'code': code, 'error_type': type(error).__name__, 'hint': hint}
            report['status'] = 'FAIL'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', action='version', version=version('ocp-candidate'))
    commands = parser.add_subparsers(dest='command', required=True)
    serve = commands.add_parser('serve', help='Start the installed reference MCP server over stdio')
    config = commands.add_parser('config', help='Print local MCP JSON configuration without editing a host')
    config.add_argument('--name', default='ocp-native-local', help='Server name in generated configuration')
    check = commands.add_parser('doctor', help='Inspect the installed environment; optionally probe real stdio discovery')
    check.add_argument('--probe', action='store_true', help='Start a temporary local server and discover tools/catalogs; no solve')
    check.add_argument('--timeout', type=int, default=30, choices=range(1, 121), metavar='SECONDS')
    for command in (serve, config, check):
        command.add_argument('--verification', action='store_true', help='Enable the optional independent checker integration')
        command.add_argument('--evidence', action='store_true', help='Enable checked preparation/explanation; includes verification (11 tools)')
        command.add_argument('--domain', action='append', help='Expose only this built-in domain; repeat to select several (default: all)')
    args = parser.parse_args(argv)
    if args.command == 'doctor':
        report = doctor(verification=args.verification, evidence=args.evidence, probe=args.probe, timeout=args.timeout, domains=args.domain)
        print(json.dumps(report, indent=2))
        return 0 if report['status'] == 'PASS' else 1
    try:
        value = configuration(verification=args.verification, evidence=args.evidence, name=getattr(args, 'name', 'ocp-native-local'), domains=args.domain)
        report = environment_report(verification=args.verification, evidence=args.evidence, domains=args.domain)
        if report['status'] != 'PASS':
            print(json.dumps(report), file=sys.stderr)
            return 1
        if args.command == 'config':
            print(json.dumps(value, indent=2))
        else:
            from .native_mcp import main as serve_main
            serve_main(mode_flags(verification=args.verification, evidence=args.evidence, domains=args.domain))
        return 0
    except SetupError as error:
        print(json.dumps({'status': 'FAIL', 'code': error.code, 'hint': error.hint}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
