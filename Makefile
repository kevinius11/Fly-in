PYTHON = python3
VENV = .venv
BIN = $(VENV)/bin

.PHONY: install run debug clean lint

$(VENV):
	$(PYTHON) -m venv $(VENV)

install: $(VENV)
	$(BIN)/pip install flake8 mypy pytest

run: $(VENV)
	$(BIN)/python main.py "$(MAP)"

debug: $(VENV)
	$(BIN)/python -m pdb main.py "$(MAP)"

clean:
	rm -rf __pycache__ .mypy_cache .pytest_cache $(VENV)
	find . -type d -name "__pycache__" -exec rm -rf {} +

lint: $(VENV)
	$(BIN)/flake8 --exclude=$(VENV) .
	$(BIN)/mypy --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs .
