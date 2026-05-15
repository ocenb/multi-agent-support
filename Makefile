export UV_CACHE_DIR ?= $(CURDIR)/.cache/uv
export MYPY_CACHE_DIR ?= $(CURDIR)/.cache/mypy
export RUFF_CACHE_DIR ?= $(CURDIR)/.cache/ruff
export DO_NOT_TRACK ?= true

include .env

.PHONY: run langflow lint run-api run-eval

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
