# How the Decision Engine got here

The engine in `decision-engine/` is the last of nine iterations written over
the course of the trial. Each one existed because the previous one hit
something real on the testbed. The intermediate versions are not published —
they were near-copies of each other, and several carried testbed credentials in
source — but the sequence is worth recording, because it is a fair picture of
how the mechanism was actually found.

| Step | What it added | Why |
|---|---|---|
| 1 | A Flask server accepting the core's event POSTs, logging them | First question: does the core actually tell us about handovers, and in what shape? |
| 2 | The gNB-to-edge topology table, exposed on `/telco_infra` | Needed something to map a gNB onto before there was anywhere to send the decision |
| 3 | Orchestrator authentication and the service lookup | The engine became a northbound client; now it could see where the workload was |
| 4 | Migration: rewriting the site label and `PUT`ting it back | The first end-to-end handover-to-migration |
| 5 | Migration timing, and token refresh on a timer | Sessions expired mid-trial. Timing became the thing the paper needed to report |
| 6 | Filtering by SUPI from the environment | The core reports every subscriber; only the vehicle mattered |
| 7 | `REDIS_HOST` rewritten alongside the site label | The migrated pod came up pointing at the previous edge's state |
| 8 | Refresh driven by 401 instead of a timer | Simpler and correct: let the orchestrator say when the token is stale |
| 9 | Handover counting on `/handover_count`, threaded event handling | Needed a handover count to compare against migrations; the POST handler was blocking while a migration ran |

Steps 7 and 8 are the two worth keeping. Step 7 is the difference between a
migration that works and one that silently serves stale state — a moving
workload has to take its state endpoint with it. Step 8 replaced a guess about
session lifetime with the signal the server was already sending.

## What changed on the way into this repository

The published version is step 9 with the testbed pulled out of it:

- Credentials, endpoints, the org identifier and the observed SUPI moved from
  literals in the source to environment variables, with no defaults for the
  secrets — the engine refuses to start rather than falling back to something
  wrong.
- The topology table moved from a dict in the source to a YAML file, validated
  on load, mounted from a ConfigMap by the chart.
- gNB IDs are compared as strings, because cores differ on whether they send
  them as JSON numbers or strings.
- The status poll gained a timeout. Previously a service that never reached
  the in-sync state would have spun forever.
- HTTP calls gained timeouts.
