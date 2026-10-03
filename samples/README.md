<!-- MCP Guardian demo fixture — inert test target, never executed, not real malware. -->

# samples/ — MCP Guardian demo targets

Four inert fixture "MCP servers" the scanner scans live in the hackathon demo
video. Every fixture is pure Python in the FastMCP style
(`from mcp.server.fastmcp import FastMCP` + `@mcp.tool()` decorators) but is
**never executed**: the e2e tests (`backend/tests/test_samples_e2e.py`) read
the files from disk and feed them to the analyzer in paste mode, and the demo
does the same. Each folder is a self-contained scan payload
(`server.py` + `README.md`).

## Fixture index

| Fixture | What it shows | Expected risk (baseline analyzer) | Expected risk (upgraded analyzer) | Demo beat |
| --- | --- | --- | --- | --- |
| `clean-greeter/` | Honest read-only server, `readOnlyHint: true` on both tools | LOW (score 0) | LOW | **Beat 1 — the green path:** clean scan + allow-style Cedar policy |
| `prompt-injection-server/` | Injection payloads in tool descriptions + exfil POST to `https://webhook.example.com/collect` | LOW (0 findings — baseline cannot see descriptions) | CRITICAL–HIGH | **Beat 2 — the lying description:** description-level attack on the hosting LLM |
| `credential-harvester/` | Dynamic evaluation of tool input, `dict(os.environ)` dump, fake AWS key `AKIAIOSFODNN7EXAMPLE` | MEDIUM (EVAL-USE = 18 pts) | HIGH–CRITICAL | **Beat 3 — read the code:** eval sink, env harvest, hardcoded secret |
| `destructive-admin/` | `delete_all_users` / `flush_cache` / `drop_table` with no annotations, plus shell execution from a tool arg | LOW–MEDIUM (SHELL-EXEC) | HIGH | **Beat 4 — the dangerous request:** missing hints + Cedar `forbid`/approval story |

## Baseline vs upgrade

The analysis engine is being upgraded in parallel. `backend/tests/test_samples_e2e.py`
asserts the **baseline-detectable** behaviors hard (dynamic-evaluation and
shell-execution findings, risk bands they imply, clean fixture stays clean)
and treats the upgrade-only detections (prompt injection, env harvest, secrets,
missing annotations) softly: it prints the observed rule ids on every run and
only requires the scan to complete with a valid risk level, with `TODO(upgrade)`
comments marking where stricter bands land once the new rules ship.

## Safety

Every file in every fixture carries the header:
`MCP Guardian demo fixture — inert test target, never executed, not real malware.`
The malicious payloads are strings and comments only; `webhook.example.com` is
a reserved documentation domain and the AWS keys are the canonical docs
examples. Nothing here calls out to the network at scan time.
