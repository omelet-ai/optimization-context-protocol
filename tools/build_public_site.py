"""Build documentation-only public pages; never publish or include package assets.

The existing review builder supplies the real synthetic illustration. Its kit,
manifests and execution evidence stay in temporary local storage. This builder
copies an explicit static-file selection and obtains CLI blocks from README.
"""
import argparse
import hashlib
from html import escape
import importlib.util
import json
from pathlib import Path
import re
import shutil
from string import Template
import tempfile
from urllib.parse import urlsplit

from build_site import ROOT, CONTRACTS, SCHEMAS, build as build_review, source

REPO = "https://github.com/omelet-ai/optimization-context-protocol"
ASSETS = ("site.css", "site.js", "mark.svg", "example.json", "basic-input.json")


def document_commands(path, marker):
    matches = re.findall(r"<!-- ocp:" + re.escape(marker) + r" -->\s*```sh\n(.*?)\n```", source(path).read_text(), re.S)
    if len(matches) != 1:
        raise ValueError("Command marker missing or ambiguous: " + marker)
    return matches[0]


def readme_commands(marker):
    return document_commands("README.md", marker)


def canonical_base(value):
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
            parsed.password or parsed.query or parsed.fragment or parsed.port or
            not re.fullmatch(r"[a-z0-9.-]+", parsed.hostname) or
            not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)*/?", parsed.path)):
        raise ValueError("Use an HTTPS base URL without credentials, query or fragment")
    return value.rstrip("/") + "/"


def build(output, base_url):
    base = canonical_base(base_url)
    target = Path(output).absolute()
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise ValueError("Symlink output is not allowed")
    target = target.resolve()
    if target == ROOT or (target.is_relative_to(ROOT) and not target.is_relative_to(ROOT / ".harness/work")):
        raise ValueError("Use .harness/work or a new directory outside the checkout")
    target.mkdir(parents=True, exist_ok=True)
    if list(target.iterdir()):
        raise ValueError("Website output must be empty")
    with tempfile.TemporaryDirectory(prefix="ocp-public-site-") as scratch:
        review = Path(scratch).resolve() / "review"
        build_review(review)
        module_spec = importlib.util.spec_from_file_location("public_site_content", source("site/content.py"))
        content = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(content)
        pages = content.public_pages(json.loads(source("site/commands.json").read_text()),
                                     json.loads((review / "assets/example.json").read_text()),
                                     {**{key: readme_commands(key) for key in ("readme-build", "readme-examples", "readme-mcp")},
                                      "worker-analysis": document_commands("docs/users/WORKER_ANALYSIS.md", "worker-analysis")})
        template_text = source("site/templates/page.html").read_text().replace(
            '<meta name="robots" content="noindex, nofollow">', '$publication_meta').replace(
            'Local review edition. Public distribution is pending.', 'Open-source developer preview · Apache-2.0')
        template = Template(template_text)
        for name, page in pages.items():
            prefix = ("../" * name.count("/")).rstrip("/") or "."
            nav = ''.join(f'<a href="{prefix}/{path}"' + (' aria-current="page"' if path == name else '') + f'>{label}</a>' for path, label in (("start/index.html", "Get started"), ("examples/index.html", "Examples"), ("guides/apps/index.html#mcp", "AI agents"), ("reference/index.html", "Docs"), ("ko/index.html", "한국어 소개")))
            nav += f'<a class="nav-cta" href="{REPO}">GitHub ↗</a>'
            canonical = base + ("" if name == "index.html" else name.removesuffix("index.html"))
            meta = f'<meta name="robots" content="index, follow"><link rel="canonical" href="{canonical}"><meta property="og:url" content="{canonical}">'
            path = target / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(template.substitute(lang=page["lang"], title=escape(page["title"]), description=escape(page["description"], quote=True), root=prefix, nav=nav, body=page["body"], skip="본문으로 바로가기" if page["lang"] == "ko" else "Skip to content", publication_meta=meta))
        for name in ASSETS:
            (target / "assets").mkdir(exist_ok=True)
            shutil.copyfile(review / "assets" / name, target / "assets" / name)
        for name in list(CONTRACTS.values()) + ["schemas/" + n for n in SCHEMAS]:
            destination = target / "contracts" / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(review / "contracts" / name, destination)
    for name in ("LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md"):
        shutil.copyfile(source(name), target / (name.removesuffix(".md") + ".txt"))
    # Absolute base paths keep assets and navigation valid at arbitrary 404 URLs.
    (target / "404.html").write_text(template.substitute(lang="en", title="Page not found", description="Return to the OCP documentation.", root=base.rstrip("/"), nav=f'<a href="{base}">OCP home</a>', body=f'<section class="wrap section"><h1>Page not found</h1><p><a href="{base}">Return to OCP</a></p></section>', skip="Skip to content", publication_meta='<meta name="robots" content="noindex">'))
    (target / "robots.txt").write_text("User-agent: *\nAllow: /\nSitemap: " + base + "sitemap.xml\n")
    urls = [base + ("" if p == "index.html" else p.removesuffix("index.html")) for p in pages]
    (target / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + ''.join('<url><loc>' + escape(u) + '</loc></url>' for u in urls) + '</urlset>\n')
    (target / ".nojekyll").touch()
    files = {p.relative_to(target).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(target.rglob("*")) if p.is_file()}
    # Returned proof is for private records, not copied into the deployed output.
    return {"directory": str(target), "base_url": base, "pages": len(pages), "files": files,
            "packages_included": False, "trial_service_included": False, "deployed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output, args.base_url)))
