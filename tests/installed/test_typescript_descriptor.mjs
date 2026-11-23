import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createRequire} from 'node:module';
import {join, resolve} from 'node:path';

const root = new URL('../../', import.meta.url);
const read = path => JSON.parse(readFileSync(new URL(path, root), 'utf8'));
const require = createRequire(join(resolve(process.argv[2]), 'client.js'));
const {lintPackage, validateRequest, requireReference} = require('./server_package.js');
const manifest = read('examples/inventory-lot-sizing/content/manifest.json');
const schema = read('spec/schemas/server-package-0.1.schema.json');
const input = {demand: 36, capacity: 4, order_fee: 9, holding_fee: 2};
lintPackage(manifest, schema);
assert.deepEqual(validateRequest(manifest, input, {}), {});
assert.throws(() => validateRequest(manifest, {...input, capacity: 0}, {}));
assert.throws(() => lintPackage({...manifest, format_version: '999'}, schema));
assert.throws(() => lintPackage({...manifest, required_extensions: ['unknown']}, schema));
assert.throws(() => requireReference({version: '1'}, {version: '2'}));
console.log(JSON.stringify({status: 'PASS', tests_run: 6, errors: 0, failures: 0, skipped: 0}));
