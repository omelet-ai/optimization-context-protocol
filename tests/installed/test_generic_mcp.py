"""Official SDK stdio and durable-job replay from the just-executed quickstart."""
import argparse
import asyncio
import base64
import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import inspect
import os
from pathlib import Path
import sqlite3
import signal
import sys
from unittest.mock import patch
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
import mcp.client.stdio as stdio_module


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def close_processes(processes,helper,registry):
    """Use the same birth-identity guard as the durable outer supervisor."""
    try:
        current=helper.process_details(os.getpid())
        if current is None:raise ValueError('CONTROLLER_IDENTITY_UNAVAILABLE')
        groups=helper.registered_groups(registry,helper.process_identity(current))
        records=helper.close_registered_groups(groups)
        if {row['owner']['pid']for row in records}!={p.pid for p in processes}:raise ValueError('REGISTERED_CHILD_SET_MISMATCH')
        return [{'pid':p.pid,'pgid':p.pid,'returncode':p.returncode,
            'owner':record['owner'],'group_absent_after_sdk_context':None if record['group_before_cleanup']is None else not record['group_before_cleanup'],
            'group_absent_after_cleanup':None if record['group_after_cleanup']is None else not record['group_after_cleanup'],
            'cleanup_signals':record['cleanup_signals'],'cleanup_errors':record['errors'],
            'closure':record['closure']if p.returncode is not None else'UNKNOWN'}
            for p in processes for record in records if p.pid==record['owner']['pid']]
    except (ValueError,OSError,KeyError,TypeError)as exc:
        return [{'pid':p.pid,'pgid':p.pid,'returncode':p.returncode,
            'group_absent_after_sdk_context':None,'group_absent_after_cleanup':None,
            'cleanup_signals':[],'cleanup_errors':[type(exc).__name__+': '+str(exc)],'closure':'UNKNOWN'}for p in processes]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--quickstart',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--expected-version',required=True);parser.add_argument('--process-registry',type=Path,required=True);args=parser.parse_args()
    root=args.quickstart.resolve();out=args.output.absolute()
    if out.exists()or any(p.is_symlink()for p in [out,*out.parents])or out.is_relative_to(root):raise ValueError('NEW_OUTSIDE_OUTPUT_REQUIRED')
    if metadata.version('ocp-candidate')!=args.expected_version:raise ValueError('INSTALLED_VERSION_MISMATCH')
    if metadata.version('mcp')!='2.3.0':raise ValueError('PINNED_MCP_VERSION_REQUIRED')
    for name in ('foundry_capability_contract','ocp_primary_bridge','ocp_native_catalog','ocp_catalog_bridge'):
        if importlib.util.find_spec(name)is not None:raise ValueError('UNEXPECTED_OPTIONAL_PACKAGE')
    host=root/'.quickstart/host-config.json';config=json.loads(host.read_text())
    if set(config)!= {'mcpServers'}or set(config['mcpServers'])!={'routing.example'}:raise ValueError('EXACT_SERVER_CONFIG_REQUIRED')
    entry=config['mcpServers']['routing.example'];local=root/'.quickstart/local-config.json';settings=json.loads(local.read_text())
    expected=['-B','-m','ocp_routing_ocp_server.server','serve','--config',str(local)]
    if set(entry)!={'command','args'}or entry['command']!=sys.executable or entry['args']!=expected:raise ValueError('EXACT_INSTALLED_COMMAND_REQUIRED')
    state=Path(settings['state_directory'])
    if not state.is_relative_to(root)or (state/'jobs.sqlite').exists()or settings['api_endpoint']is not None or settings['credential_environment_variable']is not None:raise ValueError('FRESH_LOCAL_STATE_REQUIRED')
    out.mkdir(parents=True,mode=0o700,exist_ok=False)
    helper_spec=importlib.util.spec_from_file_location('generic_harness',Path(__file__).resolve().parents[2]/'tools/check_generic_candidate.py')
    helper=importlib.util.module_from_spec(helper_spec);helper_spec.loader.exec_module(helper)
    calls=[];processes=[];create_process=stdio_module._create_platform_compatible_process
    async def observed(*a,**kw):
        process=await create_process(*a,**kw);processes.append(process)
        assert os.getpgid(process.pid)==process.pid
        helper.register_detached_process(args.process_registry,process.pid)
        return process
    env={k:os.environ[k]for k in ('PATH','HOME','TMPDIR','PYTHONDONTWRITEBYTECODE','PYTHONUTF8')if k in os.environ}
    async def journey():
        params=StdioServerParameters(**entry,env=env,cwd=str(root))
        with(out/'stderr.log').open('x')as log,patch.object(stdio_module,'_create_platform_compatible_process',observed):
            async with stdio_client(params,errlog=log)as streams:
                async with ClientSession(*streams,read_timeout_seconds=30.0)as client:
                    initialized=await client.initialize();tools={t.name for t in(await client.list_tools()).tools}
                    assert len(tools)==16 and {'ocp_context','ocp_describe','ocp_prepare','ocp_validate','ocp_submit','ocp_job','ocp_result','ocp_evaluate'}<=tools
                    async def call(name,arguments,error=False):
                        answer=await client.call_tool(name,arguments);value=answer.structured_content;assert answer.is_error==error,(name,value)
                        if isinstance(value,dict)and value.get('inline')is False:
                            ref=value['artifact'];offset=0;blob=b''
                            while offset<ref['size_bytes']:
                                part=await client.call_tool('ocp_read_artifact',{'reference':ref,'offset':offset});assert not part.is_error;item=part.structured_content
                                blob+=base64.b64decode(item['data_base64']);assert item['next_offset']>offset;offset=item['next_offset']
                            assert len(blob)==ref['size_bytes']and hashlib.sha256(blob).hexdigest()==ref['sha256'];value=json.loads(blob)
                        calls.append({'tool':name,'arguments':arguments,'result':value,'is_error':answer.is_error});return value
                    context=await call('ocp_context',{});assert len(context['servers'])==1;summary=context['servers'][0];server=summary['id'];assert server=='routing.example'
                    described=await call('ocp_describe',{'server_id':server,'expected_digest':summary['digest'],'section':'input','item_id':'input'});assert 'properties'in described['item']['value']
                    original=json.loads((root/'examples/routing-ocp-server/content/examples/matrix/input.json').read_text());query={'server_id':server,'input_value':original,'configuration':{'time_limit_seconds':.05}}
                    prepared=await call('ocp_prepare',query);assert prepared['input']==original and prepared['execute_calls']==0
                    valid=await call('ocp_validate',query);assert valid['status']=='valid'and valid['execute_calls']==0
                    submit=await call('ocp_submit',{**query,'idempotency_key':'generic-smoke-one'});job=submit['job']['jobId']
                    replay=await call('ocp_submit',{**query,'idempotency_key':'generic-smoke-one'});assert replay['replayed']and replay['job']['jobId']==job
                    conflict=await call('ocp_submit',{**query,'configuration':{'time_limit_seconds':.06},'idempotency_key':'generic-smoke-one'},True);assert conflict['code']=='IDEMPOTENCY_CONFLICT'
                    # A cold worker imports the solver before its solve time limit starts.
                    # Bound observation independently of the requested solver time.
                    async with asyncio.timeout(60):
                        while True:
                            progress = await call('ocp_job', {'server_id': server, 'job_id': job})
                            if progress['status'] in ('succeeded', 'failed', 'infeasible', 'cancelled'):
                                break
                            await asyncio.sleep(.25)
                    assert progress['status']=='succeeded'
                    result=await call('ocp_result',{'server_id':server,'job_id':job});assert result['outcome']['solution_status']=='feasible'and result['outcome']['evaluation']['status']=='pass'
                    evaluated=await call('ocp_evaluate',{'server_id':server,'job_id':job});assert evaluated['evaluation']==result['outcome']['evaluation']and evaluated['checker_available']
                    return {'protocol_version':initialized.protocol_version,'tools':sorted(tools),'job_id':job,'solution_status':'feasible','checker_status':'pass'}
    error=None;result={};transport_exited=False;closures=[]
    previous_term=signal.getsignal(signal.SIGTERM)
    def interrupted(signum,frame):raise KeyboardInterrupt('MCP controller terminated')
    signal.signal(signal.SIGTERM,interrupted)
    try:
        result=asyncio.run(asyncio.wait_for(journey(),timeout=120))
        transport_exited=True
        assert len(processes)==1 and processes[0].returncode==0
        with sqlite3.connect((state/'jobs.sqlite').as_uri()+'?mode=ro',uri=True)as database:
            rows=[json.loads(x[0])for x in database.execute('SELECT body FROM jobs')]
        assert len(rows)==1 and rows[0]['id']==result['job_id']and rows[0]['status']=='succeeded'and rows[0]['attempt']==1
        assert rows[0]['lease_owner']is None and rows[0]['lease_until']is None and rows[0]['finished_at']is not None
        result.update(durable_job_count=1,durable_attempts=[rows[0]['attempt']],durable_replay_created_no_extra_job=True)
    except BaseException as exc:error=type(exc).__name__+': '+str(exc)
    finally:
        previous_int=signal.getsignal(signal.SIGINT)
        try:
            signal.signal(signal.SIGINT,signal.SIG_IGN);signal.signal(signal.SIGTERM,signal.SIG_IGN)
            closures=close_processes(processes,helper,args.process_registry)
        finally:
            signal.signal(signal.SIGINT,previous_int);signal.signal(signal.SIGTERM,previous_term)
    if len(closures)!=1 or any(c['closure']!='CLOSED'or c['group_absent_after_sdk_context']is not True or c['returncode']!=0 for c in closures):
        error=error or 'SDK_TRANSPORT_CLOSURE_NOT_CONFIRMED'
    with(out/'calls.json').open('x')as handle:json.dump(calls,handle,indent=2);handle.write('\n')
    result.update(status='PASS'if error is None else'FAIL',tests_run=1,errors=0 if error is None else 1,failures=0,skipped=0,error=error,
        host_config_sha256=sha(host),calls_sha256=sha(out/'calls.json'),processes=closures,transport_context_exited=transport_exited,
        mcp_sdk_version=metadata.version('mcp'),read_timeout_seconds=30.0,
        client_session_signature=str(inspect.signature(ClientSession)),
        sdk_stdio_sha256=sha(inspect.getfile(stdio_module)),sdk_session_sha256=sha(inspect.getfile(ClientSession)),
        expected_version=args.expected_version,scope='Actual local official SDK stdio; one durable local Routing attempt and independent checker',
        network_denial_enforced=False,external_host_ui='NOT_RUN',models=0,publication_authorized=False)
    with(out/'result.json').open('x')as handle:json.dump(result,handle,indent=2);handle.write('\n')
    print(json.dumps(result));raise SystemExit(error is not None)


if __name__=='__main__':main()
