UV ?= uv

.PHONY: install data test lint format eval app check

install:
	$(UV) sync --all-groups

data:
	$(UV) run python -m pergunteoee.data.generate --force

test:
	$(UV) run pytest

lint:
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format:
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

eval:
	$(UV) run python -m pergunteoee.eval.run --provider mock

app:
	$(UV) run streamlit run src/pergunteoee/app/streamlit_app.py

check: lint test eval
