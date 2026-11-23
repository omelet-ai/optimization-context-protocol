"""Reproduce the generic installed/README/MCP journey using pinned offline wheels.

Output is always a fresh directory outside source. This check neither publishes
sources nor validates an external host UI, production auth or consumer migration.
"""
import argparse
import ctypes
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import threading
import time
import tomllib

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SELECTION = 'provenance/public-format-candidate-selection.json'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def output_path(source, output):
    source, raw = Path(source).resolve(), Path(output).absolute()
    if any(p.is_symlink() for p in [raw, *raw.parents]) or raw.exists():
        raise ValueError('OUTPUT_EXISTS_OR_SYMLINK')
    output = raw.resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('OUTPUT_MUST_BE_OUTSIDE_SOURCE')
    return output


def clean_environment(work, *, python=None, wheels=None):
    work = Path(work)
    env = {'PATH': os.defpath, 'HOME': str(work / 'home'), 'TMPDIR': str(work / 'tmp'),
           'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1', 'GIT_OPTIONAL_LOCKS': '0',
           'PIP_NO_INDEX': '1', 'PIP_CONFIG_FILE': os.devnull, 'PIP_DISABLE_PIP_VERSION_CHECK': '1',
           'PIP_NO_CACHE_DIR': '1'}
    if python is not None: env['PATH'] = str(Path(python).absolute().parent) + os.pathsep + os.defpath
    if wheels is not None: env['PIP_FIND_LINKS'] = Path(wheels).absolute().as_uri()
    return env


def extract_quickstart(text):
    start, end = '<!-- ocp:generic-quickstart:start -->', '<!-- ocp:generic-quickstart:end -->'
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError('EXACT_QUICKSTART_MARKERS_REQUIRED')
    match = re.fullmatch(r'\s*```sh\n(.*?)\n```\s*', text.split(start, 1)[1].split(end, 1)[0], re.S)
    if match is None: raise ValueError('EXACT_QUICKSTART_SHELL_REQUIRED')
    return match.group(1)


def passed(report, minimum):
    if (report.get('status') != 'PASS' or type(report.get('tests_run')) is not int
            or report['tests_run'] < minimum or any(type(report.get(k)) is not int or report[k] != 0
            for k in ('errors', 'failures', 'skipped'))):
        raise ValueError('INCOMPLETE_OR_FAILED_CHECK')
    return report


def group_alive(pgid):
    try: os.killpg(pgid, 0)
    except ProcessLookupError: return False
    return True


def process_details(pid):
    """Kernel birth identity, following tools/product_lab/environment.py.

    Only IDs, ownership and start time are read, never arguments or environment.
    """
    if type(pid) is not int or pid <= 0: raise ValueError('POSITIVE_PID_REQUIRED')
    if sys.platform == 'darwin':
        class Info(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint32) for name in ('flags', 'status', 'xstatus', 'pid', 'ppid', 'uid', 'gid', 'ruid', 'rgid', 'svuid', 'svgid', 'reserved')]
            _fields_ += [('comm', ctypes.c_char * 16), ('name', ctypes.c_char * 32)]
            _fields_ += [(name, ctypes.c_uint32) for name in ('nfiles', 'pgid', 'pjobc', 'tdev', 'tpgid')]
            _fields_ += [('nice', ctypes.c_int32), ('start_sec', ctypes.c_uint64), ('start_usec', ctypes.c_uint64)]
        value = Info(); lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        lib.proc_pidinfo.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_uint64, ctypes.c_void_p, ctypes.c_int]
        lib.proc_pidinfo.restype = ctypes.c_int
        ctypes.set_errno(0); size = lib.proc_pidinfo(pid, 3, 0, ctypes.byref(value), ctypes.sizeof(value))
        if size == 0 and ctypes.get_errno() in (errno.ESRCH, errno.ENOENT): return None
        if size != ctypes.sizeof(value) or value.pid != pid: raise ValueError('KERNEL_IDENTITY_UNAVAILABLE')
        return {'pid': pid, 'ppid': value.ppid, 'pgid': value.pgid, 'uid': value.uid,
                'started': 'darwin:%d:%d' % (value.start_sec, value.start_usec), 'zombie': value.status == 5}
    if sys.platform.startswith('linux'):
        try:
            path = Path('/proc') / str(pid); raw = (path / 'stat').read_text(); fields = raw[raw.rindex(')') + 2:].split()
            boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
            return {'pid': pid, 'ppid': int(fields[1]), 'pgid': int(fields[2]), 'uid': path.stat().st_uid,
                    'started': 'linux:%s:%s' % (boot, fields[19]), 'zombie': fields[0] in ('Z', 'X', 'x')}
        except FileNotFoundError: return None
    raise ValueError('UNSUPPORTED_KERNEL_IDENTITY')


def process_identity(value):
    return {key: value[key] for key in ('pid', 'pgid', 'uid', 'started')}


def group_members(pgid):
    """Enumerate kernel IDs in one group; no ps command or argument access."""
    if sys.platform == 'darwin':
        lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
        lib.proc_listpids.argtypes = [ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_int]
        lib.proc_listpids.restype = ctypes.c_int
        capacity = 64
        while True:
            values = (ctypes.c_int * capacity)()
            ctypes.set_errno(0)
            count = lib.proc_listpids(2, pgid, ctypes.byref(values), ctypes.sizeof(values))
            error = ctypes.get_errno()
            if count == 0 and error: raise OSError(error, 'GROUP_ENUMERATION_FAILED')
            if count < 0 or count % ctypes.sizeof(ctypes.c_int): raise ValueError('GROUP_ENUMERATION_INVALID')
            if count < ctypes.sizeof(values): break
            capacity *= 2
            if capacity > 65536: raise ValueError('GROUP_ENUMERATION_TOO_LARGE')
        pids = [pid for pid in values[:count // ctypes.sizeof(ctypes.c_int)] if pid > 0]
    elif sys.platform.startswith('linux'):
        pids = [int(path.name) for path in Path('/proc').iterdir() if path.name.isdigit()]
    else: raise ValueError('UNSUPPORTED_KERNEL_IDENTITY')
    members = []
    for pid in pids:
        row = process_details(pid)
        if row is not None and row['pgid'] == pgid: members.append(row)
    return members


def registry_write(path, value):
    data = (json.dumps(value, sort_keys=True) + '\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
        directory = os.open(Path(path).parent, os.O_RDONLY)
        try: os.fsync(directory)
        finally: os.close(directory)
    except BaseException: raise


def registry_read(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077 or info.st_size > 16384:
            raise ValueError('UNTRUSTED_PROCESS_REGISTRY')
        return json.loads(stream.read())


def register_detached_process(registry, pid):
    """Called immediately after SDK spawn; one explicit detached group only."""
    registry = Path(registry)
    owner = registry_read(registry / 'owner.json')
    current = process_details(os.getpid()); child = process_details(pid)
    if (current is None or process_identity(current) != owner or child is None
            or child['ppid'] != current['pid'] or child['pgid'] != child['pid']
            or child['pgid'] == current['pgid'] or child['uid'] != current['uid']):
        raise ValueError('DETACHED_PROCESS_OWNERSHIP_MISMATCH')
    registry_write(registry / 'child.json', {'controller': owner, 'child': process_identity(child)})
    registry_write(registry / 'complete.json', {'controller': owner, 'children': [pid]})


def registered_groups(registry, owner):
    """Incomplete registration is uncertainty, not evidence of no child."""
    if set(p.name for p in registry.iterdir()) != {'owner.json', 'child.json', 'complete.json'}:
        raise ValueError('PROCESS_REGISTRATION_INCOMPLETE')
    child = registry_read(registry / 'child.json'); complete = registry_read(registry / 'complete.json')
    row = child['child']
    if (registry_read(registry / 'owner.json') != owner or child['controller'] != owner
            or complete != {'controller': owner, 'children': [row['pid']]}
            or set(row) != {'pid', 'pgid', 'uid', 'started'}
            or type(row['pid']) is not int or row['pid'] <= 0 or row['pgid'] != row['pid']
            or row['uid'] != owner['uid'] or row['pgid'] in (owner['pgid'], os.getpgrp())):
        raise ValueError('PROCESS_REGISTRATION_MISMATCH')
    current = process_details(row['pid'])
    if current is not None and process_identity(current) != row:
        raise ValueError('REGISTERED_PROCESS_IDENTITY_CHANGED')
    found = group_members(row['pgid'])
    if found and not any(process_identity(value) == row for value in found):
        raise ValueError('REGISTERED_GROUP_ANCHOR_MISSING')
    return [{'owner': row, 'tracked': [process_identity(value) for value in found]}]


def close_registered_groups(groups):
    receipts = []
    for group in groups:
        owner = group['owner']; tracked = group['tracked']; signals = []; errors = []
        before = None; after = None
        try:
            before = group_members(owner['pgid']); after = before
            for sig in (signal.SIGTERM, signal.SIGKILL):
                if not after: break
                if (not any(process_identity(row) in tracked + [owner] for row in after)
                        or any(row['uid'] != owner['uid'] for row in after)):
                    raise ValueError('REGISTERED_GROUP_ANCHOR_MISSING')
                # Preserve newly observed descendants as anchors before signalling.
                tracked = [process_identity(row) for row in after]
                os.killpg(owner['pgid'], sig); signals.append(sig.name)
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    after = group_members(owner['pgid'])
                    if not after: break
                    time.sleep(.02)
            if after: raise ValueError('REGISTERED_GROUP_SURVIVORS')
        except (ValueError, OSError, subprocess.SubprocessError) as exc: errors.append(str(exc))
        receipts.append({'owner': owner, 'group_before_cleanup': before, 'group_after_cleanup': after,
                         'cleanup_signals': signals, 'errors': errors,
                         'closure': 'CLOSED' if not errors and after == [] else 'UNKNOWN'})
    return receipts


def run_command(argv, *, cwd, env, log, timeout=300, process_registry=None):
    """Own one POSIX group; every exit path records bounded positive closure.

    A terminated parent alone is insufficient: descendants must disappear too.
    Interruptions propagate only after cleanup and a failure receipt are saved.
    """
    log = Path(log)
    receipt_path = log.with_suffix('.receipt.json')
    if any(p.exists() or p.is_symlink() for p in (log, receipt_path)):
        raise ValueError('LOG_EXISTS')
    registry = Path(process_registry) if process_registry is not None else None
    if registry is not None:
        if registry.exists() or any(p.is_symlink() for p in [registry, *registry.parents]): raise ValueError('NEW_PROCESS_REGISTRY_REQUIRED')
        registry.mkdir(mode=0o700)
    process = subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    stdout = stderr = ''
    timed_out = lingering = False
    caught = None
    signals = []; cleanup_errors = []
    previous_handlers = {}
    registry_owner = None; owned_groups = []; registered_closure = []; registry_error = None

    def terminated(signum, frame):
        raise InterruptedError('Controller received signal ' + str(signum))

    def alive():
        try: return group_alive(process.pid)
        except OSError as exc:
            cleanup_errors.append(type(exc).__name__)
            return None

    def signal_group(sig):
        try:
            os.killpg(process.pid, sig)
            signals.append(sig.name)
        except ProcessLookupError: pass
        except OSError as exc: cleanup_errors.append(type(exc).__name__)

    def drain_until(seconds):
        nonlocal stdout, stderr
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            try:
                stdout, stderr = process.communicate(timeout=min(.05, remaining))
            except subprocess.TimeoutExpired: pass
            except (OSError, ValueError) as exc:
                cleanup_errors.append(type(exc).__name__)
                break
            if process.returncode is not None and alive() is False: return
            time.sleep(min(.02, max(0, deadline - time.monotonic())))

    try:
        if threading.current_thread() is threading.main_thread():
            previous_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
            signal.signal(signal.SIGTERM, terminated)
        if registry is not None:
            row = process_details(process.pid)
            if row is None or row['ppid'] != os.getpid() or row['pgid'] != process.pid: raise ValueError('CONTROLLER_IDENTITY_UNAVAILABLE')
            registry_owner = process_identity(row)
            registry_write(registry / 'owner.json', registry_owner)
        stdout, stderr = process.communicate(timeout=timeout)
        lingering = alive() is not False
    except BaseException as exc:
        caught = exc
        timed_out = isinstance(exc, subprocess.TimeoutExpired)
    finally:
        # A second interruption must not abandon our children during this
        # bounded section. Restore the caller's handlers after the receipt.
        try:
            for sig in previous_handlers: signal.signal(sig, signal.SIG_IGN)
            if registry is not None:
                try: owned_groups = registered_groups(registry, registry_owner)
                except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc: registry_error = type(exc).__name__ + ': ' + str(exc)
            if process.returncode is None or alive() is not False:
                signal_group(signal.SIGTERM)
                drain_until(2)
            if process.returncode is None or alive() is not False:
                signal_group(signal.SIGKILL)
                drain_until(2)
            # Re-read after controller shutdown to catch registrations completed
            # during cleanup. Missing/invalid registration still fails closed.
            if registry is not None and not owned_groups:
                try: owned_groups = registered_groups(registry, registry_owner); registry_error = None
                except (ValueError, OSError, KeyError, TypeError, subprocess.SubprocessError) as exc: registry_error = type(exc).__name__ + ': ' + str(exc)
            registered_closure = close_registered_groups(owned_groups)
            reaped = process.returncode is not None
            group_absent = alive() is False
            closed = (reaped and group_absent and not cleanup_errors and registry_error is None
                      and all(row['closure'] == 'CLOSED' for row in registered_closure))
            # These handles are ours even when closure cannot be established.
            for stream in (process.stdout, process.stderr):
                if stream is not None: stream.close()
            with log.open('x') as out: out.write(stdout + '\n' + stderr)
            interrupted = caught is not None and not timed_out
            detached_lingering = any(row['group_before_cleanup'] for row in registered_closure)
            ok = closed and not (timed_out or interrupted or lingering or detached_lingering or process.returncode)
            receipt = {'status': 'PASS' if ok else 'FAIL', 'pid': process.pid, 'pgid': process.pid,
                       'returncode': process.returncode, 'timed_out': timed_out,
                       'interrupted': interrupted, 'exception_type': type(caught).__name__ if caught else None,
                       'unexpected_group_after_parent': lingering, 'cleanup_signals': signals,
                       'process_reaped': reaped, 'group_absent_after_cleanup': group_absent,
                       'closure': 'CLOSED' if closed else 'UNKNOWN', 'cleanup_errors': cleanup_errors,
                       'registered_groups': registered_closure, 'registration_error': registry_error,
                       'unexpected_detached_group_after_parent': detached_lingering,
                       'log_sha256': sha(log)}
            with receipt_path.open('x') as out: json.dump(receipt, out, indent=2); out.write('\n')
        finally:
            for sig, handler in previous_handlers.items(): signal.signal(sig, handler)
    if caught is not None and not timed_out: raise caught
    if not ok: raise RuntimeError('CHILD_FAILED: ' + log.name)
    return receipt


def collect_wheels(directories, output):
    if not directories: raise ValueError('OFFLINE_WHEELHOUSE_REQUIRED')
    candidates = {}
    for directory in directories:
        directory = Path(directory).absolute()
        if not directory.is_dir(): raise ValueError('WHEELHOUSE_NOT_FOUND')
        for path in sorted(directory.glob('*.whl')):
            if path.is_symlink(): raise ValueError('WHEEL_SYMLINK')
            digest = sha(path)
            if path.name in candidates and candidates[path.name][1] != digest:
                raise ValueError('CONFLICTING_DEPENDENCY_WHEELS')
            candidates[path.name] = path, digest
    if not candidates: raise ValueError('EMPTY_WHEELHOUSE')
    output = Path(output); output.mkdir(exist_ok=False)
    for name, (path, _) in candidates.items(): shutil.copyfile(path, output / name)
    return {name: digest for name, (_, digest) in candidates.items()}


def source_selection(source, selection):
    rel = PurePosixPath(selection)
    if rel.is_absolute() or '..' in rel.parts or rel.as_posix() != selection:
        raise ValueError('INVALID_SELECTION_PATH')
    # Use this version's verifier against the exact selected source root.
    # -I omits the script directory; tool dependencies are loaded only from
    # this reviewed harness, never from the installed runtime source tree.
    tool_path = str(Path(__file__).resolve().parent)
    added = tool_path not in sys.path
    if added: sys.path.insert(0, tool_path)
    try:
        from verify_repository import verify
        import verify_repository
    finally:
        if added: sys.path.remove(tool_path)
    previous = verify_repository.ROOT
    try:
        verify_repository.ROOT = source
        report = verify(selection_path=selection)
    finally: verify_repository.ROOT = previous
    paths = json.loads((source / selection).read_text())['files']
    historical = set(json.loads((source / 'provenance/repository-selection.json').read_text())['files'])
    if not historical.issubset(paths): raise ValueError('HISTORICAL_SOURCE_REMOVED')
    return report, paths


def check(source, output, wheelhouses, expected_version, selection=DEFAULT_SELECTION):
    if sys.version_info[:2] != (3, 12) or os.name != 'posix': raise ValueError('PYTHON_3_12_POSIX_REQUIRED')
    source = Path(source).resolve(); work = output_path(source, output)
    selected, paths = source_selection(source, selection)
    version = tomllib.loads((source / 'sdk/python/pyproject.toml').read_text())['project']['version']
    if version != expected_version: raise ValueError('EXPECTED_VERSION_MISMATCH')
    before = {name: sha(source / name) for name in paths}
    work.mkdir(parents=True, mode=0o700, exist_ok=False)
    for name in ('home', 'tmp', 'logs'): (work / name).mkdir(mode=0o700)
    copied = work / 'source'; copied.mkdir()
    for name in paths:
        target = copied / name; target.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source / name, target)
    env = clean_environment(work, python=sys.executable)
    stages = []; reports = {}; error = None; dependency_hashes = {}
    def run(label, argv, *, cwd=work, timeout=300, process_registry=None):
        log = work / 'logs' / (label + '.log')
        try:
            run_command(argv, cwd=cwd, env=env, log=log, timeout=timeout, process_registry=process_registry)
        finally:
            receipt = log.with_suffix('.receipt.json')
            detail = json.loads(receipt.read_text()) if receipt.exists() else {'status': 'NOT_STARTED_OR_UNRECORDED'}
            stages.append({'stage': label, **detail})
    try:
        dependency_hashes = collect_wheels(wheelhouses, work / 'wheels')
        env['PIP_FIND_LINKS'] = (work / 'wheels').as_uri()
        run('fresh-env', [sys.executable, '-B', '-m', 'venv', work / 'env'])
        python = work / 'env/bin/python'
        run('dependencies', [python, '-B', '-m', 'pip', 'install', '--no-index', '--no-compile', '--find-links', work / 'wheels', '-r', copied / 'tools/requirements-dev.lock'])
        builder = "import importlib.util,json;spec=importlib.util.spec_from_file_location('builder',%r);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);print(json.dumps(m.build(%r)))" % (str(copied / 'tools/build_candidate.py'), str(work / 'dist'))
        run('runtime-build', [python, '-B', '-c', builder])
        staged = work / 'routing-source'; shutil.copytree(copied / 'examples/routing-ocp-server', staged)
        run('routing-build', [python, '-B', '-m', 'build', '--wheel', '--no-isolation', '--outdir', work / 'dist', staged])
        wheels = sorted((work / 'dist').glob('*.whl'))
        if len(wheels) != 2: raise ValueError('EXACT_TWO_BUILT_WHEELS_REQUIRED')
        run('install', [python, '-B', '-m', 'pip', 'install', '--no-index', '--no-deps', '--no-compile', *wheels])
        run('pip-check', [python, '-B', '-m', 'pip', 'check'])
        # Published examples must be genuine products of the installed template.
        # A stale generation record would make strip/inject fail for an author.
        generated = sorted({(copied / name).parent for name in paths
                            if name.startswith('examples/') and name.endswith('/.ocp-generation.json')})
        if not generated: raise ValueError('GENERATED_EXAMPLE_RECORD_REQUIRED')
        run('generation-records', [python, '-I', '-B', '-c',
            'import sys; from ocp_runtime.authoring.scaffold import verified_record; '
            '[verified_record(path) for path in sys.argv[1:]]',
            *generated])
        run('installed', [python, '-I', '-B', copied / 'tests/installed/test_generic_runtime.py', '--expected-version', expected_version, '--output', work / 'installed.json'])
        reports['installed'] = passed(json.loads((work / 'installed.json').read_text()), 16)
        run('quickstart', [python, '-I', '-B', copied / 'tests/installed/test_generic_quickstart.py', '--source', copied, '--selection', selection,
                          '--wheelhouse', work / 'wheels', '--output', work / 'quickstart', '--expected-version', expected_version])
        reports['quickstart'] = passed(json.loads((work / 'quickstart/result.json').read_text()), 1)
        quick = work / 'quickstart/source'
        run('mcp', [quick / '.quickstart-venv/bin/python', '-I', '-B', copied / 'tests/installed/test_generic_mcp.py',
                    '--quickstart', quick, '--output', work / 'mcp', '--expected-version', expected_version,
                    '--process-registry', work / 'mcp-processes'], timeout=180, process_registry=work / 'mcp-processes')
        reports['mcp'] = passed(json.loads((work / 'mcp/result.json').read_text()), 1)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc: error = type(exc).__name__ + ': ' + str(exc)
    # Keep failed subreports as observations without accepting their gates.
    observed_reports = {}; observation_errors = {}
    for label, path in {'installed': work / 'installed.json', 'quickstart': work / 'quickstart/result.json', 'mcp': work / 'mcp/result.json'}.items():
        if path.exists():
            try:
                value = json.loads(path.read_text())
                if not isinstance(value, dict): raise ValueError('REPORT_OBJECT_REQUIRED')
                observed_reports[label] = value
            except (ValueError, OSError) as exc: observation_errors[label] = type(exc).__name__
    unchanged = before == {name: sha(source / name) for name in paths}
    copied_unchanged = before == {name: sha(copied / name) for name in paths}
    ok = error is None and not observation_errors and unchanged and copied_unchanged and set(reports) == {'installed', 'quickstart', 'mcp'}
    result = {'status': 'PASS' if ok else 'FAIL', 'tests_run': sum(r.get('tests_run', 0) for r in observed_reports.values() if type(r.get('tests_run')) is int and r['tests_run'] >= 0),
              'tests_accepted': sum(r['tests_run'] for r in reports.values()),
              'errors': 0 if ok else 1, 'failures': 0, 'skipped': 0, 'error': error, 'stages': stages,
              'checks': observed_reports, 'accepted_checks': sorted(reports), 'report_observation_errors': observation_errors,
              'expected_version': expected_version, 'source_selection': selection, 'source_tree_sha256': selected['tree_content_sha256'],
              'source_unchanged': unchanged, 'selected_copy_unchanged': copied_unchanged, 'source_files': len(paths),
              'built_wheels': {p.name: sha(p) for p in sorted((work / 'dist').glob('*.whl'))}, 'dependency_wheels': dependency_hashes,
              'scope': 'Fresh installed generic runtime, verbatim README and local official SDK stdio; no external host UI or full native regression',
              'network_denial_enforced': False, 'dependency_downloads': 0, 'models': 0, 'publication_authorized': False,
              'external_host_ui': 'NOT_RUN', 'consumer_acceptance': 'NOT_RUN'}
    with (work / 'result.json').open('x') as out: json.dump(result, out, indent=2); out.write('\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT); parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wheelhouse', action='append', type=Path, required=True); parser.add_argument('--expected-version', required=True)
    parser.add_argument('--selection', default=DEFAULT_SELECTION); args = parser.parse_args()
    try: report = check(args.source, args.output, args.wheelhouse, args.expected_version, args.selection)
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc: report = {'status': 'FAIL', 'error': type(exc).__name__ + ': ' + str(exc), 'publication_authorized': False}
    print(json.dumps(report)); raise SystemExit(report['status'] != 'PASS')
