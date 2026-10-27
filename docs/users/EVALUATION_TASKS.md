# OCP independent developer evaluation

Prepared private candidate; the organizer must authorize delivery of this exact
kit before inviting participants. No public release or license grant is implied.
This is a no-key study. No trial session, production data or remote engine is needed.

Use an anonymous participant ID supplied by the organizer. Record your OS, CPU,
Python/Node versions, ZIP SHA-256 and `source_tree_sha256` from source-manifest.json
in a new copy of FEEDBACK_TEMPLATE.md. Start from an extracted, unmodified kit and
a fresh environment. Verify the ZIP hash supplied by the organizer before running it.
Use README.md, DEVELOPER_GUIDE.md and LLM_QUICKSTART.md; avoid verbal setup coaching
until you record the first point where you are blocked. Asking for help is useful
evidence, not a failed participant. Record every hint, retry and waiting period.

1. **First result (15-minute target).** From README, install and run the local
   example. Explain whether the returned solution is feasible or proven optimal,
   its checked cost and what the checker actually covers. Record elapsed time and
   all setup/dependency errors. Do not edit the kit manifest to bypass a failure.
2. **Your input.** Save a new synthetic input. Change demands or capacities and
   double the entire distance matrix. Run it and explain the changed cost. Try an
   unsupported unit in another new file; show that validation rejects it. Do not
   invent a conversion to fit the example.
3. **Your app (60-minute target).** Choose Python or Node. Build a small new entry
   point that discovers, validates, executes and evaluates your changed input.
   Explain failure, unknown and null handling. Record any copied boilerplate and
   hints. Running the supplied app unchanged is a rehearsal, not this task's pass.
4. **Your engine (separate 60-minute target).** Replace the teaching solver in a
   new file using your own small calculation. Advertise/reject its limits. Run a
   valid and unsupported case, then export a transcript tied to your new artifact
   hash and run the conformance checker. Keep the first failed attempt too. Do not
   claim optimality or infeasibility without the profile's required proof.
5. **LLM connection, without a model.** Follow LLM_QUICKSTART: install with `--mcp`,
   run doctor and smoke, and generate config. Explain which operation solves and
   which operation only reads context. Do not launch a paid/model task for this
   study unless its separate host, data and usage scope has been approved.

Run `demo.py --diagnostics` and explain the capacity, missing-visit and wrong-cost
rejections and real deadline result. These are deliberately damaged synthetic
results, not evidence that your engine supports all constraints.

Return only your reviewed feedback and synthetic code/input/results through the
organizer's agreed channel. Remove names, home paths, credentials, private URLs,
account logs and customer data. Do not upload automatically. Record inability to
finish honestly; no fabricated participant success. Automated rehearsals, human
no-key trials and hosted Omelet trials are separate cohorts. The formal release
gate still requires its own rights, environment and actual-user evidence.
