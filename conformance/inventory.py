"""Independent order-vector enumeration and inventory accounting; no DP/provider imports."""
from itertools import product
import sys
from .planning import shape, verify, integral_numbers
from .core_contract import ContractError
ID='inventory.replenishment'
STEM='inventory-replenishment'
PROOF='bounded-order-enumeration'

def validate_problem(p):
    shape(STEM,'input',p)
    ids=[x['id'] for x in p['products']]
    if len(set(ids))!=len(ids):raise ContractError('DUPLICATE_ID')
    for x in p['products']:
        if any(len(x[k])!=p['periods'] for k in ['demand','scheduled_receipts']):raise ContractError('PERIOD_MISMATCH')
        if x['initial_inventory']>x['storage_capacity']:raise ContractError('INITIAL_CAPACITY_EXCEEDED')

def evaluate(p,s):
    validate_problem(p);shape(STEM,'solution',s);p=integral_numbers(p);s=integral_numbers(s)
    ids=[r['product_id'] for r in s['plans']];products={x['id']:x for x in p['products']}
    if len(ids)!=len(set(ids)) or set(ids)!=set(products):raise ContractError('SOLUTION_PRODUCTS')
    counts=dict.fromkeys(['inventory_balance','no_stockout','storage_capacity','order_limit','terminal_inventory'],0);total=0
    for r in s['plans']:
        x=products[r['product_id']];n=p['periods'];q=r['orders'];ends=r['ending_inventory']
        if len(q)!=n or len(ends)!=n:raise ContractError('PERIOD_MISMATCH')
        arrivals=x['scheduled_receipts'].copy()
        for placed,amount in enumerate(q):
            due=placed+x['lead_time']
            counts['order_limit']+=int(amount>x['max_order_quantity'] or (due>=n and amount!=0))
            if due<n:arrivals[due]+=amount
        for t,(previous,remaining) in enumerate(zip([x['initial_inventory']]+ends[:-1],ends)):
            available=previous+arrivals[t]
            counts['inventory_balance']+=int(remaining+x['demand'][t]!=available)
            counts['no_stockout']+=int(available<x['demand'][t])
            counts['storage_capacity']+=int(available>x['storage_capacity'])
        counts['terminal_inventory']+=int(ends[-1]<x['terminal_min_inventory'])
        total+=sum(q)*x['unit_order_cost']+sum(1 for a in q if a)*x['fixed_order_cost']+sum(ends)*x['holding_cost']
    return {'feasible':not any(counts.values()),'total_cost':total,'violations':counts}

def exhaustive_optimum(p):
    validate_problem(p);p=integral_numbers(p);total=0;n=p['periods']
    for x in p['products']:
        minimum=None;lag=x['lead_time'];order_periods=max(0,n-lag)
        for prefix in product(range(x['max_order_quantity']+1),repeat=order_periods):
            orders=list(prefix)+[0]*(n-order_periods);stock=x['initial_inventory'];stock_sum=0;valid=True
            for t in range(n):
                stock+=x['scheduled_receipts'][t]+(orders[t-lag] if t>=lag else 0)
                if stock>x['storage_capacity']:valid=False;break
                stock-=x['demand'][t]
                if stock<0:valid=False;break
                stock_sum+=stock
            if not valid or stock<x['terminal_min_inventory']:continue
            cost=sum(orders)*x['unit_order_cost']+sum(q>0 for q in orders)*x['fixed_order_cost']+stock_sum*x['holding_cost']
            if minimum is None or cost<minimum:minimum=cost
        if minimum is None:return None
        total+=minimum
    return total

def verify_result(request,result):return verify(sys.modules[__name__],request,result)
