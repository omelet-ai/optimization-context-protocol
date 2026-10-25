import Ajv2020 from "ajv/dist/2020";
import { visit } from "jsonc-parser";
import { isDeepStrictEqual } from "node:util";
import { randomUUID, createHash } from "node:crypto";

export type Message = Record<string, any>;
const schema = require("./schemas/core-0.1.schema.json");
const validator = new Ajv2020({strict:false, allErrors:false}).compile(schema);
const MAX_RESPONSE_BYTES = 1048576;

async function responseText(response: Response): Promise<string> {
  if (!response.body) throw new Error("EMPTY_RESPONSE");
  if (Number(response.headers.get("content-length")) > MAX_RESPONSE_BYTES) {
    await response.body.cancel();
    throw new Error("RESPONSE_TOO_LARGE");
  }
  const reader=response.body.getReader();
  const chunks: Uint8Array[]=[];
  let size=0;
  try {
    while (true) {
      const {done,value}=await reader.read();
      if (done) break;
      size+=value.byteLength;
      if (size>MAX_RESPONSE_BYTES) {
        await reader.cancel();
        throw new Error("RESPONSE_TOO_LARGE");
      }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return new TextDecoder("utf-8",{fatal:true}).decode(Buffer.concat(chunks));
}

function jsonValues(value: any): void {
  if (typeof value === "number" && (!Number.isFinite(value) || (Number.isInteger(value) && !Number.isSafeInteger(value)))) throw new Error("INVALID_JSON_NUMBER");
  if (value === null || ["string","boolean","number"].includes(typeof value)) return;
  if (Array.isArray(value)) { value.forEach(jsonValues); return; }
  if (typeof value === "object" && Object.getPrototypeOf(value) === Object.prototype) { Object.values(value).forEach(jsonValues); return; }
  throw new Error("INVALID_JSON_VALUE");
}

export function strictParse(text: string): Message {
  const stack: Set<string>[] = [];
  visit(text, {
    onObjectBegin: () => { stack.push(new Set()); },
    onObjectProperty: name => { const keys=stack[stack.length-1]; if (keys.has(name)) throw new Error("DUPLICATE_JSON_KEY"); keys.add(name); },
    onObjectEnd: () => { stack.pop(); },
    onError: () => { throw new Error("INVALID_JSON"); },
  }, {disallowComments:true, allowTrailingComma:false, allowEmptyContent:false});
  const value=JSON.parse(text);
  jsonValues(value);
  return value;
}

export function envelope(value: Message): Message {
  jsonValues(value);
  if (!validator(value)) throw new Error("INVALID_ENVELOPE");
  for (const field of ["extensions","metrics","constraints","objectives"]) {
    const entries=value[field];
    if (Array.isArray(entries) && entries.every((v:any)=>typeof v === "object" && v!==null && "id" in v)) {
      if (new Set(entries.map((v:any)=>v.id)).size!==entries.length) throw new Error("DUPLICATE_ID");
    }
  }
  if ((value.extensions??[]).some((v:any)=>v.required)) throw new Error("UNSUPPORTED_EXTENSION");
  const configuration=value.configuration??value.effective_configuration??value.defaults;
  if (configuration && new Set(configuration.objectives.map((v:any)=>v.id)).size!==configuration.objectives.length) throw new Error("DUPLICATE_ID");
  if (value.kind === "result" && value.provenance.request_id !== value.request_id) throw new Error("INVALID_PROVENANCE");
  return value;
}

export class Client {
  private constructor(private base: string, private capability: Message, private token?: string) {}
  static async connect(base: string, options: {token?: string}={}): Promise<Client> {
    const url = new URL(base);
    if (url.protocol!=="https:" && !(url.protocol==="http:" && url.hostname==="127.0.0.1")) throw new Error("HTTPS_REQUIRED");
    if (url.username || url.password || url.search || url.hash || url.pathname!=="/") throw new Error("INVALID_ENDPOINT");
    if (options.token!==undefined && (!options.token || /[\r\n]/.test(options.token))) throw new Error("INVALID_CREDENTIAL");
    const client = new Client(url.origin, {}, options.token);
    client.capability=await client.call("/v1/capability");
    if (client.capability.kind!=="capability") throw new Error("INVALID_RESPONSE");
    return client;
  }
  describe(): Message { return structuredClone(this.capability); }
  private async call(path: string, payload?: Message): Promise<Message> {
    if (payload!==undefined) jsonValues(payload);
    const headers: Record<string,string>={"Content-Type":"application/json"};
    if (this.token) headers.Authorization="Bearer "+this.token;
    if (this.token && path==="/v1/execute" && payload) headers["Idempotency-Key"]=createHash("sha256").update(payload.request_id,"utf8").digest("hex");
    const response = await fetch(this.base+path, {method:payload===undefined?"GET":"POST", redirect:"error",
      headers, body:payload===undefined?undefined:JSON.stringify(payload), signal:AbortSignal.timeout(10000)});
    if (!response.headers.get("content-type")?.startsWith("application/json")) throw new Error("INVALID_CONTENT_TYPE");
    const message = envelope(strictParse(await responseText(response)));
    if (!response.ok && message.kind!=="failure") throw new Error("INVALID_HTTP_RESPONSE");
    return message;
  }
  request(input: Message, configuration: Message=this.capability.defaults, requestId: string=randomUUID(), timeLimitMs=1000): Message {
    return envelope({core_version:"0.1.0",kind:"request",request_id:requestId,capability:structuredClone(this.capability.capability),
      domain_profile:structuredClone(this.capability.domain_profile),execution_profile:{id:"execution.sync",version:"0.1.0"},
      configuration:structuredClone(configuration),input:structuredClone(input),budget:{time_limit_ms:timeLimitMs}});
  }
  async requirements(configuration: Message=this.capability.defaults): Promise<Message> {
    const result=await this.call("/v1/requirements",{configuration});
    if (result.kind!=="failure" && (result.kind!=="requirements" || !isDeepStrictEqual(result.effective_configuration,configuration) || !isDeepStrictEqual(result.capability,this.capability.capability))) throw new Error("INVALID_RESPONSE");
    return result;
  }
  async validate(request: Message): Promise<Message> {
    envelope(request);
    const result=await this.call("/v1/validate",request);
    if (result.kind!=="validation" || result.request_id!==request.request_id) throw new Error("INVALID_RESPONSE");
    return result;
  }
  async execute(request: Message): Promise<Message> {
    envelope(request);
    const result=await this.call("/v1/execute",request);
    if (!["result","failure"].includes(result.kind) || result.request_id!==request.request_id) throw new Error("INVALID_RESPONSE");
    if (result.kind==="result") {
      for (const key of ["capability","domain_profile","execution_profile"]) if (!isDeepStrictEqual(result[key],request[key])) throw new Error("INVALID_RESPONSE");
      if (!isDeepStrictEqual(result.effective_configuration,request.configuration)) throw new Error("INVALID_RESPONSE");
    }
    return result;
  }
}
