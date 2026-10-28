import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync,writeFileSync} from 'node:fs';
import {createOptimizationApiClient,capabilityDigest} from 'ocp-candidate/native';
import legacy from 'ocp-candidate';
const connection=JSON.parse(readFileSync('public-connection.json','utf8'));
const inputs=JSON.parse(readFileSync('inputs.json','utf8'));
const transcripts={};
for (const [domain,profile,cost] of [['routing-basic','routing.basic',18],['worker-scheduling','worker.scheduling',7],['inventory-replenishment','inventory.replenishment',16]]) {
  test(`public TypeScript native SDK: ${domain}`,async()=>{
    const api=createOptimizationApiClient({baseUrl:connection.base+'/api/'+domain+'/v1',token:connection.token,pollIntervalMs:30,maxPollIntervalMs:100});
    const catalog=await api.capabilities();const {catalogDigest,...rest}=catalog;
    assert.equal(capabilityDigest(rest),catalogDigest);
    const request=structuredClone(catalog.requestTemplate);request.input=inputs[profile];request.request_id='node-'+domain;
    assert.equal((await api.validate(request)).valid,true);
    const resolved=await api.resolveConfiguration({configuration:request.configuration});assert.deepEqual(resolved.resolved.configuration,request.configuration);
    const value=await api.solve(request,{tenantId:'node',idempotencyKey:domain,timeoutMs:60000});
    assert.equal(value.job.status,'succeeded');assert.equal(value.result.result.metrics[0].value,cost);
    const replay=await api.submit(request,{tenantId:'node',idempotencyKey:domain});assert.equal(replay.replayed,true);assert.equal(replay.job.jobId,value.job.jobId);
    await assert.rejects(()=>api.job(value.job.jobId,{tenantId:'different'}),e=>e.code==='JOB_NOT_FOUND');
    const changed=structuredClone(request);changed.configuration={unsupported:true};
    assert.equal((await api.validate(changed)).valid,false);
    transcripts[domain]={request,response:value.result.result};writeFileSync('node-transcripts.json',JSON.stringify(transcripts));
  });
}
test('old public SDK still exposes its original client',()=>assert.equal(typeof legacy.Client.connect,'function'));
