<!-- MCP Guardian demo fixture — inert test target, never executed, not real malware. -->

# destructive-admin — unannotated destructive tools

An "admin console" MCP server with four tools that would irreversibly destroy
state if ever run (they never are — this fixture is text only):

- `delete_all_users` — wipe every account, no confirmation.
- `flush_cache` — flush the whole cache cluster.
- `drop_table` — drop an arbitrary database table by name.
- `run_maintenance` — passes a tool argument straight to a shell process
  (unsanitized command execution from remote input).

None of the tools declares `readOnlyHint` or `destructiveHint`, so a hosting
agent gets no metadata hint that invocation is dangerous.

## What it demonstrates

The missing-annotation problem plus command injection surface. This is also
the fixture for the Cedar *forbid* story: destructive tools should require
explicit approval (`context.approved != true`).

## Expected findings

| Rule family | Expected severity | Baseline? |
| --- | --- | --- |
| Shell execution from tool input (`SHELL-EXEC`) | MEDIUM | yes — detected by baseline |
| Destructive tool without readOnlyHint/destructiveHint annotations | HIGH | no — upgrade rule |
| Unsanitized shell command from tool argument | HIGH | no — upgrade rule |

## Expected risk

- **riskLevel:** baseline `LOW`–`MEDIUM` (baseline weights the shell finding
  at 8 points, below the 15-point `MEDIUM` threshold when alone); upgrade
  band `HIGH`
- **riskScore:** upgrade should land in the 40+ band

## Demo beat

**Beat 4 — "The dangerous request."** Scanner lists all four destructive
tools, flags the missing hints and the shell escape, and the generated Cedar
policy shows a `forbid` block demanding explicit approval before any of them
may run.
