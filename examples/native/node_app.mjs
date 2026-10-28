import { createOptimizationApiClient } from 'ocp-candidate/native';
let raw = '';
for await (const chunk of process.stdin) raw += chunk;
const { baseUrl, token, problem } = JSON.parse(raw);
const api = createOptimizationApiClient({ baseUrl, token, pollIntervalMs: 20 });
if (!(await api.validate(problem)).valid) throw new Error('INPUT_REJECTED');
const result = await api.solve(problem, { tenantId: 'local-engineer', idempotencyKey: problem.request_id });
console.log(JSON.stringify(result));
