export UV_CACHE_DIR ?= $(CURDIR)/.cache/uv
export MYPY_CACHE_DIR ?= $(CURDIR)/.cache/mypy
export RUFF_CACHE_DIR ?= $(CURDIR)/.cache/ruff
export DO_NOT_TRACK ?= true

include .env

.PHONY: run langflow lint

run:
	uv run main.py

langflow:
	uv run langflow run

lint:
	-uv run ruff format . 
	-uv run ruff check --fix . 
	-uv run mypy . 
