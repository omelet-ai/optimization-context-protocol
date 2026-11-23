from pathlib import Path
import hashlib,json,re,runpy,threading,math,os


def verify_authored_sensitive_files(root):
    """Check authored files, not private runs or installed third-party caches.

    This is not publication approval. The publication allowlist has its own
    verifier; imported source paths are always checked explicitly below.
    """
    root = Path(root).resolve()
    for directory, directories, names in os.walk(root, followlinks=False):
        if Path(directory) == root:
            directories[:] = [d for d in directories if d not in {'.git', '.harness', '.private'}]
        for name in names:
            p = Path(directory) / name
            assert not name.startswith('.env') and p.suffix.lower() not in {'.pem','.key','.p12','.pfx','.pyc'}, str(p.relative_to(root))


def verify_document_links(root):
    root = Path(root).resolve()
    # Excluded generated trees can contain installed environments and large
    # experiment histories. Prune them before traversal, not after enumeration.
    # Only the existing root-level exclusions apply to authored documents.
    def unreadable(error):
        raise error
    paths = []
    for directory, directories, names in os.walk(root, followlinks=False, onerror=unreadable):
        if Path(directory) == root:
            directories[:] = [d for d in directories if d not in {'.private', 'reference', '.harness'}]
        paths.extend(Path(directory) / name for name in names if name.endswith('.md'))
    for path in sorted(paths):
        relative = path.relative_to(root)
        text = path.read_text()
        assert sum(line.startswith('```') for line in text.splitlines()) % 2 == 0, str(relative)
        for link in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)', text):
            if re.match(r'[a-z]+://', link): continue
            target = (path.parent / link.split('#')[0]).resolve()
            assert target.is_relative_to(root) and target.exists(), (str(relative), link)


def main():
 root=Path(__file__).resolve().parents[1]
 m=json.loads((root/'provenance/source-manifest.json').read_text())
 for item in m['files']:
  p=root/item['destination_path']
  assert p.is_file() and not p.is_symlink(), item['destination_path']
  assert not p.name.startswith('.env') and p.suffix.lower() not in {'.pem','.key','.p12','.pfx','.pyc'}, item['destination_path']
  assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'], item['destination_path']
  assert item['publication_approved'] is False
 verify_document_links(root)
 verify_authored_sensitive_files(root)
 case=json.loads((root/'cases/failure-semantics/greedy-feasible.json').read_text())
 module=runpy.run_path(str(root/'reference/imported-foundry/factory/templates/optimization-api/app/adapters/greedy_allocation.py'))
 answer=module['GreedyAllocationSolver']().solve({'resources':case['resources'],'demands':case['demands']},case['configuration'],threading.Event())
 assert answer['unassigned']==case['expected_legacy_unassigned']
 assert answer['objective_value']==case['expected_legacy_objective_value']
 demands={x['id']:x['amount'] for x in case['demands']};used=[]
 for resource in case['resources']:
  assigned=case['witness'][resource['id']];used+=assigned
  assert sum(demands[x] for x in assigned)<=resource['max_capacity']
 assert sorted(used)==sorted(demands)
 routing=json.loads((root/'cases/routing/design-case.json').read_text())
 visits={x['id']:x for x in routing['visits']};visited=[]
 for vehicle in routing['vehicles']:
  route=routing['witness_routes'][vehicle['id']];visited+=route
  assert sum(visits[x]['demand'] for x in route)<=vehicle['capacity']
  points=[routing['depot']]+[visits[x]['point'] for x in route]+[routing['depot']]
  assert sum(math.dist(a,b) for a,b in zip(points,points[1:]))>0
 assert sorted(visited)==sorted(visits)
 print(json.dumps({'status':'PASS','copied_source_files':len(m['files']),'source_hashes_verified':True,'local_project_links_verified':True,'legacy_greedy_counterexample_reproduced':True,'synthetic_routing_witness_verified':True,'product_build_or_trial_verified':False},ensure_ascii=False))


if __name__ == '__main__': main()
