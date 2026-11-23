"""Exercise the documented generic server quickstarts in an isolated source copy."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import shutil
import sys

VALIDATE = '''import importlib.metadata as m,importlib.util,json,stat,sys
from pathlib import Path
assert m.version('ocp-candidate')==sys.argv[1]
for name in ('foundry_capability_contract','ocp_primary_bridge','ocp_native_catalog','ocp_catalog_bridge'):assert importlib.util.find_spec(name)is None
p=Path('.quickstart');c=json.loads((p/'local-config.json').read_text())
assert c['api_endpoint'] is None and c['credential_environment_variable'] is None and c['allowed_local_roots']==[]
assert Path(c['state_directory']).is_absolute() and Path(c['state_directory']).is_relative_to(Path.cwd())
assert stat.S_IMODE(Path(c['state_directory']).stat().st_mode)==0o700 and stat.S_IMODE((p/'local-config.json').stat().st_mode)==0o600
h=json.loads((p/'host-config.json').read_text());assert len(h['mcpServers'])==1
e=next(iter(h['mcpServers'].values()));assert set(e)=={'command','args'} and e['command']==sys.executable
assert e['args']==['-B','-m','ocp_routing_ocp_server.server','serve','--config',str((p/'local-config.json').resolve())]
print(json.dumps({'generic_only':True,'version':m.version('ocp-candidate'),'execute_calls':0}))
'''


def check_cutting_stock(helper, target, work, env):
    guide = (target / 'examples/cutting-stock/README.md').read_text()
    blocks = {}
    for marker in ('build', 'config', 'orders'):
        pattern = rf'^<!-- ocp:cutplan-{marker} -->\n```sh\n(.*?)\n```$'
        matches = re.findall(pattern, guide, re.MULTILINE | re.DOTALL)
        if len(matches) != 1:
            raise ValueError(f'Expected one cutting-stock {marker} command block')
        blocks[marker] = matches[0]
    script = blocks['build'] + '\n' + blocks['config'] + '\n{\n' + blocks['orders'] + '\n} > cutplan-orders.json\n'
    helper.run_command(['/bin/sh', '-eu', '-c', script], cwd=target, env=env,
                       log=work / 'logs/cutplan.log', timeout=180)
    remaining = (target / 'cutplan-orders.json').read_text().strip()
    jobs = set()
    decoder = json.JSONDecoder()
    expected_checks = {'bar_count', 'each_piece_once', 'stock_capacity', 'independent_minimum'}
    for count in (2, 3):
        receipt, end = decoder.raw_decode(remaining)
        remaining = remaining[end:].strip()
        job = receipt['job_id']
        evaluation = receipt['evaluation']
        if (not job or job in jobs or receipt['solution_status'] != 'optimal'
                or receipt['result']['stock_count'] != count or evaluation['status'] != 'pass'
                or {row['id']: row['status'] for row in evaluation['checks']} != dict.fromkeys(expected_checks, 'pass')):
            raise ValueError(f'Invalid receipt for the {count}-bar order')
        jobs.add(job)
        instance = target / '.harness/work/cutplan-demo'
        log = work / f'logs/cutplan-lookup-{count}.log'
        helper.run_command([instance / 'venv/bin/python', 'examples/cutting-stock/order.py',
                            '--config', instance / 'config.json', '--job-id', job],
                           cwd=target, env=env, log=log, timeout=60)
        reopened, _ = decoder.raw_decode(log.read_text().lstrip())
        if reopened != receipt:
            raise ValueError('Reopened job differs from the submitted order')
    if remaining:
        raise ValueError('Unexpected additional cutting-stock receipt')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--selection',required=True);parser.add_argument('--wheelhouse',type=Path,required=True);parser.add_argument('--expected-version',required=True);args=parser.parse_args()
    source=args.source.resolve();spec=importlib.util.spec_from_file_location('generic_harness',source/'tools/check_generic_candidate.py')
    helper=importlib.util.module_from_spec(spec);spec.loader.exec_module(helper)
    work=helper.output_path(source,args.output);work.mkdir(parents=True,mode=0o700,exist_ok=False)
    for name in ('home','tmp','logs'):(work/name).mkdir(mode=0o700)
    target=work/'source';target.mkdir()
    paths=json.loads((source/args.selection).read_text())['files']
    for name in paths:
        dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source/name,dest)
    shell=helper.extract_quickstart((source/'README.md').read_text())
    (target/'executed-quickstart.sh').write_text(shell+'\n')
    env=helper.clean_environment(work,python=sys.executable,wheels=args.wheelhouse)
    helper.run_command(['/bin/sh','-eu','executed-quickstart.sh'],cwd=target,env=env,log=work/'logs/shell.log',timeout=300)
    python=target/'.quickstart-venv/bin/python'
    helper.run_command([python,'-I','-B','-c',VALIDATE,args.expected_version],cwd=target,env=env,log=work/'logs/validation.log',timeout=30)
    helper.run_command([python,'-B','-m','pip','check'],cwd=target,env=env,log=work/'logs/pip-check.log',timeout=30)
    log=(work/'logs/shell.log').read_text()
    if '"status": "READY"' not in log or '"execute_calls": 0' not in log:raise ValueError('QUICKSTART_READY_EVIDENCE_MISSING')
    cutting_stock = 'examples/cutting-stock/README.md' in paths
    if cutting_stock:
        check_cutting_stock(helper, target, work, env)
    result={'status':'PASS','tests_run':2 if cutting_stock else 1,'errors':0,'failures':0,'skipped':0,'readme_sha256':helper.sha(source/'README.md'),
        'cutting_stock_orders_and_lookups':cutting_stock,
        'executed_shell_sha256':hashlib.sha256(shell.encode()).hexdigest(),'scope':'Marked quickstart commands executed in a fresh source copy; cutting-stock jobs reopened when selected',
        'expected_version':args.expected_version,'no_native_contract_package':True,'no_key_no_remote_endpoint':True,
        'wheel_sha256':{p.name:helper.sha(p)for p in sorted((target/'.harness/work/dist').glob('*.whl'))},
        'services_started':4 if cutting_stock else 0,'models':0,'network_denial_enforced':False,'dependency_downloads':0,'external_host_ui':'NOT_RUN','publication_authorized':False}
    with(work/'result.json').open('x')as out:json.dump(result,out,indent=2);out.write('\n')
    print(json.dumps(result))


if __name__=='__main__':main()
