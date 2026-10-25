import { readFileSync } from "node:fs";
import { Client, strictParse } from "ocp-candidate";

async function main() {
  const [endpoint, inputFile] = process.argv.slice(2);
  if (!endpoint || !inputFile) throw new Error("Usage: app-b <endpoint> <input.json>");
  const client = await Client.connect(endpoint, {token:process.env.OCP_TRIAL_TOKEN});
  const request=client.request(strictParse(readFileSync(inputFile,"utf8")),undefined,"app-b");
  const result=await client.execute(request);
  console.log(JSON.stringify(result));
  if (result.kind==="failure") process.exitCode=2;
}
main().catch(()=>{ console.error("App B failed; inspect endpoint, input and candidate compatibility. No automatic retry."); process.exitCode=2; });
