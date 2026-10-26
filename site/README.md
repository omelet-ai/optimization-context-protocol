# OCP website — local review candidate

A static, English-first site with a Korean introduction, three starting paths,
worked examples, installation commands, application guidance, and protocol reference.
No remote service or frontend framework is required to serve it.

The site is a local candidate for a future public website. Building does not
publish, issue keys, change repository visibility, or grant distribution rights.

## Build and preview

Use the environment and reviewed dependency caches in the [local runtime guide](../docs/development/LOCAL_RUNTIME.md).
The build executes a real installed OR-Tools reference and its independent checker.
It fails if the sample cannot be calculated or checked. It also builds the same
selected-source developer kit used by the existing onboarding checks.

```sh
OCP_NPM_CACHE=/path/to/reviewed/npm-cache OCP_NPM_OFFLINE=1 python3.12 -B tools/build_site.py --output .harness/work/site-preview
python3.12 -B -m http.server 8777 --bind 127.0.0.1 --directory .harness/work/site-preview
```

Open `http://127.0.0.1:8777/`. Use a new empty output directory for each build;
existing output, symlinks, and writes into source directories are rejected.
`site-manifest.json` records emitted-file, source, and developer-kit hashes.
Generated output stays out of Git. Stop the preview server after review.

## Sources and checks

- `content.py`: English pages and Korean introduction; rendered without a CMS.
- `commands.json`: canonical CLI blocks used both by the site and executable tests.
- `example.py`: actual installed SDK/reference/checker calculation on the canonical synthetic fixture.
- `templates/`, `assets/`: semantic HTML, responsive CSS, menu, copy, and accessible example tabs.
- [Site builder](../tools/build_site.py): explicit source/output selection; no remote publishing behavior.
- [H21 checker](../tools/check_h21.py): links, hashes, selected files, installed examples, independent checker, Node client, input rejection, and closed-session diagnostics.

```sh
OCP_NPM_CACHE=/path/to/reviewed/npm-cache OCP_NPM_OFFLINE=1 python3.12 -B tools/check_h21.py
```

H21 is a local technical gate after H20/H11. Its commands use reviewed public
dependency caches with a fresh environment; they do not test remote package
registry availability. Browser rendering and interaction review must be recorded
separately against the exact site manifest. The checker retains that tested site
under `.harness/work/site-reviewed/` and reports its path and manifest hash, so
browser review can use the very same downloaded-and-installed artifact.
Neither test is external-human acceptance.

For browser review, inspect desktop, tablet, and mobile widths; check navigation,
keyboard focus, the collapsed menu, code copying, both example states, stage tabs,
Korean text, downloadable files, console errors, and horizontal overflow. The
example explicitly displays precomputed real results rather than pretending to
run an engine in the browser. Preserve any blocked interaction checks as blocked.

## Publication boundary

The generated review edition has `noindex`, a disallow-all robots file, no analytics,
no forms, and no third-party fonts or scripts. Its artifact is marked local-review-only.
Trial access is described as pending; no inactive URL or credential is embedded.

Before publishing, approve the exact destination and artifact, settle the rights
and license scope, and provide a real access/support path. Only then update the
review-edition text, canonical origin, indexing/sitemap settings, public repository
or download links, and any approved trial enrollment. Rebuild, recheck, and verify
the published URLs. A domain purchase, hosting change, public source release,
registry upload, and live trial each require the corresponding scoped approval.
