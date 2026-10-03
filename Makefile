# MCP Guardian — root Makefile (infra/CI agent).
# Local dev, tests, Docker, and AWS SAM deploy in one place.
#
# Windows note: targets assume the repo's Python venv at backend/.venv
# (Scripts\python.exe) and Node 20+. Run `make venv` once to create it.

ifeq ($(OS),Windows_NT)
  VENV_PY := backend/.venv/Scripts/python.exe
else
  VENV_PY := backend/.venv/bin/python
endif

.DEFAULT_GOAL := help
.PHONY: help venv dev-backend dev-frontend test-backend check-frontend compose-up compose-down sam-build sam-deploy

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

venv: ## Create backend/.venv and install backend deps
	py -3.12 -m venv backend/.venv || python3 -m venv backend/.venv || python -m venv backend/.venv
	$(VENV_PY) -m pip install --quiet -U pip
	$(VENV_PY) -m pip install --quiet -r backend/requirements-dev.txt

dev-backend: ## Run FastAPI locally on :8000 (uvicorn --reload)
	$(VENV_PY) -m uvicorn --app-dir backend app.main:app --reload --port 8000

dev-frontend: ## Run Next.js dev server on :3000
	cd frontend && npm run dev

test-backend: ## Run backend pytest suite
	$(VENV_PY) -m pytest backend/tests -q

check-frontend: ## Frontend eslint + tsc (npm run check)
	cd frontend && npm run check

compose-up: ## Build + start the full stack in Docker (api :8000, web :3000)
	docker compose up --build

compose-down: ## Stop the full stack
	docker compose down

sam-build: ## Build the SAM app without deploying (sam build)
	sam build --template infra/template.yaml

sam-deploy: ## Build + deploy the backend to AWS via infra/deploy.sh (SAM)
	bash infra/deploy.sh
