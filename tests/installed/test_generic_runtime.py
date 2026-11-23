"""Exercise only installed generic artifacts; no services, sockets or external models."""
import copy,importlib,importlib.metadata as metadata,importlib.resources as resources,importlib.util,io,json,contextlib,subprocess,sys,sqlite3,tempfile,tomllib,unittest
from pathlib import Path
from unittest.mock import patch
from ocp_runtime.authoring.scaffold import create_project,strip_content,inject_content,tree
from ocp_runtime.server_project import project_main
from ocp_runtime.execution import ExecutionService
from ocp_runtime.execution.jobs import Principal
from ocp_runtime.inputs import prepare,prepare_operation
from ocp_runtime.analysis import build_plan,AnalysisError
from ocp_runtime.operations import OperationService,OperationConnector,OperationAnswer
from ocp_candidate.operations import reference
from ocp_routing_ocp_server.content.adapter import create_bundle
ROOT=Path(str(resources.files('ocp_routing_ocp_server').joinpath('content')))
VERSION = None
WORKER_EVIDENCE = []

class Generic(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.work=Path(self.tmp.name)
  b=create_bundle({});self.bundle=b;self.doc=json.loads((ROOT/'manifest.json').read_text());self.service=ExecutionService(self.doc,b['connector'],checker=b['checker']);self.input=json.loads((ROOT/'examples/matrix/input.json').read_text());self.config={'time_limit_seconds':.05}
 def test_01_no_private_catalog_or_native_dependency(self):
  self.assertEqual(metadata.version('ocp-candidate'),VERSION)
  for name in ('ocp_primary_bridge','ocp_native_catalog','ocp_catalog_bridge','foundry_capability_contract'):self.assertIsNone(importlib.util.find_spec(name),name)
  for name in ('ocp_candidate','ocp_runtime','ocp_routing_ocp_server','ocp_runtime.bindings.mcp'):
   m=importlib.import_module(name);self.assertTrue(Path(m.__file__).is_relative_to(Path(sys.prefix)))
  self.assertNotIn('ocp-catalog',[ep.name for ep in metadata.distribution('ocp-candidate').entry_points])
 def test_02_blank_has_no_execution(self):
  p=self.work/'blank';create_project(p,'generic-blank');s=io.StringIO()
  with contextlib.redirect_stdout(s):code=project_main(p,['check'])
  self.assertEqual(code,2);self.assertEqual(json.loads(s.getvalue())['execute_calls'],0);self.assertEqual(json.loads(s.getvalue())['status'],'UNCONFIGURED')
 def test_03_strip_and_reinject_exact_template(self):
  a=self.work/'routing';create_project(a,'routing-rehearsal',content=ROOT);b=self.work/'blank';strip_content(a,b);c=self.work/'expected';create_project(c,'routing-rehearsal');self.assertEqual(tree(b),tree(c));q=self.work/'again';inject_content(b,ROOT,q);self.assertEqual(tree(a),tree(q))
 def test_04_generated_runtime_version_pin(self):
  p=self.work/'blank';create_project(p,'generic-blank');self.assertIn('ocp-candidate[server]=='+VERSION,tomllib.loads((p/'pyproject.toml').read_text())['project']['dependencies'])
 def test_05_official_csv_xlsx_four_paths(self):
  for model in ('matrix','coordinates'):
   d=ROOT/'examples'/model
   for kind in ('csv','xlsx'):
    data={p.name:p.read_bytes()for p in d.glob('*.csv')}if kind=='csv'else{'routing.xlsx':(d/'routing.xlsx').read_bytes()}
    result=prepare(self.doc,data,configuration=self.config,format_id='routing-'+model+'-'+kind,format_version='1.0.0',converters=self.bundle['converters'])
    self.assertEqual(result['input'],json.loads((d/'input.json').read_text()));self.assertEqual(result['execute_calls'],0);self.assertTrue(result['provenance'])
 def test_06_actual_routing_matrix_and_coordinates(self):
  for model in ('matrix','coordinates'):
   result=self.service.execute(json.loads((ROOT/'examples'/model/'input.json').read_text()),self.config)
   self.assertEqual(result['solution_status'],'feasible');self.assertEqual(result['evaluation']['status'],'pass')
 def test_07_checker_rejects_corrupted_metric(self):
  result=self.service.execute(self.input,self.config);bad=copy.deepcopy(result['result']);bad['metrics']['total_distance_m']+=1
  self.assertEqual(self.bundle['checker'].evaluate(self.input,result['effective_configuration'],bad)['status'],'fail')
 def test_08_playbook_plan_no_execution(self):
  with patch.object(self.bundle['connector'],'execute',side_effect=AssertionError('unexpected solve')):
   p=build_plan(self.service,'vehicle_weights',self.input,self.config,variables=[{'binding':'vehicle_weight','values':[0,200]}],ranking_metric='total_distance_m')
   self.assertEqual(len(p['candidates']),2)
   with self.assertRaises(AnalysisError):build_plan(self.service,'vehicle_weights',self.input,self.config,ranking_metric='weighted_cost')
 def operation(self,*,completion=None,effect='unknown',data=None):
  doc=copy.deepcopy(self.doc);doc['required_extensions']=['ocp.operations'];doc['extensions']={};doc['schemas'].update(request={'type':'object','properties':{'value':{'type':'integer'}},'required':['value'],'additionalProperties':False},response={'type':['null','object']})
  op={'id':'generic.command','version':'1.0.0','kind':'command','description':'Synthetic scoped optimization configuration command','request_schema':'request','response_schema':'response','effects':'optimization_context_write','execution':'sync','binding':{'connector':'generic.command'},'capabilities':{k:False for k in ('idempotency','reconciliation','cancel','atomic_precondition','snapshot')}}
  doc['extensions']['ocp.operations']={'version':'0.1.0-draft.2','operations':[op]};calls=[];allowed=[True]
  def invoke(*a):calls.append(a);return OperationAnswer(data,effect=effect,completion=completion)
  svc=OperationService(doc,{op['id']:OperationConnector(lambda:copy.deepcopy(op),invoke,lambda *a:allowed[0])},journal=self.work/'operations.sqlite');principal=Principal('synthetic','review',frozenset({'read','execute'}))
  return doc,op,svc,principal,calls,allowed
 def test_09_ack_null_preserves_unknown_effect(self):
  doc,op,s,p,c,a=self.operation(completion='acknowledged');r=s.invoke(p,op['id'],{'value':0},expected=reference(doc,op),request_id='one',kind='command');self.assertEqual((r['status'],r['effect'],r['completion']),('completed','unknown','acknowledged'));self.assertIsNone(r['data'])
 def test_10_no_ack_is_uncertain(self):
  doc,op,s,p,c,a=self.operation(data={'value':0});r=s.invoke(p,op['id'],{'value':0},expected=reference(doc,op),request_id='one',kind='command');self.assertEqual(r['status'],'uncertain');self.assertNotIn('completion',r)
 def test_11_ack_replay_no_resend_current_auth(self):
  doc,op,s,p,c,a=self.operation(completion='acknowledged');kw={'expected':reference(doc,op),'request_id':'one','kind':'command'};s.invoke(p,op['id'],{'value':0},**kw);self.assertTrue(s.invoke(p,op['id'],{'value':0},**kw)['replayed_observation']);self.assertEqual(len(c),1);a[0]=False
  with self.assertRaises(Exception):s.invoke(p,op['id'],{'value':0},**kw)
  self.assertEqual(len(c),1)
 def test_12_prepare_operation_never_invokes_or_authorizes(self):
  doc,op,s,p,c,a=self.operation();r=prepare_operation(doc,op['id'],{'value':0},expected=reference(doc,op));self.assertEqual(r['execute_calls'],0);self.assertEqual(r['effects'],'none');self.assertEqual(r['authorization'],'not_evaluated');self.assertEqual(c,[])
 def test_13_installed_notices_present(self):
  dist=metadata.distribution('ocp-candidate');names=[str(x)for x in dist.files]
  for notice in ('LICENSE','NOTICE','THIRD_PARTY_NOTICES.md'):self.assertTrue(any(x.endswith('/licenses/'+notice)for x in names));self.assertTrue(resources.files('ocp_runtime._worker_contract').joinpath(notice).is_file())
 def api_dispatch(self):
  from ocp_routing_ocp_server.content import http_api as api
  from types import SimpleNamespace
  def no_socket(address,handler):return SimpleNamespace(handler=handler,daemon_threads=False)
  with patch.object(api,'ThreadingHTTPServer',no_socket):server,pool=api.make_api('127.0.0.1',8088,self.work/'http-api.sqlite','synthetic-local-token')
  def dispatch(path,payload=None,run=False):
   h=object.__new__(server.handler);h.path=path;raw=json.dumps(payload).encode()if payload is not None else b'';h.headers={'Host':'127.0.0.1','Authorization':'Bearer synthetic-local-token','Content-Length':str(len(raw))};h.rfile=io.BytesIO(raw);answers=[];h.answer=lambda code,body:answers.append((code,body))
   (h.do_POST if payload is not None else h.do_GET)()
   if run and path=='/jobs'and answers[0][0]==202:self.assertTrue(pool._make_worker(0).run_once())
   return answers[0]
  return api,pool,dispatch
 def test_14_remote_factory_full_path_without_sockets(self):
  import os
  api,pool,dispatch=self.api_dispatch()
  def transport(connector,path,payload=None,**kw):
   code,body=dispatch(path,payload,run=True)
   if code>=400:raise api.ExecutionError('API_RESPONSE_REJECTED')
   return body
  with patch.dict(os.environ,{'OCP_TEST_TOKEN':'synthetic-local-token'}),patch.object(api.HTTPConnector,'_request',transport):
   bundle=create_bundle({'api_endpoint':'http://127.0.0.1:8088','credential_environment_variable':'OCP_TEST_TOKEN'});service=ExecutionService(self.doc,bundle['connector'],checker=bundle['checker']);result=service.execute(self.input,self.config)
  self.assertEqual(result['solution_status'],'feasible');self.assertEqual(result['evaluation']['status'],'pass');self.assertEqual(pool._threads,[])
  # This solve runs in ProcessSolveRunner; a parent-process call list cannot
  # observe its memory. Verify the actual durable worker attempt separately.
  with sqlite3.connect((self.work/'http-api.sqlite').as_uri()+'?mode=ro',uri=True)as database:
   rows=[json.loads(row[0])for row in database.execute('SELECT body FROM jobs')]
  self.assertEqual(len(rows),1);job=rows[0]
  self.assertEqual(job['status'],'succeeded');self.assertEqual(job['attempt'],1)
  self.assertIsNone(job['lease_owner']);self.assertIsNone(job['lease_until']);self.assertIsNotNone(job['finished_at'])
  self.assertEqual(job['problem']['input'],self.input)
  self.assertEqual(job['problem']['configuration'],result['effective_configuration'])
  self.assertEqual(job['result']['result'],result['result'])
  self.assertEqual(job['result']['solution_status'],'feasible')
  WORKER_EVIDENCE.append({'job_id':job['id'],'attempt':job['attempt'],'status':job['status'],
   'lease_released':job['lease_owner']is None and job['lease_until']is None,
   'request_and_result_matched':True,'checker_status':result['evaluation']['status']})
 def test_15_http_idempotency_replay_and_conflict_class(self):
  api,pool,dispatch=self.api_dispatch();payload={'input':self.input,'configuration':self.config,'idempotency_key':'synthetic-one'}
  code,body=dispatch('/jobs',payload);self.assertEqual(code,202);code,replay=dispatch('/jobs',payload);self.assertEqual(code,202);self.assertTrue(replay['replayed']);self.assertEqual(body['job']['jobId'],replay['job']['jobId'])
  conflict=copy.deepcopy(payload);conflict['configuration']['time_limit_seconds']=.06;code,bad=dispatch('/jobs',conflict);self.assertEqual(code,409);self.assertEqual(bad['code'],'IDEMPOTENCY_CONFLICT');self.assertEqual(pool._threads,[])
 def test_16_blank_build_install_check(self):
  p=self.work/'blank';create_project(p,'generic-blank');d=self.work/'dist'
  r=subprocess.run([sys.executable,'-B','-m','build','--wheel','--no-isolation','--outdir',str(d),str(p)],capture_output=True,text=True,timeout=120);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([sys.executable,'-B','-m','pip','install','--no-index','--no-cache-dir','--no-compile',str(next(d.glob('*.whl')))],capture_output=True,text=True,timeout=120);self.assertEqual(r.returncode,0,r.stderr)
  r=subprocess.run([str(Path(sys.prefix)/'bin/generic-blank'),'check'],cwd=self.work,capture_output=True,text=True,timeout=30);self.assertEqual(r.returncode,2,r.stderr);self.assertEqual(json.loads(r.stdout)['status'],'UNCONFIGURED')
 def project_command(self,command,*,settings=None,bundle=None,descriptor=None):
  project=self.work/'project';(project/'content').mkdir(parents=True,exist_ok=True)
  (project/'content/manifest.json').write_text(json.dumps(descriptor or self.doc))
  config=self.work/'config.json';config.write_text(json.dumps(settings if settings is not None else {'connector_factory':'synthetic:factory','state_directory':'state'}))
  output=io.StringIO()
  with patch('ocp_runtime.server_project._factory',return_value=lambda settings:bundle if bundle is not None else self.bundle) as factory,contextlib.redirect_stdout(output):
   code=project_main(project,[command,'--config',str(config)])
  return code,json.loads(output.getvalue()),factory.call_count
 def test_17_doctor_rejects_missing_or_mismatched_converter_without_execution(self):
  from ocp_runtime.inputs import InputConverter
  key='routing/matrix';original=self.bundle['converters'][key]
  cases=[({},'CONVERTER_NOT_REGISTERED'),({key:object()},'CONVERTER_NOT_REGISTERED'),({key:InputConverter(key,'wrong',original.convert)},'CONVERTER_VERSION_MISMATCH')]
  for converters,error in cases:
   with self.subTest(error=error),patch.object(self.bundle['connector'],'execute',side_effect=AssertionError('unexpected solve')):
    code,result,_=self.project_command('doctor',bundle={**self.bundle,'converters':converters})
    self.assertEqual(code,2);self.assertEqual(result['code'],error);self.assertEqual(result['execute_calls'],0)
    self.assertFalse((self.work/'state').exists())
  code,result,_=self.project_command('doctor');self.assertEqual(code,0);self.assertEqual(result['status'],'READY')
 def test_18_operation_file_registration_is_checked_before_ready(self):
  doc,op,service,principal,calls,allowed=self.operation()
  op['input_formats']=copy.deepcopy(doc['input_formats']);doc['input_formats']=[]
  code,result,_=self.project_command('doctor',descriptor=doc,bundle={**self.bundle,'converters':{}})
  self.assertEqual((code,result['code']),(2,'CONVERTER_NOT_REGISTERED'));self.assertEqual(calls,[])
  self.assertFalse((self.work/'state').exists())
 def test_19_host_config_validates_settings_without_imports_secrets_or_state(self):
  base={'connector_factory':'synthetic:factory','state_directory':'state'}
  for settings,error in [({**base,'state_directory':None},'STATE_DIRECTORY_REQUIRED'),({**base,'connector_factory':None},'CONNECTOR_FACTORY_REQUIRED'),({**base,'transport':'streamable-http','http_auth_environment_variable':'UNSET_OCP_TEST_SECRET','http_port':True},'HTTP_PORT_INVALID')]:
   code,result,imports=self.project_command('host-config',settings=settings);self.assertEqual((code,result['code']),(2,error));self.assertEqual(imports,0)
  settings={**base,'transport':'streamable-http','http_auth_environment_variable':'UNSET_OCP_TEST_SECRET','http_port':8042}
  with patch.dict('os.environ',{},clear=True):code,result,imports=self.project_command('host-config',settings=settings)
  self.assertEqual((code,result['url'],imports),(0,'http://127.0.0.1:8042/mcp',0));self.assertFalse((self.work/'state').exists())
 def test_20_missing_domain_dependency_points_to_generic_installation(self):
  project=self.work/'project';(project/'content').mkdir(parents=True);(project/'content/manifest.json').write_text(json.dumps(self.doc))
  config=self.work/'config.json';config.write_text(json.dumps({'connector_factory':'synthetic:factory','state_directory':'state'}));output=io.StringIO()
  with patch('ocp_runtime.server_project._factory',side_effect=ModuleNotFoundError('synthetic')),contextlib.redirect_stdout(output):code=project_main(project,['doctor','--config',str(config)])
  result=json.loads(output.getvalue());self.assertEqual((code,result['status']),(2,'DEPENDENCY_MISSING'));self.assertIn('ocp-candidate[server]',result['next']);self.assertIn('do not require native-contract',result['next']);self.assertFalse((self.work/'state').exists())
 def test_21_invalid_distribution_name_does_not_create_a_project(self):
  from ocp_runtime.authoring.scaffold import ScaffoldError
  for name in ('invalid-','ab','a' * 65):
   target=self.work/name
   with self.assertRaisesRegex(ScaffoldError,'INVALID_PACKAGE_NAME'):create_project(target,name)
   self.assertFalse(target.exists())
  for name in ('a-b','a' * 64):
   record=create_project(self.work/name,name);self.assertEqual(record['parameters']['package_name'],name)
if __name__ == '__main__':
 import argparse
 from ocp_routing_ocp_server.content.engine import LibraryConnector
 parser=argparse.ArgumentParser();parser.add_argument('--expected-version',required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
 VERSION=args.expected_version
 observed=[];original_execute=LibraryConnector.execute
 def counted_execute(self,*a,**kw):
  observed.append('local_reference_execute')
  return original_execute(self,*a,**kw)
 with patch.object(LibraryConnector,'execute',counted_execute):
  # The public policy regressions must also run against the installed runtime.
  # Only test code and public input fixtures are loaded from this source copy.
  policy_path=Path(__file__).resolve().parents[1]/'runtime/test_binding_authorization.py'
  spec=importlib.util.spec_from_file_location('installed_binding_authorization',policy_path)
  policy=importlib.util.module_from_spec(spec);spec.loader.exec_module(policy)
  suite=unittest.defaultTestLoader.loadTestsFromTestCase(Generic)
  suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(policy.BindingAuthorization))
  result=unittest.TextTestRunner(verbosity=2).run(suite)
 accounted=len(observed)==3 and len(WORKER_EVIDENCE)==1
 ok=result.wasSuccessful() and not result.skipped and result.testsRun==36 and accounted
 report={'status':'PASS' if ok else 'FAIL','tests_run':result.testsRun,'errors':len(result.errors),'failures':len(result.failures),'skipped':len(result.skipped),'observed_parent_connector_execute_calls':len(observed),'durable_worker_attempts':WORKER_EVIDENCE,'execution_accounting_ok':accounted,'expected_version':VERSION,'http_transport':'in_memory_handler_only','models':0,'services_started':0,'publication_authorized':False}
 with args.output.open('x') as out:json.dump(report,out,indent=2);out.write('\n')
 print(json.dumps(report));raise SystemExit(not ok)
