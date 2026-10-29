"""Installed business exercise: real jobs and CSV/report regressions, no LLM."""
import csv
import asyncio
import contextlib
from copy import deepcopy
import importlib.util
import io
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

ROOT=Path.cwd()


def module(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/(name+'.py'))
    value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value


class Inspection(unittest.TestCase):
    @classmethod
    def command(cls,value,expected=0):
        p=subprocess.run(['/bin/sh','-eu','-c',value],cwd=ROOT,capture_output=True,text=True,timeout=240)
        with (ROOT/'inspection-check.log').open('a') as log:log.write(value+'\n'+p.stdout+p.stderr+'\n')
        if p.returncode!=expected:raise AssertionError(p.stdout[-3000:]+p.stderr[-3000:])
        return [json.loads(line) for line in p.stdout.splitlines() if line.startswith('{')]

    @classmethod
    def documented(cls,name):
        guide=(ROOT/'INSPECTION_GUIDE.md').read_text()
        return cls.command(re.search(r'<!-- ocp:'+name+r' -->\s*```sh\n(.*?)\n```',guide,re.S).group(1))

    @classmethod
    def setUpClass(cls):
        cls.app=module('inspection');cls.project=module('project')
        cls.base=cls.documented('inspection-baseline')
        cls.original=cls.project.read(ROOT/'scenarios/baseline/input.json')
        cls.command('.native/bin/python -I -B -m pip install --no-index --no-deps --no-compile ./ocp_worker_greedy_example-0.1.0-py3-none-any.whl')

    def temp(self):
        path=Path(tempfile.mkdtemp(prefix='inspection-case-',dir=ROOT))
        self.addCleanup(shutil.rmtree,path);return path

    def scenario(self,name,data,engine='reference'):
        path=ROOT/'scenarios'/name;path.mkdir()
        settings=self.project.read(ROOT/'scenarios/baseline/project.json')
        self.project.save(path/'project.json',settings);self.project.save(path/'input.json',data)
        return self.command(f'.native/bin/python -I -B project.py run --project scenarios/{name}/project.json --output runs/{name} --engine {engine}')[-1]

    def test_01_baseline_conversion_execution_assignment_and_loads(self):
        prepared,run,report=self.base
        self.assertEqual((prepared['workers'],prepared['tasks'],run['solution_status'],run['objective_value']),(3,6,'optimal',16))
        self.assertEqual([(t['start'],t['end']) for t in self.original['tasks']],[(540,600),(540,600),(600,660),(600,660),(660,720),(660,720)])
        self.assertEqual(report['objective_value'],16)
        self.assertEqual({r['task_id']:r['worker_id'] for r in report['assignments']},
                         {'pump':'alex','panel':'casey','valve':'alex','safety':'blair','meter':'casey','report':'blair'})
        self.assertEqual([r['assigned_minutes'] for r in report['worker_loads']],[120,120,120])
        self.assertEqual(sum(r['cost'] for r in report['assignments']),16)
        self.assertEqual(report['checks']['execution_attestation']['status'],'NOT_CHECKED')
        with (ROOT/'reviews/baseline/assignments.csv').open() as stream:self.assertEqual(len(list(csv.DictReader(stream))),6)
        self.command('.native/bin/python -I -B -m pip check')

    def test_02_documented_workload_change(self):
        rows=self.documented('inspection-change');comparison=rows[-1]
        self.assertEqual((rows[1]['objective_value'],comparison['right_minus_left'],comparison['same_problem']),(19,3,False))
        report=rows[2]
        self.assertEqual([r['assigned_minutes'] for r in report['worker_loads']],[60,180,120])

    def test_03_availability_is_distinct_from_workload(self):
        data=deepcopy(self.original);data['workers'][0]['availability'][0]['end']=600
        result=self.scenario('early-departure',data)
        self.assertEqual((result['solution_status'],result['objective_value']),('optimal',25))
        report=self.command('.native/bin/python -I -B inspection.py report --run runs/early-departure --output reviews/early')[-1]
        self.assertTrue(all(a['end']<='10:00' for a in report['assignments'] if a['worker_id']=='alex'))

    def test_04_missing_eligibility_is_not_zero_cost_or_dropped_task(self):
        folder=self.temp()
        with (ROOT/'inspection-costs.csv').open() as source:
            rows=[r for r in csv.DictReader(source) if r['task_id']!='panel']
        self.app.write_csv(folder/'costs.csv',['task_id','worker_id','cost'],rows)
        self.app.prepare(ROOT/'inspection-workers.csv',ROOT/'inspection-tasks.csv',folder/'costs.csv',folder/'input')
        data=self.project.read(folder/'input/input.json')
        self.assertEqual(len(data['tasks']),6)
        self.assertEqual(data['tasks'][1]['eligible_workers'],[])
        for name,engine,status in [('unqualified','reference','infeasible'),('unqualified-byo','byo','unknown')]:
            result=self.scenario(name,data,engine)
            self.assertEqual(result['solution_status'],status);self.assertIsNone(result['objective_value'])
            report=self.command(f'.native/bin/python -I -B inspection.py report --run runs/{name} --output reviews/{name}')[-1]
            self.assertIsNone(report['worker_loads']);self.assertIsNone(report['assignments'])
            self.assertFalse((ROOT/'reviews'/name/'assignments.csv').exists())
            self.assertFalse((ROOT/'reviews'/name/'worker-loads.csv').exists())

    def test_05_documented_engine_swap(self):
        before=(ROOT/'project.py').read_bytes()
        rows=self.documented('inspection-byo');comparison=rows[-1]
        self.assertTrue(comparison['same_problem'])
        self.assertEqual(comparison['right']['solution_status'],'feasible')
        self.assertEqual(comparison['right']['optimality'],'NOT_CLAIMED')
        self.assertGreaterEqual(comparison['right']['objective_value'],16)
        self.assertEqual(before,(ROOT/'project.py').read_bytes())

    def test_06_real_mcp_on_imported_business_input(self):
        result=self.documented('inspection-mcp')[-1]
        self.assertEqual((result['status'],result['execute_calls'],result['model_calls']),('PASS',1,0))
        self.assertEqual(result['request']['input'],self.original)
        self.assertEqual(result['independent_check']['checks']['objective_recomputation']['value'],16)
        self.assertTrue(result['replayed'])
        self.assertTrue({'ocp_native_context','ocp_native_requirements','ocp_native_validate','ocp_native_submit',
                         'ocp_native_job','ocp_native_result','ocp_native_evaluate'} <= {r['tool'] for r in result['tool_calls']})

    def test_07_actionable_csv_errors_never_create_output(self):
        folder=self.temp()
        sources={kind:(ROOT/f'inspection-{kind}.csv').read_text() for kind in ['workers','tasks','costs']}
        mutations=[('workers',lambda s:s.replace('worker_id','unknown',1),'CSV_HEADER',1),
                   ('workers',lambda s:s.replace('09:00','9:00',1),'CSV_TIME',2),
                   ('workers',lambda s:s.replace('09:00','24:00',1),'CSV_TIME',2),
                   ('workers',lambda s:s.replace('12:00','08:00',1),'CSV_INTERVAL',2),
                   ('workers',lambda s:s.replace('alex,',' alex,',1),'CSV_EMPTY_OR_WHITESPACE',2),
                   ('workers',lambda s:s.replace('blair,','alex,',1),'CSV_DUPLICATE',3),
                   ('workers',lambda s:s.replace('120','1.5',1),'CSV_INTEGER',2),
                   ('workers',lambda s:s.replace('120','1441',1),'CSV_RANGE',2),
                   ('tasks',lambda s:s.replace('pump,','=1+1,',1),'CSV_ID',2),
                   ('tasks',lambda s:s.replace('task_id,start,end','task_id,start,start'),'CSV_HEADER',1),
                   ('tasks',lambda s:s.replace('pump,09:00,10:00','pump,09:00,10:00,extra'),'CSV_COLUMNS',2),
                   ('costs',lambda s:s.replace('pump,','missing,',1),'CSV_UNKNOWN_TASK',2),
                   ('costs',lambda s:s.replace('alex,','missing,',1),'CSV_UNKNOWN_WORKER',2),
                   ('costs',lambda s:s.replace('pump,blair,5','pump,alex,5'),'CSV_DUPLICATE',3),
                   ('costs',lambda s:s.replace('alex,2','alex,2.5',1),'CSV_INTEGER',2),
                   ('costs',lambda s:s.replace('alex,2','alex,-1',1),'CSV_INTEGER',2),
                   ('costs',lambda s:s.replace('alex,2','alex,100001',1),'CSV_RANGE',2)]
        for number,(kind,change,code,row) in enumerate(mutations):
            with self.subTest(code=code,number=number):
                for key,source in sources.items():(folder/(key+'.csv')).write_text(change(source) if key==kind else source)
                output=folder/f'output-{number}'
                with self.assertRaises(self.app.InputError) as raised:
                    self.app.prepare(*(folder/(k+'.csv') for k in ['workers','tasks','costs']),output)
                self.assertEqual(raised.exception.code,code)
                self.assertEqual(raised.exception.details['row'],row)
                self.assertTrue(raised.exception.details['field']);self.assertFalse(output.exists())

    def test_08_bom_crlf_zero_cost_and_day_boundary(self):
        folder=self.temp()
        (folder/'workers.csv').write_bytes(b'\xef\xbb\xbfworker_id,start,end,max_minutes\r\na,23:00,24:00,60\r\n')
        (folder/'tasks.csv').write_text('task_id,start,end\nt,23:00,24:00\n')
        (folder/'costs.csv').write_text('task_id,worker_id,cost\nt,a,0\n')
        data,_=self.app.problem(*(folder/(k+'.csv') for k in ['workers','tasks','costs']))
        self.assertEqual((data['tasks'][0]['end'],data['tasks'][0]['costs']['a']),(1440,0))
        result=self.scenario('zero',data);self.assertEqual(result['objective_value'],0)
        report=self.command('.native/bin/python -I -B inspection.py report --run runs/zero --output reviews/zero')[-1]
        self.assertEqual(report['assignments'][0]['end'],'24:00')

    def test_09_table_size_empty_and_read_errors(self):
        folder=self.temp()
        for name in ['workers','tasks','costs']:shutil.copyfile(ROOT/f'inspection-{name}.csv',folder/f'{name}.csv')
        path=folder/'workers.csv';original=path.read_text()
        for text,code in [(original+'d,09:00,12:00,120\ne,09:00,12:00,120\n','CSV_ROW_LIMIT'),
                          (original.splitlines()[0]+'\n','CSV_EMPTY_TABLE'),('x'*65537,'CSV_TOO_LARGE')]:
            path.write_text(text)
            with self.assertRaisesRegex(self.app.InputError,code):self.app.problem(path,folder/'tasks.csv',folder/'costs.csv')
        path.write_bytes(b'\xff')
        with self.assertRaisesRegex(self.app.InputError,'CSV_UTF8_REQUIRED'):self.app.problem(path,folder/'tasks.csv',folder/'costs.csv')
        path.unlink()
        with self.assertRaisesRegex(self.app.InputError,'CSV_UNREADABLE'):self.app.problem(path,folder/'tasks.csv',folder/'costs.csv')

    def test_10_report_rechecks_instead_of_trusting_saved_pass(self):
        folder=self.temp();record=folder/'record';shutil.copytree(ROOT/'runs/inspection-baseline',record)
        self.project.save(record/'check.json',{'status':'FAIL','fake':True})
        self.project.save(record/'files.sha256.json',{n:self.project.digest((record/n).read_bytes()) for n in self.project.RUN_FILES})
        self.assertEqual(self.app.report(record,folder/'review')['status'],'PASS')
        response=self.project.read(record/'response.json');response['solution']['assignments'].pop()
        self.project.save(record/'response.json',response)
        job=self.project.read(record/'job.json');job['result']['result']=response;self.project.save(record/'job.json',job)
        self.project.save(record/'files.sha256.json',{n:self.project.digest((record/n).read_bytes()) for n in self.project.RUN_FILES})
        with self.assertRaisesRegex(ValueError,'INDEPENDENT_CHECK_FAILED'):self.app.report(record,folder/'bad')
        self.assertFalse((folder/'bad').exists())

    def test_11_overwrite_and_human_acceptance_boundaries(self):
        path=ROOT/'scenarios/baseline';before={p.name:p.read_bytes() for p in path.iterdir()}
        with self.assertRaisesRegex(ValueError,'OUTPUT_EXISTS'):
            self.app.prepare(*(ROOT/f'inspection-{k}.csv' for k in ['workers','tasks','costs']),path)
        self.assertEqual(before,{p.name:p.read_bytes() for p in path.iterdir()})
        with self.assertRaisesRegex(ValueError,'OUTPUT_EXISTS'):self.app.report(ROOT/'runs/inspection-baseline',ROOT/'reviews/baseline')
        owner=self.project.read(path/'OWNER_REVIEW.json')
        self.assertEqual(owner['status'],'NOT_RUN');self.assertEqual(set(owner['criteria'].values()),{'NOT_RUN'})
        self.assertIsNone(owner['reviewer'])
        self.assertEqual(self.project.read(ROOT/'ADOPTION_REVIEW.json')['external_independent_developer'],'NOT_RUN')

    def test_12_offline_report_imports_no_solver_or_sdk(self):
        code='''import importlib.abc,importlib.util,sys,json
from pathlib import Path
class Deny(importlib.abc.MetaPathFinder):
 def find_spec(self,fullname,path=None,target=None):
  if fullname.split('.')[0] in {'ocp_candidate','ocp_runtime','ocp_planning','ocp_worker_greedy'}:raise RuntimeError('ENGINE_IMPORT')
sys.meta_path.insert(0,Deny())
spec=importlib.util.spec_from_file_location('inspection',Path('inspection.py'))
app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
print(json.dumps(app.report(Path('runs/inspection-baseline'),Path('reviews/import-guard'))))
'''
        p=subprocess.run([str(ROOT/'.native/bin/python'),'-I','-B','-c',code],cwd=ROOT,capture_output=True,text=True,timeout=40)
        self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(json.loads(p.stdout)['execute_calls'],0)

    def test_13_changed_cost_is_used_not_cached(self):
        folder=self.temp()
        with (ROOT/'inspection-costs.csv').open() as source:rows=list(csv.DictReader(source))
        for row in rows:
            if (row['task_id'],row['worker_id'])==('pump','blair'):row['cost']='1'
        self.app.write_csv(folder/'costs.csv',['task_id','worker_id','cost'],rows)
        data,_=self.app.problem(ROOT/'inspection-workers.csv',ROOT/'inspection-tasks.csv',folder/'costs.csv')
        result=self.scenario('cost-change',data)
        self.assertEqual((result['solution_status'],result['objective_value']),('optimal',13))
        comparison=self.project.compare(ROOT/'runs/inspection-baseline',ROOT/'runs/cost-change')
        self.assertEqual((comparison['same_problem'],comparison['right_minus_left']),(False,-3))

    def installer_failure(self, arguments, **patches):
        stream=io.StringIO()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(sys,'argv',['install.py',*arguments]))
            stack.enter_context(contextlib.redirect_stderr(stream))
            for name,value in patches.items():stack.enter_context(patch(name,**value))
            with self.assertRaises(SystemExit) as error:runpy.run_path(str(ROOT/'install.py'),run_name='__main__')
        self.assertEqual(error.exception.code,1)
        self.assertNotIn('Traceback',stream.getvalue())
        result=json.loads(stream.getvalue().splitlines()[-1]);self.assertEqual(result['status'],'FAIL')
        return result

    def test_14_wrong_python_explains_required_interpreter_before_writing(self):
        output=self.temp()/'environment'
        result=self.installer_failure(['--venv',str(output)],**{'sys.version_info':{'new':(3,11)}})
        self.assertEqual(result['code'],'PYTHON_3_12_REQUIRED')
        self.assertIn('python3.12 -B install.py',result['hint']);self.assertFalse(output.exists())

    def test_15_dependency_timeout_is_structured_and_does_not_retry(self):
        output=self.temp()/'partial';output.mkdir();(output/'diagnostic.txt').write_text('preserve')
        # Simulate the timeout after environment creation, without a model/network call.
        fresh=output/'environment'
        with patch('subprocess.run',side_effect=subprocess.TimeoutExpired('pip',300)) as command:
            result=self.installer_failure(['--venv',str(fresh)],**{'venv.EnvBuilder.create':{'return_value':None}})
        self.assertEqual(result['code'],'INSTALL_TIMEOUT');self.assertEqual(command.call_count,1)
        self.assertIn('new --venv',result['hint']);self.assertEqual((output/'diagnostic.txt').read_text(),'preserve')

    def test_16_existing_environment_is_preserved_and_recovery_is_explicit(self):
        folder=self.temp();environment=folder/'partial';environment.mkdir()
        (environment/'diagnostic.txt').write_text('original failure')
        p=subprocess.run([sys.executable,'-I','-B',str(ROOT/'install.py'),'--venv',str(environment)],capture_output=True,text=True)
        self.assertEqual(p.returncode,1);value=json.loads(p.stderr)
        self.assertEqual(value['code'],'ENVIRONMENT_EXISTS');self.assertIn('pip check',value['hint'])
        self.assertIn('incomplete',value['hint']);self.assertEqual((environment/'diagnostic.txt').read_text(),'original failure')

    def test_17_unicode_space_directory_install_and_mcp_configuration(self):
        folder=self.temp()/'개발자 kit';folder.mkdir()
        manifest=json.loads((ROOT/'manifest.json').read_text())
        for name in [*manifest['files'],'manifest.json']:shutil.copyfile(ROOT/name,folder/name)
        environment=folder/'별도 environment'
        p=subprocess.run([sys.executable,'-I','-B',str(folder/'install.py'),'--venv',str(environment)],
                         cwd=folder.parent,capture_output=True,text=True,timeout=300)
        self.assertEqual(p.returncode,0,p.stderr[-3000:]);self.assertEqual(json.loads(p.stdout)['status'],'PASS')
        shutil.copyfile(ROOT/'worker-project.json',folder/'worker-project.json')
        for script in ['project.py','mcp_config.py']:
            args=['run','--project',str(folder/'worker-project.json'),'--output',str(folder/'run')] if script=='project.py' else []
            p=subprocess.run([str(environment/'bin/python'),'-I','-B',str(folder/script),*args],cwd=folder.parent,capture_output=True,text=True,timeout=120)
            self.assertEqual(p.returncode,0,p.stderr[-3000:]);value=json.loads(p.stdout)
            if script=='project.py':self.assertEqual(value['status'],'PASS')
            else:self.assertEqual(value['mcpServers']['ocp-native-local']['command'],str(environment/'bin/python'))

    def test_18_malformed_manifest_does_not_create_environment(self):
        folder=self.temp();shutil.copyfile(ROOT/'install.py',folder/'install.py')
        (folder/'manifest.json').write_text('{broken')
        p=subprocess.run([sys.executable,'-I','-B',str(folder/'install.py'),'--venv',str(folder/'env')],capture_output=True,text=True)
        self.assertEqual(p.returncode,1);self.assertEqual(json.loads(p.stderr)['code'],'KIT_INVALID')
        self.assertFalse((folder/'env').exists())

    def test_19_csv_rejection_gives_a_correction_without_running_solver(self):
        folder=self.temp()
        for kind,value,code in [('workers','작업자','CSV_ID'),('tasks','9:00','CSV_TIME'),('costs','2.5','CSV_INTEGER')]:
            paths={k:ROOT/f'inspection-{k}.csv' for k in ['workers','tasks','costs']}
            text=paths[kind].read_text();old={'workers':'alex','tasks':'09:00','costs':'alex,2'}[kind]
            text=text.replace(old,'alex,'+value if kind=='costs' else value,1)
            paths[kind]=folder/(kind+'.csv');paths[kind].write_text(text)
            argv=[sys.executable,'-I','-B',str(ROOT/'inspection.py'),'prepare']
            for key,path in paths.items():argv+=['--'+key,str(path)]
            p=subprocess.run([*argv,'--output',str(folder/'output')],capture_output=True,text=True)
            result=json.loads(p.stdout);self.assertEqual(p.returncode,1);self.assertEqual(result['code'],code)
            self.assertTrue(result['hint']);self.assertEqual(result['execute_calls'],0);self.assertFalse((folder/'output').exists())

    def test_20_adjacent_tasks_are_allowed_but_overlap_is_infeasible(self):
        data={'time_unit':'minute','cost_unit':'cost_unit','workers':[{'id':'w','availability':[{'start':0,'end':30}],'max_minutes':30}],
              'tasks':[{'id':'t'+str(i),'start':i*10,'end':(i+1)*10,'eligible_workers':['w'],'costs':{'w':i}} for i in range(3)]}
        result=self.scenario('adjacent-new',data)
        self.assertEqual((result['solution_status'],result['objective_value']),('optimal',3))
        data['tasks'][1]['start']=9
        data['workers'][0]['max_minutes']=31  # isolate overlap, not workload capacity
        result=self.scenario('overlap-new',data)
        self.assertEqual(result['solution_status'],'infeasible');self.assertIsNone(result['objective_value'])

    def test_21_mcp_lease_failure_and_cancellation_preserve_job_without_result_or_retry(self):
        from datetime import datetime, timedelta, UTC
        from foundry_capability_contract import MemoryJobStore
        now=[datetime(2026,1,1,tzinfo=UTC)]
        store=MemoryJobStore(max_attempts=1,clock=lambda:now[0])
        kwargs={'tenant':'test','problem_type':'worker-scheduling','request_hash':'synthetic','caller':'test','problem':{}}
        job,_=store.submit(**kwargs,idempotency_key='lost-lease')
        store.claim(problem_type='worker-scheduling',worker_id='first',lease_seconds=30)
        now[0]+=timedelta(seconds=31)
        self.assertIsNone(store.claim(problem_type='worker-scheduling',worker_id='next',lease_seconds=30))
        failed=store.get(tenant='test',problem_type='worker-scheduling',job_id=job.id).public()
        self.assertEqual(failed['error']['code'],'ATTEMPTS_EXHAUSTED')
        queued,_=store.submit(**kwargs,idempotency_key='cancelled')
        cancelled=store.request_cancel(tenant='test',problem_type='worker-scheduling',job_id=queued.id).public()
        app=module('mcp_walkthrough')
        for terminal in [failed,cancelled]:
            calls=[]
            class Host:
                def __init__(self,*args,**kw):pass
                async def __aenter__(self):return self
                async def __aexit__(self,*args):pass
                async def call_tool(self,name,args):
                    calls.append(name)
                    values={'ocp_native_context':{'catalog':{'domainProfile':{'id':'worker.scheduling','version':'0.1.0'},'selectionTemplate':{},'requestTemplate':{}}},
                            'ocp_native_requirements':{},'ocp_native_validate':{'valid':True},'ocp_native_submit':{'job':terminal}}
                    if name not in values:raise AssertionError('Unexpected result, evaluation or retry: '+name)
                    return SimpleNamespace(is_error=False,structured_content=values[name])
            with patch.object(app,'Client',Host):value=asyncio.run(app.run('worker-scheduling',self.original))
            self.assertEqual(value['code'],'JOB_'+terminal['status'].upper())
            self.assertEqual(value['job'],terminal);self.assertIsNone(value['response'])
            self.assertIsNone(value['independent_check']);self.assertIsNone(value['execute_calls'])
            self.assertEqual(value['idempotency_key'],value['request']['request_id'])
            self.assertEqual(calls.count('ocp_native_submit'),1);self.assertEqual(value['model_calls'],0)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Inspection))
    report={'status':'PASS' if result.wasSuccessful() and not result.skipped else 'FAIL','tests_run':result.testsRun,
            'errors':len(result.errors),'failures':len(result.failures),'skipped':len(result.skipped),'model_calls':0,
            'scope':'Installed synthetic inspection business exercise, CSV errors and report integrity; no human acceptance'}
    print(json.dumps(report));raise SystemExit(report['status']!='PASS')
