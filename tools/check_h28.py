"""Inventory DP vs independent order enumeration, state/accounting mutations."""
from copy import deepcopy
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest
R=Path(__file__).resolve().parents[1];sys.path.insert(0,str(R))
from build_candidate import build
from conformance import inventory
from conformance.core_contract import ContractError,validate_message
WORK=tempfile.TemporaryDirectory(prefix='ocp-inventory-');WHEEL=build(WORK.name);sys.path.insert(0,WHEEL['wheel'])
from ocp_planning import inventory_adapter
from ocp_candidate import Client
F=json.loads((R/'cases/inventory/small.json').read_text())
class Inventory(unittest.TestCase):
    def setUp(self):self.a=inventory_adapter();self.c=Client(self.a);self.p=deepcopy(F['input'])
    def solve(self):
        r=self.c.request(self.p,request_id='inventory-check');o=self.a.execute(r);validate_message(o);return r,o
    def test_01_real_optimum(self):
        r,o=self.solve();self.assertEqual(o['status'],'optimal');self.assertEqual(inventory.verify_result(r,o)['total_cost'],16)
    def test_02_random_oracle(self):
        rng=random.Random(428)
        for _ in range(50):
            self.p=deepcopy(F['input']);x=self.p['products'][0]
            x.update(demand=[rng.randrange(5) for _ in range(4)],scheduled_receipts=[rng.randrange(3) for _ in range(4)],lead_time=rng.randrange(5),initial_inventory=rng.randrange(4),max_order_quantity=rng.randrange(6),fixed_order_cost=rng.randrange(6),holding_cost=rng.randrange(3),terminal_min_inventory=rng.randrange(3),storage_capacity=rng.randrange(4,9))
            r,o=self.solve();inventory.verify_result(r,o);self.assertEqual(o['proof']['evidence']['objective'],inventory.exhaustive_optimum(self.p))
    def test_03_zero_lead_time_receipts_before_demand(self):
        x=self.p['products'][0];x.update(lead_time=0,initial_inventory=0);r,o=self.solve();self.assertEqual(o['status'],'optimal');inventory.verify_result(r,o)
    def test_04_shortage_is_infeasible(self):
        self.p['products'][0]['initial_inventory']=0;r,o=self.solve();self.assertEqual(o['status'],'infeasible');inventory.verify_result(r,o)
    def test_05_storage_checked_before_demand(self):
        x=self.p['products'][0];x['scheduled_receipts'][0]=8;r,o=self.solve();self.assertEqual(o['status'],'infeasible');inventory.verify_result(r,o)
    def test_06_terminal_requirement(self):
        self.p['products'][0]['terminal_min_inventory']=1;r,o=self.solve();inventory.verify_result(r,o);self.assertGreaterEqual(o['solution']['plans'][0]['ending_inventory'][-1],1)
    def test_07_inventory_and_order_corruption(self):
        for field in ('orders','ending_inventory'):
            r,o=self.solve();o['solution']['plans'][0][field][0]+=1
            with self.assertRaises(ContractError):inventory.verify_result(r,o)
    def test_08_cost_and_proof_corruption(self):
        for kind in ('metric','proof','boolean'):
            r,o=self.solve()
            if kind=='metric':o['metrics'][0]['value']+=1
            elif kind=='proof':o['proof']['evidence']['objective']+=1
            else:o['proof']['evidence']['objective']=True
            with self.assertRaises(ContractError):inventory.verify_result(r,o)
    def test_09_multiple_products(self):
        x=deepcopy(self.p['products'][0]);x['id']='second';self.p['products'].append(x)
        r,o=self.solve();self.assertEqual(inventory.verify_result(r,o)['total_cost'],32)
    def test_10_invalid_input(self):
        for mut in (lambda p:p.update(period_unit='week'),lambda p:p['products'][0]['demand'].pop(),lambda p:p['products'][0].update(initial_inventory=50),lambda p:p['products'][0].update(backlog=True)):
            p=deepcopy(self.p);mut(p);self.assertFalse(self.a.validate(self.c.request(p))['valid'])
    def test_11_deadline_no_partial_plan(self):
        self.a.clock=iter([0,1]).__next__;r,o=self.solve();self.assertEqual(o['status'],'unknown');self.assertIsNone(o['solution']);inventory.verify_result(r,o)
    def test_12_no_late_orders(self):
        r,o=self.solve();o['solution']['plans'][0]['orders'][-1]=1
        with self.assertRaises(ContractError):inventory.verify_result(r,o)
    def test_13_no_orders_with_long_lead(self):
        x=self.p['products'][0];x.update(lead_time=6,initial_inventory=8)
        r,o=self.solve();self.assertEqual(o['solution']['plans'][0]['orders'],[0]*4);inventory.verify_result(r,o)
    def test_14_zero_demand_and_zero_capacity(self):
        x=self.p['products'][0];x.update(demand=[0]*4,initial_inventory=0,storage_capacity=0,max_order_quantity=0)
        r,o=self.solve();self.assertEqual(inventory.verify_result(r,o)['total_cost'],0)
    def test_16_json_schema_integral_floats(self):
        self.p['periods']=4.0;self.p['products'][0]['max_order_quantity']=5.0
        r,o=self.solve();self.assertEqual(inventory.verify_result(r,o)['total_cost'],16)
        self.assertEqual(type(self.p['periods']),float)
    def test_15_actual_expired_solver_clock(self):
        import time
        from ocp_planning.inventory import solve
        self.assertEqual(solve(self.p,time.monotonic()-1,time.monotonic),(None,False))
if __name__=='__main__':
    r=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(Inventory));ok=r.wasSuccessful() and not r.skipped
    print(json.dumps({'artifact_sha256':WHEEL['sha256'],'status':'PASS' if ok else 'FAIL','tests_run':r.testsRun,'failures':len(r.failures),'errors':len(r.errors),'skipped':len(r.skipped),'scope':'Actual inventory DP, 50 differential cases and independent accounting; no model'}));WORK.cleanup();sys.exit(0 if ok else 1)
