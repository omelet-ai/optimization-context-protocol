"""Website artifact and exact documented CLI journeys; browser review is separate."""
from copy import deepcopy
from functools import partial
import hashlib
from html.parser import HTMLParser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
import uuid
from urllib.parse import unquote, urlsplit
from urllib.request import urlopen
import zipfile

from build_site import build
from build_typescript import NODE
from isolated_candidate import clean_env

ROOT=Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self,text):
        super().__init__();self.ids=[];self.links=[];self.tags=[];self.commands={};self.current=None;self.feed(text)
    def handle_starttag(self,tag,attrs):
        a=dict(attrs);self.tags.append((tag,a))
        if 'id' in a:self.ids.append(a['id'])
        for key in ('href','src'):
            if key in a:self.links.append(a[key])
        if tag=='code' and 'data-command' in a:self.current=a['data-command'];self.commands[self.current]=''
    def handle_endtag(self,tag):
        if tag=='code':self.current=None
    def handle_data(self,data):
        if self.current:self.commands[self.current]+=data


class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass


class SiteJourney(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='ocp-site-test-')
        cls.work=Path(cls.temp.name).resolve();cls.output=cls.work/'site'
        cls.built=build(cls.output)
        cls.manifest=json.loads((cls.output/'site-manifest.json').read_text())
        cls.pages={name:Page((cls.output/name).read_text()) for name in cls.manifest['pages']}
        cls.commands=json.loads((ROOT/'site/commands.json').read_text())
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(cls.output)))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url='http://127.0.0.1:'+str(cls.server.server_port)
        cls.download=cls.work/'fresh folder with spaces';cls.download.mkdir()
        archive=cls.download/'ocp-developer-kit.zip'
        with urlopen(cls.url+'/downloads/ocp-developer-kit.zip',timeout=10) as r:archive.write_bytes(r.read())
        if hashlib.sha256(archive.read_bytes()).hexdigest()!=cls.manifest['kit_sha256']:raise RuntimeError('Download changed')
        cls.home=cls.work/'fresh-home';cls.home.mkdir();cls.env=clean_env(cls.home)
        binaries=cls.work/'bin';binaries.mkdir();(binaries/'python3.12').symlink_to(Path(sys._base_executable).resolve())
        cls.env['PATH']=str(binaries)+os.pathsep+str(NODE.parent)+os.pathsep+os.defpath
        wheelhouse=ROOT/'.harness/work/wheels'
        reviewed=json.loads((ROOT/'tools/dependency-wheels.json').read_text())['sha256']
        for name,h in reviewed.items():
            if hashlib.sha256((wheelhouse/name).read_bytes()).hexdigest()!=h:raise RuntimeError('Dependency wheel changed')
        cls.env.update(PIP_NO_INDEX='1',PIP_FIND_LINKS=str(wheelhouse),PIP_NO_CACHE_DIR='1',npm_config_offline='true',npm_config_cache=os.environ['OCP_NPM_CACHE'])
        current=cls.download
        for line in cls.commands['unpack']['code'].splitlines():
            argv=shlex.split(line)
            if argv[0]=='cd':current=current/argv[1]
            else:
                r=subprocess.run(argv,cwd=current,env=cls.env,capture_output=True,text=True,timeout=30)
                if r.returncode:raise RuntimeError('Documented unpack failed')
        cls.kit=current
        cls.run_block('local-install')
        cls.run_block('byo-install')
        cls.runtime=None

    @classmethod
    def run_block(cls,key,expected=0):
        outputs=[]
        for line in cls.commands[key]['code'].splitlines():
            r=subprocess.run(shlex.split(line),cwd=cls.kit,env=cls.env,capture_output=True,text=True,timeout=90)
            if r.returncode!=expected:raise AssertionError(key+': '+r.stderr[-2500:]+r.stdout[-1000:])
            outputs.append(r)
        return outputs[-1]

    @classmethod
    def tearDownClass(cls):
        if cls.runtime:
            cls.runtime.terminate()
            try:cls.runtime.wait(timeout=10)
            except subprocess.TimeoutExpired:cls.runtime.kill();cls.runtime.wait()
        cls.server.shutdown();cls.server.server_close();cls.thread.join()
        # Retain the exact downloaded-and-installed site for separate browser review.
        # This is private harness output, never a source or publication selection.
        cls.review=ROOT/'.harness/work/site-reviewed'/uuid.uuid4().hex
        shutil.copytree(cls.output,cls.review)
        cls.temp.cleanup()

    def test_01_page_metadata_and_landmarks(self):
        self.assertEqual(len(self.pages),10)
        for name,page in self.pages.items():
            with urlopen(self.url+'/'+name,timeout=10) as r:self.assertEqual(r.status,200)
            self.assertEqual(len(page.ids),len(set(page.ids)),name)
            self.assertEqual(sum(tag=='h1' for tag,_ in page.tags),1,name)
            self.assertEqual(sum(tag=='main' for tag,_ in page.tags),1,name)
            self.assertIn(('html',{'lang':'ko' if name.startswith('ko/') else 'en'}),page.tags)
            self.assertTrue(any(t=='meta' and a.get('name')=='description' and a.get('content') for t,a in page.tags))

    def test_02_all_local_links_assets_and_fragments(self):
        for name,page in self.pages.items():
            for link in page.links:
                parsed=urlsplit(link)
                if parsed.scheme:
                    self.assertEqual(parsed.scheme,'https');continue
                path=(self.output/name).parent/unquote(parsed.path) if parsed.path else self.output/name
                path=path.resolve()
                self.assertTrue(path.is_relative_to(self.output));self.assertTrue(path.is_file(),(name,link))
                if parsed.fragment and path.suffix=='.html':self.assertIn(parsed.fragment,Page(path.read_text()).ids)

    def test_03_documented_commands_are_canonical(self):
        observed={}
        for page in self.pages.values():
            for key,value in page.commands.items():
                self.assertEqual(value,self.commands[key]['code']);observed[key]=value
        self.assertEqual(set(observed),set(self.commands))

    def test_04_explicit_output_inventory_and_kit_hashes(self):
        self.assertEqual({p.relative_to(self.output).as_posix() for p in self.output.rglob('*') if p.is_file()},set(self.manifest['files'])|{'site-manifest.json'})
        for name,h in self.manifest['files'].items():self.assertEqual(hashlib.sha256((self.output/name).read_bytes()).hexdigest(),h)
        manifest=json.loads((self.kit/'manifest.json').read_text())
        self.assertFalse(manifest['distribution_authorized']);self.assertFalse(self.manifest['publication_authorized'])
        for name,h in manifest['files'].items():self.assertEqual(hashlib.sha256((self.kit/name).read_bytes()).hexdigest(),h)

    def test_05_no_credentials_private_paths_or_external_scripts(self):
        patterns=[rb'ocp_trial_[A-Za-z0-9_-]{43}',rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'/Users/'+b'omeletjk/',rb'https://[^\s"<>]+\.trycloudflare\.com']
        kit_files=json.loads((self.kit/'manifest.json').read_text())['files']
        for path in list(self.output.rglob('*'))+[self.kit/name for name in kit_files]:
            if not path.is_file():continue
            self.assertNotIn(path.name,('.env','session.json'))
            if path.suffix not in ('.zip','.whl','.tgz'):
                data=path.read_bytes()
                for pattern in patterns:self.assertIsNone(re.search(pattern,data),path.name)
        for page in self.pages.values():
            for tag,attrs in page.tags:
                self.assertNotIn(tag,('form','iframe'))
                if tag=='script' and 'src' in attrs:self.assertFalse(urlsplit(attrs['src']).scheme)

    def test_06_saved_example_is_real_and_explicit(self):
        demo=json.loads((self.output/'assets/example.json').read_text())
        self.assertEqual(demo['routing']['result']['provenance']['engine']['id'],'ortools.routing')
        self.assertEqual(demo['routing']['result']['status'],'feasible')
        self.assertEqual(demo['routing']['independent_check']['total_cost'],18)
        self.assertEqual(demo['rejected']['result']['kind'],'failure')
        self.assertIsNone(demo['rejected']['evaluation'])
        self.assertIn('Precomputed at site build',(self.output/'examples/index.html').read_text())

    def test_07_exact_local_run_from_download(self):
        value=json.loads(self.run_block('local-run').stdout)
        self.assertEqual(value['result']['kind'],'result')
        self.assertEqual(value['independent_check']['total_cost'],18)
        self.assertEqual(value['evaluation']['kind'],'evaluation')

    def test_08_exact_byo_and_independent_checker(self):
        installed=subprocess.run([str(self.kit/'.byo/bin/python'),'-m','pip','list','--format=json'],cwd=self.kit,env=self.env,capture_output=True,text=True,timeout=15)
        self.assertNotIn('ortools',{p['name'] for p in json.loads(installed.stdout)})
        value=json.loads(self.run_block('byo-run').stdout)
        self.assertEqual(value['status'],'PASS')

    def test_09_exact_python_app_and_new_input(self):
        value=json.loads(self.run_block('python-app').stdout);self.assertTrue(value['independent_check']['feasible'])
        data=json.loads((self.kit/'basic-input.json').read_text());data['visits'][0]['demand']=2
        for v in data['vehicles']:v['capacity']=3
        (self.kit/'my-input.json').write_text(json.dumps(data))
        r=subprocess.run([str(self.kit/'.local/bin/python'),'-B','own_app.py','--input','my-input.json','--request-id','my-own-problem','--trace','my-own.json'],cwd=self.kit,env=self.env,capture_output=True,text=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(json.loads(r.stdout)['independent_check']['feasible'])

    def test_10_exact_typescript_build_and_http_client(self):
        self.run_block('ts-install')
        # Use the documented fixed port; never stop an unrelated listener.
        self.__class__.runtime=subprocess.Popen(shlex.split(self.commands['http-provider']['code']),cwd=self.kit,env=self.env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        import time
        for _ in range(100):
            if self.runtime.poll() is not None:raise AssertionError('Reference port is unavailable; provider could not start')
            try:
                with urlopen('http://127.0.0.1:8765/v1/capability',timeout=.2) as response:
                    self.assertEqual(json.loads(response.read())['kind'],'capability');break
            except OSError:time.sleep(.05)
        else:raise AssertionError('Reference did not become ready')
        value=json.loads(self.run_block('ts-run').stdout)
        self.assertEqual(value['kind'],'result');self.assertEqual(value['status'],'feasible')

    def test_11_trial_install_and_closed_session_diagnostics(self):
        # Exact installer; no invitation is invented and no external provider is called.
        lines=self.commands['trial-install']['code'].splitlines()
        for line in lines[:2]:
            r=subprocess.run(shlex.split(line),cwd=self.kit,env=self.env,capture_output=True,text=True,timeout=90)
            self.assertEqual(r.returncode,0,r.stderr)
        r=subprocess.run(shlex.split(lines[-1]),cwd=self.kit,env=self.env,capture_output=True,text=True,timeout=20)
        self.assertNotEqual(r.returncode,0)
        self.assertEqual(json.loads(r.stderr)['code'],'INVITATION_NOT_FOUND')
        text=(self.output/'start/omelet/index.html').read_text()
        self.assertIn('no active public endpoint',text)
        self.assertIn('public signup', (self.output/'start/omelet/index.html').read_text().replace('self-service signup','public signup'))

    def test_12_overwrite_and_source_output_guards(self):
        with self.assertRaises(ValueError):build(self.output)
        with self.assertRaises(ValueError):build(ROOT/'site')
        link=self.work/'linked';link.symlink_to(self.output)
        with self.assertRaises(ValueError):build(link)
        self.assertEqual(hashlib.sha256((self.output/'site-manifest.json').read_bytes()).hexdigest(),self.built['manifest_sha256'])

    def test_13_rejected_input_preserves_failure(self):
        value=json.loads((self.kit/'basic-input.json').read_text());value['visits'][0]['time_window']=[0,100]
        (self.kit/'unsupported.json').write_text(json.dumps(value))
        r=subprocess.run([str(self.kit/'.local/bin/python'),'-B','own_app.py','--input','unsupported.json','--request-id','unsupported'],cwd=self.kit,env=self.env,capture_output=True,text=True,timeout=20)
        self.assertNotEqual(r.returncode,0);self.assertFalse(json.loads(r.stdout)['valid'])


if __name__=='__main__':
    result=unittest.TextTestRunner().run(unittest.defaultTestLoader.loadTestsFromTestCase(SiteJourney))
    passed=result.wasSuccessful() and result.testsRun>=13 and not result.skipped
    print(json.dumps({'status':'PASS' if passed else 'FAIL','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'site_manifest_sha256':getattr(SiteJourney,'built',{}).get('manifest_sha256'),
        'review_directory':str(getattr(SiteJourney,'review','')),
        'scope':'Static site selection, downloaded artifact, exact documented offline installs, real reference/BYO/Python/Node execution; browser review separate; no external trial or publication'}))
    sys.exit(0 if passed else 1)
