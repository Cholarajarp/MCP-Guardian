# infra/ — AWS deployment (SAM)

Backend = FastAPI on **AWS Lambda** (python3.12 + Mangum) behind **API Gateway
(REST)**, with a **Bedrock InvokeModel** policy and a **DynamoDB ScansTable**
reserved for the future store swap. Frontend hosting options (Amplify Hosting
or App Runner/EC2) are in [`docs/deploy.md`](../docs/deploy.md).

## Files

| File | Purpose |
| --- | --- |
| `template.yaml` | SAM template: `ScanFunction`, `Api` (REST, CORS), `ScansTable` |
| `lambda_handler` (in `../backend/app/lambda_handler.py`) | Mangum wrapper — FastAPI → Lambda |
| `deploy.sh` | One command: `sam build` + `sam deploy --guided` + prints stack outputs |
| `samconfig.toml.example` | Copy to `samconfig.toml` for non-interactive defaults |

## Quick start (3 commands)

```bash
cp infra/samconfig.toml.example infra/samconfig.toml   # adjust region/params
bash infra/deploy.sh                                   # sam build && sam deploy --guided
# → note the ApiUrl output
```

Then host the frontend and set `NEXT_PUBLIC_API_URL=<ApiUrl>` — full
console steps for **Amplify Hosting** and **App Runner/EC2** (plus CORS and
Bedrock model-access setup, teardown, and the honest `/tmp` SQLite limitation)
are in **[docs/deploy.md](../docs/deploy.md)**.

Prereqs: AWS SAM CLI, AWS credentials, and either Docker running (build in the
official python3.12 image) or a local Python 3.12 on PATH. `sam build`
installs `backend/requirements.txt` into the artifact and automatically
excludes `.venv` / `__pycache__` / `.env` (aws-lambda-builders
PythonPipBuilder excludes list).

## Deployed env vars (ScanFunction)

| Var | Value | Why |
| --- | --- | --- |
| `GUARDIAN_DB_PATH` | `/tmp/guardian.db` | Ephemeral per Lambda sandbox — OK for the demo; see `docs/deploy.md` for the DynamoDB swap |
| `ALLOWED_ORIGINS` | parameter `AllowedOrigins` | FastAPI CORS (`*` default; set the frontend URL after hosting) |
| `AWS_REGION` | *not set — Lambda-injected* | `AWS_REGION` is a **reserved** Lambda env var (setting it fails deployment); the runtime injects it automatically and `app/agents/narrator.py` reads it at runtime |
| `BEDROCK_MODEL_ID` | parameter `BedrockModelId` | Narrative model (enable model access in the console) |
| `SCANS_TABLE_NAME` | `ScansTable` ref | Already wired for the future `Store` protocol swap |

Teardown: `sam delete --config-file infra/samconfig.toml`
