"""H26 additive profile schemas and hand-calculated contract examples."""
import json
from pathlib import Path
import unittest
import sys
from jsonschema import Draft202012Validator
R=Path(__file__).resolve().parents[1]

def load(name):return json.loads((R/name).read_text())
class Contracts(unittest.TestCase):
    def test_01_schemas(self):
        for stem in ('worker-scheduling','inventory-replenishment'):
            for kind in ('input','solution','configuration'):
                s=load(f'spec/schemas/{stem}-{kind}-0.1.schema.json');Draft202012Validator.check_schema(s)
                self.assertIn(':0.1.0:',s['$id'])
    def test_02_worker_fixture(self):
        f=load('cases/worker/small.json')
        for kind,key in [('input','input'),('solution','witness'),('configuration','configuration')]:
            Draft202012Validator(load(f'spec/schemas/worker-scheduling-{kind}-0.1.schema.json')).validate(f[key])
        costs={t['id']:t['costs'] for t in f['input']['tasks']}
        self.assertEqual(sum(costs[a['task_id']][a['worker_id']] for a in f['witness']['assignments']),7)
    def test_03_inventory_fixture(self):
        f=load('cases/inventory/small.json');p=f['input']['products'][0];q=f['witness']['plans'][0]['orders'];stock=p['initial_inventory'];ends=[]
        for t,d in enumerate(p['demand']):
            stock+=p['scheduled_receipts'][t]+(q[t-p['lead_time']] if t>=p['lead_time'] else 0)-d;ends.append(stock)
        self.assertEqual(ends,[0,0,2,0]);self.assertEqual(sum(q)+4*sum(x>0 for x in q)+sum(ends),16)
        for kind,key in [('input','input'),('solution','witness'),('configuration','configuration')]:
            Draft202012Validator(load(f'spec/schemas/inventory-replenishment-{kind}-0.1.schema.json')).validate(f[key])
    def test_04_wrong_units(self):
        for domain,stem,key in [('worker','worker-scheduling','time_unit'),('inventory','inventory-replenishment','period_unit')]:
            f=load(f'cases/{domain}/small.json')['input'];f[key]='hour'
            self.assertFalse(Draft202012Validator(load(f'spec/schemas/{stem}-input-0.1.schema.json')).is_valid(f))
    def test_05_required_not_defaulted(self):
        for domain,stem in [('worker','worker-scheduling'),('inventory','inventory-replenishment')]:
            f=load(f'cases/{domain}/small.json')['input'];s=Draft202012Validator(load(f'spec/schemas/{stem}-input-0.1.schema.json'))
            for key in f:self.assertFalse(s.is_valid({k:v for k,v in f.items() if k!=key}))
    def test_06_unsupported_constraints(self):
        for domain,stem in [('worker','worker-scheduling'),('inventory','inventory-replenishment')]:
            f=load(f'cases/{domain}/small.json')['configuration'];f['constraints'].append('guess_business_policy')
            self.assertFalse(Draft202012Validator(load(f'spec/schemas/{stem}-configuration-0.1.schema.json')).is_valid(f))
    def test_07_unknown_fields(self):
        for domain,stem in [('worker','worker-scheduling'),('inventory','inventory-replenishment')]:
            f=load(f'cases/{domain}/small.json')['input'];f['relax_constraints']=True
            self.assertFalse(Draft202012Validator(load(f'spec/schemas/{stem}-input-0.1.schema.json')).is_valid(f))
    def test_08_core_remains_domain_neutral(self):
        core=(R/'spec/schemas/core-0.1.schema.json').read_text()
        self.assertNotIn('worker.scheduling',core);self.assertNotIn('inventory.replenishment',core)
        self.assertIn('solver 구현을 제공하지 않는다',(R/'spec/profiles/ASSIGNMENT_FIXTURE_0_1.md').read_text())
if __name__=='__main__':
    r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Contracts));ok=r.wasSuccessful() and not r.skipped
    print(json.dumps({'status':'PASS' if ok else 'FAIL','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'scope':'Additive bounded profile contracts; no solver or model execution'}));sys.exit(0 if ok else 1)
