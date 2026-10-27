# OCP website

A static, English-first site with a Korean introduction, three starting paths,
worked examples, installation commands, application guidance, and protocol reference.
No remote service or frontend framework is required to serve it.

The public documentation is hosted at
[GitHub Pages](https://omelet-ai.github.io/optimization-context-protocol/).
The two builders below produce local artifacts; neither deploys, issues keys,
changes repository visibility, or publishes packages. The review builder retains
its kit download for local testing. The public builder emits documentation only.

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

- `content.py`: English pages and Korean introduction, including `public_pages` for the public edition. Shared route labels, scope tables and agent guidance live here rather than in the build tool.
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

H21 records bounded error categories for individual checks and class setup/cleanup
failures (reserved diagnostic number `10000`). It cleans up its temporary server,
provider, and install directory even if preparation fails. A later passing run
does not erase earlier failure evidence or establish its cause.

The build runs the real example once in a newly installed environment. Native
engine startup has a 60-second bound; after the engine reports readiness, the
example has a separate 30-second process bound. Its solve budget stays at 1,000 ms.
This accommodates variable first-load library validation on macOS without warming
the engine or retrying a failed example. Readiness alone is never a successful
example: exit status, real result, evaluation, and independent verification still
have to pass. Timeouts retain only the fixed `site_engine_startup` or
`site_example_execution` phase and numeric limit in harness diagnostics.

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

## Documentation-only public build

```sh
python3.12 -B tools/build_public_site.py --output .harness/work/public-site-new --base-url https://omelet-ai.github.io/optimization-context-protocol/
python3.12 -B tools/check_public_site.py --directory .harness/work/public-site-new --base-url https://omelet-ai.github.io/optimization-context-protocol/
```

The public builder takes install/MCP commands from README, includes the synthetic
worked examples and license notices, and excludes kits, manifests and private
evidence. Check the exact output before any separately authorized deployment.
The source approval inventory does not grant new deployment authority.

The public homepage links directly to local setup and AI agent setup. Omelet
remains the recommended first experience **when invited**; public signup is not
open. Profile limits describe current contracts, with narrower engine limits
identified separately. `example.py` executes routing, worker and inventory
engines in a fresh installed environment, independently checks each result and
emits their saved inputs/results/evaluations. No browser control invokes a solver.
Agent conversation steps are illustrative guidance, not model acceptance evidence.

Keep README command blocks and the referenced source revision available together
when publishing a future update. A local preview may include source changes that
have not yet reached public `main`; building it does not publish those changes.

The public edition distinguishes the available Core 0.1 quickstart from the
local, unpublished native v1 candidate at each entry point. The protocol page
renders the marked `core-native-table` directly from README; keep its three-column
Markdown format. Artifact checks compare every rendered cell with README, retain
the existing Core command blocks, and check the separate native job/MCP guidance.
Native implementation, extracted contracts and review bundles are not included
by documenting them. Do not link to unpublished repository files or packages.
