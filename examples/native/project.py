"""Create and run an independent local project using installed OCP packages.

This application is a replaceable example, not a required protocol layer.
It never loads Python code from input data or a saved execution record.
"""
import argparse
from copy import deepcopy
import hashlib
from importlib.metadata import distributions
import json
from pathlib import Path
import platform
import re
import shutil
import sys
import uuid


class ProjectError(ValueError):
    def __init__(self, code, **details):
        super().__init__(code)
        self.code, self.details = code, details


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n').encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    # No implicit duplicate-key or nonfinite-number coercion, even before install.
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result: raise ProjectError('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    with Path(path).open('rb') as stream: raw = stream.read(1048577)
    if len(raw) > 1048576: raise ProjectError('FILE_TOO_LARGE')
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ProjectError('NONFINITE_JSON')))


def save(path, value):
    # Journal updates are atomic; the output directory is reserved before execution.
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_bytes(encoded(value))
    temporary.replace(path)


def config(path):
    value = read(path)
    keys = {'format', 'domain', 'profile', 'input'}
    if not isinstance(value, dict) or set(value) != keys or value['format'] != 'ocp-project/1':
        raise ProjectError('PROJECT_CONFIG_INVALID')
    if not isinstance(value['domain'], str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,79}', value['domain']):
        raise ProjectError('PROJECT_DOMAIN_INVALID')
    if (not isinstance(value['profile'], dict) or set(value['profile']) != {'id', 'version'}
            or any(not isinstance(v, str) or not v for v in value['profile'].values())):
        raise ProjectError('PROJECT_PROFILE_INVALID')
    name = value['input']
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9_.+-]+\.json', name):
        raise ProjectError('PROJECT_INPUT_NAME_INVALID')
    source = path.parent / name
    if source.is_symlink(): raise ProjectError('PROJECT_INPUT_SYMLINK')
    data = read(source)
    if not isinstance(data, dict): raise ProjectError('PROJECT_INPUT_INVALID')
    return value, data


def initialize(destination):
    root = Path(__file__).resolve().parent
    manifest = read(root / 'manifest.json')
    if manifest.get('format') != 'ocp-native-review-kit/1': raise ProjectError('KIT_INVALID')
    files = manifest['files']
    wheels = manifest['python_wheels']
    optional = manifest.get('example_wheels', {})
    names = {'install.py', 'constraints.txt', 'project.py', 'PROJECT_GUIDE.md',
             'mcp_config.py', 'mcp_walkthrough.py', 'byo_worker_scenarios.py',
             'routing-input.json', 'worker-input.json', 'inventory-input.json',
             'budget-input.json', 'inspection.py', 'INSPECTION_GUIDE.md',
             'inspection-workers.csv', 'inspection-tasks.csv', 'inspection-costs.csv',
             *wheels.values(), *optional.values()}
    for name in names:
        if not re.fullmatch(r'[A-Za-z0-9_.+-]+', name): raise ProjectError('KIT_INVALID')
        path = root / name
        if path.is_symlink() or name not in files or digest(path.read_bytes()) != files[name]:
            raise ProjectError('KIT_CHANGED', file=name)
    try: destination.mkdir(parents=True, exist_ok=False)
    except FileExistsError: raise ProjectError('PROJECT_EXISTS') from None
    for name in names: shutil.copyfile(root / name, destination / name)
    shutil.copyfile(root / 'PROJECT_GUIDE.md', destination / 'README.md')
    for domain, profile, source in [('routing-basic','routing.basic','routing'),
                                    ('worker-scheduling','worker.scheduling','worker'),
                                    ('inventory-replenishment','inventory.replenishment','inventory'),
                                    ('budget-selection','example.budget-selection','budget')]:
        save(destination / (source + '-project.json'), {'format':'ocp-project/1','domain':domain,
             'profile':{'id':profile,'version':'0.1.0'},'input':source + '-input.json'})
    save(destination / 'ADOPTION_REVIEW.json', {'format':'ocp-adoption-review/1',
        'internal_owner_acceptance':'NOT_RUN', 'external_independent_developer':'NOT_RUN',
        'tasks': {name:'NOT_STARTED' for name in ['own_input','changed_condition','engine_swap','mcp','independent_check']},
        'findings':[], 'note':'Automation cannot fill human acceptance. Record actual reviewer findings separately.'})
    save(destination / 'SOURCE_KIT.json', {'manifest_sha256':digest((root / 'manifest.json').read_bytes()),
        'scope':'Local project preparation; no sharing, publication or production adoption.'})
    (destination / '.gitignore').write_text('.native*/\nruns/\nreviews/\n.env*\n__pycache__/\n')
    save(destination / 'manifest.json', {'format':'ocp-native-review-kit/1', 'publication_authorized':False,
        'python_wheels':wheels, 'example_wheels':optional,
        'files':{p.name:digest(p.read_bytes()) for p in sorted(destination.iterdir()) if p.is_file()}})
    return {'status':'PREPARED','directory':str(destination),'execute_calls':0,'model_calls':0}


def summary(response, check):
    metric = check['checks']['objective_recomputation']
    return {'solution_status':response['status'], 'objective_value':metric['value'],
            'objective_unit':metric.get('unit'), 'optimality':check['checks']['optimality']['status'],
            'infeasibility':check['checks']['infeasibility']['status']}


def run(project, output, *, engine='reference', extension=None, checker_factory=None):
    if output.exists() or output.is_symlink(): raise ProjectError('OUTPUT_EXISTS', submit_attempts=0)
    settings, data = config(project)
    from conformance.assessment import assess, load_registry
    from ocp_runtime.native_server import LocalAPI
    registrations = None
    if extension:
        if engine != 'reference': raise ProjectError('ENGINE_OPTIONS_CONFLICT')
        from ocp_runtime.native_extension import load_extension
        registrations = load_extension(extension)
    elif engine == 'byo':
        if settings['domain'] != 'worker-scheduling': raise ProjectError('BYO_WORKER_DOMAIN_REQUIRED')
        try:
            from ocp_worker_greedy.registration import registration
        except ModuleNotFoundError as error:
            if error.name != 'ocp_worker_greedy': raise
            raise ProjectError('BYO_ENGINE_NOT_INSTALLED') from None
        registrations = [registration()]
    registry = load_registry(checker_factory)
    registry.resolve(settings['profile'])  # Missing checker rejected before any job.
    journal = {'format':'ocp-project-run/1', 'state':'PREPARING', 'submit_attempts':0,
               'model_calls':0,'human_acceptance':'NOT_RUN', 'project':settings,
               'engine_choice':extension or engine, 'job_id':None, 'idempotency_key':str(uuid.uuid4())}
    try: output.mkdir(parents=True, exist_ok=False)
    except FileExistsError: raise ProjectError('OUTPUT_EXISTS', submit_attempts=0) from None
    save(output / 'run.json', journal)
    try:
        with LocalAPI(registrations) as local:
            api = local.client(settings['domain'])
            catalog = api.capabilities()
            if catalog.get('contractVersion') != '1' or catalog['domainProfile'] != settings['profile']:
                raise ProjectError('PROFILE_OR_CONTRACT_MISMATCH')
            request = deepcopy(catalog['requestTemplate'])
            request.update(input=data, request_id=journal['idempotency_key'])
            requirements = api.resolve_data_requirements(catalog['selectionTemplate'])
            validation = api.validate(request)
            save(output / 'request.json', request)
            save(output / 'context.json', {'catalog':catalog, 'requirements':requirements, 'validation':validation})
            if not validation['valid']:
                raise ProjectError('INPUT_REJECTED', issues=validation['issues'])
            # Save identity before crossing the submit boundary. Never automatically retry.
            journal.update(state='SUBMITTING', submit_attempts=1)
            save(output / 'run.json', journal)
            submitted = api.submit(request, tenant='local-project', idempotency_key=journal['idempotency_key'])
            journal.update(state='SUBMITTED', job_id=submitted['job']['jobId'])
            save(output / 'run.json', journal)
            job = api.wait(journal['job_id'], tenant='local-project')
            result = api.result(journal['job_id'], tenant='local-project')
            if result['jobId'] != job['jobId'] or result['status'] != job['status'] or job['status'] not in ('succeeded','infeasible'):
                raise ProjectError('JOB_NOT_SUCCESSFUL')
            journal['state'] = 'RESULT_RECEIVED'
            response = result['result']
            check = assess(request, response, registry=registry)
            save(output / 'response.json', response)
            save(output / 'check.json', check)
            save(output / 'job.json', {'job':job,'result':result,'replayed':submitted['replayed']})
            if check['status'] != 'PASS': raise ProjectError('INDEPENDENT_CHECK_FAILED')
            journal.update(state='VERIFIED', job_status=job['status'], **summary(response, check))
        save(output / 'environment.json', {'python':platform.python_version(), 'system':platform.system(),
             'machine':platform.machine(), 'packages':sorted([[d.metadata['Name'],d.version] for d in distributions()]),
             'application_sha256':digest(Path(__file__).read_bytes())})
        save(output / 'run.json', journal)
        save(output / 'files.sha256.json', {p.name:digest(p.read_bytes()) for p in sorted(output.iterdir()) if p.is_file()})
        return {'status':'PASS','run':str(output),'submit_attempts':1,'model_calls':0, **summary(response,check)}
    except Exception as error:
        code = getattr(error, 'code', 'PROJECT_RUN_FAILED')
        state = 'FAILED' if journal['state'] == 'RESULT_RECEIVED' else 'UNCERTAIN' if journal['submit_attempts'] else 'REJECTED'
        journal.update(state=state, error=code)
        if isinstance(error, ProjectError): journal.update(error_details=error.details)
        journal['recovery'] = ('No automatic retry. Keep this identity and evidence. This local server is volatile; '
            'after shutdown this journal cannot resume its jobs or prove cancellation. A new experiment needs a new output directory.')
        save(output / 'run.json', journal)
        raise ProjectError(code, submit_attempts=journal['submit_attempts'], record=str(output / 'run.json'),
                           **(error.details if isinstance(error, ProjectError) else {})) from None


RUN_FILES = {'run.json','context.json','request.json','response.json','job.json','check.json','environment.json'}


def review(folder, *, checker_factory=None):
    # A transcript cannot choose/import its own checker, engine or SDK.
    manifest = read(folder / 'files.sha256.json')
    if not isinstance(manifest, dict) or set(manifest) != RUN_FILES: raise ProjectError('RUN_MANIFEST_INVALID')
    for name, expected in manifest.items():
        path = folder / name
        if path.is_symlink() or digest(path.read_bytes()) != expected: raise ProjectError('RUN_FILE_CHANGED', file=name)
    from conformance.assessment import assess, load_registry
    record, request, response = [read(folder / name) for name in ['run.json','request.json','response.json']]
    if record.get('format') != 'ocp-project-run/1' or record.get('state') != 'VERIFIED': raise ProjectError('RUN_NOT_VERIFIED')
    job = read(folder / 'job.json')
    context = read(folder / 'context.json')
    if (record.get('idempotency_key') != request['request_id']
            or record.get('job_id') != job['job']['jobId']
            or job['result']['jobId'] != job['job']['jobId']
            or record.get('job_status') != job['job']['status']
            or job['result']['status'] != job['job']['status']
            or job['result']['result'] != response
            or context['catalog']['domainProfile'] != request['domain_profile']
            or record['project']['profile'] != request['domain_profile']):
        raise ProjectError('RUN_IDENTITY_MISMATCH')
    check = assess(request,response,registry=load_registry(checker_factory))
    if check['status'] != 'PASS': raise ProjectError('INDEPENDENT_CHECK_FAILED')
    if any(record.get(k) != v for k,v in summary(response,check).items()): raise ProjectError('RUN_SUMMARY_MISMATCH')
    return {'status':'PASS','scope':'Offline integrity and independent transcript recheck; no execution attestation or human acceptance.',
            'execute_calls':0,'model_calls':0,'request':request,'response':response,'independent_check':check,
            'summary':summary(response,check)}


def compare(left, right, *, checker_factory=None):
    a, b = [review(path, checker_factory=checker_factory) for path in [left,right]]
    ar, br = a['request'], b['request']
    if ar['domain_profile'] != br['domain_profile']: raise ProjectError('COMPARISON_PROFILE_MISMATCH')
    av, bv = a['summary']['objective_value'], b['summary']['objective_value']
    am, bm = [r['independent_check']['checks']['objective_recomputation'] for r in [a,b]]
    comparable = av is not None and bv is not None and all(am.get(k) == bm.get(k) for k in ['unit','definition'])
    same = all(ar[k] == br[k] for k in ['input','configuration','execution_profile'])
    return {'status':'PASS','same_problem':same, 'objectives_comparable':comparable,
            'right_minus_left':bv-av if comparable else None, 'left':a['summary'],'right':b['summary'],
            'interpretation':'A numeric difference is not an engine ranking when inputs differ; null is not zero.',
            'execute_calls':0,'model_calls':0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init'); init.add_argument('--directory',type=Path,required=True)
    solve = commands.add_parser('run'); solve.add_argument('--project',type=Path,required=True)
    solve.add_argument('--output',type=Path,required=True)
    solve.add_argument('--engine',choices=['reference','byo'],default='reference')
    solve.add_argument('--extension',help='Trusted installed MODULE:FACTORY selected by the host')
    solve.add_argument('--checker-factory',help='Trusted installed MODULE:FACTORY selected by the host')
    verify = commands.add_parser('review'); verify.add_argument('directory',type=Path)
    verify.add_argument('--checker-factory')
    diff = commands.add_parser('compare'); diff.add_argument('left',type=Path); diff.add_argument('right',type=Path)
    diff.add_argument('--checker-factory')
    args = parser.parse_args(argv)
    try:
        if args.command == 'init': result = initialize(args.directory)
        elif args.command == 'run': result = run(args.project,args.output,engine=args.engine,extension=args.extension,checker_factory=args.checker_factory)
        elif args.command == 'review': result = review(args.directory,checker_factory=args.checker_factory)
        else: result = compare(args.left,args.right,checker_factory=args.checker_factory)
        print(json.dumps(result,allow_nan=False)); return 0
    except Exception as error:
        result = {'status':'FAIL','code':getattr(error,'code','PROJECT_COMMAND_FAILED'),'model_calls':0}
        if isinstance(error, ProjectError): result.update(error.details)
        print(json.dumps(result,allow_nan=False)); return 1


if __name__ == '__main__': sys.exit(main())
