"""Deterministic replenishment via per-product inventory-state dynamic programming."""
from ocp_candidate.contract import OCPError
ID='inventory.replenishment'
STEM='inventory-replenishment'
ENGINE='ocp.inventory-dynamic-programming'
PROOF='bounded-order-enumeration'
LIMITATIONS=['1-4 independent products, 1-6 daily periods; integer items; orders <=5, capacity <=50',
             'Demand is an explicit forecast, not inferred; no backlog, lost sales, uncertainty or shared capacity',
             'Receipts before demand, holding cost on ending stock; late-horizon orders must be zero',
             'Budget 1-5000 ms; independent enumeration required to verify optimal/infeasible proofs']
REQUIREMENTS=[{'path':'/'+p,'reason':r,'unit':u} for p,r,u in [
 ('products','Explicit demand, receipts, lead time, capacity, terminal stock and three cost coefficients','item'),
 ('periods','Shared finite horizon; every product array must match this length','day'),
 ('period_unit','Equal daily buckets; receipts before demand','day'),('quantity_unit','Indivisible nonnegative quantities','item'),
 ('cost_unit','Additive ordering and end-of-day holding costs','cost_unit')]]

def validate_problem(p):
    if len({x['id'] for x in p['products']})!=len(p['products']):raise OCPError('DUPLICATE_ID')
    for x in p['products']:
        if len(x['demand'])!=p['periods'] or len(x['scheduled_receipts'])!=p['periods']:raise OCPError('PERIOD_MISMATCH')
        if x['initial_inventory']>x['storage_capacity']:raise OCPError('INITIAL_CAPACITY_EXCEEDED')

def evaluate(p,s):
    products={x['id']:x for x in p['products']};ids=[x['product_id'] for x in s['plans']]
    if len(ids)!=len(set(ids)) or set(ids)!=set(products):raise OCPError('SOLUTION_PRODUCTS')
    cost=0;v={k:0 for k in ['inventory_balance','no_stockout','storage_capacity','order_limit','terminal_inventory']}
    n=p['periods']
    for row in s['plans']:
        x=products[row['product_id']];q=row['orders'];end=row['ending_inventory'];lag=x['lead_time']
        if len(q)!=n or len(end)!=n:raise OCPError('PERIOD_MISMATCH')
        for t in range(n):
            previous=x['initial_inventory'] if t==0 else end[t-1]
            received=previous+x['scheduled_receipts'][t]+(q[t-lag] if t>=lag else 0)
            expected=received-x['demand'][t]
            v['inventory_balance']+=end[t]!=expected;v['no_stockout']+=expected<0
            v['storage_capacity']+=received>x['storage_capacity']
            v['order_limit']+=q[t]>x['max_order_quantity'] or (t+lag>=n and q[t]!=0)
            cost+=q[t]*x['unit_order_cost']+(x['fixed_order_cost'] if q[t]>0 else 0)+end[t]*x['holding_cost']
        v['terminal_inventory']+=end[-1]<x['terminal_min_inventory']
    return cost,v

def solve(p,deadline,clock):
    plans=[];n=p['periods']
    for x in p['products']:
        # State: ending stock -> (cost, full order vector, inventory prefix).
        states={x['initial_inventory']:(0,[0]*n,[])};lag=x['lead_time']
        for t in range(n):
            following={}
            for previous,(cost,orders,ends) in states.items():
                for q in range(x['max_order_quantity']+1) if t>=lag else (0,):
                    if clock()>=deadline:return None,False
                    available=previous+x['scheduled_receipts'][t]+q
                    end=available-x['demand'][t]
                    if available>x['storage_capacity'] or end<0:continue
                    value=cost+q*x['unit_order_cost']+(x['fixed_order_cost'] if q else 0)+end*x['holding_cost']
                    if end not in following or value<following[end][0]:
                        new_orders=orders.copy()
                        if t>=lag:new_orders[t-lag]=q
                        following[end]=(value,new_orders,ends+[end])
            states=following
            if not states:return None,True
        valid=[v for end,v in states.items() if end>=x['terminal_min_inventory']]
        if not valid:return None,True
        _,q,ends=min(valid,key=lambda a:(a[0],a[1]));plans.append({'product_id':x['id'],'orders':q,'ending_inventory':ends})
    return {'plans':plans},True
