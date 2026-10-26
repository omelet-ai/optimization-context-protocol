"""Build a local-review static website from explicit source selections.

This does not grant distribution rights, create remote infrastructure, or publish.
"""
import argparse
import hashlib
from html import escape
import importlib.util
import json
from pathlib import Path
import queue
import shutil
from string import Template
import subprocess
import sys
import tempfile
import threading
import time
import zipfile

from build_invitation_kit import build as build_kit
from isolated_candidate import install

ROOT=Path(__file__).resolve().parents[1]
SOURCE_FILES=["site/content.py","site/commands.json","site/example.py","site/versioning.txt",
              "site/templates/page.html","site/assets/site.css","site/assets/site.js","site/assets/mark.svg"]
CONTRACTS={"spec/core/CORE_0_1.md":"core.txt","spec/profiles/ROUTING_BASIC_0_1.md":"routing-basic.txt",
           "spec/profiles/ROUTING_COORDINATES_0_1.md":"routing-coordinates.txt","site/versioning.txt":"versioning.txt"}
SCHEMAS=["core-0.1.schema.json","routing-input-0.1.schema.json","routing-solution-0.1.schema.json",
         "routing-configuration-0.1.schema.json","routing-coordinates-input-0.1.schema.json",
         "assignment-fixture-input-0.1.schema.json","assignment-fixture-solution-0.1.schema.json"]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def source(name):
    p=ROOT/name
    if not p.is_file() or any(q.is_symlink() for q in [p,*p.parents] if q.is_relative_to(ROOT)):
        raise ValueError("Invalid site source")
    return p


def run_example(argv, *, env, cwd, startup_timeout=60, execution_timeout=30):
    """One cold process: bound native startup separately from example execution.

    The readiness line is emitted only after ORToolsBackend finishes loading.
    It never substitutes for a zero exit and a verified example JSON result.
    """
    started=time.monotonic();phase="site_engine_startup";limit=startup_timeout
    with tempfile.TemporaryFile() as errors:
        # Unbuffered stdout prevents readline from consuming JSON bytes that
        # communicate must read after the readiness line (including fast exits).
        process=subprocess.Popen(argv,env=env,cwd=cwd,stdout=subprocess.PIPE,
                                 stderr=errors,bufsize=0)
        ready=queue.Queue(maxsize=1)
        reader=threading.Thread(target=lambda:ready.put(process.stdout.readline()),daemon=True)
        reader.start()
        try:
            try:line=ready.get(timeout=startup_timeout)
            except queue.Empty:raise subprocess.TimeoutExpired(argv,startup_timeout) from None
            if line!=b"OCP_SITE_ENGINE_READY\n":
                raise RuntimeError("Site example exited or returned invalid engine readiness")
            loaded=time.monotonic();phase="site_example_execution";limit=execution_timeout
            stdout,_=process.communicate(timeout=execution_timeout)
            errors.seek(0);stderr=errors.read().decode(errors="replace")
            timings={"startup_ms":round((loaded-started)*1000),
                     "execution_ms":round((time.monotonic()-loaded)*1000),
                     "startup_timeout_seconds":startup_timeout,"execution_timeout_seconds":execution_timeout}
            return subprocess.CompletedProcess(argv,process.returncode,stdout.decode(),stderr),timings
        except subprocess.TimeoutExpired as exc:
            # Fixed identifiers only; no argv, output, paths or arbitrary messages
            # enter the shared harness failure diagnostics.
            exc.ocp_phase=phase;exc.ocp_timeout_seconds=limit
            raise
        finally:
            if process.poll() is None:process.kill()
            process.wait();reader.join();process.stdout.close()


def build(output):
    target=Path(output).absolute()
    if any(p.is_symlink() for p in [target,*target.parents]):raise ValueError("Symlink output is not allowed")
    target=target.resolve()
    if target==ROOT or (target.is_relative_to(ROOT) and not target.is_relative_to(ROOT/".harness/work")):
        raise ValueError("Use a new directory under .harness/work or outside the checkout")
    target.mkdir(parents=True,exist_ok=True)
    if list(target.iterdir()):raise ValueError("Website output must be empty")
    for name in SOURCE_FILES+list(CONTRACTS)+["spec/schemas/"+n for n in SCHEMAS]:source(name)
    for name in ("assets","downloads","contracts/schemas"):(target/name).mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ocp-site-") as directory:
        scratch=Path(directory);kit=scratch/"kit";built=build_kit(kit)
        archive=target/"downloads/ocp-developer-kit.zip"
        with zipfile.ZipFile(archive,"w",zipfile.ZIP_DEFLATED) as z:
            for p in sorted(kit.iterdir()):z.write(p,"ocp-developer-kit/"+p.name)
        kit_hash=sha(archive)
        (target/"downloads/ocp-developer-kit.sha256").write_text(kit_hash+"  ocp-developer-kit.zip\n")
        envdir=scratch/"installed";envdir.mkdir()
        python,env=install(envdir,kit/"ocp_candidate-0.1.0-py3-none-any.whl")
        checked=subprocess.run([str(python),"-B","-m","pip","install","--no-index","--no-cache-dir","--no-compile","--find-links",str(ROOT/".harness/work/wheels"),str(kit/"ocp_conformance_candidate-0.1.0-py3-none-any.whl")],env=env,cwd=scratch,capture_output=True,text=True,timeout=60)
        if checked.returncode:raise RuntimeError("Site checker install failed")
        example,timings=run_example([str(python),"-B",str(source("site/example.py")),str(kit/"basic-input.json"),"--report-ready"],env=env,cwd=scratch)
        if example.returncode:raise RuntimeError("Site real-engine example failed: "+example.stderr[-1500:])
        demo=json.loads(example.stdout)
        shutil.copyfile(kit/"basic-input.json",target/"assets/basic-input.json")
    (target/"assets/example.json").write_text(json.dumps(demo,ensure_ascii=False,indent=2)+"\n")
    commands=json.loads(source("site/commands.json").read_text())
    module_spec=importlib.util.spec_from_file_location("ocp_site_content",source("site/content.py"))
    content=importlib.util.module_from_spec(module_spec);module_spec.loader.exec_module(content)
    template=Template(source("site/templates/page.html").read_text())
    pages=content.pages(commands,demo,kit_hash)
    for name,page in pages.items():
        prefix=("../"*name.count('/')).rstrip('/') or '.'
        nav=[]
        for path,label in [("start/index.html","Get started"),("examples/index.html","Examples"),("reference/index.html","Docs"),("ko/index.html","한국어")]:
            attrs=(' aria-current="page"' if path==name else '')+(' lang="ko"' if path.startswith('ko') else '')
            nav.append(f'<a href="{prefix}/{path}"{attrs}>{label}</a>')
        nav.append(f'<a class="nav-cta" href="{prefix}/start/local/index.html">Run locally <span aria-hidden="true">↗</span></a>')
        path=target/name;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(template.substitute(lang=page['lang'],title=escape(page['title']),description=escape(page['description'],quote=True),
                                           root=prefix,nav=''.join(nav),body=page['body'],skip='본문으로 바로가기' if page['lang']=='ko' else 'Skip to content'))
    for name in ("site.css","site.js","mark.svg"):shutil.copyfile(source("site/assets/"+name),target/"assets"/name)
    for name,dest in CONTRACTS.items():shutil.copyfile(source(name),target/"contracts"/dest)
    for name in SCHEMAS:shutil.copyfile(source("spec/schemas/"+name),target/"contracts/schemas"/name)
    (target/"robots.txt").write_text("User-agent: *\nDisallow: /\n")
    (target/"404.html").write_text(template.substitute(lang='en',title='Page not found',description='This page is not part of the OCP review site.',root='.',nav='',skip='Skip to content',body='<section class="wrap section"><p class="eyebrow">404</p><h1>That path ends here.</h1><p><a class="button" href="/index.html">Return to OCP</a></p></section>'))
    files={p.relative_to(target).as_posix():sha(p) for p in sorted(target.rglob('*')) if p.is_file()}
    manifest={"schema":"ocp-site-review/v1","audience":"local_review_only","publication_authorized":False,
              "candidate_version":"0.1.0-candidate","files":files,"pages":list(pages),"kit_sha256":kit_hash,
              "sources":{name:sha(source(name)) for name in SOURCE_FILES+list(CONTRACTS)+["spec/schemas/"+n for n in SCHEMAS]},
              "example_scope":"Real installed OR-Tools on synthetic input, independent checker; precomputed, no external trial",
              "external_calls":0}
    (target/"site-manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n")
    return {"directory":str(target),"pages":len(pages),"kit_sha256":kit_hash,"manifest_sha256":sha(target/"site-manifest.json"),"publication_authorized":False,"example_timings":timings}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    try:print(json.dumps(build(parser.parse_args().output)))
    except (ValueError,RuntimeError,OSError) as exc:print(json.dumps({"status":"FAIL","reason":str(exc)}));sys.exit(1)
