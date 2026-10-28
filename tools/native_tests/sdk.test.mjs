import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createOptimizationApiClient, OptimizationApiError } from '@omelet/ocp-server-base';

test('invalid successful catalog is rejected by the shared validator', async () => {
  const api=createOptimizationApiClient({baseUrl:'http://invalid.local',token:'synthetic',
    fetch:async()=>Response.json({contractVersion:'0.1.0'})});
  await assert.rejects(()=>api.capabilities(), e=>e instanceof OptimizationApiError && e.code==='BAD_ANSWER');
});
test('job submission without a tenant does not send a request', async () => {
  let calls=0;
  const api=createOptimizationApiClient({baseUrl:'http://invalid.local',token:'synthetic',
    fetch:async()=>{calls++;throw Error('must not send');}});
  await assert.rejects(()=>api.submit({}, {idempotencyKey:'key'}), e=>e.code==='TENANT_REQUIRED');
  assert.equal(calls,0);
});
test('failed transport remains uncertain and is not retried as a new job', async () => {
  let calls=0;
  const api=createOptimizationApiClient({baseUrl:'http://invalid.local',token:'synthetic',
    fetch:async()=>{calls++;throw Error('offline');}});
  await assert.rejects(()=>api.submit({}, {idempotencyKey:'key',tenantId:'local'}),e=>e.code==='UNREACHABLE');
  assert.equal(calls,1);
});
test('native API error envelope is preserved', async () => {
  const error={code:'IDEMPOTENCY_CONFLICT',message:'different request',requestId:'test',retryable:false,issues:[]};
  const api=createOptimizationApiClient({baseUrl:'http://invalid.local',token:'synthetic',
    fetch:async()=>Response.json(error,{status:409})});
  await assert.rejects(()=>api.submit({}, {idempotencyKey:'key',tenantId:'local'}),e=>
    e.code===error.code && e.retryable===false && JSON.stringify(e.envelope)===JSON.stringify(error));
});
