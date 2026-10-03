<!-- MCP Guardian demo fixture — inert test target, never executed, not real malware. -->

# credential-harvester — code-level dangers

A "math sandbox" MCP server with three independent red flags in plain sight:

1. **`run_expression`** — pipes user-supplied strings straight into dynamic
   evaluation (the classic `eval` sink) with zero sandboxing.
2. **`dump_env`** — returns the full process environment map
   (`dict(os.environ)`), a secret-harvesting primitive.
3. **Hardcoded demo credentials** at module scope: `AKIAIOSFODNN7EXAMPLE` and
   its companion secret — the canonical AWS *documentation example* keys,
   chosen precisely so they are obviously fake and never a real account.
   `show_support_bundle` echoes the fake key.

## What it demonstrates

Dangers that live in code, not descriptions. The baseline analyzer already
flags the dynamic-evaluation sink; the upgraded rule set adds environment
harvesting and hardcoded secrets.

## Expected findings

| Rule family | Expected severity | Baseline? |
| --- | --- | --- |
| Dynamic evaluation of user input (`EVAL-USE`) | HIGH | yes — detected by baseline |
| Environment-variable harvesting (`dict(os.environ)`) | HIGH–CRITICAL | no — upgrade rule |
| Hardcoded secret (`AKIA...`) | HIGH–CRITICAL | no — upgrade rule |

## Expected risk

- **riskLevel:** baseline `MEDIUM` (one high-severity EVAL-USE finding = 18
  points, below the 40-point HIGH threshold); upgrade band `HIGH`–`CRITICAL`
  (observed during integration: `HIGH`, score 66)
- **riskScore:** 40+ after upgrade

## Demo beat

**Beat 3 — "Read the code."** Scanner surfaces the eval sink, the env dump,
and the fake AWS key; narrator explains why a math tool needs the
environment at all.
