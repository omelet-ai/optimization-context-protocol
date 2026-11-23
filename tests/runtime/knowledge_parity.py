"""Run explicit Python/TypeScript Knowledge semantic and fingerprint parity.

Pass --node and --typescript-dist from the independently built TypeScript SDK.
This is an explicit check, never silently skipped when Node is absent.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import tempfile

from ocp_candidate.fingerprint import fingerprint
from ocp_candidate.knowledge import lint
from ocp_runtime.native_knowledge import KnowledgeService
from ocp_runtime.native_server import reference_domains


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--node', required=True)
    parser.add_argument('--typescript-dist', required=True, type=Path)
    args = parser.parse_args()
    domain = reference_domains(['routing-coordinates'])[0].domain
    catalog = domain.capabilities()
    bundle = KnowledgeService({domain.problem_type: domain}).bundle(domain.problem_type)
    values = [None, True, False, 0, -0.0, 1, 1.0, 1.25, 1e-30, '한국어😀', [], {},
              {'😀': 0, '\ue000': -1.25, '한국': ['a', True, None]}, {'b': 2, 'a': 1}]
    cases = [deepcopy(bundle)]
    for operation in (
        lambda b: b['sections']['constraints'].append(deepcopy(b['sections']['constraints'][0])),
        lambda b: b['sections']['objectives'][0]['value'].pop('unit'),
        lambda b: b['sections']['objectives'][0]['value'].update(direction='guess'),
        lambda b: b['sections']['objectives'][0]['value'].update(unit='km'),
        lambda b: b['required_extensions'].append('unsupported'),
        lambda b: b['localizations']['en'].update(aliases=['Alias', ' alias ']),
        lambda b: b.update(default_locale='ja'),
        lambda b: b['profile'].update(version='99'),
        lambda b: b['catalog_fingerprint'].update(sha256='0' * 64),
        lambda b: b.update(unknown=True),
        lambda b: b['sections'].pop('input'),
    ):
        value = deepcopy(bundle); operation(value); cases.append(value)
    def accepted(value):
        try: lint(value, catalog=catalog); return True
        except ValueError: return False
    expected = {'hashes': [fingerprint(value) for value in values], 'accepted': [accepted(value) for value in cases]}
    code = """
const fs = require('node:fs');
const {fingerprint} = require(process.argv[1] + '/fingerprint.js');
const {lintKnowledge} = require(process.argv[1] + '/knowledge.js');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const hashes = data.values.map(fingerprint);
const accepted = data.cases.map(value => {try {lintKnowledge(value, data.catalog); return true;} catch {return false;}});
for (const value of [NaN, Infinity, 2**53, undefined, '\\ud800', {x:undefined}, new Date(), [,,]]) {
  let rejected = false; try {fingerprint(value);} catch {rejected = true;}
  if (!rejected) throw new Error('unsafe JSON accepted');
}
process.stdout.write(JSON.stringify({hashes,accepted}));
"""
    result = subprocess.run([args.node, '-e', code, str(args.typescript_dist.resolve())],
        input=json.dumps({'values': values, 'cases': cases, 'catalog': catalog}), capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr)
    actual = json.loads(result.stdout)
    assert actual == expected, (actual, expected)
    assert expected['accepted'] == [True] + [False] * (len(cases) - 1)
    print(json.dumps({'status': 'PASS', 'fingerprint_vectors': len(values), 'knowledge_cases': len(cases),
                      'typescript_non_json_rejections': 8, 'model_calls': 0}))


if __name__ == '__main__': main()
