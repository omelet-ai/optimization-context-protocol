"""An exact bounded lot-sizing solver with no external service or package dependencies."""
from pathlib import Path
import json


class LotSizer:
    isolation = 'local_process'

    def describe(self):
        manifest=json.loads(Path(__file__).with_name('manifest.json').read_bytes())
        return {key:manifest[key] for key in ('api','schemas','capabilities')}

    def validate(self, data, configuration):
        return {'valid':True,'issues':[]}

    def execute(self, data, configuration):
        def evaluate(quantity):
            orders=(data['demand']+quantity-1)//quantity
            return orders*data['order_fee']+(quantity-1)*data['holding_fee'], quantity, orders
        cost,lot,orders=min(evaluate(q) for q in range(1,min(data['capacity'],data['demand'])+1))
        return {'solution_status':'optimal','termination_reason':'completed','effective_configuration':dict(configuration),
                'result':{'lot':lot,'orders':orders,'cost':cost},'proof':{'method':'complete integer enumeration'}}


class Feasibility:
    identity={'id':'lot-sizing.accounting','version':'1.0.0','kind':'independent'}

    def evaluate(self,data,configuration,result):
        q,n=result['lot'],result['orders']
        checks={'capacity':1<=q<=min(data['capacity'],data['demand']),
                'demand':(n-1)*q<data['demand']<=n*q,
                'cost':result['cost']==n*data['order_fee']+(q-1)*data['holding_fee']}
        return {'status':'pass' if all(checks.values()) else 'fail',
                'checks':[{'id':k,'status':'pass' if ok else 'fail'} for k,ok in checks.items()],
                'tolerance':{'absolute':0},'unverified':['global optimality']}


def create_bundle(settings):
    return {'connector':LotSizer(),'checker':Feasibility(),'converters':{}}
