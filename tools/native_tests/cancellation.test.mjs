/** A real SDK call sequence against a labelled protocol fixture, not a solver. */
import assert from 'node:assert/strict';
import test from 'node:test';
import * as external from 'ocp-candidate/native';
import * as shared from '@omelet/ocp-native-contracts';

for (const [name, sdk] of [['public entry', external], ['canonical package', shared]]) {
  test(`${name}: a failed cancellation cannot claim that computation stopped`, async () => {
    assert.equal(sdk.createOptimizationApiClient, shared.createOptimizationApiClient);
    const calls = [];
    const jobId = '12345678-1234-4234-8234-123456789abc';
    const stamp = '2026-10-28T00:00:00+00:00';
    const api = sdk.createOptimizationApiClient({ baseUrl: 'http://fixture.invalid', token: 'synthetic',
      fetch: async (url, options) => {
        calls.push(options.method);
        assert.equal(new URL(url).pathname, `/jobs/${jobId}`);
        if (options.method === 'DELETE') return Response.json({code:'UNAVAILABLE', message:'controlled outage',
          retryable:true, requestId:'fixture', issues:[]}, {status:503});
        await new Promise(resolve => setTimeout(resolve, 5));
        return Response.json({jobId, problemType:'fixture', status:'running', attempt:1, cancelRequested:false,
          createdAt:stamp, updatedAt:stamp, startedAt:stamp, finishedAt:null, expiresAt:stamp});
      }});
    let error;
    try { await api.wait(jobId, {tenantId:'local', timeoutMs:1}); } catch (e) { error=e; }
    assert.deepEqual(calls, ['GET', 'DELETE']);
    assert.equal(error.code, 'TIMEOUT'); assert.equal(error.retryable, true);
    assert.doesNotMatch(error.message, /it was cancelled/);
    assert.match(error.message, /termination is unconfirmed/);
  });
}
