<!-- MCP Guardian demo fixture — inert test target, never executed, not real malware. -->

# clean-greeter — the safe control group

A genuinely safe MCP server: two read-only tools (`greet`, `echo`) that never
touch the filesystem, network, shell, or secrets. Both tools declare explicit
`readOnlyHint: true` annotations.

## What it demonstrates

The *green path* of the demo: MCP Guardian scans an honest server, finds
nothing alarming, and produces an allow-style Cedar policy. This is the
baseline every risky fixture is compared against on camera.

## Expected findings

| Rule family | Expected severity |
| --- | --- |
| (none) | — |

No findings expected from either the baseline analyzer (which flags dynamic
evaluation, dynamic execution, and shell execution via regex) or the upgraded
rule set (injection-in-description, env harvesting, exfil POSTs, destructive
tools missing annotations).

## Expected risk

- **riskLevel:** `LOW`
- **riskScore:** 0–15

## Demo beat

**Beat 1 — "The green path."** Clean scan, LOW badge, Cedar policy permits
`greet` and `echo`. Establishes trust in the scanner before the scary fixtures.
