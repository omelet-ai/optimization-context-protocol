// Minimal Node app: use your input/UI with the same discovery-to-evaluation flow.
const { readFileSync } = require("node:fs");
const { Client, strictParse } = require("ocp-candidate");

async function main() {
  const [endpoint, inputFile, requestId, extra] = process.argv.slice(2);
  if (!endpoint || !inputFile || !requestId || extra !== undefined) {
    console.error("Usage: node own_app.cjs <endpoint> <input.json> <stable-request-id>");
    process.exitCode = 2; return;
  }
  const client = await Client.connect(endpoint);
  const requirements = await client.requirements();
  if (requirements.kind === "failure") throw new Error("REQUIREMENTS_REJECTED");
  const request = client.request(strictParse(readFileSync(inputFile, "utf8")), undefined, requestId);
  const validation = await client.validate(request);
  if (!validation.valid) {
    console.log(JSON.stringify({ status: "FAIL", validation, execute_calls: 0 }));
    process.exitCode = 2; return;
  }
  const response = await client.execute(request);
  if (response.kind === "failure") {
    console.log(JSON.stringify({ status: "FAIL", response, execute_calls: 1 }));
    process.exitCode = 2; return;
  }
  const evaluation = response.solution === null ? null : await client.evaluate(request, response.solution);
  const ok = evaluation === null || evaluation.kind === "evaluation";
  console.log(JSON.stringify({ status: ok ? "PASS" : "FAIL", request, response, evaluation,
    execute_calls: 1, scope: "provider_evaluation_not_independent_check", solution_found: response.solution !== null }));
  if (!ok) process.exitCode = 2;
}
main().catch(() => {
  console.error(JSON.stringify({ status: "FAIL", code: "LOCAL_APP_ERROR",
    hint: "Check the local provider and input file. Preserve the request ID after an uncertain solve; no automatic retry." }));
  process.exitCode = 2;
});
