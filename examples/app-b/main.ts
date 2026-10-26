import { readFileSync } from "node:fs";
import { Client, strictParse, OCPClientError } from "ocp-candidate";

async function main() {
  const [endpoint, inputFile, option, requestId, extra] = process.argv.slice(2);
  if (!endpoint || !inputFile || option!=="--request-id" || !requestId || extra!==undefined) {
    console.error("Usage: node dist/main.js <endpoint> <input.json> --request-id <stable-job-id>. Reuse the ID only for the same input; choose a new ID for a different job.");
    process.exitCode=2; return;
  }
  const input=strictParse(readFileSync(inputFile,"utf8"));
  const client = await Client.connect(endpoint, {token:process.env.OCP_TRIAL_TOKEN});
  const request=client.request(input,undefined,requestId);
  const result=await client.execute(request);
  console.log(JSON.stringify(result));
  if (result.kind==="failure") process.exitCode=2;
}
main().catch((error: unknown)=>{
  // Never echo arbitrary exceptions, request bodies, credential values or URLs.
  const safe=new Set(["UNAUTHORIZED","CATALOG_CHANGED","TRIAL_EXPIRED","QUOTA_EXCEEDED","INVALID_JSON","DUPLICATE_JSON_KEY","INVALID_JSON_NUMBER","INVALID_ENVELOPE","INVALID_RESPONSE","ENOENT","EACCES"]);
  const candidate=error instanceof OCPClientError ? error.code : error instanceof Error ? ((error as NodeJS.ErrnoException).code ?? error.message) : "";
  const code=safe.has(candidate)?candidate:"CONNECTION_OR_INPUT_ERROR";
  const hint=code==="UNAUTHORIZED"?"Check OCP_TRIAL_TOKEN with your inviter; never paste the key.":code==="ENOENT"?"Check the input JSON file path.":"Check input, endpoint and invitation hours. Preserve the request ID after uncertainty; no automatic retry.";
  console.error(JSON.stringify({status:"FAIL",code,hint})); process.exitCode=2;
});
