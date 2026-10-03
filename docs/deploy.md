# Deploying MCP Guardian to AWS

The backend is an **AWS SAM** app: FastAPI wrapped with
[Mangum](https://github.com/jordaneremieff/mangum) on **AWS Lambda**
(python3.12), reached over a **Lambda Function URL**, with **DynamoDB** for scan
history and **Amazon Bedrock** (Nova Lite, Converse API) for risk narratives.

**Everything here is free except Bedrock**, which is pay-per-token at roughly
**$0.0001 per scan**. Lambda's 1M requests + 400,000 GB-s and DynamoDB's 25 GB
are *always* free, with no 12-month cliff. A Function URL is free HTTPS with
CORS built in, which is why it is preferred over API Gateway (whose free tier
does expire after 12 months; the template keeps API Gateway available anyway).

```
Browser --> Amplify Hosting (Next.js)     $0, 12-month free tier
              | NEXT_PUBLIC_API_URL
              v
        Lambda Function URL               free HTTPS + CORS, no API Gateway
              |
              v
        Lambda ScanFunction               $0, always-free: 1M req + 400k GB-s/mo
          |- 17-rule scanner (pure Python)  ~1.5 GB-s per scan (512 MB x ~3 s)
          |- Cedar policy generator         -> 260,000+ scans/mo inside free tier
          |- Bedrock Converse   -- ONLY PAID PIECE -- per token
          \- DynamoDB ScansTable          $0, always-free: 25 GB + 25 WCU/RCU
```

---

## 1. Prerequisites

1. **AWS account** with credentials configured (`aws configure`, SSO, or env
   vars; `sam` uses the same credential chain).
2. **AWS SAM CLI** - [install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html).
3. A build path, either:
   - **Docker Desktop** running, so `sam build --use-container` builds inside
     the official `python3.12` Lambda image. `infra/deploy.sh` picks this up
     automatically when Docker is available.
   - **No Docker**: `infra/build-nodocker.ps1` (Windows/PowerShell) vendors the
     dependencies with a local Python 3.12 and writes
     `.aws-sam-nodocker/template.yaml`.
4. Copy the SAM defaults: `cp infra/samconfig.toml.example infra/samconfig.toml`.

## 2. Costs (verified 2026-09-18 against the AWS pricing pages)

| Piece | Free tier | Beyond it | Our usage |
|---|---|---|---|
| **Lambda** | 1M req + 400,000 GB-s/mo, **always free** | $0.20/1M req + ~$0.0000133/GB-s | $0 at any hackathon scale |
| **Lambda Function URL** | included, no extra charge | n/a | $0 |
| **DynamoDB** | 25 GB storage always free. **The 25 RCU/WCU allowance is provisioned-mode only**, and this table is `PAY_PER_REQUEST` — so reads/writes are billed per request, not free. | ~$0.125/1M writes, ~$0.025/1M reads | fractions of a cent (a scan is a few write units) |
| **Amplify Hosting** | 12 mo: 1,000 build-min, 15 GB served | $0.01/build-min, $0.15/GB | $0 |
| **API Gateway** (optional) | 1M calls/mo, **12 months only** | $1.00/1M HTTP calls | $0, prefer Function URL |
| **Nova Lite** (default) | none, Bedrock has no free tier | $0.06/1M in + $0.24/1M out | **~$0.0001 per scan** |
| Nova Micro / Pro | none | $0.035 to $0.80 /1M in | ~$0.00006 / ~$0.0014 per scan |

1,000 scans with Nova Lite is about **$0.11 of Bedrock**. Accounts created after
2025-07-15 start with up to **$200 in credits**, which covers everything here.

## 3. Coming from Cloud Run / GCP

| You already know (GCP) | AWS equivalent here | Notes |
|---|---|---|
| Cloud Run, `min=0` | **Lambda** | Scale-to-zero is the default. Nothing to configure. |
| Cloud Run, `max=1` | `ReservedConcurrency` parameter | Set in `samconfig.toml.example`. Raise it if several people demo at once. |
| Cloud Run service URL | **Lambda Function URL** | Free HTTPS + CORS, no API Gateway needed |
| Cloud SQL / Firestore | **DynamoDB** | `SCANS_TABLE_NAME` selects `DynamoDBStore` |
| Firebase Hosting | **Amplify Hosting** (12-mo free), or S3 + CloudFront | CloudFront's 1 TB egress is always free |
| Vertex AI / Gemini API | **Bedrock** (Nova Lite) | The only metered piece, same as paying Gemini per call |
| Artifact Registry | ECR | Only if you go the container-image route |

## 4. Deploy the backend

```bash
bash infra/deploy.sh          # sam build && sam deploy --guided, then prints outputs
```

No Docker (Windows):

```powershell
pwsh infra/build-nodocker.ps1
sam deploy --template ".aws-sam-nodocker\template.yaml" --stack-name mcp-guardian --capabilities CAPABILITY_IAM --resolve-s3 --region us-east-1
```

First run prompts for stack name (`mcp-guardian`), region, changeset
confirmation, and IAM role creation. Copy the **`FunctionUrl`** output:

```
https://<id>.lambda-url.us-east-1.on.aws/
```

Smoke-test it. The health endpoint reports its own dependencies, so it tells you
whether the store and the Bedrock config actually came up:

```bash
curl https://<id>.lambda-url.us-east-1.on.aws/api/health
# {"ok":true,"service":"mcp-guardian","store":{"kind":"dynamodb","reachable":true},
#  "narrative":{"bedrockConfigured":true,"modelId":"amazon.nova-lite-v1:0",...}}
```

`store.reachable: false` means an IAM or table-name problem, which is far easier
to read here than as a 500 on the first scan.

What `infra/template.yaml` creates:

- **`ScanFunction`** - Lambda, python3.12, `Handler: app.lambda_handler.handler`
  (Mangum), 512 MB, 60 s timeout, with a **Function URL**. Env:
  `SCANS_TABLE_NAME`, `GUARDIAN_SYNC_SCAN=1`, `ALLOWED_ORIGINS`,
  `BEDROCK_MODEL_ID`. (`AWS_REGION` is a **reserved** Lambda variable: the
  runtime injects it, so the template deliberately does not set it.)
- **`ScansTable`** - DynamoDB (`AWS::DynamoDB::Table`, key `id`), with a TTL on
  `expires_at` so scan rows self-delete after 30 days.
- **`Api`** - REST API with gateway CORS, kept as an alternative front door.
- **IAM** - inline `bedrock:InvokeModel`, plus SAM's `DynamoDBCrudPolicy` scoped
  to the table ARN. No stored credentials: the execution role calls Bedrock.

## 5. Enable Bedrock model access (2 minutes)

Console -> **Amazon Bedrock -> Model access -> Enable specific models** -> enable
the model matching `BedrockModelId` (default `amazon.nova-lite-v1:0`, an
on-demand model, so access is only needed in the region you deploy to: one
click, no approval queue). Without it the narrative agent **falls back
gracefully** to its deterministic template (`backend/app/agents/narrator.py`),
so the demo still works.

The code path is model-agnostic (Converse API), so `BedrockModelId` accepts any
Converse-compatible model. These were verified with live `converse` calls in
us-east-1 on 2026-09-19:

| `BedrockModelId` | Works | Notes |
|---|---|---|
| `amazon.nova-lite-v1:0` | yes | Template default. On-demand, price verified above. |
| `us.amazon.nova-2-lite-v1:0` | yes | Newest Nova Lite. **Inference profile only** — needs the `us.` prefix. |
| `amazon.nova-2-lite-v1:0` | **no** | `ValidationException: on-demand throughput isn't supported`. |
| `amazon.nova-lite-v2:0` | **no** | Does not exist. The generation goes in the family name (`nova-2-lite`), not the version suffix. |
| `us.anthropic.claude-3-5-sonnet-20241022-v2:0` | yes | ~50x Nova Lite per input token. |

Two things worth knowing before switching to Nova 2 Lite:

- Its price is **not** included in the table above because the Bedrock pricing
  page renders its tables client-side and could not be read programmatically.
  The $0.06/$0.24 figures are Nova Lite **v1**. Even at several times that rate a
  hackathon's worth of scans stays in cents, but the number is unverified.
- It bills **more input tokens for the same prompt**: an identical one-line probe
  counted 7 input tokens on Nova Lite v1 and 53 on Nova 2 Lite, which evidently
  adds its own scaffolding.

The template default stays on Nova Lite v1 deliberately: it is the variant whose
cost is verified. Opt into Nova 2 per-deploy instead:

```bash
--parameter-overrides "BedrockModelId=us.amazon.nova-2-lite-v1:0"
```

A wrong or unenabled model ID is not a hard failure — `narrator.py` falls back to
the deterministic template, so scans keep working and only the AI narrative goes
missing. Check `narrative.modelId` on `/api/health` to confirm what is live.

## 6. Host the frontend

`NEXT_PUBLIC_*` values are **inlined at build time**, so set
`NEXT_PUBLIC_API_URL` *before* the build. The frontend is not a static export
(dynamic routes + client fetch), so it needs an SSR-capable host.

### Option A - Amplify Hosting (console, no Docker)

1. Console -> **AWS Amplify** -> **Create new app** -> **Host your web app** ->
   **GitHub**, authorize, then pick this repo and branch.
2. Amplify auto-detects Next.js. Under **App settings -> Environment variables**
   add `NEXT_PUBLIC_API_URL` = your Function URL. That is the only variable the
   app needs.
3. Save and deploy (`npm ci && npm run build`, served SSR). You get
   `https://main.<id>.amplifyapp.com`.
4. Lock CORS: redeploy the backend with
   `--parameter-overrides AllowedOrigins="https://main.<id>.amplifyapp.com"`.

> Caveat: Amplify's managed Next.js runtime can lag the newest Next major (this
> repo is on Next 16). If the build fails on the Next version, use Option B.

### Option B - App Runner via Docker

`frontend/Dockerfile` (node:20-alpine, multi-stage) runs `next start -p 3000`.
Build with `--build-arg NEXT_PUBLIC_API_URL=<function-url>`, push to ECR, then
App Runner -> Create service -> Container registry -> port **3000**. Set the
same origin as `AllowedOrigins` and redeploy the backend.

## 7. CI

`.github/workflows/ci.yml` runs on every push and PR with
`permissions: contents: read`:

- **frontend** - Node 20: `npm ci` -> `npm run check` (eslint + tsc) -> `npm run build`
- **backend** - Python 3.12: `pip install -r requirements.txt` -> `pytest -q`

## 8. Honest limitations

- **Cold starts** - the first request after idle adds ~1-2 s (Python + Mangum).
  Keep a tab warm before recording a demo.
- **Sync scans on Lambda** - `GUARDIAN_SYNC_SCAN=1` runs the scan inline before
  responding, because Lambda freezes background threads once the handler
  returns. The UI polls either way, so both modes look identical.
- **Bedrock is never free** - by design here: you pay only when a scan generates
  an AI narrative (~$0.0001). Rules, scoring and Cedar generation cost nothing.
- **`ReservedConcurrency=1`** makes a second simultaneous scan throttle. It is a
  cost guard, not a requirement; raise it before a live demo.
- **Amplify's free tier is 12 months**, then roughly $0-2/month, or export to
  S3 + CloudFront (always-free CDN).
- **`NEXT_PUBLIC_*` are build-time** - changing the API URL needs a rebuild.
- **CORS is enforced twice** - at the Function URL/gateway and in-app
  (`ALLOWED_ORIGINS`). Lock it to the real origin before shipping.

## 9. Teardown

```bash
sam delete --config-file infra/samconfig.toml   # Lambda, Function URL, table, roles
# Amplify:    console -> App settings -> General -> Delete app
# App Runner: console -> Delete service (and delete the ECR repo if desired)
```
