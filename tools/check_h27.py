"""Real worker search vs independent enumeration, mutations and deadline semantics."""
from copy import deepcopy
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
from unittest.mock import patch
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from build_candidate import build
from conformance import worker
from conformance.core_contract import ContractError,validate_message
WORK=tempfile.TemporaryDirectory(prefix='ocp-worker-');WHEEL=build(WORK.name);sys.path.insert(0,WHEEL['wheel'])
from ocp_planning import worker_adapter
from ocp_candidate import Client
F=json.loads((R/'cases/worker/small.json').read_text())
class Workers(unittest.TestCase):
    def setUp(self):self.a=worker_adapter();self.c=Client(self.a);self.p=deepcopy(F['input'])
    def solve(self):
        r=self.c.request(self.p,request_id='worker-check');out=self.a.execute(r);validate_message(out);return r,out
    def test_01_real_optimum(self):
        r,o=self.solve();self.assertEqual(o['status'],'optimal');self.assertEqual(worker.verify_result(r,o)['total_cost'],7)
    def test_02_random_oracle(self):
        rng=random.Random(427)
        for _ in range(30):
            self.p=deepcopy(F['input'])
            for t in self.p['tasks']:
                t['eligible_workers']=[w for w in ['alice','bob'] if rng.random()>.2];t['costs']={w:rng.randrange(9) for w in t['eligible_workers']}
            r,o=self.solve();worker.verify_result(r,o);self.assertEqual(o['proof']['evidence']['objective'],worker.exhaustive_optimum(self.p))
    def test_03_adjacent_intervals(self):
        self.p['tasks'][1].update(start=60,end=90);r,o=self.solve();worker.verify_result(r,o)
    def test_04_empty_eligibility(self):
        self.p['tasks'][0].update(eligible_workers=[],costs={});r,o=self.solve();self.assertEqual(o['status'],'infeasible');worker.verify_result(r,o)
    def test_05_overlap_corruption(self):
        r,o=self.solve();o['solution']['assignments'][1]['worker_id']='alice'
        with self.assertRaises(ContractError):worker.verify_result(r,o)
    def test_06_missing_and_duplicate_task(self):
        for mode in ('missing','duplicate'):
            r,o=self.solve()
            if mode=='missing':o['solution']['assignments'].pop()
            else:o['solution']['assignments'][1]=deepcopy(o['solution']['assignments'][0])
            with self.assertRaises(ContractError):worker.verify_result(r,o)
    def test_07_bad_metric_and_proof(self):
        for kind in ('metric','proof','definition'):
            r,o=self.solve()
            if kind=='metric':o['metrics'][0]['value']+=1
            elif kind=='proof':o['proof']['evidence']['objective']+=1
            else:o['constraints'][0]['definition']='wrong'
            with self.assertRaises(ContractError):worker.verify_result(r,o)
    def test_08_invalid_inputs(self):
        for mut in (lambda p:p.update(time_unit='hour'),lambda p:p['tasks'][0].update(end=0),lambda p:p['tasks'][0]['costs'].update(ghost=1),lambda p:p['workers'].append(deepcopy(p['workers'][0]))):
            p=deepcopy(self.p);mut(p);self.assertFalse(self.a.validate(self.c.request(p))['valid'])
    def test_09_workload_and_availability(self):
        for w in self.p['workers']:w['max_minutes']=0
        r,o=self.solve();self.assertEqual(o['status'],'infeasible');worker.verify_result(r,o)
        self.p=deepcopy(F['input']);self.p['workers'][0]['availability']=[{'start':150,'end':180}]
        r,o=self.solve();worker.verify_result(r,o)
    def test_10_deadline_unknown_not_infeasible(self):
        self.a.clock=iter([0,1]).__next__;r,o=self.solve();self.assertEqual(o['status'],'unknown');self.assertEqual(o['termination'],'time_limit');worker.verify_result(r,o)
    def test_11_deadline_incumbent(self):
        self.a.clock=iter([0,0,0,0,0,1]).__next__;r,o=self.solve();self.assertEqual(o['status'],'feasible');self.assertIsNone(o['proof']);worker.verify_result(r,o)
    def test_12_configuration_version_budget(self):
        for mut in (lambda r:r['configuration']['constraints'].append('fairness'),lambda r:r['domain_profile'].update(version='9.0.0'),lambda r:r['budget'].update(time_limit_ms=5001)):
            r=self.c.request(self.p);mut(r);self.assertFalse(self.a.validate(r)['valid'])
    def test_13_provider_evaluation_not_independent(self):
        r,o=self.solve();e=self.a.evaluate(r,o['solution']);validate_message(e);self.assertEqual(e['metrics'][0]['source'],'engine')
    def test_15_ineligible_cost_is_not_zero(self):
        self.p['tasks'][0].update(eligible_workers=['bob'],costs={'bob':5})
        r=self.c.request(self.p);e=self.a.evaluate(r,F['witness'])
        self.assertEqual(e['kind'],'failure');self.assertEqual(e['error']['code'],'INELIGIBLE_ASSIGNMENT')
        with self.assertRaises(ContractError):worker.evaluate(self.p,F['witness'])
    def test_14_actual_expired_solver_clock(self):
        import time
        from ocp_planning.worker import solve
        self.assertEqual(solve(self.p,time.monotonic()-1,time.monotonic),(None,False))
    def test_16_eligibility_error_identifies_fix_without_executing(self):
        for mode,field in [('missing_cost','costs'),('extra_cost','costs'),('unknown_worker','eligible_workers')]:
            p=deepcopy(self.p)
            if mode=='missing_cost':p['tasks'][0]['costs'].pop(p['tasks'][0]['eligible_workers'][0])
            elif mode=='extra_cost':p['tasks'][0]['costs']['ghost']=1
            else:p['tasks'][0]['eligible_workers'].append('ghost')
            r=self.c.request(p)
            with patch.object(self.a.profile,'solve',side_effect=AssertionError('invalid input reached solver')):
                checked=self.a.validate(r);failed=self.a.execute(r)
            self.assertFalse(checked['valid']);issue=checked['issues'][0]
            self.assertEqual(issue['code'],'INVALID_ELIGIBILITY')
            self.assertEqual(issue['path'],'/tasks/0/'+field)
            self.assertNotEqual(issue['message'],'Request cannot be processed')
            self.assertEqual(failed['kind'],'failure')
            self.assertEqual(failed['error']['code'],issue['code'])
if __name__=='__main__':
    r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Workers));ok=r.wasSuccessful() and not r.skipped
    print(json.dumps({'artifact_sha256':WHEEL['sha256'],'status':'PASS' if ok else 'FAIL','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'scope':'Actual bounded worker solver, 30 differential cases and independent faults; no model'}));WORK.cleanup();sys.exit(0 if ok else 1)
