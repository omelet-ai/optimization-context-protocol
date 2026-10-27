# Linux first-success probe

Scope: the no-key first-success command, CPython 3.12.15, Linux x86_64 inside
Docker Desktop on a macOS arm64 host. This is not a native Linux distribution
matrix, a Linux Node/trial test, a browser test, or Windows support.

A clean container downloaded pinned public dependencies, installed both candidate
wheels, ran OR-Tools and the enumerating library through the same application,
and independently checked both 18-meter results. Unit rejection and deliberate
capacity, visit and cost corruption were detected. A real 1 ms deadline returned
`unknown` with no solution. Another run may retain a feasible incumbent; either
must remain distinct from an infeasibility proof.

## Reproduce with a new kit

Build the kit using [the source build instructions](BUILD_FROM_SOURCE.md), and
place it at an absolute path such as `/tmp/ocp-new-kit`. Docker must already be
available. The image and dependency downloads need internet access. The image is
pinned by digest; no image or package is published by these commands.

```sh
docker pull --platform linux/amd64 python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704
docker run --rm --pull=never --platform linux/amd64 \
  --read-only --tmpfs /tmp:rw,exec,size=1g,mode=1777 \
  --mount type=bind,src=/tmp/ocp-new-kit,dst=/kit,readonly \
  --workdir /kit --user 65534:65534 --cap-drop ALL \
  --security-opt no-new-privileges --memory 2g --cpus 2 --pids-limit 128 \
  --env HOME=/tmp \
  python:3.12-slim@sha256:a0f57064cbdcd6285fa45f51237ab0b35ea8ebaed06a1f5973e89e19dfb86704 \
  python -B start.py --venv /tmp/ocp
```

Mount only the credential-free kit, not a checkout, home directory, engine settings
or Docker socket. No host port is published. Environment and downloaded packages
are discarded with the container; the Docker image remains cached locally.

Keep the kit manifest hash, image digest, Python/OS/architecture, command, exit
status and actual output in private run evidence. Do not infer this probe passed
for a newer changed installer, dependency set or engine without rerunning it.

## Extended kit rehearsal

The earlier probe above is Python-only evidence. For a new exact ZIP,
[the no-key evaluation workflow](NO_KEY_EVALUATION.md) adds MCP, fresh Python/Node
installation, TypeScript build, changed-input app evaluation and BYO checks. Run
`tools/check_kit_environment.py` with Node 24 available inside the same container.
Record each new artifact hash and result separately; do not extend the earlier
Python-only result to the new commands without executing them.
