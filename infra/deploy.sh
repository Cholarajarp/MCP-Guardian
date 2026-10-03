#!/usr/bin/env bash
# MCP Guardian — one-command backend deploy to AWS via AWS SAM.
#   ./infra/deploy.sh            (or: bash infra/deploy.sh, or: make sam-deploy)
# Requires: AWS SAM CLI, AWS credentials (env/SSO/profile), and either
#   - Docker running  -> we build inside the amazon/python3.12 image, or
#   - a local Python 3.12 executable (python3.12 on PATH / py -3.12).
# Full walkthrough: docs/deploy.md
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT_DIR"

# --- preflight ---------------------------------------------------------------
for cmd in sam aws; do
  command -v "$cmd" >/dev/null 2>&1 || {
    echo "ERROR: '$cmd' CLI not found on PATH." >&2
    echo "       SAM install guide: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html" >&2
    exit 1
  }
done

BUILD_ARGS=(--template "infra/template.yaml")
if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  echo "==> Docker detected: building inside the Lambda python3.12 image."
  BUILD_ARGS+=(--use-container)
else
  echo "==> Docker not available: building on the host (needs a local python3.12)." >&2
  echo "    Tip: install Python 3.12 and put 'python3.12' on PATH, or install Docker and re-run." >&2
fi

CONFIG_ARGS=()
if [[ -f "$SCRIPT_DIR/samconfig.toml" ]]; then
  echo "==> Using config: infra/samconfig.toml"
  CONFIG_ARGS+=(--config-file "$SCRIPT_DIR/samconfig.toml" --config-env default)
else
  echo "==> infra/samconfig.toml not found — starting from infra/samconfig.toml.example defaults." >&2
  echo "    Copy it (cp infra/samconfig.toml.example infra/samconfig.toml) to skip prompts." >&2
fi

# --- build + deploy ----------------------------------------------------------
echo "==> sam build"
sam build "${BUILD_ARGS[@]}" "${CONFIG_ARGS[@]}"

echo "==> sam deploy (--guided prompts the first time; defaults come from infra/samconfig.toml)"
sam deploy --template .aws-sam/build/template.yaml --guided "${CONFIG_ARGS[@]}"

# --- post-deploy -------------------------------------------------------------
STACK_NAME="$(sed -n 's/^stack_name *= *\"\([^\"]*\)\".*/\1/p' "$SCRIPT_DIR/samconfig.toml" 2>/dev/null || true)"
STACK_NAME="${STACK_NAME:-mcp-guardian}"
echo "==> Stack outputs (use ApiUrl as NEXT_PUBLIC_API_URL for the frontend):"
aws cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query "Stacks[0].Outputs" \
  --output table 2>/dev/null || \
  echo "    (could not describe stack '$STACK_NAME' — check the sam deploy output above)"

echo "==> Done. Next: host the frontend and set NEXT_PUBLIC_API_URL=<ApiUrl> (docs/deploy.md)."
echo "==> Teardown later: sam delete --config-file infra/samconfig.toml"
