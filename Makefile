export UV_CACHE_DIR ?= $(CURDIR)/.cache/uv
export MYPY_CACHE_DIR ?= $(CURDIR)/.cache/mypy
export RUFF_CACHE_DIR ?= $(CURDIR)/.cache/ruff
export DO_NOT_TRACK ?= true

include .env

.PHONY: run langflow lint run-api run-eval run-langflow-api run-eval-langflow

run:
	uv run main.py

run-api:
	uv run uvicorn app.api:app --host 0.0.0.0 --port 8000

langflow:
	uv run langflow run

lint:
	-uv run ruff format . 
	-uv run ruff check --fix . 
	-uv run mypy . 

run-eval:
	uv run python -m scripts.run_eval --dataset datasets/eval_seed.jsonl --out reports/predictions.jsonl
	uv run python -m scripts.eval_runner --dataset datasets/eval_seed.jsonl --predictions reports/predictions.jsonl --report reports/eval_report.json

run-langflow-api:
	@test -n "$(FLOW_ID)" || (echo "FLOW_ID is required. Example: make run-langflow-api FLOW_ID=<id>" && exit 1)
	uv run python -m scripts.run_langflow_api --flow-id "$(FLOW_ID)" --message "$(MESSAGE)" --base-url "$(LANGFLOW_URL)" --api-key "$(LANGFLOW_API_KEY)"

run-eval-langflow:
	@test -n "$(FLOW_ID)" || (echo "FLOW_ID is required. Example: make run-eval-langflow FLOW_ID=<id>" && exit 1)
	uv run python -m scripts.run_eval_langflow --dataset datasets/eval_seed.jsonl --out reports/predictions_langflow.jsonl --flow-id "$(FLOW_ID)" --base-url "$(LANGFLOW_URL)" --api-key "$(LANGFLOW_API_KEY)"
	uv run python -m scripts.eval_runner --dataset datasets/eval_seed.jsonl --predictions reports/predictions_langflow.jsonl --report reports/eval_report_langflow.json
