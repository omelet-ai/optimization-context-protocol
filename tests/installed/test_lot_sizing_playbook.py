"""Build a new authored wheel and exercise all of its playbook candidates over installed MCP."""
import asyncio
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

def run(work):
    from ocp_runtime.authoring.scaffold import create_project
    work.mkdir(mode=0o700)
    project=work/'project'
    create_project(project,'portable-lot-sizing',content=Path(__file__).resolve().parents[2]/'examples/inventory-lot-sizing/content')
    subprocess.run([sys.executable,'-Im','pip','wheel','--no-index','--no-build-isolation','--no-deps','-w',str(work),str(project)],check=True)
    wheel,=work.glob('*.whl')
    subprocess.run([sys.executable,'-Im','pip','install','--no-index','--no-deps','--force-reinstall',str(wheel)],check=True)
    conf=work/'config.json'
    conf.write_text(json.dumps({'connector_factory':'ocp_portable_lot_sizing.content.engine:create_bundle','transport':'stdio','state_directory':str(work/'state')}))
    async def verify():
        params=StdioServerParameters(command=sys.executable,args=['-IBm','ocp_portable_lot_sizing.server','serve','--config',str(conf)],cwd=str(work))
        async with stdio_client(params) as streams, ClientSession(*streams,read_timeout_seconds=30.0) as client:
            await client.initialize()
            async def call(tool,args):
                reply=await client.call_tool(tool,args);assert not reply.is_error,(tool,reply.structured_content)
                assert json.loads(reply.content[0].text)==reply.structured_content
                return reply.structured_content
            entry,=(await call('ocp_context',{}))['servers'];server={'server_id':entry['id']};assert entry['id']=='inventory.lot-sizing'
            book=(await call('ocp_describe',{**server,'section':'playbooks','item_id':'compare-storage-limits','expected_digest':entry['digest']}))['item']['value']
            args={'playbook_id':book['id'],'input_value':{'demand':36,'capacity':7,'order_fee':9,'holding_fee':2},'configuration':{}}
            plan=await call('ocp_plan',{**server,**args});assert plan['attempts_started']==0
            ref={**server,'analysis_id':plan['id']}
            confirm={**ref,'expected_plan_fingerprint':plan['plan']['plan_fingerprint']}
            await call('ocp_run',confirm)
            async def complete():
                while True:
                    analysis=await call('ocp_analysis',ref)
                    if analysis['status'] in ('completed','stopped'):return analysis
                    await asyncio.sleep(.15)
            analysis=await asyncio.wait_for(complete(),45)
            report=await call('ocp_compare',ref)
            assert analysis['status']=='completed' and report['attempts_started']==3
            native={row['id']:row['result'] for row in analysis['candidates']}
            for candidate in plan['plan']['candidates']:
                cap=candidate['request']['input']['capacity']
                cost,q,n=min((9*n+2*(q-1),q,n) for q in range(1,cap+1) for n in range(1,37) if (n-1)*q<36<=n*q)
                outcome=native[candidate['id']];assert outcome['solution_status']=='optimal' and outcome['evaluation']['status']=='pass'
                assert outcome['result']=={'cost':cost,'lot':q,'orders':n}
            assert sorted(row['metrics']['cost'] for row in report['rows'])==[49,64,87]
            assert (await call('ocp_run',confirm))['replayed'];assert await call('ocp_compare',ref)==report
    asyncio.run(verify())
    store,=(work/'state').glob('analysis-*.sqlite')
    with sqlite3.connect(store.as_uri()+'?mode=ro',uri=True) as db:assert db.execute('SELECT count(*) FROM jobs').fetchone()[0]==3
    print(json.dumps({'status': 'PASS', 'tests_run': 1, 'errors': 0, 'failures': 0, 'skipped': 0,
                      'candidates': 3, 'replay_new_jobs': 0}))
if __name__=='__main__':run(Path(sys.argv[1]).resolve())
