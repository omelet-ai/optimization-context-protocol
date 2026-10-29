"""Portable H61/H62 exercise from a public-source kit, without Foundry or a model.

These checks do not promote historical harness evidence or human acceptance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parent.parent


def exercise(kit, wheelhouses, output, suite):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    bundle=output/'kit';shutil.copytree(kit,bundle)
    home=output/'empty-home';home.mkdir()
    binary=output/'bin';binary.mkdir();(binary/'python3.12').symlink_to(sys._base_executable)
    env={'HOME':str(home),'PATH':str(binary)+os.pathsep+os.defpath,'PIP_CONFIG_FILE':os.devnull,
         'PIP_NO_INDEX':'1','PYTHONDONTWRITEBYTECODE':'1',
         'PIP_FIND_LINKS':' '.join(Path(p).resolve().as_uri() for p in wheelhouses)}
    if shutil.which('node',path=env['PATH']):raise ValueError('NODE_PRESENT')
    guide=(bundle/'INSPECTION_GUIDE.md').read_text()
    def call(command,label):
        p=subprocess.run(['/bin/sh','-eu','-c',command],cwd=bundle,env=env,capture_output=True,text=True,timeout=400)
        (output/(label+'.log')).write_text(p.stdout+'\n'+p.stderr)
        if p.returncode:raise RuntimeError('Inspection check failed; see '+str(output/(label+'.log')))
        return json.loads(p.stdout)
    def block(name):
        return re.search(r'<!-- ocp:'+name+r' -->\s*```sh\n(.*?)\n```',guide,re.S).group(1)
    call(block('inspection-init'),'init')
    bundle=output/'inspection project'
    call(block('inspection-install'),'install')
    shutil.copyfile(suite,bundle/'inspection_suite.py')
    report=call('.native/bin/python -I -B inspection_suite.py','suite')
    # Installed optional dependencies must also match the public prerelease SDK.
    call(''' .native/bin/python -I -B - <<'PY'
import json,subprocess,sys
from pathlib import Path
manifest=json.loads(Path('manifest.json').read_text())
wheels=[str(Path(n).resolve()) for key,n in manifest['example_wheels'].items() if key.startswith('budget_')]
subprocess.run([sys.executable,'-m','pip','install','--no-index','--no-deps','--no-compile',*wheels],check=True,stdout=subprocess.DEVNULL)
subprocess.run([sys.executable,'-m','pip','check'],check=True,stdout=subprocess.DEVNULL)
print(json.dumps({'status':'PASS'}))
PY''','optional-dependencies')
    budget=call('.native/bin/python -I -B project.py run --project budget-project.json --output runs/budget-public --extension ocp_budget_engine.registration:extension --checker-factory ocp_budget_check:registry','budget-smoke')
    if budget['objective_value']!=11 or budget['status']!='PASS':raise AssertionError('BUDGET_SMOKE_FAILED')
    report.update(platform=platform.platform(),python=platform.python_version(),node_present=False,
                  optional_dependencies='PASS',budget_objective=11,foundry_checkout_required=False,
                  kit_manifest_sha256=hashlib.sha256((Path(kit)/'manifest.json').read_bytes()).hexdigest())
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def linux(kit,wheelhouses,output,docker):
    if len(wheelhouses)!=1:raise ValueError('Linux requires one reviewed Linux wheelhouse')
    wheels=Path(wheelhouses[0]).resolve();kit=Path(kit).resolve();output=Path(output).resolve()
    dependency=json.loads((ROOT/'tools/linux-dependencies.json').read_text())
    if {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in wheels.glob('*.whl')}!=dependency['files']:
        raise ValueError('LINUX_WHEELHOUSE_DRIFT')
    output.mkdir(parents=True,exist_ok=False)
    argv=[docker,'run','--rm','--pull=never','--platform=linux/amd64','--network=none','--read-only',
          '--cap-drop=ALL','--security-opt=no-new-privileges','--pids-limit=256','--memory=2g','--cpus=2',
          '--user',f'{os.getuid()}:{os.getgid()}','--tmpfs','/tmp:rw,exec,size=1g,mode=1777',
          '-v',f'{kit}:/input:ro','-v',f'{wheels}:/wheels:ro','-v',f'{output}:/output:rw',
          '-v',f'{Path(__file__).resolve()}:/check.py:ro',
          '-v',f'{ROOT/"tools/native_tests/inspection_suite.py"}:/suite.py:ro',
          dependency['image'],'python','-B','/check.py','--inside']
    result=subprocess.run(argv,capture_output=True,text=True,timeout=1000)
    (output/'container.log').write_text(result.stdout+'\n'+result.stderr)
    if result.returncode:raise RuntimeError('Inspection Linux check failed; see '+str(output/'container.log'))
    report=json.loads((output/'result.json').read_text());report.update(image=dependency['image'],network='none')
    (output/'result.json').write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    if sys.argv[1:]==['--inside']:
        report=exercise('/input',['/wheels'],'/tmp/exercise','/suite.py')
        shutil.copyfile('/tmp/exercise/result.json','/output/result.json')
        shutil.copytree('/tmp/exercise/inspection project/reviews','/output/reviews')
    else:
        parser=argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--kit',required=True);parser.add_argument('--wheelhouse',action='append',required=True)
        parser.add_argument('--output',required=True);parser.add_argument('--linux',action='store_true')
        parser.add_argument('--docker',default='docker');args=parser.parse_args()
        report=linux(args.kit,args.wheelhouse,args.output,args.docker) if args.linux else exercise(args.kit,args.wheelhouse,args.output,ROOT/'tools/native_tests/inspection_suite.py')
    print(json.dumps(report));raise SystemExit(report['status']!='PASS')
