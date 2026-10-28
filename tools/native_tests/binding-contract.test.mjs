import test from 'node:test';
import assert from 'node:assert/strict';
import * as native from 'ocp-candidate/native';
import * as shared from '@omelet/ocp-native-contracts';
import legacy from 'ocp-candidate';
import {readFileSync} from 'node:fs';
test('public native entry uses identical canonical implementation',()=>{
  for(const key of ['createOptimizationApiClient','capabilityCatalogSchema','capabilityJobSchema','validateOcpStandardDomainManifest'])
    assert.equal(native[key],shared[key]);
  assert.equal(typeof legacy.Client,'function');
  assert.equal('createOptimizationApiClient' in legacy,false);
});
test('catalog digest fixtures remain canonical',()=>{
  for(const v of JSON.parse(readFileSync('vectors.json','utf8')).vectors) {
    assert.equal(native.canonicalDigest(JSON.parse(v.input)),v.digest);
  }
});
test('Python and Zod agree on representative contract responses',()=>{
  const schemas={Capabilities:native.capabilityCatalogSchema,Job:native.capabilityJobSchema,
    JobResult:native.capabilityJobResultSchema,ErrorEnvelope:native.capabilityErrorEnvelopeSchema,Validation:native.capabilityValidationSchema};
  for(const item of JSON.parse(readFileSync('contract-cases.json','utf8')))
    assert.equal(schemas[item.component].safeParse(item.value).success,item.valid,item.id);
});
test('original SDK transport failures remain uncertainty',async()=>{
  let calls=0;
  const api=native.createOptimizationApiClient({baseUrl:'http://invalid.local',token:'synthetic',
    fetch:async()=>{calls++;throw Error('offline');}});
  await assert.rejects(()=>api.submit({}, {tenantId:'local',idempotencyKey:'stable'}),e=>e.code==='UNREACHABLE');
  assert.equal(calls,1);
});
